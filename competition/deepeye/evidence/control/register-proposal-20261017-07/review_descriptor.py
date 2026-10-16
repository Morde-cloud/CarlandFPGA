"""Static source/field/arithmetic review only. This is not an MMIO simulator."""
import argparse,csv,hashlib,io,json
from pathlib import Path
p=argparse.ArgumentParser()
for name in ('descriptor','examples','register_source','interface','enums','output'):p.add_argument('--'+name.replace('_','-'),type=Path,required=True)
a=p.parse_args();assert not a.output.exists(),'preserve existing review output'
raw={n:getattr(a,n).read_bytes() for n in ('descriptor','examples','register_source','interface','enums')}
d=json.loads(raw['descriptor']);x=json.loads(raw['examples']);interface=json.loads(raw['interface']);enums=json.loads(raw['enums'])
assert d['candidate_only'] and not d['public_abi_frozen'] and not d['hardware_enable_eligible']
assert d['contract']['requirements_sha256']=='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
assert d['contract']['requirements_ids']==[f'H{i:02}' for i in range(1,16)]
assert hashlib.sha256(raw['register_source']).hexdigest()==d['register_csv_sha256']=='fd3d69509776829a4e33ea4f1a6ce8b39679bd101080b33dc2ff1df38c0a4f33'
src=list(csv.DictReader(io.StringIO(raw['register_source'].decode())))
assert len(src)==29 and [r['source_row'] for r in d['registers']]==src
by_offset={r['offset']:r['proposal'] for r in d['registers']};assert len(by_offset)==29 and set(by_offset)==set(range(0,0x74,4))
field_count=0;external=[]
for off,r in by_offset.items():
    mask=0;names=set()
    for f in r['fields']:
        assert f['name'] not in names;names.add(f['name']);lo=f['lsb'];width=f['width']
        assert type(lo) is int and type(width) is int and 0<=lo<32 and 1<=width<=32-lo
        part=((1<<width)-1)<<lo;assert not(mask&part);mask|=part;field_count+=1
        assert f['encoding'] in ('unsigned','twos_complement')
        dom=f.get('domain')
        if dom:
            if dom['kind']=='integer_range':assert type(dom['minimum']) is int and dom['minimum']<=dom['maximum']
            elif dom['kind']=='enumeration':assert dom['values'] and len(set(dom['values']))==len(dom['values'])
            else:assert dom['kind']=='A_owned_domain' and dom['reference'];external.append(dict(offset=off,field=f['name'],reference=dom['reference']))
        if f['encoding']=='twos_complement':assert width==32 and lo==0 and f['canonical_sign_extension_from_bits']==16
    assert mask==int(r['defined_mask_hex'],16) and (mask^0xffffffff)==int(r['reserved_zero_mask_hex'],16)
    rv=r['reset_value']
    if rv is not None:assert type(rv) is int and 0<=rv<2**32 and rv&~mask==0
assert field_count==51
assert by_offset[0x2c]['access']=='NO_ACCESS' and not by_offset[0x2c]['fields'] and by_offset[0x2c]['reset_value'] is None
assert int(by_offset[8]['defined_mask_hex'],16)==0x1f and by_offset[12]['reset_value']==1
assert int(by_offset[12]['defined_mask_hex'],16)==0x00ff07ff
assert by_offset[0x50]['fields'][0]['width']==16 and by_offset[0x70]['fields'][0]['width']==16
assert {f['name']:f['lsb'] for f in by_offset[0x54]['fields']}==enums['capture_quality_bits']
assert by_offset[0x58]['fields'][0]['domain']['values']==[int(k) for k in interface['gain_code_to_multiplier']]
assert interface['gain_code_to_multiplier']=={'0':1,'1':2,'2':4,'4':8}
assert any(f['name']=='measured_ratio_q8_8' and f['type']=='u16' for f in interface['frames']['GAIN_ACK']['fields'])
def encode(field,value):
    assert type(value) is int
    bits=field['width'];signed=field['encoding']=='twos_complement'
    assert -(1<<(bits-1))<=value<(1<<(bits-1)) if signed else 0<=value<(1<<bits)
    dom=field.get('domain')
    if dom and dom['kind']=='integer_range':assert dom['minimum']<=value<=dom['maximum']
    elif dom and dom['kind']=='enumeration':assert value in dom['values']
    if signed:assert -(1<<15)<=value<(1<<15)
    return (value&((1<<bits)-1))<<field['lsb']
examples={q['name']:q for q in x['examples']};assert len(examples)==len(x['examples'])==35
arith=[];negative=[]
for name,e in examples.items():
    if 'word_hex' in e and 'value' in e:
        field=by_offset[int(e['offset'],16)]['fields'][0];word=encode(field,e['value']);assert word==int(e['word_hex'],16)
        if 'little_endian_bytes_hex' in e:assert word.to_bytes(4,'little').hex()==e['little_endian_bytes_hex']
        arith.append(name)
    elif 'word_hex' in e and 'fields' in e:
        fs={f['name']:f for f in by_offset[int(e['offset'],16)]['fields']};word=0
        for n,v in e['fields'].items():word|=encode(fs[n],v)
        assert word==int(e['word_hex'],16);arith.append(name)
    elif 'words' in e:
        lo,hi=[int(v,16) for v in e['words'].values()]
        value=int(e['value_hex'],16) if 'value_hex' in e else e['value']
        assert lo|(hi<<32)==value;arith.append(name)
    elif 'set_bits' in e:
        assert sum(1<<b for b in e['set_bits'])==int(e['word_hex'],16);arith.append(name)
e=examples['ratio_one_and_half'];assert e['ratio_numerator']*256//e['ratio_denominator']==int(e['word_hex'],16);arith.append(e['name'])
e=examples['counter_saturates'];assert min(e['initial']+e['increments'],65535)==e['expected'];arith.append(e['name'])
assert int(examples['capture_quality_all4']['word_hex'],16)==15;arith.append('capture_quality_all4')
assert int(examples['reset_status']['word_hex'],16)==by_offset[12]['reset_value'];arith.append('reset_status')
assert int(examples['ratio_invalid_reset']['word_hex'],16)==0 and examples['ratio_invalid_reset']['gain_ratio_valid'] is False;arith.append('ratio_invalid_reset')
for name in ('capture_local_batch_no_truncation','last_observation_no_truncation','gain_code_invalid'):
    e=examples[name];field=by_offset[int(e['offset'],16)]['fields'][0]
    try:encode(field,e['value'])
    except AssertionError:negative.append(name)
    else:raise AssertionError('invalid field example accepted: '+name)
e=examples['capture_quality_reserved'];assert int(e['word_hex'],16)&int(by_offset[0x54]['reserved_zero_mask_hex'],16);negative.append(e['name'])
# Command examples remain proposed transitions; no state machine is executed here.
result=dict(status='PASS_STATIC_DESCRIPTOR_REVIEW',register_rows=29,fields=field_count,hand_derived_examples=35,
    arithmetic_examples_checked=len(arith),arithmetic_example_names=arith,rejected_field_encodings=len(negative),rejected_field_names=negative,
    proposed_transition_examples_not_executed=True,external_domains_not_frozen=external,
    hashes={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()},runtime=False,simulation=False,synthesis=False,implementation=False,board=False,system=False)
with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
print(json.dumps({k:result[k] for k in ['status','register_rows','fields','hand_derived_examples','arithmetic_examples_checked','rejected_field_encodings','runtime']}))
