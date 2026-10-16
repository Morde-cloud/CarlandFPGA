"""Independent port-only mailbox review. No imports of worker model/runner/TB.

Stimuli are intentionally opaque raw port vectors. In stress phases source
payload is adversarially changed while not accepted to verify captured-bus
isolation; this is not a claim of AXI source compliance. Accepted values only
define the external queue oracle. All states below derive from visible ports.
"""
import argparse, gzip, hashlib, json, random, re, subprocess
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

def sha(b): return hashlib.sha256(b).hexdigest()
def write_json(p,x): p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')

def generate(width,sh,dh,phase,seed,steps=10000):
    rng=random.Random(seed); sc=dc=0; mask=(1<<width)-1
    out=[]; phases=Counter()
    # Some reset intervals are shorter than a clock period, but >one vector step.
    resets=[(0,30,'both'),(1300,1310,'src'),(2510,2520,'dst'),
            (3900,3912,'src'),(5210,5220,'dst'),(6810,6820,'both'),
            (8100,8110,'src')]
    for t in range(steps):
        srcstop=3600<=t<4200 or 6600<=t<7000 or (seed==97 and t<250)
        dststop=5000<=t<5500 or 6600<=t<7000 or (seed==101 and t<250)
        if t%sh==0 and not srcstop: sc^=1
        if (t+phase)%dh==0 and not dststop: dc^=1
        sr=dr=1
        for start,end,kind in resets:
            if start<=t<end:
                if kind in ('src','both'): sr=0
                if kind in ('dst','both'): dr=0
        # High through reset and recovery, followed by explicit low rearming.
        sv=int(rng.randrange(8)!=0)
        if 0<=t<100 or 1240<=t<1450 or 2450<=t<2650 or 3850<=t<4350 or 5150<=t<5650 or 6750<=t<7150 or 8050<=t<8250:
            sv=1
        if 100<=t<150 or 1450<=t<1510 or 2650<=t<2710 or 4350<=t<4410 or 5650<=t<5710 or 7150<=t<7210 or 8250<=t<8310:
            sv=0
        dy=int(rng.randrange(4)!=0)
        if 800<=t<1400 or 2200<=t<2600 or 4800<=t<5600 or 7800<=t<8200: dy=0
        if t>=9500: sv=0;dy=1
        # Unique full-width patterns in larger widths; low width has exact value oracle.
        sd=(rng.getrandbits(width) ^ ((t+1)*0x9e3779b97f4a7c15))&mask
        out.append((sc,dc,sr,dr,sv,dy,sd))
        phases['steps']+=1;phases['source_stopped']+=srcstop;phases['destination_stopped']+=dststop
    return out,dict(phases)

def review(vectors,raw,width):
    lines=raw.decode('ascii').splitlines();assert len(lines)==len(vectors),(len(lines),len(vectors))
    q=deque();counts=Counter();prevsc=prevdc=0;armed=False;priorreset=True
    prevrst=(0,0);previous_valid=0;previous_data=0;prior_dy=0
    src_edges=dst_edges=0
    for i,(v,line) in enumerate(zip(vectors,lines)):
        fields=line.split(',');assert len(fields)==18,(i,fields)
        assert all('x' not in s.lower() and 'z' not in s.lower() for s in fields),(i,'unknown port',line)
        got=[int(s,16 if j in (7,12,17) else 10) for j,s in enumerate(fields)]
        _,sc,dc,sr,dr,sv,dy,sd,sready,sonline,dvalid,donline,dd,psready,psonline,pdvalid,pdonline,pdd=got
        assert got[0]==i and tuple(got[1:8])==v,(i,'stimulus mismatch')
        se=not prevsc and sc; de=not prevdc and dc
        reset=not(sr and dr)
        if reset:
            if not priorreset: counts['reset_events']+=1
            counts['reset_discarded']+=len(q);q.clear();armed=False;src_edges=dst_edges=0
            assert not any((sready,sonline,dvalid,donline,dd,psready,psonline,pdvalid,pdonline,pdd)),(i,'async reset incomplete',got)
        else:
            src_edges+=se;dst_edges+=de
            if sonline or donline or psonline or pdonline:
                assert src_edges>=2 and dst_edges>=2,(i,'premature online')
            if de and dvalid and dy:
                assert q,(i,'phantom consume')
                assert dd==q.popleft(),(i,'consume data torn/order')
                counts['delivered']+=1
            if se and sv and sready:
                assert sonline and armed,(i,'postreset replay or offline accept')
                assert not q,(i,'multiple outstanding')
                q.append(sd);counts['accepted']+=1
            if se and sonline and not sv: armed=True;counts['rearm_low_edges']+=1
            if not armed:
                assert not sready,(i,'ready before valid-low rearm')
                assert not psready,(i,'postready before valid-low rearm')
                counts['unarmed_steps']+=1
            if dvalid:
                # A just-consumed token is represented by its preedge value; compare earlier if needed.
                if not(de and dy): assert q and dd==q[0],(i,'prevalid without captured token')
                counts['valid_steps']+=1
            if pdvalid: assert q and pdd==q[0],(i,'postvalid without captured token')
            if dvalid and not(de and dy):
                assert pdvalid and pdd==dd,(i,'valid/payload changed under stall')
                counts['stability_checks']+=1
            assert len(q)<=1
        prevsc,prevdc=sc,dc;priorreset=reset
    assert not q,('undrained',list(q))
    assert counts['accepted']==counts['delivered']+counts['reset_discarded']
    assert counts['accepted']>=20 and counts['delivered']>=10 and counts['reset_discarded']>=2,counts
    assert counts['reset_events']==6,counts
    return dict(counts)

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--tb',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--tools',type=Path,default=Path('D:/modelsim1/win64'))
    p.add_argument('--negative-control',action='store_true');a=p.parse_args()
    source=a.source.resolve();tb=a.tb.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    commands=[]
    def run(name,args,cwd,expected=0):
        start=datetime.now(timezone.utc).isoformat()
        r=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True,timeout=60)
        (out/(name+'.stdout.txt')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
        rec=dict(argv=[str(x) for x in args],cwd=str(cwd),started_at=start,exit_code=r.returncode,expected_exit=expected,
            stdout_sha256=sha(r.stdout),stderr_sha256=sha(r.stderr));commands.append(rec);write_json(out/'commands.json',commands)
        assert r.returncode==expected,(name,r.returncode,expected)
        assert b'** Error:' not in r.stdout and b'** Fatal:' not in r.stdout,(name,'simulator error')
        return r
    build=out/'build';build.mkdir();run('vlib',[a.tools/'vlib.exe','work'],build)
    run('vlog',[a.tools/'vlog.exe','-sv','-work','work',source,tb],build)
    cases=[(1,2,7,1,31),(32,7,2,0,41),(256,3,5,1,59),(256,5,3,2,73),
           (1024,4,9,4,89),(8,11,13,3,97),(16,13,11,5,101)]
    results=[]
    for ci,(width,sh,dh,phase,seed) in enumerate(cases):
        name='case'+str(ci);vs,cover=generate(width,sh,dh,phase,seed)
        vf=out/(name+'.vectors.txt');lf=out/(name+'.ports.csv')
        vf.write_text(''.join(' '.join(map(str,v[:6]))+' '+format(v[6],'x')+'\n' for v in vs),encoding='ascii')
        do=out/(name+'.do');do.write_text('onerror {quit -force -code 8}\nonbreak {quit -force -code 7}\nrun 40 us\nputs "MAIN_RUN_BOUND"\nquit -force -code 0\n',encoding='ascii')
        r=run(name,[a.tools/'vsim.exe','-c','-voptargs=+acc','-onfinish','stop','-gWIDTH='+str(width),
            'work.main_port_replay_tb','+INPUT='+str(vf),'+OUTPUT='+str(lf),'-do',do],build)
        assert re.search(rb'^# MAIN_PORT_REPLAY_DONE 10000\r?$',r.stdout,re.M),(name,'no completed bench')
        assert re.search(rb'^MAIN_RUN_BOUND\r?$',r.stdout,re.M)
        raw=lf.read_bytes();counts=review(vs,raw,width)
        # Raw bytes remain losslessly available in gzip; only scratch text is unlinked.
        for f in (vf,lf):
            b=f.read_bytes()
            with (out/(f.name+'.gz')).open('xb') as z: z.write(gzip.compress(b,mtime=0))
            f.unlink()
        results.append(dict(case=name,width=width,clock_half_steps=[sh,dh],phase=phase,seed=seed,
            stimulus=cover,checks=counts,port_raw_sha256=sha(raw)))
        print(json.dumps(results[-1]),flush=True)
    result=dict(status='PASS',scope='independent digital RTL simulation of candidate only',source_sha256=sha(source.read_bytes()),
        tb_sha256=sha(tb.read_bytes()),results=results,commands=commands,public_abi_frozen=False,
        synthesis=False,implementation=False,physical_cdc_rdc=False,board=False)
    write_json(out/'result.json',result)
if __name__=='__main__':main()
