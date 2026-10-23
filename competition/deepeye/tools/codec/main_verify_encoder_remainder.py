"""Main op36 execution of reused independent op08 cases with a public-port miter."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys
ROOT=Path(__file__).resolve().parents[4]
EP='competition/deepeye/evidence/codec/encoder-remainder-20261024-36/main'
CORE='competition/deepeye/fpga/codec/deepeye_block_encoder.sv'
CANDIDATE='competition/deepeye/fpga/codec/deepeye_block_encoder_remainder_candidate.sv'
TB='competition/deepeye/tests/rtl/codec/main_tb_encoder_remainder.sv'
SHA=lambda b:hashlib.sha256(b).hexdigest()
def put(p,x):
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,indent=2)
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def terminal(text,cycles):
 rows=[]
 for raw in text.splitlines():
  line=raw.strip().removeprefix('# ')
  if any(k in line for k in ('MAIN_PORT_','MAIN_REMAINDER_')):rows.append(line)
 assert rows==[f'MAIN_PORT_COMPLETE cycles={cycles}',f'MAIN_REMAINDER_COMPLETE cycles={cycles} ports=13'],rows
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=Path,default=ROOT);a.add_argument('--out',type=Path,required=True);a.add_argument('--candidate',type=Path);a.add_argument('--negative',action='store_true');args=a.parse_args();root=args.root.resolve();out=args.out.resolve();out.relative_to(root/EP);out.mkdir(exist_ok=False,parents=True);e=root/EP;f=e/'preinspection-01'
 frozen=json.loads((f/'MAIN_FREEZE.json').read_bytes());design=json.loads((e/'miter-design-01/DESIGN.json').read_bytes())
 for n,p in frozen['pins'].items():assert SHA((root/'competition/deepeye'/n).read_bytes())==p['sha256'],n
 assert SHA((root/TB).read_bytes())==design['tb_sha256'];cases=json.loads((f/'historical_cases.json').read_bytes());assert len(cases)==1559 and SHA((f/'historical_cases.json').read_bytes())==frozen['cases_sha256']
 model=module('main_op08_math',f/'main_encoder_review.py')
 helper=root/'competition/deepeye/evidence/stream/buffered-block-stream-20261024-35/main/preinspection-01/main_verify_encoded_frame_queue.py';h=helper.read_bytes()
 hpin=json.loads((helper.parent/'MAIN_FREEZE.json').read_bytes())['pins']['tools/stream/main_verify_encoded_frame_queue.py']['sha256'];assert SHA(h)==hpin;command=module('main_exec_helper_op20',helper).command
 snap=out/'inputs';snap.mkdir();sources={CORE:root/CORE,CANDIDATE:args.candidate or root/CANDIDATE,TB:root/TB};pins={}
 for n,p in sources.items():
  b=p.read_bytes();(snap/Path(n).name).write_bytes(b);pins[n]={'path':str(p),'sha256':SHA(b)}
 for p in [Path(__file__),helper,f/'MAIN_FREEZE.json',f/'MAIN_PROOF.md',f/'main_encoder_review.py',f/'historical_cases.json']:(snap/p.name).write_bytes(p.read_bytes())
 text='\n'.join(' '.join(map(str,[c['id'],c['count'],c['e'],len(c['samples']),c['last_mode'],c['abort_stage'],c['abort_reset'],c['seed'],*c['samples']])) for c in cases)+'\n';(snap/'cases.txt').write_text(text,encoding='ascii');put(out/'INPUTS.json',pins)
 result={'status':'RUNNING','negative':args.negative,'scope':'new execution of1559reused independent historicalcases; same-cycle public endpoint miter; no timingclaim'}
 try:
  tool=Path('D:/modelsim1/win64');command(out,'version',[tool/'vsim.exe','-version'],30);command(out,'vlib',[tool/'vlib.exe','lib'],30);command(out,'vlog',[tool/'vlog.exe','-sv','-work','lib',*[snap/Path(n).name for n in sources]],60)
  raw=command(out,'vsim',[tool/'vsim.exe','-c','-work','lib','-l',out/'sim.transcript','-wlf',out/'sim.wlf','-do','run -all; quit -f','main_encoder_port_tb','+INPUT='+str(snap/'cases.txt'),'+OUTPUT='+str(out/'ports.txt')],600,'MAIN_REMAINDER_NUMERIC_FAILURE' if args.negative else None)
  if args.negative:
   markers=[s.removeprefix('# ') for s in raw.splitlines() if 'MAIN_REMAINDER_MISMATCH' in s];assert len(markers)==1;z=re.fullmatch(r'MAIN_REMAINDER_MISMATCH cycle=([0-9]+) expected=([0-9a-f]+) actual=([0-9a-f]+)',markers[0]);assert z and int(z[1])>1 and int(z[2],16)!=int(z[3],16);assert 'MAIN_REMAINDER_COMPLETE' not in raw;result.update(status='EXPECTED_NUMERIC_REJECTION',cycle=int(z[1]),expected=z[2],actual=z[3])
  else:
   stats=model.verify(cases,out/'ports.txt');cycles=stats['monitor_totals']['cycles'];terminal(raw,cycles);result.update(status='PASS',stats=stats,public_port_comparisons=(cycles-1)*13)
  result['ports_sha256']=SHA((out/'ports.txt').read_bytes())
 except Exception as ex:result.update(status='FAILED',error=repr(ex));raise
 finally:put(out/'RESULT.json',result);print(json.dumps(result))
if __name__=='__main__':main()
