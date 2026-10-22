"""Rehash every independent execution and frozen input; no extra vendor run."""
import gzip,hashlib,importlib.util,json
from pathlib import Path
from datetime import datetime,timezone
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';O=Path(__file__).parent;M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main'
sha=lambda b:hashlib.sha256(b).hexdigest()
S=W/'competition/deepeye/tools/acquisition/main_verify_sample_scan_capture.py';spec=importlib.util.spec_from_file_location('main21',S);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
freeze=json.loads((M/'frozen-inputs/FREEZE.json').read_bytes());assert sha((M/'freeze21.py').read_bytes())==freeze['model_sha256']
names=[k+'-01' for k in freeze['cases']]+['guard-'+p+'-'+str(n)+'-01' for p,ns in [('SEQ_W',[1,33]),('TICK_W',[0,65]),('TAG_W',[0,65]),('STAT_W',[1,33])] for n in ns]+['mutant-wrong-channel-mix-01','mutant-ordinal-plus-two-01']
assert len(names)==18 and len(set(names))==18
records=[];commands=[];artifacts={};guardcases=[]
for name in names:
    d=M/name;r=json.loads((d/'RESULT.json').read_bytes());pins=json.loads((d/'INPUTS.json').read_bytes())
    for f,info in pins.items():assert sha((d/'inputs'/f).read_bytes())==info['sha256'],(name,f)
    assert pins['verifier.py']['sha256']==sha(S.read_bytes())
    assert r['source_sha256']==pins['deepeye_sample_scan_capture.sv']['sha256']
    mutate=name.startswith('mutant-')
    assert r['status']==('EXPECTED_BEHAVIORAL_REJECTION' if mutate else 'PASS')
    if not mutate:assert r['source_sha256']=='9eadd35c3cdeedd00560c9d79b66a77a9bb06ab42a6b25ef7a70ded831e46b76'
    if name.startswith('guard-'):guardcases.append(r['case'])
    else:
        raw=(d/'trace.txt').read_bytes();packed=(d/'trace.txt.gz').read_bytes()
        assert gzip.decompress(packed)==raw and sha(raw)==r['trace_sha256'] and sha(packed)==r['trace_gzip_sha256']
        case=r['case'];meta=freeze['cases'][case]
        for f,h in [('vectors.hex',meta['vectors_sha256']),('expected.json.gz',meta['expected_sha256'])]:assert sha((d/'inputs'/f).read_bytes())==h
        assert r['edges']==meta['edges'] and r['unknowns']==0
        if mutate:assert r['mismatches']>0 and len(r['numeric_examples'])>0
        else:assert r['mismatches']==0
    for c in ['version','vlib','vlog','vsim']:
        rec=json.loads((d/(c+'.command.json')).read_bytes());stdout=(d/(c+'.stdout.txt')).read_bytes();stderr=(d/(c+'.stderr.txt')).read_bytes()
        assert sha(stdout)==rec['stdout_sha256'] and sha(stderr)==rec['stderr_sha256']
        own=r.get('own_fatal') if c=='vsim' else None
        assert not v.classify(rec['exit_code'],rec['timed_out'],(stdout+b'\n'+stderr).decode('utf-8',errors='replace'),own)
        assert not rec['classification'];commands.append({'run':name,'command':c,'argv':rec['argv'],'exit_code':rec['exit_code'],'sha256':sha((d/(c+'.command.json')).read_bytes())})
        if c=='version':assert b'10.7' in stdout
    assert not v.diagnostics((d/'sim.transcript.txt').read_text(encoding='utf-8'),r.get('own_fatal'))
    process=json.loads((O/(name+'.process.json')).read_bytes());assert process['exit_code']==0 and process['source_sha256']==sha(S.read_bytes())==process['source_after_sha256']
    for stream in ['stdout','stderr']:assert sha((O/(name+'.'+stream+'.txt')).read_bytes())==process[stream+'_sha256']
    records.append({k:r[k] for k in ['case','status','source_sha256','edges','mismatches','unknowns','own_fatal','public_conservation_edges'] if k in r})
    for f in d.rglob('*'):
        if f.is_file() and 'lib' not in f.relative_to(d).parts and f.name not in ['sim.wlf','trace.txt','vectors.hex']:
            artifacts[f.relative_to(W).as_posix()]=sha(f.read_bytes())
assert len(commands)==72
normal=[r for r in records if not r['case'].startswith('guard-') and r['status']=='PASS']
assert sum(r['edges'] for r in normal)==165149
result={'at_utc':datetime.now(timezone.utc).isoformat(),'status':'independent main simulation passed; author terminal and runner review still pending','source_sha256':'9eadd35c3cdeedd00560c9d79b66a77a9bb06ab42a6b25ef7a70ded831e46b76','frozen_sha256':v.FREEZE_SHA,'healthy_edges':165149,'guard_cases':guardcases,'actual_commands':len(commands),'actual_runs':len(names),'raw_artifacts_rehashed':len(artifacts),'runs':records,'commands':commands,'artifacts':artifacts,'limitations':['STAT_W32 saturation not exercised at maximum','SEQ_W32 namespace only bounded coverage','simulation only; no physical sampling/clock/ADC/source authority','all29/B02/G05/B06/R03/fullproduct/synthesis/implementation/CDC_RDC/board/system not_run']}
with (M/'MAIN_EXECUTION_REVIEW.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:result[k] for k in ['status','healthy_edges','actual_commands','actual_runs','raw_artifacts_rehashed']}))
