import argparse,hashlib,json,random,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# Independent mathematical oracle: builds all complete finite bit strings,
# rather than importing the golden model, worker runner, or DUT implementation.
def expected(values,e):
    p=values[0];zs=[];recon=[p]
    for x in values[1:]:
        q,_=divmod(x-p+e,2*e+1)
        p=max(0,min(65535,p+q*(2*e+1)))
        assert abs(p-x)<=e
        zs.append(q*2 if q>=0 else -q*2-1);recon.append(p)
    options=[]
    for k in range(16):
        if any((z>>k)>31 for z in zs):continue
        text=''.join('0'*(z>>k)+'1'+(format(z&((1<<k)-1),'0%db'%k) if k else '') for z in zs)
        options.append((len(text),k,text))
    raw=''.join(format(x,'016b') for x in values[1:])
    best=min(options) if options else None
    israw=best is None or len(raw)<=best[0]
    k=0 if israw else best[1]
    text=format(values[0],'016b')+(raw if israw else best[2])
    padded=text+'0'*((-len(text))%8)
    data=bytes(int(padded[i:i+8],2) for i in range(0,len(padded),8))
    return {'error':0,'count':len(values),'e':e,'raw':int(israw),'k':k,'bits':len(text),'bytes':len(data),'payload_hex':data.hex(),'decoded':values if israw else recon}

def build_cases():
    cases=[]
    def add(values,e,**kw):
        c={'id':len(cases),'samples':values,'count':len(values),'e':e,'last_mode':0,'abort_stage':0,'abort_reset':0,'seed':len(cases)%97}
        c.update(kw);cases.append(c)
    manual=[([1234],0,'04d2',16,1,0),([100,98],1,'006440',18,0,0),([100,99],1,'006480',17,0,0),([0,65535],0,'0000ffff',32,1,0),([65535,0],0,'ffff0000',32,1,0),([42,42],8,'002a80',17,0,0)]
    for v,e,h,b,r,k in manual:
        out=expected(v,e);assert (out['payload_hex'],out['bits'],out['raw'],out['k'])==(h,b,r,k)
        add(v,e,manual=True)
    # Sparse steps force selected k and long unary runs, not merely arbitrary
    # random residuals that may switch to RAW or a larger k.
    for k in range(13):
        for quotient in [17,18,30,31]:
            z=quotient<<k
            anchor=65535 if z%2 else 0
            target=anchor-(z+1)//2 if z%2 else z//2
            values=[anchor]*64+[target]*64
            out=expected(values,0)
            assert not out['raw'] and out['k']==k
            add(values,0,forced_unary=quotient,forced_k=k)
    rng=random.Random(20261018)
    for e in [0,1,2,4,8]:
        for n in range(1,129):
            family=n%5
            if family==0:values=[rng.randrange(65536)]*n
            elif family==1:values=[i*23%65536 for i in range(n)]
            elif family==2:values=[65535 if i%2 else 0 for i in range(n)]
            elif family==3:values=[rng.randrange(65536) for _ in range(n)]
            else:values=[65535 if i==n//2 else 10 for i in range(n)]
            add(values,e)
        # Negative division, clipping and sign/zero boundaries.
        for p in [0,1,8,32767,65527,65534,65535]:
            for delta in [-65535,-18,-9,-5,-2,-1,0,1,2,5,9,18,65535]:
                x=max(0,min(65535,p+delta));add([p,x,p],e)
    for _ in range(300):
        n=rng.randrange(1,129);e=rng.choice([0,1,2,4,8]);p=rng.randrange(65536);v=[]
        for i in range(n):
            p=max(0,min(65535,p+rng.choice([-65535,-17,-9,-3,-1,0,1,3,9,17,65535])));v.append(p)
        add(v,e)
    for e in [3,5,6,7,9,10,11,12,13,14,15]:add([],e,count=128,error=1)
    for n in [0,129,130,254,255]:add([],0,count=n,error=1)
    for e in [0,1,2,4,8]:
        add([100,101,102],e,count=7,last_mode=1,error=2)
        add([300,299,298,297],e,last_mode=2,error=2)
    for reset in [0,1]:
        for stage in [1,2,3,4]:
            for e in [0,1,2,4,8]:
                add([65535 if i%3 else 0 for i in range(128)],e,abort_stage=stage,abort_reset=reset)
                add([123,98,65535,0,321],e,recovery=True)
    return cases

def verify(cases,path):
    by={c['id']:{'C':[],'S':[],'H':[],'O':[],'X':[],'D':[]} for c in cases}
    end=[]
    for line in Path(path).read_text().splitlines():
        tok=line.split();assert tok
        if tok[0]=='END':end.append([int(x) for x in tok[1:]]);continue
        typ=tok[0];ident=int(tok[1]);assert typ in by[ident]
        by[ident][typ].append([int(x) for x in tok[2:]])
    assert len(end)==1
    stats={'blocks':len(cases),'success':0,'errors':0,'aborted':0,'samples':0,'raw':0,'rice':0,'bytes':0,'recoveries':0,'all_n':set(),'all_e':set(),'all_k':set(),'max_latency_including_header_hold':0}
    for c in cases:
        ev=by[c['id']];assert len(ev['C'])==1 and len(ev['D'])==1,(c,ev)
        assert ev['C'][0][1:]==[c['count'],c['e']]
        accepted=c['samples'][:2] if c['abort_stage']==1 else c['samples']
        assert len(ev['S'])==len(accepted),(c['id'],'input count')
        for i,(s,x) in enumerate(zip(ev['S'],accepted)):
            last=int(i==c['count']-1)
            if c['last_mode']==1:last=int(i==len(c['samples'])-1)
            if c['last_mode']==2:last=0
            assert s[1:]==[i,x,last],(c['id'],'input port bytes')
        if c['abort_stage']:
            stats['aborted']+=1;assert len(ev['X'])==1
            assert ev['X'][0][1:]==[c['abort_stage'],c['abort_reset']]
            if c['abort_stage']<4:assert not ev['H'] and not ev['O']
            else:
                want=expected(c['samples'],c['e']);assert len(ev['H'])==1 and len(ev['O'])==1
                assert ev['H'][0][1:]==[want[k] for k in ['error','count','e','raw','k','bits','bytes']]
                assert ev['O'][0][1:]==[0,bytes.fromhex(want['payload_hex'])[0],0]
            continue
        assert not ev['X'] and len(ev['H'])==1
        if c.get('error'):
            stats['errors']+=1;assert ev['H'][0][1:]==[c['error'],0,0,1,0,0,0] and not ev['O'];continue
        want=expected(c['samples'],c['e'])
        assert ev['H'][0][1:]==[want[k] for k in ['error','count','e','raw','k','bits','bytes']],(c['id'],'metadata',ev['H'],want)
        data=bytes.fromhex(want['payload_hex']);assert len(ev['O'])==len(data)
        for i,(row,b) in enumerate(zip(ev['O'],data)):assert row[1:]==[i,b,int(i==len(data)-1)],(c['id'],'byte',i,row,b)
        assert ev['O'][0][0]>ev['H'][0][0]
        delta=ev['H'][0][0]-ev['S'][-1][0];assert delta<=20020
        stats['max_latency_including_header_hold']=max(stats['max_latency_including_header_hold'],delta)
        stats['success']+=1;stats['samples']+=len(c['samples']);stats['raw' if want['raw'] else 'rice']+=1;stats['bytes']+=len(data)
        stats['recoveries']+=int(c.get('recovery',False));stats['all_n'].add(c['count']);stats['all_e'].add(c['e'])
        if not want['raw']:stats['all_k'].add(want['k'])
    assert len(end[0])==7 and end[0][1]==len(cases)
    for col,kind in [(1,'C'),(2,'S'),(3,'H'),(4,'O'),(5,'X')]:
        assert end[0][col]==sum(len(ev[kind]) for ev in by.values()),('monitor counter',kind)
    assert end[0][0]==max(ev['D'][0][0] for ev in by.values())+5 and end[0][6]>0
    for k in ['all_n','all_e','all_k']:stats[k]=sorted(stats[k])
    stats['monitor_totals']=dict(zip(['cycles','configs','samples','headers','output_bytes','aborts','stability_checks'],end[0]))
    return stats

def run(argv,cwd,out,name,timeout=180):
    r=subprocess.run([str(x) for x in argv],cwd=cwd,capture_output=True,timeout=timeout)
    (out/(name+'.stdout.txt')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
    info={'argv':[str(x) for x in argv],'cwd':str(cwd),'exit_code':r.returncode,'stdout_sha256':sha(out/(name+'.stdout.txt')),'stderr_sha256':sha(out/(name+'.stderr.txt'))}
    (out/(name+'.command.json')).write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    assert r.returncode==0,(name,r.returncode,r.stdout[-2000:],r.stderr[-1000:]);return r

def main():
    p=argparse.ArgumentParser();p.add_argument('--rtl',required=True,type=Path);p.add_argument('--tb',required=True,type=Path);p.add_argument('--modelsim-home',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--check-log',type=Path)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    cases=build_cases();(out/'cases.json').write_text(json.dumps(cases,separators=(',',':'))+'\n',encoding='utf-8')
    if a.check_log:
        stats=verify(cases,a.check_log);print(json.dumps(stats));return
    (out/'cases.txt').write_text('\n'.join(' '.join(map(str,[c['id'],c['count'],c['e'],len(c['samples']),c['last_mode'],c['abort_stage'],c['abort_reset'],c['seed'],*c['samples']])) for c in cases)+'\n',encoding='ascii')
    bindir=a.modelsim_home/'win64'
    run([bindir/'vsim.exe','-version'],out,out,'version')
    run([bindir/'vlib.exe','work'],out,out,'vlib')
    run([bindir/'vlog.exe','-sv','-work','work',a.rtl.resolve(),a.tb.resolve()],out,out,'vlog')
    do='onerror {quit -code 8}\nonbreak {quit -code 7}\nvsim -voptargs=+acc work.main_encoder_port_tb {+INPUT='+str(out/'cases.txt').replace('\\','/')+'} {+OUTPUT='+str(out/'ports.txt').replace('\\','/')+'}\nrun -all\nquit -code 0\n'
    (out/'run.do').write_text(do,encoding='ascii')
    r=run([bindir/'vsim.exe','-c','-do',str(out/'run.do')],out,out,'vsim',600)
    assert b'MAIN_PORT_COMPLETE' in r.stdout and b'MAIN_PORT_FAIL' not in r.stdout and b'** Error' not in r.stdout and b'** Fatal' not in r.stdout
    stats=verify(cases,out/'ports.txt')
    result={'status':'PASS_INDEPENDENT_RTL_PORT_REVIEW','rtl_sha256':sha(a.rtl),'tb_sha256':sha(a.tb),'checker_sha256':sha(__file__),'cases_sha256':sha(out/'cases.json'),'ports_sha256':sha(out/'ports.txt'),'stats':stats,'oracle_imports_worker_or_golden':False,'scope':'single-clock integer inner encoder digital simulation only; not TRACE/synthesis/implementation/board/B01 acceptance'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))

if __name__=='__main__':main()
