import argparse,hashlib,importlib.util,json
from pathlib import Path
from datetime import datetime,timezone
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main';A=M.parent/'author'
p=argparse.ArgumentParser();p.add_argument('--runner',required=True);p.add_argument('--name',required=True);a=p.parse_args();D=M/a.name;D.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest();S=Path(a.runner);spec=importlib.util.spec_from_file_location('repair21',S);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
author_files={f.relative_to(W).as_posix():{'bytes':f.stat().st_size,'sha256':sha(f.read_bytes())} for f in A.rglob('*') if f.is_file()}
final=A/'final-all-01/results';summary=json.loads((final/'summary.json').read_bytes());assert summary['ok'] is True and len(summary['selected'])==27
records=[];commands=[];checks=0
for name in summary['selected']:
    d=final/'cases'/name;c=json.loads((d/'case.json').read_bytes());entry=m.CASE_BY_NAME[name]
    streams={}
    for tool in ['vlog','vsim']:
        rec=c[tool];assert rec and not rec['timed_out'] and rec['exit']==0,(name,tool)
        for stream in ['stdout','stderr']:
            raw=(d/rec[stream+'_path']).read_bytes();assert sha(raw)==rec[stream+'_sha256'];streams[tool+'_'+stream]=raw.decode('utf-8',errors='strict')
        commands.append({'case':name,'tool':tool,'argv':rec['argv'],'exit':rec['exit'],'stdout_sha256':rec['stdout_sha256'],'stderr_sha256':rec['stderr_sha256']})
    assert m.classify_compile(0,streams['vlog_stdout'],streams['vlog_stderr'])['ok']
    for key,f in [('rtl_input','deepeye_sample_scan_capture.sv'),('tb_input','tb_sample_scan_capture.sv')]:assert sha((d/'inputs'/f).read_bytes())==c['source'][key]['sha256']
    assert c['source']['source_rtl']['sha256']=='fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d'
    assert c['source']['source_tb']['sha256']=='bf240773bc9a7e15683194e0d7418b1bf07f4e1b6f54267264223e161e47f393'
    if entry['kind']=='simulation':
        result=m.classify_simulation_output(0,streams['vsim_stdout'],streams['vsim_stderr'],entry['case_arg'],entry['expected_stats'],check_identities=entry['identities']);checks+=result['stats']['checks']
    elif entry['kind']=='guard':result=m.classify_guard_output(0,streams['vlog_stdout'],streams['vlog_stderr'],0,streams['vsim_stdout'],streams['vsim_stderr'],entry['expected_family'],entry['expected_message'])
    else:result=m.classify_mutant_output(0,streams['vlog_stdout'],streams['vlog_stderr'],0,streams['vsim_stdout'],streams['vsim_stderr'],entry['expected_case'],entry['required_mismatches'])
    records.append({'name':name,'kind':entry['kind'],'strict_classification':result})
for tool in ['vlog','vsim']:
    rec=json.loads((final/'tool-check'/(tool+'.invocation.json')).read_bytes());assert rec['exit']==0 and not rec['timed_out']
    for stream in ['stdout','stderr']:assert sha((final/'tool-check'/rec[stream+'_path']).read_bytes())==rec[stream+'_sha256']
    commands.append({'tool':tool+'-version','exit':0,'stdout_sha256':rec['stdout_sha256']})
result={'at_utc':datetime.now(timezone.utc).isoformat(),'runner_sha256':sha(S.read_bytes()),'scope':'Independent hash audit and stricter reclassification of saved author final27; not new vendor runs. Full local author inventory may exceed selected published subset.','local_author_files':len(author_files),'core_checks':checks,'case_count':len(records),'actual_saved_commands':len(commands),'failed_reclassification':[r['name'] for r in records if not r['strict_classification']['ok']],'cases':records,'commands':commands}
with (D/'AUTHOR_FILE_HASHES.json').open('x',encoding='utf-8') as f:json.dump(author_files,f,indent=2);f.write('\n')
with (D/'RESULT.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
assert checks==820621 and not result['failed_reclassification'],result['failed_reclassification']
print(json.dumps({k:v for k,v in result.items() if k not in ['cases','commands']}))
