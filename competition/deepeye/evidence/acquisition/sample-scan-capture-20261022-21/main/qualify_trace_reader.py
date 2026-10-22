"""Literal trace reader faults; synthetic only, never counted as RTL runs."""
import copy,gzip,hashlib,importlib.util,json
from pathlib import Path
M=Path(__file__).parent;W=M.parents[5];S=W/'competition/deepeye/tools/acquisition/main_verify_sample_scan_capture.py'
spec=importlib.util.spec_from_file_location('trace_qualification21',S);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
D=M/'trace-reader-qualification';D.mkdir(exist_ok=False)
fields=json.loads((M/'frozen-inputs/FREEZE.json').read_bytes())['fields']
zero=[0]*20;armed=zero.copy();armed[7]=1
orphan=armed.copy()
for i in [9,11,14,17,18]:orphan[i]=1
inputs=[[1,0,0,0,0,0,0,0,0,0],[0,0,1,1,0,0,0,0,0,0],[0,0,0,0,1,1,7,3,5,0]]
expected=[[zero,zero],[zero,armed],[armed,orphan]]
vectors=(''.join(' '.join(format(x,'x') for x in a)+'\n' for a in inputs)).encode()
compressed=gzip.compress(json.dumps(expected).encode(),mtime=0)
base=[['S',str(i),*[format(x,'x') for x in inputs[i]],*[format(x,'x') for x in expected[i][0]],*[format(x,'x') for x in expected[i][1]]] for i in range(3)]
cases=[]
def execute(name,rows,accept,ending='\n'):
    p=D/(name+'.txt');p.write_bytes(('\n'.join(' '.join(row) for row in rows)+ending).encode('ascii'))
    try:
        r=v.compare(p,vectors,compressed,fields);passed=r['mismatches']==0;desc=r
    except (ValueError,AssertionError) as e:passed=False;desc={'exception':repr(e)}
    assert passed==accept,(name,desc)
    cases.append({'name':name,'expected_acceptance':accept,'accepted':passed,'result':desc,'trace_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
execute('literal-three-edges',base,True)
execute('missing-last-row',base[:-1],False)
execute('extra-row',base+[base[-1]],False)
for name,row,index,val in [('wrong-prefix',1,0,'X'),('duplicate-index',2,1,'1'),('wrong-input',2,2,'1'),('unknown-input',2,7,'x'),('unknown-control',2,32+7,'x'),('wrong-ordinal',2,32+9,'0'),('lost-not-counted',2,32+17,'0'),('dropped-fault-pulse',2,32+11,'0'),('wrong-pre-armed',2,12+7,'0'),('pre-reset-valid',0,12,'1')]:
    c=copy.deepcopy(base);c[row][index]=val;execute(name,c,False)
c=copy.deepcopy(base);c[1][13]='xxxx';c[2][33]='ffff';execute('inactive-payload-dontcare',c,True)
c=copy.deepcopy(base);c[2].append('0');execute('extra-column',c,False)
c=copy.deepcopy(base);c[2].pop();execute('missing-column',c,False)
execute('crlf-reader',base,True,ending='\r\n')
(D/'expected.json.gz').write_bytes(compressed);(D/'vectors.hex').write_bytes(vectors)
with (D/'RESULT.json').open('x',encoding='utf-8') as f:json.dump({'runner_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'cases':cases,'scope':'17 synthetic reader controls, not vendor RTL evidence'},f,indent=2);f.write('\n')
print(json.dumps({'cases':len(cases),'positive':sum(x['accepted'] for x in cases),'negative':sum(not x['accepted'] for x in cases)}))
