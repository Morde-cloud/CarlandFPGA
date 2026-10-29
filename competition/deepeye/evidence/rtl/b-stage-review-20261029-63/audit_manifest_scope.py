"""Main's byte/identity/scope audit of existing tracked manifests, no reruns."""
from pathlib import Path
import hashlib, json, subprocess, datetime

HERE=Path(__file__).parent
ROOT=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args])
head=git('rev-parse','HEAD').decode().strip()
assert head=='056844e02e49f5047edb2151a838947dd8cdf409'
rows=[]
for path in git('ls-files','handoffs/b/*/manifest.json').decode().splitlines():
    blob=git('show',head+':'+path)
    obj=json.loads(blob); req=obj['request']
    rh=hashlib.sha256(json.dumps(req,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    utf8_rh=hashlib.sha256(json.dumps(req,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert req['task_id']=='DEEPEYE-IMPLEMENTATION-20261014' and req['task_version']==1
    subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',req['code_commit'],head],check=True)
    roots={k:v['status'] for k,v in obj['stages'].items() if k in ('B01','B02','B03','B04','B05','B06','G01','G05','formal_cards','fullH12')}
    assert all(v!='passed' for v in roots.values()),(path,roots)
    rows.append({'path':path,'manifest_sha256':hashlib.sha256(blob).hexdigest(),'code_commit':req['code_commit'],'declared_request_hash':obj['request_hash'],'standard_request_hash':rh,'standard_request_hash_matches':rh==obj['request_hash'],'utf8_literal_request_hash':utf8_rh,'root_stages':roots,'passed_scoped_stages':[k for k,v in obj['stages'].items() if v['status']=='passed'],'failed_stages':[k for k,v in obj['stages'].items() if v['status']=='failed'],'expected_result':req['expected_result']})
record={'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,'work_id':'B-SUCCESSOR-INDEPENDENT-REVIEW-20261029-63-v1','reviewer_thread':'01a18824-4172-74e2-a13f-f3e3d1e3ed99','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':head,'manifest_count':len(rows),'checks':'Exact tracked manifest bytes; canonical request hash; task identity; code_commit ancestry; no root-card passed stage','limits':'Does not re-execute tests or rehash every historical raw archive; no board/product acceptance. Prior exact source62 remote readback retained.','manifests':rows}
record['standard_hash_mismatches']=[r['path'] for r in rows if not r['standard_request_hash_matches']]
record['initial_audit_failure']='First read-only audit correctly stopped at source62 hash mismatch; evidence retained in HASH_ERRATUM_FINDING.json. Updated inventory enumerates rather than hides mismatches.'
(HERE/'MAIN_MANIFEST_SCOPE_AUDIT.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({k:v for k,v in record.items() if k!='manifests'},ensure_ascii=False))
