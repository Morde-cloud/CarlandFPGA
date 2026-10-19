"""Descriptor and synthetic arithmetic audit only; no register/HWH I/O."""
import argparse, copy, hashlib, json
from pathlib import Path
def validate(d):
    assert d['candidate_only'] is True and d['A_approval_required'] is True
    assert d['physical_base_address'] is None and d['hwh_instance_name'] is None
    assert d['ai_input_allowed'] is False and d['bank_size_bytes']==256
    rows=d['rows'];by={r['offset']:r for r in rows};assert len(rows)==len(by)==51
    headers={0,4,8,12,16,20,24,28,32,36,40,48,52,56,60}
    channels={64,128,192};expected=headers|{b+v for b in channels for v in (*range(0,40,4),40,48)}
    assert set(by)==expected and 44 not in by
    assert set(d['no_access_offsets'])==set(range(0,256,4))-expected
    for o,r in by.items():
        assert type(o) is int and o%4==0 and r['width_bits']==32
        assert r['access']==('RO_IMAGE' if o in (0,4,8) else 'RO_LATCHED')
        assert r['reset_valid'] is False and r['offset_hex']==f'0x{o:03x}'
    for name,base in zip(('yaw','pitch','speed'),(64,128,192)):
        for i,field in enumerate(('period','high_count','rise0_tick','fall_tick','rise1_tick')):
            for word in range(2):
                r=by[base+8*i+4*word]
                assert (r['channel'],r['logical_field'],r['logical_width_bits'],r['word_index'])==(name,field,64,word)
    assert all(s=='not_run' for s in d['stages'].values())
def edge(r0,f,r1,period,high,flags):
    vals=(r0,f,r1,period,high)
    if any(type(v) is not int or not 0<=v<1<<64 for v in vals):return False
    return type(flags) is int and flags==1 and r0<f<r1 and period==r1-r0 and high==f-r0 and 0<high<period
def run(path):
    raw=Path(path).read_bytes();d=json.loads(raw);validate(d)
    cases=[([0,1,2,2,1,1],True),([2**32-1,2**32,2**32+1,2,1,1],True),([2**64-3,2**64-2,2**64-1,2,1,1],True),([0,1,2**64-1,2**64-1,1,1],True),([0,0,2,2,0,1],False),([0,2,2,2,2,1],False),([2**64-1,0,1,2,1,1],False),([0,1,2,3,1,1],False),([0,1,2,2,2,1],False),([0,1,2,2,1,3],False),([0,1,2,2,1,0],False),([0,1,2,2,1,256],False),([0,1,2**64,2**64,1,1],False),([True,1,2,2,1,1],False)]
    for data,expected in cases:assert edge(*data)==expected,(data,expected)
    failures=[]
    def bad(name,change):
        q=copy.deepcopy(d);change(q)
        try:validate(q)
        except (AssertionError,KeyError,TypeError):failures.append(name);return
        raise AssertionError('accepted corrupt descriptor '+name)
    bad('missing-channel-word',lambda q:q['rows'].pop())
    bad('duplicate-offset',lambda q:q['rows'][16].update(offset=q['rows'][15]['offset']))
    bad('steal-reserved',lambda q:q['rows'][14].update(offset=44))
    bad('narrow-high-count',lambda q:q['rows'][17].update(logical_width_bits=32))
    bad('wrong-word-order',lambda q:q['rows'][16].update(word_index=0))
    bad('writable-bank',lambda q:q['rows'][20].update(access='RW'))
    bad('fabricated-base',lambda q:q.update(physical_base_address=0x40000000))
    bad('AI-side-channel',lambda q:q.update(ai_input_allowed=True))
    bad('false-board-pass',lambda q:q['stages'].update(board='passed'))
    bad('reset-validity',lambda q:q['rows'][20].update(reset_valid=True))
    print(json.dumps({'descriptor_sha256':hashlib.sha256(raw).hexdigest(),'accessible_words':51,'channels':3,'wide_fields':15,'synthetic_cases':len(cases),'negative_descriptors':failures,'scope':'descriptor/fixture arithmetic only; no RTL, HWH parse, physical capture or register transition execution','result':'passed'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('descriptor');a=p.parse_args();run(a.descriptor)
