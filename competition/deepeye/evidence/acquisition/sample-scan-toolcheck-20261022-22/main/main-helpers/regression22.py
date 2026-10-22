"""Narrow non-vendor regression and raw/AST scope audit."""
import argparse,ast,hashlib,importlib.util,json,sys
from pathlib import Path
from datetime import datetime,timezone
O=Path(__file__).parent;W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014');M=W/'competition/deepeye/evidence/acquisition/sample-scan-toolcheck-20261022-22/main'
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--name',required=True);a=p.parse_args();out=M/a.name;out.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
fixture=Path('D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/main-continuation-20261019-v1/sample-scan-capture-20261022-21/classifier-controls-01/FROZEN.json')
raw=fixture.read_bytes();(out/'COORDINATOR_CLASSIFIER_FIXTURES.json').write_bytes(raw)
spec=importlib.util.spec_from_file_location('regression_candidate22',a.source);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
cases=json.loads(raw)['cases'];rows=[]
for c in cases:
    try:
        result=getattr(mod,c['fn'])(*c['args'],**c['kwargs']);ok=result['ok'];err=None
    except Exception as exc:ok=False;result=None;err=repr(exc)
    rows.append({'id':c['id'],'expected_ok':c['expected_ok'],'actual_ok':ok,'agrees':ok is c['expected_ok'] and err is None,'error':err,'result':result})
old=(M/'inputs/original_runner.py').read_bytes();new=a.source.read_bytes();ot=ast.parse(old);nt=ast.parse(new)
of={n.name:n for n in ot.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))};nf={n.name:n for n in nt.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
unchanged=[];changed=[];missing=[]
oldlines=old.decode().splitlines();newlines=new.decode().splitlines()
for name,node in of.items():
    if name not in nf:missing.append(name);continue
    other=nf[name]
    if ast.dump(node,include_attributes=False)==ast.dump(other,include_attributes=False):
        assert oldlines[node.lineno-1:node.end_lineno]==newlines[other.lineno-1:other.end_lineno],name
        unchanged.append(name)
    else:changed.append(name)
oldglobals=[ast.dump(n,include_attributes=False) for n in ot.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
newglobals=[ast.dump(n,include_attributes=False) for n in nt.body if not isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
oldpreserved=all(n in newglobals for n in oldglobals)
result={'at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':sha(new),'original_source_sha256':sha(old),'fixture_sha256':sha(raw),'scope':'Fresh pure-function tests using previously frozen coordinator literals, not independent new stimulus or vendor execution','cases':len(rows),'mismatches':[r['id'] for r in rows if not r['agrees']],'rows':rows,'unchanged_functions':unchanged,'changed_functions':changed,'missing_functions':missing,'added_functions':sorted(set(nf)-set(of)),'original_global_nodes_preserved':oldpreserved,'new_global_nodes':[n for n in newglobals if n not in oldglobals]}
with (out/'RESULT.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','new_global_nodes']}))
assert not result['mismatches'] and not missing and changed==['_tool_version'] and oldpreserved
