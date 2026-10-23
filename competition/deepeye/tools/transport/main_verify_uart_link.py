"""Run frozen main link vectors against eight exact Git source snapshots."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,subprocess,time
PINS={'deepeye_crc16_byte.sv':'8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f','deepeye_wire_serializer.sv':'efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885','deepeye_uart_frame_tx.sv':'83261e4c5a317500e224f5cd0e9ce538f067be24d3957dd98c7116425e706be3','deepeye_uart_tx.sv':'5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47','deepeye_wire_uart_tx.sv':'4998acb76fed7e53405816c91203bc93df622f05b621da342e1cc8178f51133d','deepeye_uart_rx.sv':'935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f','deepeye_wire_parser.sv':'7806c5d08785b96eae3708d9fd6d6002ef82faa4416a1f7244da73bece552649','deepeye_uart_wire_rx.sv':'b6abab4e1be54ee61bd45e4d7adfcfea8db39f7574d3ce2ae7b7030ff74ade2c'}
SOURCE='bbfb11439b35e0866a6d2486f3857b92ed6cf529'
def sha(b):return hashlib.sha256(b).hexdigest()
def put(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def classify(raw,code,f,mutant=False):
 lines=[x[2:] if x.startswith('# ') else x for x in raw.decode('utf-8').splitlines()]
 protocol=[x for x in lines if 'MAIN_' in x or re.search(r'\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings)\s*:',x)]
 expected=['MAIN_LINK_BEGIN',f'MAIN_LINK_STATS events={f["events"]} checks={f["checks"]}','MAIN_LINK_PASS','Errors: 0, Warnings: 0'];numeric=[]
 if mutant:
  for line in protocol:
   m=re.fullmatch(r'MAIN_MISMATCH event=(\d+) time_ps=(\d+) field=([a-z_]+) got=([0-9a-f]+) expected=([0-9a-f]+)',line)
   if m and 0<int(m[1])<=f['events'] and int(m[4],16)!=int(m[5],16):numeric.append(line)
  expected=['MAIN_LINK_BEGIN',*numeric,'** Fatal: main link numeric mismatch','Errors: 1, Warnings: 0']
 return {'accepted':code==0 and protocol==expected and (not mutant or len(numeric)==1),'protocol':protocol,'numeric_counterexamples':numeric}
def main():
 p=argparse.ArgumentParser();p.add_argument('--worktree',type=Path,required=True);p.add_argument('--vectors',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mutant',choices=('line_invert','no_fault_mux','no_receiver_cancel'));a=p.parse_args()
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);(out/'temp').mkdir();f=json.loads((a.vectors/'FREEZE.json').read_bytes());inputs={};commands=[]
 def snap(n,b,origin):
  (out/n).write_bytes(b);inputs[n]={'origin':origin,'sha256':sha(b),'bytes':len(b)}
 for n,h in PINS.items():
  ref=f'{SOURCE}:competition/deepeye/fpga/transport/{n}';b=subprocess.check_output(['git','-C',str(a.worktree),'show',ref]);assert sha(b)==h;snap(n,b,ref)
 tb=a.tb.read_bytes();assert sha(tb)==f['tb_sha256'];snap('original_main_tb.sv',tb,str(a.tb))
 if a.mutant:
  old,new={'line_invert':(b':t_tx;',b':~t_tx;'),'no_fault_mux':(b'assign line=(mux_mode==1)?~t_tx:(mux_mode==2)?1\'b0:(mux_mode==3)?1\'b1:t_tx;',b'assign line=t_tx;'),'no_receiver_cancel':(b'.cancel(r_cancel)',b'.cancel(1\'b0)')}[a.mutant]
  assert tb.count(old)==1;tb=tb.replace(old,new)
 snap('main_tb.sv',tb,'original or explicit test-only mutant')
 b=(a.vectors/'events.hex').read_bytes();assert sha(b)==f['vectors_sha256'];snap('events.hex',b,str(a.vectors));snap('FREEZE.json',(a.vectors/'FREEZE.json').read_bytes(),str(a.vectors));put(out/'INPUTS.json',inputs)
 (out/'run.do').write_text('onerror {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii');env=dict(os.environ,TEMP=str(out/'temp'),TMP=str(out/'temp'),TMPDIR=str(out/'temp'),PYTHONDONTWRITEBYTECODE='1')
 tools=Path('D:/modelsim1/win64');result={'accepted':False,'source_commit':SOURCE,'mutant':a.mutant,'expected_events':f['events'],'expected_checks':f['checks']}
 def run(n,argv):
  start=time.time();timed=False
  try:r=subprocess.run(argv,cwd=out,env=env,capture_output=True,timeout=300,creationflags=0x08000000);code,stdout,stderr=r.returncode,r.stdout,r.stderr
  except subprocess.TimeoutExpired as e:code,stdout,stderr=None,e.stdout or b'',e.stderr or b'';timed=True
  (out/(n+'.stdout.bin')).write_bytes(stdout);(out/(n+'.stderr.bin')).write_bytes(stderr)
  rec={'name':n,'argv':argv,'cwd':str(out),'returncode':code,'timeout':timed,'elapsed_seconds':time.time()-start,'stdout_sha256':sha(stdout),'stderr_sha256':sha(stderr)};commands.append(rec);put(out/(n+'.command.json'),rec)
  if timed:raise RuntimeError('actual tool timeout, no replay')
  return code,stdout+b'\n'+stderr
 try:
  for t in ('vlog','vsim'):
   code,_=run(t+'_version',[str(tools/(t+'.exe')),'-version']);assert code==0
  code,_=run('vlib',[str(tools/'vlib.exe'),'work']);assert code==0
  code,raw=run('vlog',[str(tools/'vlog.exe'),'-sv','-work','work',*PINS,'main_tb.sv']);assert code==0 and not re.search(rb'\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings):\s*[1-9]',raw) and raw.count(b'Errors: 0, Warnings: 0')==1,'compile diagnostics'
  code,raw=run('vsim',[str(tools/'vsim.exe'),'-c','-onfinish','stop',f'-gCLOCK_HZ={f["clock_parameter"]}',f'-gBAUD={f["baud_parameter"]}','work.main_tb_uart_link','-do','do run.do']);result.update(classify(raw,code,f,bool(a.mutant)))
 except Exception as e:result['error']=type(e).__name__+': '+str(e)
 result.update(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),commands=commands,inputs=inputs,formal='all29/B04/R03/fullproduct/implementation/timing/CDC_RDC/board/system not_run');put(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('commands','inputs')}));return 0 if result['accepted'] else 1
if __name__=='__main__':raise SystemExit(main())
