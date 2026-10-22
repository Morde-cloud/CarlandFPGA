import argparse,hashlib,importlib.util,json
from pathlib import Path
def main():
    p=argparse.ArgumentParser();p.add_argument('--runner',required=True);p.add_argument('--out',required=True);a=p.parse_args();s=Path(a.runner);out=Path(a.out);out.mkdir(parents=True,exist_ok=False)
    b=s.read_bytes();snapshot=out/'runner_snapshot.py';snapshot.write_bytes(b)
    spec=importlib.util.spec_from_file_location('author21_qualification',snapshot);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    frozen=Path(__file__).parent/'runner-probes';meta=json.loads((frozen/'FREEZE.json').read_bytes());raw=(frozen/'cases.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==meta['cases_sha256']
    cases=json.loads(raw);results=[]
    for c in cases:
        try:r=getattr(m,c['function'])(*c['args']);ok=r.get('ok') is True
        except Exception as e:r={'exception':repr(e)};ok=False
        results.append({'name':c['name'],'expected_ok':c['expected_ok'],'actual_ok':ok,'agrees':ok==c['expected_ok'],'result':r})
    result={'runner_sha256':hashlib.sha256(b).hexdigest(),'cases':len(cases),'disagreements':sum(not r['agrees'] for r in results),'unsafe_accepts':sum(not r['agrees'] and r['actual_ok'] for r in results),'false_rejects':sum(not r['agrees'] and not r['actual_ok'] for r in results),'results':results,'scope':'synthetic pure classifiers, not vendor execution'}
    with (out/'RESULT.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='results'}))
if __name__=='__main__':main()
