"""Main's preinspection absolute-clock composition oracle.

No operation30 author code is read. Packet bytes use struct/binascii; all
serial start/bit/stop/release instants follow integer clock arithmetic.
"""
from pathlib import Path
import argparse,binascii,datetime,hashlib,json,random,struct
INS=[('rst',1),('cancel',1),('cfg_valid',1),('cfg_type',8),('cfg_epoch',8),('cfg_seq',16),('cfg_tick',32),('cfg_len',6),('p_valid',1),('p_data',8),('p_last',1)]
OUTS=[('cfg_ready',1),('p_ready',1),('tx',1),('de',1),('busy',1),('receiving',1),('faulted',1),('fault_event',1),('fault_code',2)]+[(n,32) for n in ('stat_admitted','stat_sent','stat_aborted')]
def sha(b):return hashlib.sha256(b).hexdigest()
def packet(meta,payload):
 t,e,s,k,n=meta;body=struct.pack('<BBBBHI',3,t,n,e,s,k)+bytes(payload);return b'\xa5\x5a'+body+struct.pack('<H',binascii.crc_hqx(body,65535))
class Model:
 def __init__(self,c,b,pre,post,stat):self.c=c;self.b=b;self.pre=pre;self.post=post;self.cap=(1<<stat)-1;self.edge=0;self.history=[];self.reset()
 def reset(self):self.state='idle';self.counts=[0]*3;self.code=0;self.event=0;self.meta=None;self.data=[];self.wire=b'';self.rise=self.start=self.release=self.done=-1
 def inc(self,i):self.counts[i]=min(self.cap,self.counts[i]+1)
 def seal(self):
  self.state='send';self.wire=packet(self.meta,self.data);n=len(self.wire);L=(10*self.c+self.b-1)//self.b
  self.rise=self.edge+n+2;self.start=self.rise+self.pre+1;self.release=self.start+(n-1)*(L+2)+L+self.post+1;self.done=self.release+1
  self.history.append({'seal':self.edge,'wire_hex':self.wire.hex(),'de_rise':self.rise,'first_start':self.start,'de_release':self.release,'wrapper_retire':self.done})
 def ports(self,x):
  gate=not(x['rst'] or x['cancel']);tx=1;de=0
  if self.state=='send':
   de=int(self.rise<=self.edge<self.release)
   if self.start<=self.edge<self.release:
    L=(10*self.c+self.b-1)//self.b;i,t=divmod(self.edge-self.start,L+2)
    if i<len(self.wire):
     k=max(k for k in range(11) if t>=(k*self.c+self.b-1)//self.b)
     tx=0 if k==0 else (self.wire[i]>>(k-1))&1 if k<9 else 1
  return [int(self.state=='idle' and gate),int(self.state=='collect' and gate),tx,de,int(self.state!='idle'),int(self.state=='collect'),int(self.state=='fault'),self.event,self.code,*self.counts]
 def step(self,x):
  self.edge+=1
  if x['rst']:self.reset();return
  self.event=0
  if x['cancel']:
   if self.state!='idle':self.inc(2)
   self.state='idle';self.code=0;self.meta=None;self.data=[];return
  if self.state=='idle':
   if x['cfg_valid']:
    self.inc(0);self.meta=tuple(x[n] for n in ('cfg_type','cfg_epoch','cfg_seq','cfg_tick','cfg_len'));self.data=[]
    if x['cfg_len']>32:self.state='fault';self.code=1;self.event=1
    elif not x['cfg_len']:self.seal()
    else:self.state='collect'
  elif self.state=='collect' and x['p_valid']:
   if bool(x['p_last'])!=(len(self.data)==self.meta[4]-1):self.state='fault';self.code=2;self.event=1
   else:
    self.data.append(x['p_data'])
    if len(self.data)==self.meta[4]:self.seal()
  elif self.state=='send' and self.edge==self.done:self.state='idle';self.inc(1)

def bench():
 total=sum(w for _,w in INS)+2*sum(w for _,w in OUTS)
 def decl(k,n,w):return k+' '+(f'[{w-1}:0] ' if w>1 else '')+n+';'
 a=['`timescale 1ns/1ps','module main_tb_wire_uart_tx;','parameter integer CLOCK_HZ=64,BAUD=4,PRE_CYCLES=0,POST_CYCLES=0,STAT_W=32;','localparam integer SW=(STAT_W<2)?2:((STAT_W>32)?32:STAT_W);','reg clk=0;always #5 clk=~clk;']
 a += [decl('reg',n,w) for n,w in INS]+[('wire [SW-1:0] '+n+';' if n.startswith('stat_') else decl('wire',n,w)) for n,w in OUTS]
 a += [decl('reg',tag+'_'+n,w) for tag in ('pre','post') for n,w in OUTS]
 a += ['deepeye_wire_uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.PRE_CYCLES(PRE_CYCLES),.POST_CYCLES(POST_CYCLES),.STAT_W(STAT_W)) dut(.*);',f'reg [{total-1}:0] row;','integer fd,got,nrepeat,i,cycles=0,checks=0;','task automatic eq(input string field,input logic[255:0] actual,input logic[255:0] expected);begin checks++;if(actual!==expected)begin $display("MAIN_MISMATCH cycle=%0d field=%s got=%0h expected=%0h",cycles,field,actual,expected);$fatal(1,"main numeric mismatch");end end endtask','initial begin']
 a += [f'{n}='+('1' if n=='rst' else '0')+';' for n,_ in INS]
 a += ['$display("MAIN_BEGIN clock=%0d baud=%0d pre=%0d post=%0d stat=%0d",CLOCK_HZ,BAUD,PRE_CYCLES,POST_CYCLES,STAT_W);','fd=$fopen("vectors.rle","r");if(!fd)$fatal(1,"missing vectors");','while(!$feof(fd))begin','got=$fscanf(fd,"%d %h\\n",nrepeat,row);if(got==2)begin','if(nrepeat<1)$fatal(1,"invalid repeat");for(i=0;i<nrepeat;i++)begin','@(negedge clk);{'+','.join([n for n,_ in INS]+[t+'_'+n for t in ('pre','post') for n,_ in OUTS])+'}=row;#1;']
 for tag in ('pre','post'):
  if tag=='post':a+=['@(posedge clk);#1;cycles++;']
  a += [f'eq("{tag}_{n}",{n},{tag}_{n});' for n,_ in OUTS]
 a += ['end end else if(!$feof(fd))$fatal(1,"invalid vector row");end','$fclose(fd);$display("MAIN_STATS cycles=%0d checks=%0d",cycles,checks);$display("MAIN_PASS");$finish;end','endmodule']
 return '\n'.join(a)+'\n'

def main():
 p=argparse.ArgumentParser();p.add_argument('--clock',type=int,default=64);p.add_argument('--baud',type=int,default=4);p.add_argument('--pre',type=int,default=0);p.add_argument('--post',type=int,default=0);p.add_argument('--stat',type=int,default=32);p.add_argument('--brief',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 m=Model(a.clock,a.baud,a.pre,a.post,a.stat);rng=random.Random(2026102430);runs=[];labels=[];cycles=0;fullwidth=sum(w for _,w in INS)+2*sum(w for _,w in OUTS)
 def tick(label='',**kw):
  nonlocal cycles
  x={n:0 for n,_ in INS};x.update(kw);pre=m.ports(x);m.step(x);post=m.ports(x);v=0
  for n,w in INS:assert 0<=x[n]<(1<<w);v=(v<<w)|x[n]
  for values in (pre,post):
   for value,(_,w) in zip(values,OUTS):assert 0<=value<(1<<w);v=(v<<w)|value
  row=f'{v:0{(fullwidth+3)//4}x}'
  if runs and runs[-1][1]==row:runs[-1][0]+=1
  else:runs.append([1,row])
  cycles+=1
  if label:labels.append({'cycle':cycles,'label':label})
 def load(n,k=0):
  tick('config',cfg_valid=1,cfg_type=k&255,cfg_epoch=(k*19)&255,cfg_seq=(65535-k)&65535,cfg_tick=(0xffffffff-k*65537)&0xffffffff,cfg_len=n,p_valid=1,p_data=165,p_last=1)
  for j in range(n):
   for _ in range(rng.randrange(3)):tick()
   tick(p_valid=1,p_data=(k+j)&255,p_last=int(j==n-1))
 def drain():
  while m.state=='send':tick(cfg_valid=1,cfg_len=0,cfg_type=91,p_valid=1,p_data=33,p_last=1)
 tick('reset',rst=1)
 if a.brief:load(0);drain()
 else:
  for n in range(33):load(n,n);drain()
  for k in range(0,256,32):load(32,k);drain()
  for n in range(33,64):
   tick(cfg_valid=1,cfg_len=n);tick(cancel=1);tick(cancel=1)
  for n in (1,2,32):
   tick(cfg_valid=1,cfg_len=n);tick(p_valid=1,p_last=int(n!=1));tick(cancel=1)
   tick(cfg_valid=1,cfg_len=n);tick(rst=1,cancel=1)
  for rr in (0,1):
   for n in (0,1,32):
    N=n+14;L=(10*a.clock+a.baud-1)//a.baud
    offsets=sorted(set([0,1,N,N+1,N+2,N+a.pre+2,N+a.pre+3]+[N+a.pre+3+i*(L+2)+k for i in range(N) for k in (0,L//2,L-1,L)]+[N+a.pre+3+(N-1)*(L+2)+L+a.post]))
    for off in offsets:
     load(n,off)
     for _ in range(off):tick()
     tick('abort_phase',rst=rr,cancel=1,cfg_valid=1,cfg_len=0,p_valid=1,p_data=255,p_last=1);tick(rst=rr,cancel=1);tick()
  for _ in range(10):load(0,17);drain()
 tick(rst=1,cancel=1);tick()
 data=''.join(f'{n} {row}\n' for n,row in runs).encode();(a.out/'vectors.rle').write_bytes(data);tb=bench()
 if a.tb.exists():assert a.tb.read_text(encoding='utf-8')==tb
 else:a.tb.write_text(tb,encoding='utf-8',newline='\n')
 receipt={'kind':'wire_uart_tx','parameters':{'clock':a.clock,'baud':a.baud,'pre':a.pre,'post':a.post,'stat':a.stat},'brief':a.brief,'cycles':cycles,'checks':cycles*len(OUTS)*2,'rle_rows':len(runs),'vectors_sha256':sha(data),'tb_sha256':sha(a.tb.read_bytes()),'oracle_sha256':sha(Path(__file__).read_bytes()),'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'author_source_inspected':False,'scope':'Absolute-clock expected bytes, all byte starts/bit boundaries, DE and wrapper retirement; same-clock digital model only','history':m.history,'labels':labels}
 (a.out/'FREEZE.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('history','labels')}))
if __name__=='__main__':main()
