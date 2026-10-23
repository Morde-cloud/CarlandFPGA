"""Execute a frozen public-history wire oracle, never an author test model.

All simulator inputs are copied into a new evidence directory. A mutant is
rejected only for a numeric port contradiction, not compilation or infrastructure.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time

def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def classify(raw,code,f,mode='positive',guard=None):
 lines=[x[2:] if x.startswith('# ') else x for x in raw.decode('utf-8').splitlines()]
 begin=f'MAIN_BEGIN kind={f["kind"]} stat={f["stat"]}'
 stats=f'MAIN_STATS cycles={f["cycles"]} checks={f["checks"]}'
 fatal=[x for x in lines if '** Fatal:' in x]
 tallies=[x for x in lines if x.startswith('Errors:')]
 marker=[x for x in lines if 'MAIN_' in x]
 mismatch=[]
 for x in lines:
  m=re.fullmatch(r'MAIN_MISMATCH cycle=(\d+) field=(pre|post)_([a-z_]+) got=([0-9a-f]+) expected=([0-9a-f]+)',x)
  if m and int(m[4],16)!=int(m[5],16) and 0<=int(m[1])<=f['cycles']:mismatch.append(x)
 bad=any(re.search(r'\*\*\s*(Error|Warning)',x) for x in lines)
 common=code==0 and not bad
 if mode=='mutant':
  okay=common and marker==[begin,*mismatch] and len(mismatch)==1 and fatal==['** Fatal: main numeric mismatch'] and tallies==['Errors: 1, Warnings: 0']
 elif mode=='guard':
  okay=common and fatal==[f'** Fatal: deepeye_{f["kind"]}: STAT_W out of range'] and tallies==['Errors: 1, Warnings: 0'] and marker in ([],[begin])
 else:
  okay=common and not fatal and marker==[begin,stats,'MAIN_PASS'] and tallies==['Errors: 0, Warnings: 0']
 return {'accepted':bool(okay),'mode':mode,'numeric_counterexamples':mismatch,'observed_markers':marker,'fatal':fatal,'tallies':tallies}

def main():
 p=argparse.ArgumentParser();p.add_argument('--rtl',type=Path,required=True);p.add_argument('--core',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=('positive','mutant','guard'),default='positive');p.add_argument('--stat',type=int);p.add_argument('--tools',type=Path,default=Path('D:/modelsim1/win64'));a=p.parse_args()
 f=json.loads((a.vectors/'FREEZE.json').read_bytes());stat=f['stat'] if a.stat is None else a.stat
 if a.mode!='guard' and stat!=f['stat']:raise ValueError('vector counter width mismatch')
 if f['kind'] not in ('wire_serializer','wire_parser'):raise ValueError('unknown kind')
 inp=[a.rtl.resolve(strict=True),a.core.resolve(strict=True),a.tb.resolve(strict=True),(a.vectors/'vectors.hex').resolve(strict=True),(a.vectors/'FREEZE.json').resolve(strict=True)]
 out=a.out.resolve()
 if out.exists() or any(out==x or out in x.parents for x in inp):raise ValueError('fresh output required')
 out.mkdir(parents=True);(out/'temp').mkdir();snaps={}
 for name,s in zip(('dut.sv','crc.sv','main_tb.sv','vectors.hex','FREEZE.json'),inp):
  b=s.read_bytes();(out/name).write_bytes(b);snaps[name]={'path':str(s),'sha256':sha(b),'bytes':len(b)}
 assert snaps['crc.sv']['sha256']=='8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f'
 assert snaps['vectors.hex']['sha256']==f['vectors_sha256'] and snaps['main_tb.sv']['sha256']==f['tb_sha256']
 save(out/'INPUTS.json',snaps)
 env=dict(os.environ,TEMP=str(out/'temp'),TMP=str(out/'temp'),TMPDIR=str(out/'temp'),PYTHONDONTWRITEBYTECODE='1')
 (out/'run.do').write_text('onerror {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii')
 commands=[];result={'accepted':False,'mode':a.mode,'stat':stat,'kind':f['kind']}
 def run(name,argv):
  t=time.time();timeout=False
  try:r=subprocess.run(argv,cwd=out,env=env,capture_output=True,timeout=180);code,stdout,stderr=r.returncode,r.stdout,r.stderr
  except subprocess.TimeoutExpired as e:code,stdout,stderr=None,e.stdout or b'',e.stderr or b'';timeout=True
  (out/(name+'.stdout.bin')).write_bytes(stdout);(out/(name+'.stderr.bin')).write_bytes(stderr)
  rec={'name':name,'argv':argv,'cwd':str(out),'returncode':code,'timeout':timeout,'elapsed_seconds':time.time()-t,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)};commands.append(rec);save(out/(name+'.command.json'),rec)
  if timeout:raise RuntimeError('actual tool timeout')
  return code,stdout+b'\n'+stderr
 try:
  for tool in ('vlog','vsim'):
   code,_=run(tool+'_version',[str(a.tools/(tool+'.exe')),'-version']);assert code==0
  code,_=run('vlib',[str(a.tools/'vlib.exe'),'work']);assert code==0
  code,raw=run('vlog',[str(a.tools/'vlog.exe'),'-sv','-work','work','crc.sv','dut.sv','main_tb.sv'])
  assert code==0 and not re.search(rb'\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings):\s*[1-9]',raw) and b'Errors: 0, Warnings: 0' in raw,'compile diagnostics'
  code,raw=run('vsim',[str(a.tools/'vsim.exe'),'-c','-onfinish','stop',f'-gSTAT_W={stat}',f'work.main_tb_{f["kind"]}','-do','do run.do'])
  checkf=dict(f,stat=stat);result.update(classify(raw,code,checkf,a.mode))
 except Exception as e:result['error']=type(e).__name__+': '+str(e)
 result['commands']=commands;result['inputs']=snaps;result['expected_cycles']=f['cycles'];result['expected_checks']=f['checks'];result['product_nonclaims']='All29/B04/R03/fullproduct/synth/impl/timing/CDC_RDC/board/system not_run';save(out/'RESULT.json',result)
 print(json.dumps({k:v for k,v in result.items() if k not in ('commands','inputs')}));return 0 if result['accepted'] else 1

if __name__=='__main__':raise SystemExit(main())
