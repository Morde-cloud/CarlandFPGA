"""Preinspection main RX composition oracle using absolute sample deadlines.

Reuses only the earlier main public-history parser model (fixed hash), never
author RTL/tests. The digital UART reference uses delayed input and absolute
ceil half-bit deadlines, not the RTL phase accumulator.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,random
HELPER=Path(__file__).with_name('main_generate_wire_vectors.py')
assert hashlib.sha256(HELPER.read_bytes()).hexdigest()=='dc6f94b528754ec6fe439b570d4458081ea7fcacb78e73c7ca6918e07624baa0'
s=importlib.util.spec_from_file_location('main_parser_history_reference',HELPER);h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
INS=[('rst',1),('cancel',1),('rx_async',1),('out_ready',1)]
OUTS=[('out_valid',1),('out_type',8),('out_epoch',8),('out_seq',16),('out_tick',32),('out_len',6),('out_payload',256),('uart_busy',1),('receiving',1),('line_error_event',1),('line_error_bits',3),('error_event',1),('error_code',2)]+[(n,32) for n in ('stat_uart_frames','stat_uart_retired','stat_uart_overruns','stat_uart_framing','stat_uart_false_starts','stat_uart_aborted','stat_bytes','stat_frames','stat_retired','stat_version','stat_length','stat_crc','stat_aborted')]
class UART:
 def __init__(self,c,b,stat):self.c=c;self.b=b;self.cap=(1<<stat)-1;self.edge=0;self.reset()
 def reset(self):self.meta=self.sync=self.prev=1;self.warm=0;self.armed=self.active=self.full=False;self.acc=self.slot=self.events=0;self.half=1;self.start=0;self.counts=[0]*6
 def inc(self,i,n=1):self.counts[i]=min(self.cap,self.counts[i]+n)
 def boundary(self,n):return (n*self.c+2*self.b-1)//(2*self.b)
 def step(self,rst,cancel,line,ready):
  self.edge+=1;self.events=0
  if rst:self.reset();return
  if cancel:
   self.inc(5,int(self.active)+int(self.full));self.meta=self.sync=self.prev=1;self.warm=0;self.armed=self.active=self.full=False;self.half=1;self.acc=0;return
  oldsync,oldmeta,oldprev,oldfull,oldactive=self.sync,self.meta,self.prev,self.full,self.active;ret=oldfull and ready
  if ret:self.full=False;self.inc(1)
  self.meta=line;self.sync=oldmeta;self.prev=oldsync
  if self.warm<2:self.warm+=1
  elif not oldactive:
   if oldsync:self.armed=True
   elif self.armed and oldprev:self.active=True;self.armed=False;self.start=self.edge;self.half=1;self.acc=0
  elif self.edge-self.start==self.boundary(self.half):
   if self.half==1 and oldsync:self.active=False;self.armed=True;self.events=1;self.inc(4)
   elif self.half==19:
    self.active=False;self.armed=bool(oldsync)
    if not oldsync:self.events=2;self.inc(3)
    else:
     self.inc(0)
     if oldfull and not ret:self.events=4;self.inc(2)
     else:self.full=True;self.slot=self.acc
   else:
    if self.half>=3:self.acc|=oldsync<<((self.half-3)//2)
    self.half+=2
class Model:
 def __init__(self,c,b,stat):self.u=UART(c,b,stat);self.p=h.Parser(stat)
 def parser_x(self,x):return {'rst':x['rst'],'cancel':int(x['cancel'] or self.u.events),'in_valid':int(self.u.full and not(x['rst'] or x['cancel'] or self.u.events)),'in_data':self.u.slot,'out_ready':x['out_ready']}
 def ports(self,x):
  p=self.p.ports(self.parser_x(x));return [*p[1:8],int(self.u.active),p[8],int(bool(self.u.events)),self.u.events,p[9],p[10],*self.u.counts,*self.p.counts]
 def step(self,x):
  px=self.parser_x(x);ready=self.p.ports(px)[0];self.p.step(px);self.u.step(x['rst'],px['cancel'],x['rx_async'],ready)
def bench():
 width=sum(w for _,w in INS)+2*sum(w for _,w in OUTS)
 def decl(k,n,w):return k+' '+(f'[{w-1}:0] ' if w>1 else '')+n+';'
 a=['`timescale 1ns/1ps','module main_tb_uart_wire_rx;','parameter integer CLOCK_HZ=64,BAUD=4,STAT_W=32;','localparam integer SW=(STAT_W<2)?2:((STAT_W>32)?32:STAT_W);','reg clk=0;always #5 clk=~clk;']
 a += [decl('reg',n,w) for n,w in INS]+[('wire [SW-1:0] '+n+';' if n.startswith('stat_') else decl('wire',n,w)) for n,w in OUTS]
 a += [decl('reg',t+'_'+n,w) for t in ('pre','post') for n,w in OUTS]
 a += ['deepeye_uart_wire_rx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.STAT_W(STAT_W)) dut(.*);',f'reg [{width-1}:0] row;','integer fd,got,nrepeat,i,cycles=0,checks=0;','task automatic eq(input string field,input logic[255:0] actual,input logic[255:0] expected);begin checks++;if(actual!==expected)begin $display("MAIN_MISMATCH cycle=%0d field=%s got=%0h expected=%0h",cycles,field,actual,expected);$fatal(1,"main numeric mismatch");end end endtask','initial begin']
 a += [f'{n}='+('1' if n in ('rst','rx_async') else '0')+';' for n,_ in INS]
 a += ['$display("MAIN_BEGIN clock=%0d baud=%0d stat=%0d",CLOCK_HZ,BAUD,STAT_W);','fd=$fopen("vectors.rle","r");if(!fd)$fatal(1,"missing vectors");','while(!$feof(fd))begin','got=$fscanf(fd,"%d %h\\n",nrepeat,row);if(got==2)begin','if(nrepeat<1)$fatal(1,"invalid repeat");for(i=0;i<nrepeat;i++)begin','@(negedge clk);{'+','.join([n for n,_ in INS]+[t+'_'+n for t in ('pre','post') for n,_ in OUTS])+'}=row;#1;']
 for t in ('pre','post'):
  if t=='post':a+=['@(posedge clk);#1;cycles++;']
  for n,_ in OUTS:
   actual=f'(out_valid?{n}:0)' if n.startswith('out_') and n!='out_valid' else n;a.append(f'eq("{t}_{n}",{actual},{t}_{n});')
 a+=['end end else if(!$feof(fd))$fatal(1,"invalid vector row");end','$fclose(fd);$display("MAIN_STATS cycles=%0d checks=%0d",cycles,checks);$display("MAIN_PASS");$finish;end','endmodule'];return '\n'.join(a)+'\n'
def main():
 p=argparse.ArgumentParser();p.add_argument('--clock',type=int,default=64);p.add_argument('--baud',type=int,default=4);p.add_argument('--stat',type=int,default=32);p.add_argument('--brief',action='store_true');p.add_argument('--out',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False);m=Model(a.clock,a.baud,a.stat);runs=[];cycles=0;labels=[];width=sum(w for _,w in INS)+2*sum(w for _,w in OUTS)
 def tick(label='',**kw):
  nonlocal cycles
  x={'rst':0,'cancel':0,'rx_async':1,'out_ready':1};x.update(kw);pre=m.ports(x);m.step(x);post=m.ports(x);v=0
  for n,w in INS:v=(v<<w)|x[n]
  for vals in (pre,post):
   for value,(_,w) in zip(vals,OUTS):assert 0<=value<(1<<w);v=(v<<w)|value
  row=f'{v:0{(width+3)//4}x}'
  if runs and runs[-1][1]==row:runs[-1][0]+=1
  else:runs.append([1,row])
  cycles+=1
  if label:labels.append({'cycle':cycles,'label':label})
 def idle(n=8,ready=1):
  for _ in range(n):tick(out_ready=ready)
 def byte(value,stop=1,ready=1,abort=None):
  N=(10*a.clock+a.baud-1)//a.baud
  for k in range(N):
   phase=k*a.baud//a.clock;line=0 if phase==0 else (value>>(phase-1))&1 if phase<9 else stop;kw={}
   if abort and k==(abort[1]*a.clock//a.baud)+3:kw[abort[0]]=1
   tick(rx_async=line,out_ready=ready,**kw)
 def send(blob,ready=1):
  for b in blob:byte(b,ready=ready)
  idle(8,ready)
 def packet(n,k=0):return h.packet(k&255,(255-k)&255,(65535-k)&65535,(0xffffffff-k*65537)&0xffffffff,[(k+i)&255 for i in range(n)])
 tick('initial_reset',rst=1,rx_async=0)
 for _ in range(12):tick(rx_async=0)
 idle()
 if a.brief:send(packet(0))
 else:
  for n in range(33):send(packet(n,n))
  for k in range(0,256,32):send(packet(32,k))
  for n in (0,1,32):
   good=packet(n,90)
   for pos in (2,4,len(good)-2,len(good)-1):
    bad=bytearray(good);bad[pos]^=128;send(bad);send(b'\x00'*48);send(good)
   for pos in sorted(set([0,1,2,3,4,5,6,7,8,9,10,11,len(good)//2,len(good)-2,len(good)-1])):
    tick('bad_stop_boundary',cancel=1);idle();send(good[:pos]);byte(good[pos],stop=0);idle(a.clock//a.baud+12);send(good)
    tick('false_start_boundary',cancel=1);idle();send(good[:pos]);tick(rx_async=0);idle(m.u.boundary(1)+12);send(good)
  # A retained complete candidate blocks parser input. Two new UART bytes
  # force an actual overrun, whose registered event gates then flushes both.
  for n in (0,32):
   send(packet(n,17),0);idle(30,0);byte(0x11,ready=0);byte(0x22,ready=0);idle(20,0);send(packet(n,19));idle()
  for resetkind in ('rst','cancel'):
   for phase in range(10):
    tick(cancel=1);idle();send(packet(32,7)[:10]);byte(85,abort=(resetkind,phase));idle(12);send(packet(1,phase))
   send(packet(32,88),0);byte(51,ready=0);tick(out_ready=1,rx_async=0,**{resetkind:1});tick(rx_async=0,**{resetkind:1});idle();send(packet(0))
  for _ in range(8):send(packet(0,44))
 tick(rst=1,cancel=1);idle()
 data=''.join(f'{n} {row}\n' for n,row in runs).encode();(a.out/'vectors.rle').write_bytes(data);tb=bench()
 if a.tb.exists():assert a.tb.read_text(encoding='utf-8')==tb
 else:a.tb.write_text(tb,encoding='utf-8',newline='\n')
 receipt={'kind':'uart_wire_rx','parameters':{'clock':a.clock,'baud':a.baud,'stat':a.stat},'brief':a.brief,'cycles':cycles,'checks':cycles*2*len(OUTS),'rle_rows':len(runs),'vectors_sha256':hashlib.sha256(data).hexdigest(),'tb_sha256':hashlib.sha256(a.tb.read_bytes()).hexdigest(),'oracle_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256(HELPER.read_bytes()).hexdigest(),'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'author_source_inspected':False,'history':m.p.history,'labels':labels,'scope':'Same-clock digital UART loss/discard and opaque parser histories only; no physical/semantic acceptance'}
 (a.out/'FREEZE.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('history','labels')}))
if __name__=='__main__':main()
