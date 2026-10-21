from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,shutil
O=Path(__file__).resolve().parent
W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
E=W/'competition/deepeye/evidence/stream/encoded-frame-queue-20261022-20';M=E/'main';A=E/'author'
sha=lambda b:hashlib.sha256(b).hexdigest()
output=M/'EVIDENCE_REVIEW.json';assert not output.exists()
manifest=json.loads((A/'EVIDENCE_MANIFEST.json').read_bytes())
assert sha((A/'EVIDENCE_MANIFEST.json').read_bytes())=='2d30800a1675de44bc676e5df30ede406a06a5601c8aef6a5351ef8ece725d6c'
for name,row in manifest['author_files'].items():
    raw=(A/name).read_bytes();assert len(raw)==row['bytes'] and sha(raw)==row['sha256'],name
art=json.loads((A/'run-final-01/ARTIFACTS.json').read_bytes())
for name,digest in art['artifacts'].items():assert sha((A/'run-final-01'/name).read_bytes())==digest,name
spec=importlib.util.spec_from_file_location('main_current_checker',W/'competition/deepeye/tools/stream/main_verify_encoded_frame_queue.py')
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)
accepted=['standalone-01','sat2-01','sat3-01','composition-01','guard0-02','guard1-02','guard33-02','mutants-control-01','mutant-early_metadata-02','mutant-ignore_cancel-02']
base='68f9b655794a722a5cb285ac1c87749ea7acea7dcd6c1650536d1f1094c2e76a'
assert sha((W/checker.QP).read_bytes())==base
now_tb=(W/checker.TP).read_bytes();split=b'module main_queue_guard'
functional_prefix=now_tb.split(split)[0]
runs=[]
for name in accepted:
    d=M/name;result=json.loads((d/'RESULT.json').read_bytes());pins=json.loads((d/'INPUTS.json').read_bytes())
    raw=(d/'inputs/deepeye_encoded_frame_queue.sv').read_bytes()
    assert sha(raw)==result['source_sha256']==result['final_source_sha256']
    mutant=name.startswith('mutant-')
    assert result['status']==('EXPECTED_BEHAVIORAL_REJECTION' if mutant else 'PASS')
    if not mutant:assert sha(raw)==base
    if not name.startswith('guard'):
        assert (d/'inputs/main_tb_encoded_frame_queue.sv').read_bytes().split(split)[0]==functional_prefix
    else:assert (d/'inputs/main_tb_encoded_frame_queue.sv').read_bytes()==now_tb
    commands=[]
    for command in ['version','vlib','vlog','vsim']:
        record=json.loads((d/(command+'.command.json')).read_bytes())
        stdout=(d/(command+'.stdout.bin')).read_bytes();stderr=(d/(command+'.stderr.bin')).read_bytes()
        assert sha(stdout)==record['stdout_sha256'] and sha(stderr)==record['stderr_sha256']
        assert record['exit_code']==0 and not record['timed_out']
        own=result.get('own_fatal') if command=='vsim' else None
        assert not checker.errors((stdout+b'\n'+stderr).decode('utf-8',errors='replace'),own),(name,command)
        commands.append(dict(command=command,pid=record['pid'],exit=record['exit_code']))
    runs.append(dict(name=name,result_sha256=sha((d/'RESULT.json').read_bytes()),result=result,actual_commands=commands))
q=json.loads((M/'runner-qualification-02/repaired-01/RESULT.json').read_bytes())
assert q['cases']==205 and q['mismatches']==0
p=json.loads((M/'runner-entrypoint-01/RESULT.json').read_bytes());assert p['cases']==8 and p['mismatches']==0
current_runner=W/'competition/deepeye/tools/stream/run_encoded_frame_queue.py'
assert sha(current_runner.read_bytes())==q['source_sha256']
record=dict(at_utc=datetime.now(timezone.utc).isoformat(),author_all_files_rehashed=len(manifest['author_files']),
            author_final_artifacts_rehashed=len(art['artifacts']),accepted_runs=runs,accepted_actual_main_commands=40,
            final_rtl_sha256=base,final_author_runner_sha256=q['source_sha256'],
            final_main_checker_sha256=sha(Path(checker.__file__).read_bytes()),final_main_tb_sha256=sha(now_tb),
            main_functional_top_prefix_sha256=sha(functional_prefix),runner_qualification_cases=205,python_entrypoint_processes=8,
            diagnostics_reclassification='Current stricter checker re-read unchanged non-guard raw logs; not new vendor runs.',
            original_main_guard_runs='guard*-01 retain39missing-port warnings and are superseded by guard*-02',
            all29_G05_B06_R03_board_system='not_run')
output.write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='accepted_runs'}))
