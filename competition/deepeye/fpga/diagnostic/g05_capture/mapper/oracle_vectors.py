"""Independent Decimal Gauss-Legendre oracle; never reads the DUT/ROM constants."""
import argparse
from collections import Counter
from decimal import Decimal, localcontext, ROUND_FLOOR
import hashlib
import json
from math import isqrt
from pathlib import Path


def limits_at_precision(precision):
    with localcontext() as ctx:
        ctx.prec = precision
        a, b, t, p = Decimal(1), Decimal(1)/Decimal(2).sqrt(), Decimal(1)/4, Decimal(1)
        for _ in range(10):
            an = (a+b)/2
            b = (a*b).sqrt()
            t -= p*(a-an)**2
            a, p = an, 2*p
        pi = (a+b)**2/(4*t)
        table = {(profile, code): int(((Decimal(code)*90000/denominator/pi)**2)
                   .to_integral_value(rounding=ROUND_FLOOR))
                 for profile, denominator in ((1,80),(2,10000)) for code in range(21)}
        return table, str(pi)


def expected(profile, yaw, pitch, code, ttl, limits):
    limit = limits.get((profile, code), 0)
    combined = yaw*yaw + pitch*pitch
    reject = (int(profile not in (1,2))
              | (int(not(-15000 <= yaw <= 15000 and -15000 <= pitch <= 15000)
                     or code > 20 or (code == 0 and (yaw != 0 or pitch != 0))) << 1)
              | (int(ttl == 0 or (profile == 1 and ttl > 3000)
                     or (profile == 2 and ttl > 12000)) << 2)
              | (int(combined > limit) << 3))
    legal = int(reject == 0)
    mapping = [2000000,10000+16*(yaw+15000),10000+16*(pitch+15000),
               50000+1000*code,ttl*100000] if legal else [0]*5
    return [legal,reject,*mapping,combined,limit]


def generate(output):
    limits, pi140 = limits_at_precision(140)
    limits180, pi180 = limits_at_precision(180)
    assert limits == limits180 and len(limits) == 42
    cases, seen, categories = [], set(), Counter()
    def add(label, profile, yaw, pitch, code, ttl):
        inputs = (profile,yaw,pitch,code,ttl)
        if inputs in seen:
            return
        seen.add(inputs)
        values = expected(*inputs, limits)
        cases.append({'index': len(cases), 'category': label, 'inputs': list(inputs), 'expected': values})
        categories[label] += 1

    for profile, cap in ((1,3000),(2,12000)):
        for code in range(21):
            for ttl in (1,0,cap,cap+1):
                add('all42-ttl',profile,0,0,code,ttl)
            limit = limits[profile,code]
            radius, diag = isqrt(limit), isqrt(limit//2)
            for sign in (-1,1):
                for value in (radius,radius+1):
                    add('axis-curvature',profile,sign*value,0,code,1)
                    add('axis-curvature',profile,0,sign*value,code,1)
                for other_sign in (-1,1):
                    for value in (diag,diag+1):
                        add('diagonal-curvature',profile,sign*value,other_sign*value,code,1)
                    mixed_yaw = radius//3
                    mixed_pitch = isqrt(limit-mixed_yaw*mixed_yaw)
                    for value in (mixed_pitch,mixed_pitch+1):
                        add('mixed-curvature',profile,sign*mixed_yaw,other_sign*value,code,1)
            # Each axis's range faces and signed extremes, and simultaneous combinations.
            for yaw in (-32768,-15001,-15000,-14999,0,14999,15000,15001,32767):
                add('all42-range-axis',profile,yaw,0,code,1)
                add('all42-range-axis',profile,0,yaw,code,1)
            if code in (0,1,20):
                for yaw in (-32768,-15001,-15000,0,15000,15001,32767):
                    for pitch in (-32768,-15001,-15000,0,15000,15001,32767):
                        add('combined-range',profile,yaw,pitch,code,1)
        for code in (21,255):
            for yaw,pitch in ((0,0),(1,0),(0,-1),(-32768,32767)):
                for ttl in (0,1,cap,cap+1,65535):
                    add('invalid-speed',profile,yaw,pitch,code,ttl)
        for yaw,pitch in ((1,0),(-1,0),(0,1),(0,-1),(1,-1)):
            add('zero-speed',profile,yaw,pitch,0,1)
    for profile in (0,3,255):
        for code in (0,1,20,21,255):
            for yaw,pitch in ((0,0),(1,0),(0,-1),(-32768,-32768),(32767,32767)):
                for ttl in (0,1,65535):
                    add('invalid-profile-combined',profile,yaw,pitch,code,ttl)
    assert {tuple(c['inputs'][i] for i in (0,3)) for c in cases
            if c['inputs'][0] in (1,2) and c['inputs'][3] <= 20} == set(limits)
    lines=[]
    for case in cases:
        profile,yaw,pitch,code,ttl = case['inputs']
        fields = [profile,yaw & 65535,pitch & 65535,code,ttl,*case['expected']]
        lines.append(' '.join(f'{value:x}' for value in fields))
    data=('\n'.join(lines)+'\n').encode()
    output.mkdir(parents=True, exist_ok=True)
    with (output/'vectors.hex').open('xb') as stream:
        stream.write(data)
    metadata={'schema':1,'oracle':'Decimal Gauss-Legendre, ten iterations at 140 and 180 digits; all 42 floors agree; integer exact sum and mapping',
        'pi140':pi140,'pi180':pi180,'row_count':len(cases),'profile_code_count':42,
        'categories':dict(categories),'legal_count':sum(c['expected'][0] for c in cases),
        'reject_masks':dict(sorted(Counter(str(c['expected'][1]) for c in cases).items())),
        'vectors_sha256':hashlib.sha256(data).hexdigest(),
        'oracle_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'field_order':['profile','yaw','pitch','speed','ttl','legal','reject_bits','period',
                       'high_yaw','high_pitch','high_speed','ttl_ticks','curvature_sum','curvature_limit'],
        'independent_limits':[{'profile':p,'code':c,'limit':value} for (p,c),value in limits.items()],
        'cases':cases}
    with (output/'vectors.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(metadata,stream,indent=2)
        stream.write('\n')
    print(json.dumps({k:metadata[k] for k in ('row_count','profile_code_count','categories','legal_count','reject_masks','vectors_sha256')},indent=2))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    generate(parser.parse_args().output)
