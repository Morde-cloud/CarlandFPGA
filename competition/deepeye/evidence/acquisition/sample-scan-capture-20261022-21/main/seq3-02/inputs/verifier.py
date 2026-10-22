"""Actual ModelSim commands and independent frozen event-ledger port checks."""
import argparse,gzip,hashlib,json,re,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
EP='competition/deepeye/evidence/acquisition/sample-scan-capture-20261022-21/main'
RTL='competition/deepeye/fpga/acquisition/deepeye_sample_scan_capture.sv'
TB='competition/deepeye/tests/rtl/acquisition/main_tb_sample_scan_capture.sv'
FREEZE_SHA='739dc0dc264c66901eeacc437d9e6c6bccfb88b106e0f4cec77810f7f613b460'
sha=lambda b:hashlib.sha256(b).hexdigest()
now=lambda:datetime.now(timezone.utc).isoformat()
def save(p,obj):
    with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(obj,f,indent=2);f.write('\n')
def diagnostics(text,own=None):
    failures=[];fatal_count=0;positive=0
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('# '):line=line[2:]
        if own and line=='** Fatal: '+own:fatal_count+=1;continue
        tally=re.fullmatch(r'Errors: (0|[1-9][0-9]*), Warnings: (0|[1-9][0-9]*)',line,flags=re.ASCII)
        if tally:
            e,w=map(int,tally.groups())
            if w:failures.append('nonzero warnings')
            if not own and e:failures.append('nonzero errors')
            if own and ((not fatal_count and e) or (fatal_count and (e!=1 or positive))):failures.append('inconsistent own-fatal tally')
            if e:positive+=1
        elif re.search(r'\b(?:error|errors|fatal|warning|warnings)\b',line,flags=re.I|re.ASCII):failures.append('foreign/malformed diagnostic: '+line)
    if own and fatal_count!=1:failures.append('own fatal not unique')
    return failures
def classify(exit_code,timed,text,own=None):
    reasons=diagnostics(text,own)
    if exit_code!=0:reasons.append('process exit !=0')
    if timed:reasons.append('process timeout')
    if own and ('MAIN_GUARD_MISSING' in text or 'MAIN_SAMPLE_SCAN_DONE' in text):reasons.append('guard reached normal path')
    return reasons
def command(out,name,argv,timeout=180,own=None):
    argv=list(map(str,argv));intent={'argv':argv,'cwd':str(out),'started':now()};save(out/(name+'.intent.json'),intent)
    t=time.monotonic();p=subprocess.Popen(argv,cwd=out,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=0x08000000)
    timed=False
    try:stdout,stderr=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:timed=True;p.kill();stdout,stderr=p.communicate()
    (out/(name+'.stdout.txt')).write_bytes(stdout);(out/(name+'.stderr.txt')).write_bytes(stderr)
    text=(stdout+b'\n'+stderr).decode('utf-8',errors='replace');bad=classify(p.returncode,timed,text,own)
    record=dict(**intent,ended=now(),pid=p.pid,exit_code=p.returncode,timed_out=timed,elapsed_seconds=time.monotonic()-t,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),classification=bad)
    save(out/(name+'.command.json'),record)
    if bad:raise RuntimeError((name,bad))
    return text
def marker(text,params,edges):
    pat=r'MAIN_SAMPLE_SCAN_DONE edges=(0|[1-9][0-9]*) SEQ_W=([0-9]+) TICK_W=([0-9]+) TAG_W=([0-9]+) STAT_W=([0-9]+)'
    found=[]
    for raw in text.splitlines():
        s=raw.strip();s=s[2:] if s.startswith('# ') else s
        if 'MAIN_SAMPLE_SCAN_DONE' in s:
            m=re.fullmatch(pat,s,flags=re.ASCII)
            if not m:return False
            found.append(tuple(map(int,m.groups())))
    return found==[(edges,params['seq'],params['tick'],params['tag'],params['stat'])]
def compare(trace,vectors,expected,fields):
    rows=vectors.decode('ascii').splitlines();exp=json.loads(gzip.decompress(expected));assert len(rows)==len(exp)
    mismatches=0;examples=[];unknowns=0;public_conservation=0
    with trace.open(encoding='ascii') as f:
        for i,(inp,want) in enumerate(zip(rows,exp)):
            line=f.readline();parts=line.split()
            if len(parts)!=52 or parts[:2]!=['S',str(i)]:raise ValueError(('trace shape',i,line[:150]))
            if [int(x,16) for x in parts[2:12]]!=[int(x,16) for x in inp.split()]:raise ValueError(('stimulus mismatch',i))
            for phase,actual in enumerate([parts[12:32],parts[32:52]]):
                for k,(token,w) in enumerate(zip(actual,want[phase])):
                    if phase==0 and i==0 and k!=0:continue
                    if 1<=k<=6 and not want[phase][0]:continue
                    try:g=int(token,16)
                    except ValueError:g=None;unknowns+=1
                    if g!=w:
                        mismatches+=1
                        if len(examples)<32:examples.append({'edge':i,'phase':'pre' if phase==0 else 'post','field':fields[k],'expected':w,'actual':g,'token':token,'input':inp})
            # Expected ledger checks exact conservation on every edge; additionally
            # verify public counters in the unsaturated, nonabort visible window.
            row=[int(x,16) for x in inp.split()]
            if not any(row[:3]):
                a=parts[32:52]
                try:g=[int(x,16) for x in a]
                except ValueError:continue
                # No hierarchy, only public port values. Width saturation is checked
                # in frozen counter vectors; inequality filtering avoids assuming a width.
                w=want[1]
                if w[14]==4*(w[16]+w[0])+w[8]+w[17] and w[15]==w[16]+w[0]+w[19]:
                    public_conservation+=1
                    if g[14]!=4*(g[16]+g[0])+g[8]+g[17] or g[15]!=g[16]+g[0]+g[19]:
                        mismatches+=1
                        if len(examples)<32:examples.append({'edge':i,'field':'conservation','expected':w,'actual':g})
        if f.read().strip():raise ValueError('extra trace rows')
    return dict(edges=len(rows),mismatches=mismatches,unknowns=unknowns,numeric_examples=[x for x in examples if x.get('actual') is not None],examples=examples,public_conservation_edges=public_conservation)
def run(a):
    root=Path(a.root).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=False)
    snap=out/'inputs';snap.mkdir();base=root/EP;frozen=base/'frozen-inputs'
    freeze_raw=(frozen/'FREEZE.json').read_bytes();assert sha(freeze_raw)==FREEZE_SHA
    freeze=json.loads(freeze_raw);assert sha((base/'freeze21.py').read_bytes())==freeze['model_sha256']
    dut=Path(a.dut).resolve() if a.dut else root/RTL
    sources={'deepeye_sample_scan_capture.sv':dut,'main_tb_sample_scan_capture.sv':root/TB,'verifier.py':Path(__file__),'freeze21.py':base/'freeze21.py','FREEZE.json':frozen/'FREEZE.json'}
    source_receipt={}
    for name,path in sources.items():
        b=path.read_bytes();(snap/name).write_bytes(b);source_receipt[name]={'source':str(path),'sha256':sha(b)}
    save(out/'INPUTS.json',source_receipt)
    guard=a.case.startswith('guard-');params={'seq':32,'tick':64,'tag':64,'stat':32};own=None
    if guard:
        _,param,value=a.case.split('-');assert param in ['SEQ_W','TICK_W','TAG_W','STAT_W'];params[{'SEQ_W':'seq','TICK_W':'tick','TAG_W':'tag','STAT_W':'stat'}[param]]=int(value)
        own=freeze['fatal_contract'][param]
    else:
        meta=freeze['cases'][a.case];params=meta['params'];v=(frozen/a.case/'vectors.hex').read_bytes();e=(frozen/a.case/'expected.json.gz').read_bytes()
        assert sha(v)==meta['vectors_sha256'] and sha(e)==meta['expected_sha256']
        (snap/'vectors.hex').write_bytes(v);(snap/'expected.json.gz').write_bytes(e)
    result={'status':'RUNNING','case':a.case,'params':params,'source_sha256':source_receipt['deepeye_sample_scan_capture.sv']['sha256']}
    try:
        tools=Path(a.modelsim)
        command(out,'version',[tools/'vsim.exe','-version'],30)
        command(out,'vlib',[tools/'vlib.exe','lib'],30)
        command(out,'vlog',[tools/'vlog.exe','-sv','-work','lib',snap/'deepeye_sample_scan_capture.sv',snap/'main_tb_sample_scan_capture.sv'],90)
        argv=[tools/'vsim.exe','-c','-work','lib','-l',out/'sim.transcript.txt','-wlf',out/'sim.wlf','-do','run -all; quit -f']
        argv += ['-g'+key+'='+str(params[name]) for key,name in [('SEQ_W','seq'),('TICK_W','tick'),('TAG_W','tag'),('STAT_W','stat')]]
        argv += ['main_guard_sample_scan_capture' if guard else 'main_tb_sample_scan_capture']
        if not guard:argv+=['+INPUT='+str(snap/'vectors.hex'),'+TRACE='+str(out/'trace.txt')]
        text=command(out,'vsim',argv,240,own)
        transcript=(out/'sim.transcript.txt').read_text(encoding='utf-8',errors='replace')
        if diagnostics(transcript,own):raise RuntimeError(('transcript',diagnostics(transcript,own)))
        if guard:result.update(status='PASS',own_fatal=own)
        else:
            assert marker(text,params,meta['edges']),'missing/duplicate/conflicting completion'
            assert marker(transcript,params,meta['edges']),'transcript completion differs'
            checked=compare(out/'trace.txt',v,e,freeze['fields']);result.update(checked)
            raw=(out/'trace.txt').read_bytes();compressed=gzip.compress(raw,mtime=0);(out/'trace.txt.gz').write_bytes(compressed)
            result.update(trace_sha256=sha(raw),trace_bytes=len(raw),trace_gzip_sha256=sha(compressed))
            if a.expect_mismatch:
                assert checked['mismatches'] and checked['numeric_examples'] and checked['unknowns']==0,'no clean numeric public-port mutant counterexample'
                result['status']='EXPECTED_BEHAVIORAL_REJECTION'
            else:
                assert checked['mismatches']==0,checked['examples'];result['status']='PASS'
    except Exception as exc:result.update(status='FAILED',error=repr(exc));raise
    finally:
        result['ended']=now();save(out/'RESULT.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['examples','numeric_examples']}),flush=True)
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);p.add_argument('--case',required=True);p.add_argument('--dut');p.add_argument('--expect-mismatch',action='store_true');p.add_argument('--modelsim',default='D:/modelsim1/win64');run(p.parse_args())
if __name__=='__main__':main()
