"""Main exhaustive binary-domain CRC oracle; table independently generated.

No author oracle import. CLI uses snapshots and fresh output only. A compiled
mutant is killed only by a numeric mismatch with the expected deliberate fatal.
"""
from pathlib import Path
import argparse,json,hashlib,os,re,subprocess,sys,time

def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def classify(raw,code,mutant=False):
 lines=[x[2:] if x.startswith('# ') else x for x in raw.decode('utf-8').splitlines()]
 begin='MAIN_BEGIN pairs=16777216'
 fatal=[x for x in lines if '** Fatal:' in x]
 tallies=[x for x in lines if x.startswith('Errors:')]
 mismatches=[]
 for x in lines:
  m=re.fullmatch(r'MAIN_MISMATCH seed=(\d+) byte=(\d+) got=(\d+) expected=(\d+)',x)
  if m and m[3]!=m[4] and 0<=int(m[1])<65536 and 0<=int(m[2])<256:mismatches.append(x)
 bad=any(re.search(r'\*\*\s*(Error|Warning)',x) for x in lines)
 if mutant:
  okay=code==0 and lines.count(begin)==1 and len(mismatches)==1 and fatal==['** Fatal: main numeric mismatch'] and tallies==['Errors: 1, Warnings: 0'] and 'MAIN_PASS' not in lines and not bad
 else:
  stats=[x for x in lines if x.startswith('MAIN_STATS')]
  okay=code==0 and not bad and not fatal and not mismatches and lines.count(begin)==1 and lines.count('MAIN_PASS')==1 and stats==['MAIN_STATS pairs=16777216 prefix=9 standard=10673'] and tallies==['Errors: 0, Warnings: 0']
  okay=okay and not any('MAIN_PASS' in x and x!='MAIN_PASS' for x in lines)
  if okay:okay=lines.index(begin)<lines.index(stats[0])<lines.index('MAIN_PASS')
 return {'accepted':bool(okay),'numeric_counterexamples':mismatches,'scope':'compiled_mutant' if mutant else '16777216 binary pairs plus9prefixes'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--rtl',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);p.add_argument('--table',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mutant',action='store_true');p.add_argument('--tools',type=Path,default=Path('D:/modelsim1/win64'));a=p.parse_args()
 inputs=[a.rtl.resolve(strict=True),a.tb.resolve(strict=True),a.table.resolve(strict=True)];out=a.out.resolve()
 if out.exists() or any(out==x or out in x.parents for x in inputs):raise ValueError('fresh output separate from inputs required')
 out.mkdir(parents=True);(out/'temp').mkdir();snapshots={}
 for name,f in zip(('dut.sv','main_tb.sv','oracle.hex'),inputs):
  b=f.read_bytes();(out/name).write_bytes(b);snapshots[name]={'path':str(f),'sha256':sha(b),'bytes':len(b)}
 if snapshots['oracle.hex']['sha256']!='364ef72ec21a070f1f8c4641f171b53bb488c0ca3c1b06d4704cd532f562ce66':raise ValueError('wrong frozen oracle table')
 save(out/'INPUTS.json',snapshots)
 env=dict(os.environ,TEMP=str(out/'temp'),TMP=str(out/'temp'),TMPDIR=str(out/'temp'),PYTHONDONTWRITEBYTECODE='1')
 (out/'run.do').write_text('onerror {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii')
 commands=[];result={'accepted':False}
 def run(name,argv):
  start=time.time();timed=False
  try:r=subprocess.run(argv,cwd=out,env=env,capture_output=True,timeout=240);code,stdout,stderr=r.returncode,r.stdout,r.stderr
  except subprocess.TimeoutExpired as e:code,stdout,stderr=None,e.stdout or b'',e.stderr or b'';timed=True
  (out/(name+'.stdout.bin')).write_bytes(stdout);(out/(name+'.stderr.bin')).write_bytes(stderr)
  receipt={'name':name,'argv':argv,'cwd':str(out),'returncode':code,'timeout':timed,'elapsed_seconds':time.time()-start,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)};commands.append(receipt);save(out/(name+'.command.json'),receipt)
  if timed:raise RuntimeError('actual simulator timeout')
  return code,stdout+b'\n'+stderr
 try:
  for tool in ('vlog','vsim'):
   code,_=run(tool+'_version',[str(a.tools/(tool+'.exe')),'-version']);assert code==0
  code,_=run('vlib',[str(a.tools/'vlib.exe'),'work']);assert code==0
  code,raw=run('vlog',[str(a.tools/'vlog.exe'),'-sv','-work','work','dut.sv','main_tb.sv'])
  assert code==0 and not re.search(rb'\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings):\s*[1-9]',raw) and b'Errors: 0, Warnings: 0' in raw,'compile diagnostics'
  code,raw=run('vsim',[str(a.tools/'vsim.exe'),'-c','-onfinish','stop','work.main_tb_crc16_byte','-do','do run.do']);result.update(classify(raw,code,a.mutant))
 except Exception as e:result['error']=type(e).__name__+': '+str(e)
 result['commands']=commands;result['inputs']=snapshots;result['product_nonclaims']='All29/B04/R03/CDC_RDC/synth/impl/board/system not_run';save(out/'RESULT.json',result);print(json.dumps(result));return 0 if result['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())
