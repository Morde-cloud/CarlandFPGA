from pathlib import Path
import datetime,hashlib,json,subprocess,sys
D=Path(__file__).resolve().parents[1];R=D.parents[1];P=R/'.local/deployment/node-b/main-handoff-20261029/successor-01/successor-work/resume-89/product-service284'
O=Path(__file__).parent/'evidence284';O.mkdir()
names=['product_uart_service.py','PRODUCT_UART_SERVICE.md','product_uart_tests284/test_product_uart_service.py']
def pins():return {n:hashlib.sha256((D/n).read_bytes()).hexdigest() for n in names}
before=pins();argv=[sys.executable,'-B','-X','utf8',str(D/'product_uart_tests284/test_product_uart_service.py')]
r=dict(task_id='DEEPEYE-IMPLEMENTATION-20261014',task_version=1,work_id='B-A134-PRODUCT-UART-SERVICE-20261104-284',job_id='child-ef3225caa24c451894cad0665675f551',native_agent_id='/root/product_uart_service284',argv=argv,started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_before=before,scope='Synthetic Root/MMIO/HWH only; no PYNQ/COM/SWD/SSH/network or original suite',requirements_ids=['H%02d'%i for i in range(1,16)],requirements_sha256='2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d')
(O/'RUN.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');(P/'SOURCE284.json').write_text(json.dumps(before,indent=2)+'\n',encoding='utf8')
with (O/'stdout.txt').open('xb') as out,(O/'stderr.txt').open('xb') as err:
 process=subprocess.Popen(argv,stdout=out,stderr=err);r['pid']=process.pid;code=process.wait()
r.update(exit_code=code,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_after=pins(),stdout_sha256=hashlib.sha256((O/'stdout.txt').read_bytes()).hexdigest(),stderr_sha256=hashlib.sha256((O/'stderr.txt').read_bytes()).hexdigest());(O/'RUN.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');assert r['source_after']==before
result=dict(status='PASS_FOCUSED_SYNTHETIC_MECHANISMS' if code==0 else 'FAILED_FOCUSED_SYNTHETIC_MECHANISMS',exit_code=code,source_unchanged=True,hardware=False,formal=False);(O/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(json.dumps(dict(result=result,pins=before)));raise SystemExit(code)
