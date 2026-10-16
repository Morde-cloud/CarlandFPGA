"""Independent B-main arithmetic and encoded-byte checks; no product mutation."""
import hashlib
import importlib.util
import json
import random
import struct
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[5]
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--output-root',type=Path,required=True)
args=parser.parse_args()
OUT=args.output_root.resolve()
WT=ROOT
BASE=WT/'competition/deepeye'
E_VALUES=(0,1,2,4,8)
def sha(data): return hashlib.sha256(data).hexdigest()
def save(name,value):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')
def nearest_q(x,p,e):
    magnitude, remainder=divmod(abs(x-p),2*e+1)
    magnitude+=int(2*remainder>2*e+1)
    return -magnitude if x<p else magnitude
def independent_encode(values,e):
    reconstructed=[values[0]];zs=[]
    for x in values[1:]:
        q=nearest_q(x,reconstructed[-1],e)
        y=max(0,min(65535,reconstructed[-1]+q*(2*e+1)))
        reconstructed.append(y)
        zs.append(2*abs(q)-(1 if q<0 else 0))
    options=[]
    for k in range(16):
        quotients=[z//(2**k) for z in zs]
        if all(q<32 for q in quotients): options.append((sum(q+1+k for q in quotients),k))
    best=min(options) if options else None
    mode='rice' if best and best[0]<16*len(zs) else 'raw'
    k=best[1] if mode=='rice' else None
    bits=format(values[0],'016b')
    if mode=='raw':
        bits+=''.join(format(x,'016b') for x in values[1:]);reconstructed=values[:]
    else:
        for z in zs:
            q,r=divmod(z,2**k)
            bits+='0'*q+'1'+(format(r,f'0{k}b') if k else '')
    padded=bits+'0'*((-len(bits))%8)
    encoded=int(padded,2).to_bytes(len(padded)//8,'big')
    return {'mode':mode,'e':e,'k':k,'sample_count':len(values),'valid_bit_count':len(bits),'payload_hex':encoded.hex()},reconstructed

def main():
    OUT.mkdir(exist_ok=True)
    result=json.loads((BASE/'evidence/codec/byte-accounting-correction-02/result.json').read_bytes())
    pinned={}
    for rel,h in result['source_sha256'].items():
        b=(WT/rel).read_bytes();assert sha(b)==h,(rel,'source mismatch');pinned[rel]=h
    for rel,h in result['evidence_sha256'].items(): assert sha((BASE/'evidence/codec/byte-accounting-correction-02'/rel).read_bytes())==h
    save('source-manifest.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'files':pinned,'child_result_sha256':sha((BASE/'evidence/codec/byte-accounting-correction-02/result.json').read_bytes())})
    cmd=[sys.executable,'-B','-X','utf8','-m','unittest','discover','-s','competition/deepeye/tests/codec','-v']
    run=subprocess.run(cmd,cwd=WT,capture_output=True)
    (OUT/'baseline.stdout.txt').write_bytes(run.stdout);(OUT/'baseline.stderr.txt').write_bytes(run.stderr)
    save('baseline-command.json',{'argv':cmd,'cwd':str(WT),'exit_code':run.returncode,'stdout_sha256':sha(run.stdout),'stderr_sha256':sha(run.stderr)})
    assert run.returncode==0
    spec=importlib.util.spec_from_file_location('reviewed_codec',BASE/'golden/codec/codec_reference.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    metrics={'exhaustive_scalar_cases':0,'encoded_blocks':0,'samples_across_E':0,'raw_blocks':0,'rice_blocks':0,'malformed_rejections':0,'known_source_cases':0,'block_restarts':0}
    for e in E_VALUES:
        for p in (0,32768,65535):
            for x in range(65536):
                q=nearest_q(x,p,e);assert q==m.quantize(x,p,e)
                y=max(0,min(65535,p+q*(2*e+1)))
                assert y==m.reconstruct(p,q,e) and abs(x-y)<=e
                metrics['exhaustive_scalar_cases']+=1
    cases=[]
    corpus_dir=Path(__file__).resolve().parent/'corpus'
    raw=(corpus_dir/'codec-inputs.u16le').read_bytes();meta=json.loads((corpus_dir/'codec-inputs.json').read_bytes())
    assert sha(raw)==meta['corpus_sha256']=='5fc5b65b84ea2fbb66f71b308486cdf637c85193cf66f31887b3e4155a2467cf'
    for c in meta['cases']:
        start=c['byte_offset'];n=c['sample_count'];b=raw[start:start+2*n]
        vals=list(struct.unpack('<'+'H'*n,b));assert vals==c['values_u16'] and sha(b)==c['source_bytes_sha256']
        cases.extend(vals[i:i+128] for i in range(0,n,128));metrics['known_source_cases']+=1
    rng=random.Random(20261016)
    for n in range(1,129):
        cases.extend([[0]*n,[65535]*n,[i%65536 for i in range(n)],[(65535-i)%65536 for i in range(n)],[0 if i%2==0 else 65535 for i in range(n)],[rng.randrange(65536) for _ in range(n)],[(32768+rng.randrange(-20,21)) for _ in range(n)]])
    for values in cases:
        for e in E_VALUES:
            expected,ys=independent_encode(values,e);actual=m.encode_block(values,e)
            assert actual==expected,(values,e,actual,expected)
            assert m.decode_block(expected)==ys and all(abs(x-y)<=e for x,y in zip(values,ys))
            metrics['encoded_blocks']+=1;metrics['samples_across_E']+=len(values);metrics[expected['mode']+'_blocks']+=1
    valid=m.encode_block([100,101,100,99,100],0)
    bad=[]
    for key,vals in {'e':[True,-1,3,16,1.0,None], 'sample_count':[True,0,129,-1,2.0,None], 'k':[True,-1,16,1.0,None], 'valid_bit_count':[True,-1,0,15,10000,16.0,None], 'payload_hex':['z0','0',' ','',None,False]}.items():
        for value in vals: bad.append({**valid,key:value})
    # Bit-level truncated streams, extra valid bits/bytes and each nonzero tail pad bit.
    for length in range(16,valid['valid_bit_count']):
        v={**valid,'valid_bit_count':length,'payload_hex':valid['payload_hex'][:2*((length+7)//8)]};bad.append(v)
    bad.append({**valid,'payload_hex':valid['payload_hex']+'00'})
    for bit in range(8*len(bytes.fromhex(valid['payload_hex']))-valid['valid_bit_count']):
        data=bytearray.fromhex(valid['payload_hex']);data[-1]|=1<<bit;bad.append({**valid,'payload_hex':data.hex()})
    bad.append({'mode':'rice','e':0,'k':0,'sample_count':2,'valid_bit_count':49,'payload_hex':'0000'+'0000000080'})
    for fixture in bad:
        try: m.decode_block(fixture)
        except m.CodecError: metrics['malformed_rejections']+=1
        else: raise AssertionError(('invalid fixture accepted',fixture))
        assert m.decode_block(valid)==independent_encode([100,101,100,99,100],0)[1];metrics['block_restarts']+=1
    tool_spec=importlib.util.spec_from_file_location('reviewed_accounting',BASE/'tools/verify_codec_candidate.py')
    tool=importlib.util.module_from_spec(tool_spec);tool_spec.loader.exec_module(tool)
    aggregate_checks=0
    for e in E_VALUES:
        fixtures=[m.encode_block(values,e) for values in cases]
        actual=tool.accounting_summary(fixtures)
        bits=sum(f['valid_bit_count'] for f in fixtures)
        stored=sum(len(bytes.fromhex(f['payload_hex'])) for f in fixtures)
        assert actual=={'inner_codec_body_bits':bits,'inner_codec_stored_bytes':stored,'inner_codec_padding_bits':8*stored-bits}
        aggregate_checks+=1
    expected_stored=(2000000,1917593,1830103,1722097,1606532)
    expected_padding=(0,27373,27651,27408,27061)
    for e,stored,padding in zip(E_VALUES,expected_stored,expected_padding):
        actual=result['million_run']['per_e'][str(e)]
        assert actual['inner_codec_stored_bytes']==stored
        assert actual['inner_codec_padding_bits']==padding
    witness=tool.accounting_summary([m.encode_block([100,100],0)]*2)
    assert witness['inner_codec_stored_bytes']==6 and witness['inner_codec_body_bits']==34 and witness['inner_codec_padding_bits']==14
    metrics['aggregate_checks']=aggregate_checks+1
    metrics['main_precomputed_million_profiles_checked']=5
    for rel,h in pinned.items(): assert sha((WT/rel).read_bytes())==h
    save('result.json',{'work_id':'B-CODEC-MAIN-REVIEW-20261016-01','task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'source_sha256':pinned,'requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804','metrics':metrics,'scope':'pure integer inner codec candidate only; no TRACE framing/ticks/masks or B01/R03/product/board acceptance','finding':'Inner arithmetic and encoded-byte checks pass. B-CODEC-COUNT01 corrected and independently checked against actual per-block lengths and precomputed million-profile totals. No full TRACE or card acceptance.','baseline':'49 tests exit0','python':sys.version})
    print(json.dumps(metrics,sort_keys=True))

if __name__=='__main__': main()
