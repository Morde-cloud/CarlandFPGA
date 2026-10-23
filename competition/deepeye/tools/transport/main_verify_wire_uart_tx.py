"""Main-owned execution of fixed absolute-clock composition vectors."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time
PINS={'deepeye_crc16_byte.sv':'8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f','deepeye_wire_serializer.sv':'efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885','deepeye_uart_frame_tx.sv':'83261e4c5a317500e224f5cd0e9ce538f067be24d3957dd98c7116425e706be3','deepeye_uart_tx.sv':'5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47'}
PARAMS={'clock':'CLOCK_HZ','baud':'BAUD','pre':'PRE_CYCLES','post':'POST_CYCLES','stat':'STAT_W'}
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def classify(raw,code,f,params,mode='positive',guard=None):
 lines=[x[2:] if x.startswith('# ') else x for x in raw.decode('utf-8').splitlines()]
 begin='MAIN_BEGIN '+' '.join(f'{x}={params[x]}' for x in PARAMS)
 stats=f'MAIN_STATS cycles={f["cycles"]} checks={f["checks"]}'
 markers=[x for x in lines if 'MAIN_' in x];fatals=[x for x in lines if '** Fatal:' in x];tallies=[x for x in lines if x.startswith('Errors:')]
 bad=any(re.search(r'\*\*\s*(Error|Warning)',x) for x in lines);numeric=[]
 for x in markers:
  m=re.fullmatch(r'MAIN_MISMATCH cycle=(\d+) field=(pre|post)_([a-z_]+) got=([0-9a-f]+) expected=([0-9a-f]+)',x)
  if m and int(m[4],16)!=int(m[5],16) and int(m[1])<=f['cycles']:numeric.append(x)
 if mode=='positive':okay=not bad and not fatals and markers==[begin,stats,'MAIN_PASS'] and tallies==['Errors: 0, Warnings: 0']
 elif mode=='mutant':okay=not bad and len(numeric)==1 and markers==[begin,*numeric] and fatals==['** Fatal: main numeric mismatch'] and tallies==['Errors: 1, Warnings: 0']
 else:okay=not bad and fatals==[f'** Fatal: deepeye_wire_uart_tx: {guard} out of range'] and tallies==['Errors: 1, Warnings: 0'] and markers in ([],[begin])
 # Bind diagnostics and markers in actual stream order; a single early tally
 # must not be accepted merely because its value is zero.
 protocol=[x for x in lines if 'MAIN_' in x or re.search(r'\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings)\s*:',x)]
 if mode=='positive':expected=[begin,stats,'MAIN_PASS','Errors: 0, Warnings: 0']
 elif mode=='mutant':expected=[begin,*numeric,'** Fatal: main numeric mismatch','Errors: 1, Warnings: 0']
 else:expected=[*markers,*fatals,'Errors: 1, Warnings: 0']
 okay=okay and protocol==expected
 return {'accepted':bool(code==0 and okay),'numeric_counterexamples':numeric,'markers':markers,'fatals':fatals,'tallies':tallies,'protocol':protocol}

def main():
 p=argparse.ArgumentParser();p.add_argument('--rtl',type=Path,required=True);p.add_argument('--dependencies',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=('positive','mutant','guard'),default='positive');p.add_argument('--override',action='append',default=[]);p.add_argument('--guard-expect',choices=tuple(PARAMS.values()));p.add_argument('--tools',type=Path,default=Path('D:/modelsim1/win64'));a=p.parse_args()
 f=json.loads((a.vectors/'FREEZE.json').read_bytes());params=dict(f['parameters']);assert f['kind']=='wire_uart_tx'
 if a.override and a.mode!='guard':raise ValueError('only guards may override frozen parameters')
 for opt in a.override:k,v=opt.split('=',1);assert k in params;params[k]=int(v)
 out=a.out.resolve();inputs={'dut.sv':a.rtl,'main_tb.sv':a.tb,'vectors.rle':a.vectors/'vectors.rle','FREEZE.json':a.vectors/'FREEZE.json'}
 inputs.update({n:a.dependencies/n for n in PINS})
 if out.exists() or any(out==x.resolve() or out in x.resolve().parents for x in inputs.values()):raise ValueError('fresh owned output required')
 out.mkdir(parents=True);(out/'temp').mkdir();snaps={}
 for n,pth in inputs.items():
  b=pth.read_bytes();snaps[n]={'source':str(pth.resolve()),'sha256':sha(b),'bytes':len(b)};(out/n).write_bytes(b)
  if n in PINS:assert sha(b)==PINS[n]
 assert snaps['main_tb.sv']['sha256']==f['tb_sha256'] and snaps['vectors.rle']['sha256']==f['vectors_sha256']
 put(out/'INPUTS.json',snaps);commands=[];result={'accepted':False,'parameters':params,'mode':a.mode,'expected_cycles':f['cycles'],'expected_checks':f['checks']}
 env=dict(os.environ,TEMP=str(out/'temp'),TMP=str(out/'temp'),TMPDIR=str(out/'temp'),PYTHONDONTWRITEBYTECODE='1')
 (out/'run.do').write_text('onerror {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii')
 def run(n,argv):
  start=time.time();timed=False
  try:r=subprocess.run(argv,cwd=out,env=env,capture_output=True,timeout=240);code,stdout,stderr=r.returncode,r.stdout,r.stderr
  except subprocess.TimeoutExpired as e:code,stdout,stderr=None,e.stdout or b'',e.stderr or b'';timed=True
  (out/(n+'.stdout.bin')).write_bytes(stdout);(out/(n+'.stderr.bin')).write_bytes(stderr)
  rec={'name':n,'argv':argv,'cwd':str(out),'returncode':code,'timeout':timed,'elapsed_seconds':time.time()-start,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)};commands.append(rec);put(out/(n+'.command.json'),rec)
  if timed:raise RuntimeError('actual tool timeout')
  return code,stdout+b'\n'+stderr
 try:
  for t in ('vlog','vsim'):
   code,_=run(t+'_version',[str(a.tools/(t+'.exe')),'-version']);assert code==0
  code,_=run('vlib',[str(a.tools/'vlib.exe'),'work']);assert code==0
  code,raw=run('vlog',[str(a.tools/'vlog.exe'),'-sv','-work','work',*PINS,'dut.sv','main_tb.sv'])
  assert code==0 and not re.search(rb'\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings):\s*[1-9]',raw) and b'Errors: 0, Warnings: 0' in raw,'compile diagnostics'
  code,raw=run('vsim',[str(a.tools/'vsim.exe'),'-c','-onfinish','stop',*[f'-g{PARAMS[k]}={v}' for k,v in params.items()],'work.main_tb_wire_uart_tx','-do','do run.do']);result.update(classify(raw,code,f,params,a.mode,a.guard_expect))
 except Exception as e:result['error']=type(e).__name__+': '+str(e)
 result.update(commands=commands,inputs=snaps,formal='All29/B04/R03/fullproduct/synth/impl/timing/CDC_RDC/board/system not_run');put(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('commands','inputs')}));return 0 if result['accepted'] else 1
if __name__=='__main__':raise SystemExit(main())
