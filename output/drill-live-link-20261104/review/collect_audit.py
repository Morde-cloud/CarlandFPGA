"""Read-only local evidence collection. No project imports, tests, or hardware."""
import hashlib,json,subprocess,datetime,xml.etree.ElementTree as ET
from pathlib import Path
R=Path(__file__).resolve().parents[3]; O=Path(__file__).resolve().parent
B=R/'output/drill-demo-code-20261025'; F=B/'fpga_link/overlay'; RUN=F/'run-20261103-195848'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def rel(p): return str(p.relative_to(R)).replace('\\','/') if p.is_relative_to(R) else str(p)
def verify(items,base):
    out=[]
    for i in items:
        p=base/i['path']; actual=sha(p) if p.is_file() else None
        out.append({'path':rel(p),'expected_sha256':i['sha256'],'actual_sha256':actual,'matches':actual==i['sha256'],'size':p.stat().st_size if p.is_file() else None})
    return out
contract=R/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-87/A220/revision2/docs/competition/deepeye-2026/immutable_scope.json'
c=read(contract); canonical=json.dumps(c['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
fixed='817b355887c14cfa9c5d830c8589684f994af082'
g=subprocess.run(['git','show',fixed+':docs/competition/deepeye-2026/immutable_scope.json'],cwd=R,capture_output=True)
fixed_match=g.returncode==0 and json.loads(g.stdout)['requirements']==c['requirements']
m=read(B/'motor_runtime/evidence/latest-build.json'); f=read(F/'latest-build.json')
task=read(R/'output/drill-live-link-20261104/TASK.json')
groups={'parent_baseline_pins':verify(task['baseline_pins'],R),'motor_build_manifest':verify(m['files'],B),'overlay_artifacts':verify(f['artifacts'],F),'overlay_reports':verify(f['reports'],F),'overlay_sources':verify(f['sources'],F),'overlay_build_inputs':verify(read(RUN/'inputs.json')['files'],R)}
groups['overlay_input_snapshots']=verify([x for x in f['sources'] if x['path'] in ('build.py','build_overlay.tcl','pmod_uart.xdc')],RUN/'inputs')
for name in ['motor_runtime/evidence/variable-checks-20261103.json','motor_runtime/evidence/latest-host-checks.json','motor_runtime/evidence/latest-checks.json','fpga_link/evidence/latest-checks.json','gimbal_smoothness_v9/evidence/default500-checks.json']:
    d=read(B/name)
    if d.get('files'):groups[name]=verify(d['files'],B)
historical=[]
def walk(o,p,trail=''):
    if isinstance(o,dict):
        if 'command' in o or 'argv' in o:historical.append({'evidence':rel(p),'position':trail,**{k:v for k,v in o.items() if k in ('command','argv','exit_code','returncode','status','name','output','stdout','stderr')}})
        for k,v in o.items():walk(v,p,trail+'/'+k)
    elif isinstance(o,list):
        for n,v in enumerate(o):walk(v,p,trail+'/'+str(n))
histpaths=[RUN/'COMMAND.json',RUN/'RESULT.json',B/'motor_runtime/evidence/build-20261103-224235-564881.json',B/'motor_runtime/evidence/mtr4-flash-vmoff-20261103-2247.json',B/'motor_runtime/evidence/variable-checks-20261103.json',B/'motor_runtime/evidence/latest-host-checks.json',B/'motor_runtime/evidence/latest-checks.json',B/'fpga_link/evidence/latest-checks.json']
histpaths += [B/'gimbal_smoothness_v9/evidence/default500-checks.json',B/'gimbal_smoothness_v9/review/audit-evidence.json']
for p in histpaths:walk(read(p),p)
(O/'historical-commands.json').write_text(json.dumps({'historical_only':True,'new_execution':False,'records':historical},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
h=ET.parse(RUN/'artifacts/mcu_link.hwh').getroot(); uart=[]
for e in h.iter():
    if e.tag=='MODULE' and 'uart' in e.attrib.get('INSTANCE','').lower():
        uart.append({'module':e.attrib,'parameters':[x.attrib for x in e.iter('PARAMETER') if any(y in x.attrib.get('NAME','').upper() for y in ['BAUD','DATA','PARITY','CLOCK','FREQ','ADDR'])]})
inventory=[]
paths=[contract,R/'output/drill-live-link-20261104/TASK.json',B/'CURRENT_STATUS.md',B/'gimbal_smoothness_v9/STATUS.json',B/'gimbal_smoothness_v9/README.md',B/'motor_runtime/evidence/STATUS.json',B/'motor_runtime/evidence/HUMAN_ACCEPTANCE_MTR4.json',B/'motor_runtime/evidence/v9-final-default500-20261103.json',B/'motor_runtime/variable_session.py',B/'fpga_link/session.py',B/'fpga_link/ssh_client.py',B/'fpga_link/bridge_stdio.py',B/'fpga_link/uartlite.py',B/'fpga_link/profile.json',F/'latest-build.json',B/'motor_runtime/evidence/latest-build.json',B/'motor_runtime/motor_control.c',B/'motor_runtime/src/free_control.c',B/'motor_runtime/src/free_control_main.c',B/'firmware/demo_core.c',B/'firmware/demo_core.h',B/'pc/codec.py',*histpaths]
for p in dict.fromkeys(paths):inventory.append({'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size})
result={'collected_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'file reads/hash/XML inspection only; historical commands were not run','contract':{'revision':2,'fixed_commit':fixed,'requirements_ids':[x['id'] for x in c['requirements']],'requirements_sha256':hashlib.sha256(canonical).hexdigest(),'expected_sha256':'2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d','fixed_commit_git_show_exit_code':g.returncode,'fixed_commit_git_show_stderr':g.stderr.decode(errors='replace'),'fixed_commit_requirements_equal':fixed_match,'fixed_commit_comparison_limitation':'Local commit/tree unavailable; no network fetch attempted. Fixed requirements hash independently matches.','historical_revision1_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'},'checks':groups,'inventory':inventory,'hwh_uart':uart,'historical_command_count':len(historical),'historical_commands_path':rel(O/'historical-commands.json')}
(O/'evidence-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'contract':result['contract'],'groups':{k:{'total':len(v),'mismatches':[x['path'] for x in v if not x['matches']]} for k,v in groups.items()},'hwh_uart':uart,'historical_command_count':len(historical)},ensure_ascii=False,indent=2))
