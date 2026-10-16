"""Mutate captured external-port evidence to verify independent checker failures."""
import argparse,gzip,hashlib,importlib.util,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--review',type=Path,required=True);p.add_argument('--results',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
assert not a.output.exists()
s=importlib.util.spec_from_file_location('independent_main_ports',a.review);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
res=json.loads((a.results/'result.json').read_text());cases=[]
for case in res['results']:
    name=case['case'];raw=gzip.decompress((a.results/(name+'.ports.csv.gz')).read_bytes())
    assert hashlib.sha256(raw).hexdigest()==case['port_raw_sha256']
    lines=raw.decode().splitlines();rows=[x.split(',') for x in lines]
    vectors,_=m.generate(case['width'],*case['clock_half_steps'],case['phase'],case['seed'])
    candidates=[]
    idx=next(i for i,r in enumerate(rows) if r[15]=='1')
    candidates.append(('postvalid_corrupt_payload',idx,17,format(int(rows[idx][17],16)^1,'x')))
    idx=next(i for i,r in enumerate(rows) if r[10]=='1' and r[6]=='1' and r[2]=='1' and (i==0 or rows[i-1][2]=='0'))
    candidates.append(('consume_corrupt_payload',idx,12,format(int(rows[idx][12],16)^1,'x')))
    idx=next(i for i,r in enumerate(rows) if r[3:5]==['1','1'] and r[5]=='1' and r[9]=='0' and r[1]=='1' and (i==0 or rows[i-1][1]=='0'))
    candidates.append(('unarmed_accept',idx,8,'1'))
    idx=next(i for i,r in enumerate(rows) if r[3:5]==['0','1'])
    candidates.append(('asynchronous_flush_missing',idx,15,'1'))
    candidates.append(('unknown_port',50,13,'x'))
    for why,i,col,value in candidates:
        altered=[r[:] for r in rows];altered[i][col]=value
        bad=('\n'.join(','.join(r) for r in altered)+'\n').encode()
        try:m.review(vectors,bad,case['width'])
        except AssertionError as e:
            cases.append(dict(case=name,mutation=why,row=i,column=col,rejected=True,reason=str(e),mutant_sha256=hashlib.sha256(bad).hexdigest()))
        else:raise AssertionError((name,why,'checker failed negative control'))
a.output.write_text(json.dumps(dict(status='PASS',negative_controls=len(cases),cases=cases,
    scope='checker sensitivity against captured port mutations, not additional DUT runs'),indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','negative_controls':len(cases)}))
