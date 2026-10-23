"""Fresh operation37 wrapper comparison against frozen pre-adoption reference RTL."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parents[4]
EP='competition/deepeye/evidence/codec/encoder-remainder-adoption-20261024-37/main'
H='4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def get(p):return json.loads(p.read_bytes())
def put(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def module(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--mutant',type=Path);a=ap.parse_args();root=a.root.resolve();p=root/'competition/deepeye';e=root/EP;f=e/'preinspection-01';ref=e/'reference-design-01';out=a.out.resolve();out.relative_to(e);out.mkdir(exist_ok=False,parents=True)
 design=get(f/'MAIN_DESIGN.json');r=get(ref/'REFERENCE.json');core=p/'fpga/codec/deepeye_block_encoder.sv';assert sha(core)==H==design['expected_production_sha256']
 for n in ('fpga/stream/deepeye_block_stream.sv','fpga/stream/deepeye_encoded_frame_queue.sv','fpga/stream/deepeye_buffered_block_stream.sv'):assert sha(p/n)==design['pins'][n]['sha256']
 assert sha(ref/'main37_frozen_encoder.sv')==r['frozen_reference_encoder_sha256'] and sha(ref/'main37_frozen_block_stream.sv')==r['frozen_reference_stream_sha256']
 for n,x in r['transitive'].items():assert sha(ref/n)==x['sha256']
 checker=f/'main_verify_buffered_block_stream.py';assert sha(checker)==design['pins']['tools/stream/main_verify_buffered_block_stream.py']['sha256']
 score=module('main37_reused_35',checker);old=module('main37_reused_20',ref/'main_verify_encoded_frame_queue.py');model=module('main37_math_reference',ref/'independent_model.py');portdesign=get(ref/'DESIGN.json')
 tb=p/'tests/rtl/codec/main_tb_encoder_adoption_stream.sv';assert sha(tb)==r['new_tb_sha256']
 sources=[a.mutant or core,p/'fpga/stream/deepeye_block_stream.sv',p/'fpga/stream/deepeye_encoded_frame_queue.sv',p/'fpga/stream/deepeye_buffered_block_stream.sv',ref/'main37_frozen_encoder.sv',ref/'main37_frozen_block_stream.sv',tb]
 snap=out/'inputs';snap.mkdir();pins={}
 for i,s in enumerate(sources):
  name='deepeye_block_encoder.sv' if i==0 else s.name;b=s.read_bytes();(snap/name).write_bytes(b);pins[name]={'source':str(s),'sha256':hashlib.sha256(b).hexdigest()}
 for s in [Path(__file__),checker,ref/'REFERENCE.json',ref/'DESIGN.json',ref/'independent_model.py',ref/'main_verify_encoded_frame_queue.py',f/'MAIN_DESIGN.json']:(snap/s.name).write_bytes(s.read_bytes())
 put(out/'INPUTS.json',pins);result={'status':'RUNNING','negative':a.mutant is not None,'scope':'Adopted core through live wrapper vs frozenOLDcore/stream; unchanged commonqueue; reused pre-frozen math/stimulus; bounded software only.'}
 try:
  tool=Path('D:/modelsim1/win64');old.command(out,'version',[tool/'vsim.exe','-version'],30);old.command(out,'vlib',[tool/'vlib.exe','lib'],30);old.command(out,'vlog',[tool/'vlog.exe','-sv','-work','lib',*[snap/n for n in pins]],60)
  raw=old.command(out,'vsim',[tool/'vsim.exe','-c','-work','lib','-l',out/'sim.transcript','-wlf',out/'sim.wlf','-do','run -all; quit -f','main_buffered_miter','+TRACE='+str(out/'trace.txt'),'+BTRACE='+str(out/'buffered_trace.txt')],240,'MAIN_BUFFERED_NUMERIC_FAILURE' if a.mutant else None)
  if a.mutant:
   lines=[s.removeprefix('# ') for s in raw.splitlines() if 'MAIN_BUFFERED_MISMATCH' in s];assert len(lines)==1;z=re.fullmatch(r'MAIN_BUFFERED_MISMATCH cycle=([0-9]+) expected=([0-9a-f]+) actual=([0-9a-f]+)',lines[0]);assert z and int(z[1])>0 and int(z[2],16)!=int(z[3],16);assert 'MAIN_BUFFERED_DONE' not in raw;result.update(status='EXPECTED_NUMERIC_REJECTION',cycle=int(z[1]),expected=z[2],actual=z[3])
  else:
   scored=score.external_score(model,out/'buffered_trace.txt',portdesign);score.terminal(raw,scored['edges']);orig=old.composition(model,out);assert orig['mismatches']==0 and orig['edges']==scored['edges'];result.update(status='PASS',external=scored,frozen_original_reference=orig)
  for n in ('trace.txt','buffered_trace.txt'):result[n]={'sha256':sha(out/n),'bytes':(out/n).stat().st_size}
 except Exception as ex:result.update(status='FAILED',error=repr(ex));raise
 finally:put(out/'RESULT.json',result);print(json.dumps(result))
if __name__=='__main__':main()
