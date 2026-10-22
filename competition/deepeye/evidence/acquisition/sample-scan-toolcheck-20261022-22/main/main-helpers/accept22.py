"""Main exact-byte/evidence review after author terminal and independent execution."""
import hashlib,json,re,shutil
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014');E=W/'competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22';M=E/'main';A=E/'author'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def put(p,x):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
terminal=json.loads(load(O/'AUTHOR_TERMINAL.json')['content'][0]['text'])[0]
assert terminal['status']=='completed' and terminal['terminal'] and not terminal['stale']
assert not json.loads(load(O/'AUTHOR_RECLAIM.json')['content'][0]['text'])['instances']
source=W/'competition/deepeye/tools/acquisition/run_sample_scan_capture.py';test=W/'competition/deepeye/tests/acquisition/test_sample_scan_toolcheck.py';sourcehash=sha(source)
assert sourcehash=='a47dcfb493316f23578d4b10e8d832e3bc48512377e4df07c54f27ec11081547';assert sha(test)=='47e3b5031a080e6fd6fc6d31d3390940166394c4a5b3a3cc9ac348f9518b87bc'
audit=load(O/'POST_AUTHOR_BYTE_AUDIT.json');assert not audit['unexpected_new_untracked'] and len(audit['changes'])==1 and audit['changes'][0]['path']=='competition/deepeye/tools/acquisition/run_sample_scan_capture.py'
assert sha(A/'MANIFEST.json')=='038741cc695450eab3938fc4a637b556476ced9902a195c08a7b3ed9c719d009'
manifest=load(A/'MANIFEST.json');authorfiles=[]
for row in manifest['author_evidence_files']:
    p=W/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path'];authorfiles.append(row)
freeze=load(M/'FREEZE.json');dispatch=json.loads(load(O/'author-dispatch-actual.json')['result']['content'][0]['text'])
assert freeze['at_utc']<dispatch['created_at']
for rel,h in freeze['files'].items():assert sha(M/rel)==h,rel
matrix=load(M/'LITERAL_MATRIX.json')['cases'];direct=load(M/'final-direct-01/RESULT.json');entry=load(M/'final-entry-01/RESULT.json');reg=load(M/'regression-01/RESULT.json')
assert direct['source_sha256']==entry['source_sha256']==reg['source_sha256']==sourcehash
assert direct['cases']==entry['processes']==136 and not direct['mismatches'] and not direct['unhandled'] and not entry['mismatches']
assert reg['cases']==43 and not reg['mismatches'] and reg['changed_functions']==['_tool_version'] and len(reg['unchanged_functions'])==27 and not reg['new_global_nodes']
assert reg['added_functions']==['_version_failure_reasons','_version_output_bytes']
invocations=[]
for folder in ['final-direct-01','final-entry-01']:
    for f in (M/folder).rglob('*.invocation.json'):
        row=load(f)
        for stream in ['stdout','stderr']:assert sha(f.parent/row[stream+'_path'])==row[stream+'_sha256']
        invocations.append({'path':f.relative_to(M).as_posix(),'sha256':sha(f)})
assert len(invocations)==640
for row in matrix:
    for folder,suffix in [('final-direct-01','tool-check'),('final-entry-01','results/tool-check')]:
        d=M/folder/row['id']/suffix
        for tool in ['vlog','vsim']:
            meta=load(d/(tool+'.invocation.json'));out=(d/(tool+'.stdout.bin')).read_bytes();err=(d/(tool+'.stderr.bin')).read_bytes()
            if tool==row['tool']:
                kind=row['exception']
                expectedout=b'' if kind in ['OSError','FileNotFoundError'] else row['stdout'].encode();expectederr=b'' if kind in ['OSError','FileNotFoundError'] else row['stderr'].encode()
                assert out==expectedout and err==expectederr
                if kind:assert meta['exception_type']==kind and meta['exception_message'] and meta['exit'] is None
                else:assert meta['exit']==row['exit']
                assert meta['timed_out']==(row['timed_out'] or kind=='TimeoutExpired')
            else:assert out==(M/'real-version-01'/(tool+'.stdout.bin')).read_bytes() and err==b'' and meta['exit']==0
for row in entry['records']:
    d=M/'final-entry-01';name=row['id']
    assert sha(d/(name+'.stdout.bin'))==row['stdout_sha256'] and sha(d/(name+'.stderr.bin'))==row['stderr_sha256']
    assert row['case_calls']==row['expected_case_calls']
for kind in ['direct','entries','regression','unit']:
    d=M/'main-processes';row=load(d/(kind+'.process.json'));assert row['exit']==0 and row['source_unchanged'] and row['test_unchanged'] and row['source_sha256']==sourcehash
    for stream in ['stdout','stderr']:assert sha(d/(kind+'.'+stream+'.bin'))==row[stream+'_sha256']
unittext=(M/'main-processes/unit.stderr.bin').read_text();assert re.search(r'Ran 29 tests',unittext) and unittext.strip().endswith('OK')
assert not list((M/'main-unit-temp').iterdir())
actual=[]
for tool in ['vlog','vsim']:
    d=M/'real-version-01';row=load(d/(tool+'.process.json'));assert row['exit']==0 and row['argv'][1:]==['-version']
    for stream in ['stdout','stderr']:assert sha(d/(tool+'.'+stream+'.bin'))==row[stream+'_sha256']
    actual.append(row)
old=load(M/'original-direct-01/RESULT.json');olde=load(M/'original-entry-01/RESULT.json');assert len(old['mismatches'])==108 and len(old['unhandled'])==6 and len(olde['mismatches'])==114
put(M/'RAW_EVIDENCE_REVIEW.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'persisted_invocations':invocations,'exact_stream_and_exception_matrix_checks':544,'author_manifest_rehashed_files':len(authorfiles),'main_processes':4,'entry_processes':136,'only_actual_vendor_commands':actual,'frozen_before_dispatch':True,'historical_author_temp_limit':'Author units use tempfile defaults; original temp paths were not recorded. Main cannot certify historical temp locality. Main fresh unit run explicitly sets TMP/TEMP/TMPDIR inside owned main-unit-temp; directory is empty afterwards.'})
put(M/'AUTHOR_COMPLETION_RECEIPT.json',{'job_id':terminal['job_id'],'status':terminal['status'],'terminal':True,'stale':False,'updated_at':terminal['updated_at'],'thread':terminal['result']['thread_id'],'turn':terminal['result']['turn']['id'],'model':terminal['result']['model'],'provider':terminal['result']['provider'],'effort':terminal['result']['reasoning_effort'],'main_takeover':False,'source_and_test_remain_author_bytes':True})
helpers=M/'main-helpers';helpers.mkdir()
for name in ['freeze22.py','regression22.py','run_stage22.py','audit22.py','accept22.py','prepare_pack22.py']:(helpers/name).write_bytes((O/name).read_bytes())
(M/'PREPARATION_NOTES.json').write_bytes((O/'PREPARATION_NOTES.json').read_bytes())
(M/'accept-attempt01-failure.txt').write_bytes((O/'accept-attempt01-failure.txt').read_bytes())
consumed=load(O/'CONSUMED.json')
accept={'at_utc':datetime.now(timezone.utc).isoformat(),'decision':'ACCEPT_BOUNDED_TOOLCHECK_REPAIR_PENDING_COORDINATOR','task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'operation_id':consumed['product_operation'],'director_thread':consumed['actual_thread'],'director_turn':consumed['actual_turn'],'contract':consumed['contract'],'runner_sha256':sourcehash,'test_sha256':sha(test),'original_runner_sha256':old['source_sha256'],'freeze_sha256':sha(M/'FREEZE.json'),'author_dispatch_at':dispatch['created_at'],'direct_query_cases':136,'positive_cases':12,'negative_cases':124,'direct_mismatches':0,'actual_python_entry_processes':136,'entry_mismatches':0,'negative_case_compile_sim_calls':0,'positive_case_compile_sim_calls':96,'case_calls_are_synthetic':True,'coordinator_literal_classification_cases_reused_and_rerun':43,'unchanged_existing_functions':27,'new_author_units_main_rerun':29,'actual_vendor_version_queries':2,'actual_vendor_compile_sim_calls':0,'old_direct_false_accepts':108,'old_unhandled_exceptions':6,'old_entry_expectation_failures':114,'source_review':'Complete narrow parser, both streams, optional unique zero tally, exactly one matching banner; catches real launch OSError and timeout preserving evidence; main failure branch unchanged and verified. No unrelated function/global AST changes.','raw_review_sha256':sha(M/'RAW_EVIDENCE_REVIEW.json'),'author_manifest_sha256':sha(A/'MANIFEST.json'),'temporary_write_limit':'Historical author default tempfile paths unrecorded; no blanket no-outside-write claim. Main rerun uses explicit owned temp root.','not_run':consumed['not_run']+['simulation','coordinator_independent_review'],'hardware_enable_eligible':False,'board_operator':'A','op21_previous_decision':'REVISE retained; old RTL observations unchanged'}
put(M/'ACCEPTANCE.json',accept)
overview='''# Operation22 tool-version preflight repair

OP21-TOOLCHECK-ERROR01 is repaired only in the version preflight. An exit0 plus a10.7 substring no longer suffices: the parser requires exactly one complete tool/role/release banner, accepts the real CRLF/LF form without requiring a compile summary, rejects either-stream diagnostics/conflicts, and preserves startup exceptions and timeout bytes. The unchanged main branch returns nonzero before any case compile/simulation on failure.

Main froze136literal query expectations before dispatch (12positive/124negative). Old-source direct probes retained108unsafe accepts and6unhandled exceptions. The corresponding136actual Python entry processes retained114failed expectations. The final author runner a47dcfb493316f23578d4b10e8d832e3bc48512377e4df07c54f27ec11081547 passes the same136direct checks and136fresh actual Python entry processes. All124badpreflight entries make zero case calls. Twelve healthy entries each exercise normal, invalid guard, healthy guard and numeric-mutant selected controls. Every such vendor call uses explicitly synthetic saved logs; these are NOT new RTL runs.

Main freshly reran43previously frozen coordinator classification controls and29author tests.27existing functions and all old global AST nodes are unchanged; only _tool_version changes and two narrow helpers are added. Main independently checked640persisted invocation records and exact original stream bytes/exception metadata across the direct and actual-entry matrices. Author original failures and original op21 coordinator red fixtures remain intact.

Only2actualvendor queries ran: vlog -version and vsim -version, with saved process/binary hashes and real stdout. No vendor compile/simulation, synthesis, implementation or board run occurred. Author tested via defaults in tempfile; historical temp locations were not recorded, so no blanket historical no-outside-write claim is made. Main29test rerun explicitly sets TMP/TEMP/TMPDIR inside main-unit-temp and verifies it is empty after cleanup. Author report remains original, including its broader write claim, which this main limitation qualifies.

Raw per-case directories and author attempts are retained locally and published as lossless tar/gzip bundles under main/bundles, with per-member hash indexes and BUNDLE_MANIFEST.json. No raw member is omitted. Archive readback verified all member bytes without extraction. The standard handoff binds bundles, indexes, helper sources and final runner/test source. To reproduce, unpack into a new isolated evidence directory preserving the paths relative to this operation's evidence root, and invoke probe22.py direct/entries with explicit --source, --root and a fresh --out. All vendor calls in probe22.py are intercepted; never run old op21 vendor suites for this repair. Unit discovery: python -B -X utf8 -m unittest discover -s competition/deepeye/tests/acquisition -p test_sample_scan_toolcheck.py -v, with TMP/TEMP/TMPDIR set to a fresh owned directory.

Only the released runner changes among12466old tracked paths; every other old raw file and protected codec input is preserved. Original op21 remains REVISE at cd007dc8190b7c2d911d2be6c1136aabab3518e5. This bounded main acceptance does not pre-empt independent coordinator review. No next increment is started.

H01-H15 DEEPEYE-HUMAN-LOCK-20261014/revision1, canonical requirementsSHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804, contractpinf5989cd5defce561f9ba98e6b18fc2682945f0a2/design1011259415a0916054eb580687612580bc1e5f09 remain unchanged. Full3D/UI, hollow cube, solid collisions, free camera/editing/entry-exit faces, equal gates/full passage, hidden truth, device causal observations, substantive online3D PC AI and both H12 control paths remain mandatory. All29/B02/G05/B06/R03/fullproduct/simulation/synthesis/implementation/timing/CDC_RDC/board/system remain not_run; physical board A-only. No public ABI/ADC/rate/clock/BOOT/freshness/ENABLE/motion authority.
'''
with (M/'OVERVIEW.md').open('x',encoding='utf-8',newline='\n') as f:f.write(overview)
print(json.dumps({'decision':accept['decision'],'acceptance_sha256':sha(M/'ACCEPTANCE.json'),'author_files_rehashed':len(authorfiles),'persisted_invocations':len(invocations),'runner':sourcehash}))
