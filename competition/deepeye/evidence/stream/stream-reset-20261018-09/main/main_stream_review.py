import argparse,hashlib,json,os,random,re,subprocess,sys
from collections import deque,Counter
from pathlib import Path
H=Path(__file__).resolve().parent
W=Path('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
CORE=W/'competition/deepeye/fpga/codec/deepeye_block_encoder.sv'
WRAPPER=W/'competition/deepeye/fpga/stream/deepeye_block_stream.sv'
TOOLS=Path('D:/modelsim1/win64')
FIELDS='cycle rst cancel cf count e tag sf sdata slast hf mtag error mcount me raw k bits bytes bf data last level filling cfgstat sstat okstat errstat abortstat'.split()
MAX=2**32-1
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,j):p.write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def inner(xs,e):
    p=xs[0];z=[];step=2*e+1
    for x in xs[1:]:
        q=(x-p+e)//step;p=max(0,min(65535,p+q*step));z.append(2*q if q>=0 else -2*q-1)
    choices=[(sum((v>>k)+1+k for v in z),k) for k in range(16) if all((v>>k)<=31 for v in z)]
    cost,k=min(choices) if choices else (999999,0)
    raw=cost>=16*(len(xs)-1)
    if raw:k=0;bittext=''.join(format(x,'016b') for x in xs)
    else:bittext=format(xs[0],'016b')+''.join('0'*(v>>k)+'1'+(format(v&((1<<k)-1),'0%db'%k) if k else '') for v in z)
    nbits=len(bittext);padded=bittext+'0'*((-nbits)%8)
    payload=[int(padded[i:i+8],2) for i in range(0,len(padded),8)]
    return {'raw':int(raw),'k':k,'bits':nbits,'bytes':len(payload),'payload':payload}
def commands():
    out=[];labels=[];r=random.Random(0x1809B);tag=100
    def add(op,a=0,b=0,c=0,d=0):out.append((op,a,b,c,d))
    def mark(s):labels.append({'command_index':len(out),'label':s})
    def block(xs,e=0,t=None,n=None,bad=None,partial=None):
        nonlocal tag
        tag=(tag+1)&65535;t=tag if t is None else t;n=len(xs) if n is None else n
        add(1,n,e,t)
        if not (1<=n<=128 and e in (0,1,2,4,8)):return
        stop=len(xs) if partial is None else partial
        for i,x in enumerate(xs[:stop]):
            last=int(i==n-1)
            if bad=='early' and i==stop-1:last=1
            if bad=='missing' and i==n-1:last=0
            add(2,x,last)
    def drain():add(5,0,200000);add(3,12)
    def fresh():add(4,1);block([12345,12344,12347,12348,0,65535,1],2,t=65535);drain()
    mark('full two slots, metadata and byte stalls, no admission/drop');add(4,0)
    block([0,65535]*64);block(list(range(17)),4)
    add(5,4,20000);add(5,1,20000);add(6,1,0,8888,10000);add(7,31337,1,1000)
    add(4,4);add(5,2,20000);add(3,10000);add(4,1);drain()
    mark('invalid cfg and invalid last ordered with valid blocks');add(4,2)
    for n,e in [(0,0),(129,0),(255,8),(3,3),(128,15),(1,7)]:
        block([],e,n=n);block([2,3,4],1,t=5)
    for n in [2,3,17,128]:
        block([99]*n,0,bad='early',partial=n-1);block([5]*n,4,bad='missing');block([0,65535],0,t=5)
    drain();add(7,77,1,30);add(6,1,0,42,1);add(2,123,1);drain()
    mark('explicit simultaneous allocation/error retirement, then sample/error retirement')
    add(4,0);block([],0,n=0);add(5,1,20000);add(4,1);block([12,13,14],1);drain()
    add(4,0);block([],0,n=129);block([100,101,102,103],1,partial=0)
    add(4,1);add(2,100,0);add(2,101,0);add(2,102,0);add(2,103,1);drain()
    for use_reset in [False,True]:
        mark('partial input plus stalled output flush '+str(use_reset));add(4,4)
        block([0,65535]*32);block([1234]*128,8,partial=9)
        add(5,2,20000);add(3,33);add(0,int(use_reset),int(not use_reset),1,1);fresh()
    for delay in [0,1,17,100,1000]:
        mark('core pipeline pending and second partial cancel delay '+str(delay));add(4,1)
        block([1000+(i%3) for i in range(128)],1);block([5]*128,0,partial=3)
        add(3,delay);add(0,0,1,1,1);fresh()
    for limit in [0,1,7,255]:
        mark('partial output/finalbyte flush after '+str(limit));add(4,6,limit)
        block([0,65535]*64,0);block([],0,n=0)
        add(5,2,20000);add(3,limit+12)
        if limit==255:add(5,5,20000)
        add(4,1);add(0,0,1,3,1);fresh()
    mark('pending error metadata cancel and simultaneous reset priority');add(4,0)
    block([],0,n=255);block([1,2,3],0);add(5,1,20000);add(0,0,1,4,1);add(0,1,1,2,1);fresh()
    mark('randomized many blocks, duplicate tags, queue wrap, backpressure');add(4,2)
    for i in range(300):
        n=r.choice([1,2,3,7,8,17,31,64,127,128,r.randint(1,128)]);e=r.choice([0,1,2,4,8])
        kind=i%5
        if kind==0:xs=[r.randrange(65536) for _ in range(n)]
        elif kind==1:xs=[max(0,min(65535,32768+r.randint(-30,30))) for _ in range(n)]
        elif kind==2:xs=[0 if j<n//2 else r.choice([9,15,31,63,1023]) for j in range(n)]
        elif kind==3:xs=[65535 if j%2 else 0 for j in range(n)]
        else:xs=[r.choice([0,1,65534,65535])]*n
        if i%19==0 and n>1:
            block(xs,e,t=i%7,partial=max(1,n//2));add(3,r.randrange(20));add(0,0,1,1);continue
        block(xs,e,t=i%7,bad='missing' if i%23==0 else None)
        if i%17==0:add(3,r.randrange(80))
    drain()
    mark('whitebox public counter seed saturation only');add(4,1)
    for index in range(5):add(9,index,MAX-1)
    block([1]);block([2]);drain();block([],0,n=0);block([],0,n=129);drain()
    add(4,0);block([1,2]);block([3,4]);add(0,0,1,2,1)
    mark('fresh first block after final reset');add(0,1,0,1,1);fresh();add(10)
    return out,labels
def check(path):
    queue=deque();stats=[0]*5;summary=Counter();seen_e=set();seen_n=set();last_cycle=-1
    passline=None
    for line in path.read_text(encoding='utf-8').splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='S':
            _,i,v=parts;stats[int(i)]=int(v);summary['whitebox_counter_seeds']+=1;continue
        if parts[0]=='PASS':passline=list(map(int,parts[1:]));continue
        assert parts[0]=='E',('unexpected log',line)
        assert len(parts)==len(FIELDS)+1,('column count',line)
        p=dict(zip(FIELDS,map(int,parts[1:])))
        assert p['cycle']>last_cycle;last_cycle=p['cycle'];summary['event_rows']+=1
        if p['rst'] or p['cancel']:
            assert not any(p[k] for k in ['cf','sf','hf','bf'])
            summary['flushed_blocks']+=len(queue);summary['reset_edges' if p['rst'] else 'cancel_edges']+=1
            if p['rst']:stats=[0]*5
            else:stats[4]=min(MAX,stats[4]+len(queue))
            queue.clear()
        else:
            if p['cf'] and ((p['hf'] and p['error']) or (p['bf'] and p['last'])):summary['simultaneous_cfg_retire']+=1
            if p['sf'] and ((p['hf'] and p['error']) or (p['bf'] and p['last'])):summary['simultaneous_sample_retire']+=1
            if p['cf']:
                assert len(queue)<2 and not any(not b['sealed'] for b in queue),('bad cfg admission',p)
                bad=not (1<=p['count']<=128 and p['e'] in (0,1,2,4,8))
                queue.append(dict(count=p['count'],e=p['e'],tag=p['tag'],xs=[],error=int(bad),sealed=bad,header=False,index=0))
                stats[0]=min(MAX,stats[0]+1);summary['admitted']+=1
            if p['sf']:
                assert queue and not queue[-1]['sealed'],('sample without filling',p)
                b=queue[-1];b['xs'].append(p['sdata']);stats[1]=min(MAX,stats[1]+1);summary['samples']+=1
                final=len(b['xs'])==b['count']
                if bool(p['slast'])!=final:b.update(error=2,sealed=True)
                elif final:b['sealed']=True
            if p['hf']:
                assert queue and queue[0]['sealed'] and not queue[0]['header'],('bad metadata order',p)
                b=queue[0];assert p['mtag']==b['tag'],('tag',p,b)
                if b['error']:
                    expected={'error':b['error'],'mcount':0,'me':0,'raw':1,'k':0,'bits':0,'bytes':0}
                    assert all(p[k]==v for k,v in expected.items()),('error metadata',p,expected)
                    assert not p['bf'];queue.popleft();stats[3]=min(MAX,stats[3]+1);summary['error_blocks']+=1
                else:
                    code=inner(b['xs'],b['e']);b.update(code);b['header']=True
                    expected={'error':0,'mcount':b['count'],'me':b['e'],**{k:code[k] for k in ['raw','k','bits','bytes']}}
                    assert all(p[k]==v for k,v in expected.items()),('success metadata',p,expected)
                    assert not p['bf'],('payload before metadata edge completed',p)
            if p['bf']:
                assert queue and queue[0]['header'],('payload before header',p)
                b=queue[0];i=b['index'];assert i<len(b['payload'])
                assert p['data']==b['payload'][i] and bool(p['last'])==(i+1==len(b['payload'])),('payload mismatch',p,b)
                b['index']+=1;summary['payload_bytes']+=1
                if p['last']:
                    queue.popleft();stats[2]=min(MAX,stats[2]+1);summary['completed_blocks']+=1
                    summary['raw_blocks' if b['raw'] else 'rice_blocks']+=1;seen_e.add(b['e']);seen_n.add(b['count'])
        assert p['level']==len(queue),('level',p,list(queue))
        assert p['filling']==int(any(not b['sealed'] for b in queue)),('filling',p)
        assert [p[k] for k in ['cfgstat','sstat','okstat','errstat','abortstat']]==stats,('stats',p,stats)
    assert passline is not None and not queue,('missing pass or pending blocks',passline,list(queue))
    assert passline[1]==summary['event_rows']
    assert summary['simultaneous_cfg_retire']>0 and summary['simultaneous_sample_retire']>0, 'missing directed concurrent handshakes'
    return {'status':'PASS_INDEPENDENT_STREAM_PORTS','counts':dict(summary),'all_E':sorted(seen_e),'N_values':sorted(seen_n),'monitor':dict(zip(['cycles','events','stall_stability_checks','full_queue_cycles'],passline)),'oracle_imports_worker_or_golden':False,'whitebox_scope':'Only counter seeding; stream/counter transitions checked via actual public ports. No seeded state used as public stream proof.'}
def run(out,wrapper):
    out.mkdir(exist_ok=False,parents=True);cmds,labels=commands()
    cp=out/'commands.txt';cp.write_text(''.join(' '.join(map(str,x))+'\n' for x in cmds),encoding='ascii')
    dump(out/'scenarios.json',labels);port=out/'ports.txt'
    do=out/'run.do';do.write_text('onerror {quit -code 1}\nonbreak {quit -code 1}\nrun -all\nquit -code 0\n',encoding='ascii')
    rows=[]
    def call(name,args,timeout=60):
        r=subprocess.run(args,cwd=out,capture_output=True,timeout=timeout)
        (out/(name+'.stdout.txt')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
        row={'name':name,'command':list(map(str,args)),'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()};rows.append(row);dump(out/'commands.json',rows)
        assert r.returncode==0,(name,r.returncode,r.stderr.decode(errors='replace')[-1000:]);return r.stdout+r.stderr
    try:
        call('version',[str(TOOLS/'vsim.exe'),'-version'])
        call('vlib',[str(TOOLS/'vlib.exe'),'work'])
        call('vlog',[str(TOOLS/'vlog.exe'),'-sv','-work','work',str(CORE),str(wrapper),str(H/'main_stream_ports.sv')])
        transcript=call('vsim',[str(TOOLS/'vsim.exe'),'-c','-lib','work','main_stream_ports','+COMMANDS='+str(cp),'+PORTS='+str(port),'-do',str(do)],60)
        assert b'MAIN_STREAM_PASS' in transcript and not re.search(rb'MAIN_STREAM_FAIL|\*\* (?:Fatal|Error)',transcript), 'simulator marker gate'
        result=check(port);result.update(core_sha256=sha(CORE),wrapper_sha256=sha(wrapper),tb_sha256=sha(H/'main_stream_ports.sv'),checker_sha256=sha(Path(__file__)),commands_sha256=sha(cp),ports_sha256=sha(port),scope='two-slot single-clock internal stream integration digital simulation only')
        dump(out/'result.json',result);print(json.dumps(result));return result
    except Exception as e:
        dump(out/'failure.json',{'error_type':type(e).__name__,'error':str(e),'wrapper_sha256':sha(wrapper),'core_sha256':sha(CORE),'tb_sha256':sha(H/'main_stream_ports.sv')});raise
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path);p.add_argument('--wrapper',type=Path,default=WRAPPER);p.add_argument('--check',type=Path);a=p.parse_args()
    if a.check:print(json.dumps(check(a.check)))
    else:assert a.out;run(a.out.resolve(),a.wrapper.resolve())
