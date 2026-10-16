"""Main review: numeric operator rejection and byte-preserving ordinary inputs."""
import argparse, enum, hashlib, importlib.util, json, random
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()
def load(path,name):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class Passive(int):pass
class Choice(enum.IntEnum):ZERO=0;ONE=1;TWO=2;SEVENTEEN=17
operator_calls=[]
def trap(self,*args):
 operator_calls.append(type(self).__name__)
 raise AssertionError('numeric operator executed before rejecting int subclass')
class Trap(int):pass
for method in ['__add__','__radd__','__sub__','__rsub__','__mul__','__rmul__','__floordiv__','__rfloordiv__','__mod__','__rmod__','__lshift__','__rshift__','__lt__','__le__','__gt__','__ge__','__eq__','__ne__','__index__','__int__']:
 setattr(Trap,method,trap)

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--original',required=True);p.add_argument('--vectors',required=True);p.add_argument('--output-root',required=True);args=p.parse_args()
 out=Path(args.output_root).resolve();out.mkdir(parents=True,exist_ok=False)
 source=Path(args.source).resolve();original=Path(args.original).resolve()
 c=load(source,'candidate_codec');old=load(original,'historical_codec')
 base=c.encode_block([100,100],0)
 calls=[('check_samples',lambda b:c.check_samples([b(1)])),('check_sequence',lambda b:c.check_sample_sequence([b(1)])),
        ('check_e',lambda b:c.check_e(b(0))),('zigzag',lambda b:c.zigzag(b(1))),('unzigzag',lambda b:c.unzigzag(b(1))),
        ('quantize_x',lambda b:c.quantize(b(1),1,0)),('quantize_previous',lambda b:c.quantize(1,b(1),0)),('quantize_e',lambda b:c.quantize(1,1,b(0))),
        ('reconstruct_previous',lambda b:c.reconstruct(b(1),1,0)),('reconstruct_q',lambda b:c.reconstruct(1,b(1),0)),('reconstruct_e',lambda b:c.reconstruct(1,1,b(0))),
        ('select_z',lambda b:c.select_body_encoding([b(1)])),('encode_anchor',lambda b:c.encode_block([b(1)],0)),
        ('encode_body',lambda b:c.encode_block([100,b(1)],0)),('encode_e',lambda b:c.encode_block([1],b(0))),
        ('split_size',lambda b:c.split_blocks([1],b(1))),('stream_size',lambda b:c.encode_blocks([1],0,b(1))),
        ('stream_e',lambda b:c.encode_blocks([1],b(0))),('stream_sample',lambda b:c.encode_blocks([b(1)],0))]
 for field in ['e','k','sample_count','valid_bit_count']:
  calls.append(('decode_'+field,lambda b,f=field:c.decode_block(dict(base,**{f:b(base[f])}))))
  calls.append(('decode_stream_'+field,lambda b,f=field:c.decode_blocks([dict(base,**{f:b(base[f])})])))
 failures=[];negative=[]
 for name,call in calls:
  for label,builder in [('passive',Passive),('enum',Choice),('operator_trap',Trap),('bool',bool)]:
   before=len(operator_calls)
   try:call(builder)
   except c.CodecError:status='rejected'
   except Exception as ex:status='wrong_exception:'+type(ex).__name__
   else:status='accepted'
   item={'case':name,'type':label,'status':status,'operator_calls':len(operator_calls)-before};negative.append(item)
   if status!='rejected' or len(operator_calls)!=before:failures.append(item)
 # Byte parity is a regression comparison; it is NOT an independent full codec proof.
 rng=random.Random(20261017);corpus=[[0],[65535],[100,200],[0,65535]*64,[65535,0]*64,[500]*128,list(range(128)),list(range(127,-1,-1))]
 corpus += [[rng.randrange(65536) for _ in range(rng.randrange(1,129))] for _ in range(192)]
 ordinary=0;digest=hashlib.sha256();max_error=0
 for e in [0,1,2,4,8]:
  for values in corpus:
   expected=old.encode_block(values,e);actual=c.encode_block(values,e)
   assert actual==expected,'ordinary built-in byte encoding changed'
   decoded=c.decode_block(actual);assert decoded==old.decode_block(expected)
   error=max(abs(x-y) for x,y in zip(values,decoded));assert error<=e
   max_error=max(max_error,error);ordinary+=1
   digest.update(json.dumps(actual,sort_keys=True,separators=(',',':')).encode()+b'\n')
 # Direct helper built-in edge/parity controls, including large integer q clamping.
 helpers=0
 for e in [0,1,2,4,8]:
  for previous in [0,1,32767,65534,65535]:
   for value in [0,1,32768,65534,65535]:
    assert c.quantize(value,previous,e)==old.quantize(value,previous,e);helpers+=1
   for q in [-100000,-1,0,1,100000]:
    assert c.reconstruct(previous,q,e)==old.reconstruct(previous,q,e);helpers+=1
 record={'source_sha256':sha(source.read_bytes()),'original_sha256':sha(original.read_bytes()),'vectors_sha256':sha(Path(args.vectors).read_bytes()),
         'negative_numeric_cases':len(negative),'negative_results':negative,'operator_calls':operator_calls,'failures':failures,
         'ordinary_blocks':ordinary,'ordinary_helper_cases':helpers,'ordinary_fixture_digest':digest.hexdigest(),'max_error_seen':max_error,
         'status':'passed' if not failures else 'rejected','scope':'Exact built-in integer API boundary and preserved ordinary candidate bytes only; not public TRACE ABI, B01/R03, security isolation or hardware acceptance.'}
 (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in record.items() if k not in ['negative_results','operator_calls']}))
 assert not failures

if __name__=='__main__':main()
