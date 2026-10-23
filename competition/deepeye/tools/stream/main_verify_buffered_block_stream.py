"""Op35 public endpoint miter and input-derived codec history verification.

Reuses the pinned op20 direct composition/reference. This verifies a new thin
wrapper; it does not claim an independent new codec/queue algorithm.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys

ROOT=Path(__file__).resolve().parents[4]
EP='competition/deepeye/evidence/stream/buffered-block-stream-20261024-35/main'
CORE='competition/deepeye/fpga/codec/deepeye_block_encoder.sv'
STREAM='competition/deepeye/fpga/stream/deepeye_block_stream.sv'
QUEUE='competition/deepeye/fpga/stream/deepeye_encoded_frame_queue.sv'
WRAPPER='competition/deepeye/fpga/stream/deepeye_buffered_block_stream.sv'
TB='competition/deepeye/tests/rtl/stream/main_tb_buffered_block_stream.sv'
SHA=lambda b:hashlib.sha256(b).hexdigest()
def put(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def terminal(text,cycles):
 expected=[f'MAIN_BUFFERED_DONE cycles={cycles} ports=31',f'MAIN_COMPOSITION_DONE cycles={cycles} retired=11'];seen=[]
 for raw in text.splitlines():
  line=raw.strip()
  if line.startswith('# '):line=line[2:]
  if 'MAIN_BUFFERED_' in line or 'MAIN_COMPOSITION_DONE' in line:seen.append(line)
 assert seen==expected,seen

def external_score(m,path,design):
 fields=[(n,w) for n,w,_ in design['outputs']];ins=design['inputs'];pending=[];fill=None;wire=None;position=0
 admissions=retired=aborted=byte_checks=meta_checks=edges=0;counts={'RAW':0,'Rice':0,'errors':0,'stalled_meta':0,'stalled_byte':0,'full_queue':0,'cfg_backpressure':0};examples=[]
 def check(got,want,edge,kind):
  assert got==want,dict(edge=edge,kind=kind,actual=got,expected=want)
 with path.open() as f:
  for i,line in enumerate(f):
   z=line.split();assert len(z)==4 and z[:2]==['B',str(i)],(i,line)
   x=m.unpack(int(z[2],16),ins);edges+=1
   if not i:assert x['rst'];continue
   y=m.unpack(int(z[3],16),fields)
   if x['rst'] or x['cancel']:
    aborted+=len(pending)+int(fill is not None)+int(wire is not None);pending=[];fill=None;wire=None;position=0
    check([y[n] for n in ('cfg_ready','s_ready','out_meta_valid','out_valid')],[0,0,0,0],i,'suppressed handshake')
    continue
   counts['full_queue']+=int(y['queue_level']==2);counts['cfg_backpressure']+=int(x['cfg_valid'] and not y['cfg_ready'])
   check(y['queue_faulted'],0,i,'no synthetic invalid internal frames')
   if y['out_meta_valid']:
    assert pending and wire is None,(i,'unexplained or overlapping metadata')
    meta,data=pending[0];actual={k:y['out_meta_'+({'bits':'valid_bits'}.get(k,k))] for k in m.META}
    check(actual,meta,i,'input-derived metadata');meta_checks+=1;counts['stalled_meta']+=int(not x['out_meta_ready'])
    if x['out_meta_ready']:
     pending.pop(0)
     if meta['error']:retired+=1;counts['errors']+=1
     else:wire=(meta,data);position=0;counts['RAW' if meta['raw'] else 'Rice']+=1
   if y['out_valid']:
    assert wire is not None,(i,'unexplained data')
    data=wire[1];check([y['out_data'],y['out_last']],[data[position],int(position==len(data)-1)],i,'input-derived byte/last');byte_checks+=1;counts['stalled_byte']+=int(not x['out_ready'])
    if x['out_ready']:
     position+=1
     if position==len(data):wire=None;position=0;retired+=1
   if x['s_valid'] and y['s_ready']:
    assert fill is not None,(i,'sample without config')
    fill['samples'].append(x['s_data']);last=len(fill['samples'])==fill['count']
    if bool(x['s_last'])!=last:pending.append(m.codec([],0,fill['tag'],2));fill=None
    elif last:pending.append(m.codec(fill['samples'],fill['e'],fill['tag']));fill=None
   if x['cfg_valid'] and y['cfg_ready']:
    assert fill is None,(i,'overlapping fill');admissions+=1
    if not 1<=x['cfg_count']<=128 or x['cfg_e'] not in (0,1,2,4,8):pending.append(m.codec([],0,x['cfg_tag'],1))
    else:fill={'samples':[],'count':x['cfg_count'],'e':x['cfg_e'],'tag':x['cfg_tag']}
 assert not pending and fill is None and wire is None
 assert retired==11 and admissions==retired+aborted and aborted>=3,(admissions,retired,aborted)
 assert all(v>0 for v in counts.values()),counts
 return {'edges':edges,'admissions':admissions,'retired':retired,'aborted':aborted,'metadata_checks':meta_checks,'byte_checks':byte_checks,'coverage':counts,'miter_port_comparisons':(edges-1)*31}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--wrapper',type=Path);ap.add_argument('--negative',action='store_true');a=ap.parse_args()
 root=a.root.resolve();out=a.out.resolve();out.relative_to(root/EP);out.mkdir(parents=True,exist_ok=False);e=root/EP;f=e/'preinspection-01';frozen=json.loads((f/'MAIN_FREEZE.json').read_bytes());design=json.loads((e/'miter-design-01/DESIGN.json').read_bytes())
 for n,pin in frozen['pins'].items():assert SHA((root/'competition/deepeye'/n).read_bytes())==pin['sha256'],n
 assert SHA((root/TB).read_bytes())==design['main_tb_sha256'];old=module('main_op20_verifier',f/'main_verify_encoded_frame_queue.py');m=module('main_op20_model',f/'independent_model.py')
 sources={CORE:root/CORE,STREAM:root/STREAM,QUEUE:root/QUEUE,WRAPPER:a.wrapper or root/WRAPPER,TB:root/TB};snap=out/'inputs';snap.mkdir();pins={}
 for n,p in sources.items():
  raw=p.read_bytes();(snap/Path(n).name).write_bytes(raw);pins[n]={'path':str(p),'sha256':SHA(raw)}
 for p in [Path(__file__),f/'independent_model.py',f/'main_verify_encoded_frame_queue.py',f/'MAIN_FREEZE.json',e/'miter-design-01/DESIGN.json']:(snap/p.name).write_bytes(p.read_bytes())
 put(out/'INPUTS.json',pins);result={'negative':a.negative,'status':'RUNNING','scope':'bounded wrapper endpoints plus reused direct composition and codec reference'}
 try:
  tool=Path('D:/modelsim1/win64');old.command(out,'version',[tool/'vsim.exe','-version'],30);old.command(out,'vlib',[tool/'vlib.exe','lib'],30)
  old.command(out,'vlog',[tool/'vlog.exe','-sv','-work','lib',*[snap/Path(n).name for n in sources]],60)
  text=old.command(out,'vsim',[tool/'vsim.exe','-c','-work','lib','-l',out/'sim.transcript','-wlf',out/'sim.wlf','-do','run -all; quit -f','main_buffered_miter','+TRACE='+str(out/'trace.txt'),'+BTRACE='+str(out/'buffered_trace.txt')],240,'MAIN_BUFFERED_NUMERIC_FAILURE' if a.negative else None)
  if a.negative:
   lines=[s.removeprefix('# ') for s in text.splitlines() if 'MAIN_BUFFERED_MISMATCH' in s]
   assert len(lines)==1;hit=re.fullmatch(r'MAIN_BUFFERED_MISMATCH cycle=([0-9]+) expected=([0-9a-f]+) actual=([0-9a-f]+)',lines[0]);assert hit and int(hit[1])>0 and int(hit[2],16)!=int(hit[3],16),lines
   assert 'MAIN_BUFFERED_DONE' not in text
   result.update(status='EXPECTED_NUMERIC_REJECTION',cycle=int(hit[1]),expected=hit[2],actual=hit[3])
  else:
   scored=external_score(m,out/'buffered_trace.txt',design);terminal(text,scored['edges']);old_result=old.composition(m,out);assert old_result['mismatches']==0 and old_result['edges']==scored['edges'];result.update(status='PASS',external=scored,reused_reference_composition=old_result)
  for name in ('trace.txt','buffered_trace.txt'):
   raw=(out/name).read_bytes();result[name]={'sha256':SHA(raw),'bytes':len(raw)}
 except Exception as ex:result.update(status='FAILED',error=repr(ex));raise
 finally:put(out/'RESULT.json',result);print(json.dumps(result))
if __name__=='__main__':main()
