"""Produce repair candidate in main-owned evidence only; never edits author path."""
import argparse,ast,hashlib,json
from pathlib import Path
R=Path('D:/pynq/CarlandFPGA');W=R/'.local/worktrees/deepeye-implementation-20261014';M=W/'competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main'
p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args();src=Path(a.source);out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
b=src.read_bytes();text=b.decode();lines=text.splitlines(keepends=True);patch=(M/'strict_runner_classifiers.py').read_text();pl=patch.splitlines(keepends=True)
new={n.name:''.join(pl[n.lineno-1:n.end_lineno])+'\n' for n in ast.parse(patch).body if isinstance(n,ast.FunctionDef)}
old=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)]
existing={n.name for n in old};replacements=[n for n in old if n.name in new]
assert len(replacements)==5
for n in sorted(replacements,key=lambda x:x.lineno,reverse=True):lines[n.lineno-1:n.end_lineno]=[new[n.name]]
fixed=''.join(new[n]+'\n' for n in new if n not in existing)+''.join(lines)
# Future imports must remain immediately after the module docstring.
prefix=''.join(new[n]+'\n' for n in new if n not in existing)
fixed=''.join(lines);pos=fixed.index('\ndef _case(');fixed=fixed[:pos]+'\n'+prefix+fixed[pos:]
ast.parse(fixed);(out/'run_sample_scan_capture.py').write_text(fixed,encoding='utf-8',newline='\n')
record={'source':str(src),'source_sha256':hashlib.sha256(b).hexdigest(),'helper_sha256':hashlib.sha256((M/'strict_runner_classifiers.py').read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((out/'run_sample_scan_capture.py').read_bytes()).hexdigest(),'replaced_functions':[n.name for n in replacements],'scope':'main-owned candidate only, no product takeover'}
with (out/'COMPOSE.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2);f.write('\n')
print(json.dumps(record))
