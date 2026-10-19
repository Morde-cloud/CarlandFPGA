from pathlib import Path
import ast,hashlib,json,datetime
W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014');E=W/'competition/deepeye/evidence/control3d/pwm-edge-measure-20261020-13/main'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=E/'frozen-oracle/runner.py';new=E/'frozen-harness-03/runner.py'
def defs(p):return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(p.read_bytes()).body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
a=defs(old);b=defs(new)
for name in ['Reference','stimuli','vector_bytes']:assert a[name]==b[name]
vectors=[]
for p in (E/'frozen-oracle').glob('*.vectors.txt'):
 q=E/'frozen-harness-03'/p.name;assert p.read_bytes()==q.read_bytes();vectors.append({'file':p.name,'sha256':sha(p)})
assert len(vectors)==5
r={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_reference_frozen_before_author_read':True,'original_freeze_sha256':sha(E/'oracle_frozen.json'),'first_author_read_tool_chunk':'9ddf97','first_author_read_occurred_after_original_freeze_and_before_harness02':True,'final_harness_freeze_sha256':sha(E/'frozen-harness-03/result.json'),'reference_and_stimulus_AST_identical':True,'five_replay_vector_files_byte_identical':vectors,'findings':[{'id':'MAIN13-HARNESS01','original':'run-01/result.json reported passed despite TAG_W0 failing elaboration before explicit DUT guard','decision':'Reject its invalid-parameter conclusion; positive public-port results remain historical evidence only. Final acceptance requires the tightened harness and exact final RTL.'},{'id':'MAIN13-HARNESS02','original':'main TB part-select [-1:0] prevented invalid TAG_W0 diagnostic','repair':'Compare unsigned public outputs to full64 expected tokens; supported widths unchanged, no invalid part-select.'},{'id':'MAIN13-PROVENANCE01','original':'frozen-harness-02/result.json mechanically copied author_implementation_read=false after source had been read','decision':'That boolean is incorrect and explicitly superseded here; all original bytes preserved. Final runner no longer guesses human-read provenance. Original pre-author-read oracle_frozen.json remains valid.'},{'id':'DUT13-PARAM01','observed_source_sha256':json.loads((E/'run-01/result.json').read_bytes())['rtl_sha256'],'original':'TAG_ZERO uses zero replication when TAG_W0, causing elaboration failure before explicit unsupported-parameter diagnostic','status':'pending author terminal; no main write to active worker ownership'}],'other_RTL_findings':'Initial source review sees expected priorities and unsigned bounded increments; no functional acceptance before exact final bytes.'}
with (E/'HARNESS_CORRECTION.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2)
print(json.dumps(r))
