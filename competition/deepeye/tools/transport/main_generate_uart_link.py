"""Main finite-clock composition, written before reading operation34 author tests.

Reuses pinned earlier main UART references. New timestamp merge and pin link,
not a third independently derived UART implementation or analog CDC proof.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json

P=Path(__file__).parent
PINS={'main_generate_wire_uart_tx.py':'1245f14924153912051304ffe8b601fdf0a3ceb0ddbde94d8d82b134d3cc4ac6',
      'main_generate_uart_wire_rx.py':'16a0a02fdb98554e58831e39b94dbc43000ccc61d633a176b23e9508cdd5752f',
      'main_generate_wire_vectors.py':'dc6f94b528754ec6fe439b570d4458081ea7fcacb78e73c7ca6918e07624baa0'}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(name):
 p=P/name;assert digest(p)==PINS[name],name
 s=importlib.util.spec_from_file_location(name[:-3],p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
tx=module('main_generate_wire_uart_tx.py');rx=module('main_generate_uart_wire_rx.py')
INPUTS=[('t_'+n,w) for n,w in tx.INS]+[('r_rst',1),('r_cancel',1),('r_out_ready',1),('mux_mode',2)]
OUTPUTS=[('t_'+n,w) for n,w in tx.OUTS]+[('r_'+n,w) for n,w in rx.OUTS]+[('line',1)]

def bench():
 width=2+sum(w for _,w in INPUTS)+sum(w for _,w in OUTPUTS)
 def decl(k,n,w):return f'{k} '+(f'[{w-1}:0] ' if w>1 else '')+n+';'
 lines=['`timescale 1ps/1ps','module main_tb_uart_link;','parameter integer CLOCK_HZ=64,BAUD=4,PRE_CYCLES=2,POST_CYCLES=3;','reg t_clk=0,r_clk=0;']
 lines += [decl('reg',n,w) for n,w in INPUTS]+[decl('wire',n,w) for n,w in OUTPUTS]+[decl('reg','e_'+n,w) for n,w in OUTPUTS]
 lines += ['assign line=(mux_mode==1)?~t_tx:(mux_mode==2)?1\'b0:(mux_mode==3)?1\'b1:t_tx;',
 'deepeye_wire_uart_tx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD),.PRE_CYCLES(PRE_CYCLES),.POST_CYCLES(POST_CYCLES)) tx_dut('+','.join(['.clk(t_clk)']+[f'.{n}(t_{n})' for n,_ in tx.INS+tx.OUTS])+');',
 'deepeye_uart_wire_rx #(.CLOCK_HZ(CLOCK_HZ),.BAUD(BAUD)) rx_dut('+','.join(['.clk(r_clk)','.rst(r_rst)','.cancel(r_cancel)','.rx_async(line)','.out_ready(r_out_ready)']+[f'.{n}(r_{n})' for n,_ in rx.OUTS])+');',
 f'reg [{width-1}:0] row;','reg tr,rr;integer fd,got;longint unsigned target_ps,previous_ps=0,events=0,checks=0;',
 'task automatic eq(input string field,input logic[255:0] actual,input logic[255:0] expected);begin checks++;if(actual!==expected)begin $display("MAIN_MISMATCH event=%0d time_ps=%0d field=%s got=%0h expected=%0h",events,target_ps,field,actual,expected);$fatal(1,"main link numeric mismatch");end end endtask',
 'initial begin']
 lines += [f'{n}='+('1' if n in ('t_rst','r_rst','r_out_ready') else '0')+';' for n,_ in INPUTS]
 lines += ['#1;t_clk=1;r_clk=1;#1;t_clk=0;r_clk=0;',
 '$display("MAIN_LINK_BEGIN");fd=$fopen("events.hex","r");if(!fd)$fatal(1,"missing events");',
 'while(!$feof(fd))begin got=$fscanf(fd,"%d %h\\n",target_ps,row);if(got==2)begin',
 'if(target_ps<=previous_ps+3)$fatal(1,"nonmonotonic event");#(target_ps-previous_ps-3);',
 '{tr,rr,'+','.join([n for n,_ in INPUTS]+['e_'+n for n,_ in OUTPUTS])+'}=row;',
 '#1;t_clk=tr;r_clk=rr;#1;events++;']
 for n,_ in OUTPUTS:
  observed=f'(r_out_valid?{n}:0)' if n.startswith('r_out_') and n!='r_out_valid' else n
  lines += [f'eq("{n}",{observed},e_{n});']
 lines += ['#1;t_clk=0;r_clk=0;previous_ps=target_ps;end else if(!$feof(fd))$fatal(1,"bad event row");end',
 '$fclose(fd);$display("MAIN_LINK_STATS events=%0d checks=%0d",events,checks);$display("MAIN_LINK_PASS");$finish;end','endmodule']
 # Both units receive one explicit reset rising edge at1ps. Normal clock
 # schedules start after it; after each event simulator time is target+2ps.
 return '\n'.join(lines)+'\n'

class Scenario:
 def __init__(self,out,c,b,period,phase):
  self.out=out;self.c=c;self.b=b;self.tp=10000;self.rp=period;self.phase=phase
  self.t=tx.Model(c,b,2,3,32);self.r=rx.Model(c,b,32);self.nt=5000;self.nr=phase
  self.now=0;self.events=0;self.txedges=0;self.rxedges=0;self.labels=[];self.deliveries=[];self.expected=[]
  self.x={n:0 for n,_ in tx.INS};self.y={'rst':0,'cancel':0,'out_ready':1};self.mux=0
  self.f=(out/'events.hex').open('w',encoding='ascii',newline='\n');self.width=2+sum(w for _,w in INPUTS)+sum(w for _,w in OUTPUTS)
 def step(self):
  tm=min(self.nt,self.nr);tr=tm==self.nt;rr=tm==self.nr
  oldline=self.t.ports(self.x)[2];line=(1-oldline) if self.mux==1 else 0 if self.mux==2 else 1 if self.mux==3 else oldline
  y={**self.y,'rx_async':line}
  rp=self.r.ports(y)
  if rr and rp[0] and y['out_ready']:
   self.deliveries.append({'ps':tm,'descriptor':rp[1:7]})
  if tr:self.t.step(self.x);self.nt+=self.tp;self.txedges+=1
  if rr:self.r.step(y);self.nr+=self.rp;self.rxedges+=1
  newtx=self.t.ports(self.x);newlin=(1-newtx[2]) if self.mux==1 else 0 if self.mux==2 else 1 if self.mux==3 else newtx[2]
  ro=self.r.ports({**self.y,'rx_async':newlin})
  vals=[int(tr),int(rr)]+[self.x[n] for n,_ in tx.INS]+[self.y['rst'],self.y['cancel'],self.y['out_ready'],self.mux]+newtx+ro+[newlin]
  widths=[1,1]+[w for _,w in INPUTS]+[w for _,w in OUTPUTS];v=0
  for x,w in zip(vals,widths):assert type(x) is int and 0<=x<1<<w,(tm,x,w);v=(v<<w)|x
  self.f.write(f'{tm} {v:0{(self.width+3)//4}x}\n');self.now=tm;self.events+=1
 def until(self,t):
  assert t>=self.now
  while min(self.nt,self.nr)<=t:self.step()
 def tx_ticks(self,n):
  goal=self.txedges+n
  while self.txedges<goal:self.step()
 def idle(self,n=24):self.tx_ticks(n)
 def label(self,name):self.labels.append({'name':name,'at_ps':self.now,'events':self.events})
 def clear(self,rst=False):
  self.x.update(rst=int(rst),cancel=int(not rst),cfg_valid=0,p_valid=0);self.y.update(rst=int(rst),cancel=int(not rst),out_ready=1);self.mux=0
  self.idle(5);self.x.update(rst=0,cancel=0);self.y.update(rst=0,cancel=0);self.idle()
 def load(self,n,k):
  assert self.t.state=='idle'
  payload=bytes((k+j)&255 for j in range(n));meta=(k&255,(255-k)&255,(65535-k)&65535,(0xffffffff-k*65537)&0xffffffff,n)
  self.x.update(dict(zip(('cfg_type','cfg_epoch','cfg_seq','cfg_tick','cfg_len'),meta)));self.x['cfg_valid']=1
  self.tx_ticks(1);self.x['cfg_valid']=0
  for i,v in enumerate(payload):
   self.x['p_valid']=0;self.tx_ticks(i%3)
   self.x.update(p_valid=1,p_data=v,p_last=int(i==n-1));self.tx_ticks(1)
  self.x['p_valid']=0
  assert self.t.state=='send'
  seal_ps=self.now;history=self.t.history[-1];start_ps=seal_ps+(history['first_start']-history['seal'])*self.tp
  d=[*meta[:4],n,int.from_bytes(payload,'little')]
  return start_ps,d
 def drain(self):
  while self.t.state=='send':self.step()
  self.idle(32)
 def good(self,n,k):
  before=len(self.deliveries);_,d=self.load(n,k);self.drain();assert [x['descriptor'] for x in self.deliveries[before:]]==[d]
  self.expected.append(d)
 def fault(self,kind):
  self.clear();self.label(kind);before=len(self.deliveries);start,d=self.load(32,61)
  L=(10*self.c+self.b-1)//self.b
  if kind in ('crc','badstop'):
   # In payload byte12, select data bit3 or complete stop bit.
   bit=4 if kind=='crc' else 9
   t0=start+(12*(L+2)+(bit*self.c+self.b-1)//self.b)*self.tp
   t1=start+(12*(L+2)+((bit+1)*self.c+self.b-1)//self.b)*self.tp
   self.until(t0-self.tp//2);self.mux=1 if kind=='crc' else 2
   self.until(t1-self.tp//2);self.mux=0;self.drain()
   assert len(self.deliveries)==before
   assert self.r.p.counts[5]>0 if kind=='crc' else self.r.u.counts[3]>0
  elif kind in ('bothcancel','rxcancel'):
   self.until(start+7*(L+2)*self.tp);self.y['cancel']=1;self.x['cancel']=int(kind=='bothcancel');self.idle(5)
   self.x['cancel']=0;self.y['cancel']=0;self.drain();assert len(self.deliveries)==before
  self.clear();self.good(1,203)
 def overrun(self):
  self.clear();self.label('overrun');self.y['out_ready']=0
  self.load(32,80);self.drain();assert self.r.p.slot is not None
  self.load(1,81);self.drain();assert self.r.u.counts[2]>0
  self.clear();self.good(0,82)
 def run(self):
  self.clear(True)
  for n in range(33):self.good(n,n)
  for k in range(0,256,32):self.good(32,k)
  for kind in ('crc','badstop','bothcancel','rxcancel'):self.fault(kind)
  self.overrun();self.clear(True);self.f.close()
  return {'events':self.events,'checks':self.events*len(OUTPUTS),'tx_edges':self.txedges,'rx_edges':self.rxedges,
   'tx_period_ps':self.tp,'rx_period_ps':self.rp,'rx_first_rising_ps':self.phase,'clock_parameter':self.c,'baud_parameter':self.b,
   'labels':self.labels,'deliveries':self.deliveries,'source_expected':self.expected,
   'vectors_sha256':digest(self.out/'events.hex'),'oracle_sha256':digest(Path(__file__)),'reference_pins':PINS,
   'author34_source_read':False,'scope':'Finite digital posedge link fixtures only; all29/B04/B06/R03/board/system not_run'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--rx-period',type=int,required=True);p.add_argument('--phase',type=int,default=2500);p.add_argument('--clock',type=int,default=64);p.add_argument('--baud',type=int,default=4);p.add_argument('--tb',type=Path,required=True);a=p.parse_args()
 assert a.rx_period in (9900,10000,10100) and a.phase==2500
 a.out.mkdir(parents=True,exist_ok=False);tb=bench()
 if a.tb.exists():assert a.tb.read_text(encoding='utf-8')==tb
 else:a.tb.write_text(tb,encoding='utf-8',newline='\n')
 s=Scenario(a.out,a.clock,a.baud,a.rx_period,a.phase);r=s.run();r.update(tb_sha256=digest(a.tb),at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());(a.out/'FREEZE.json').write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:r[k] for k in ('events','checks','tx_edges','rx_edges','vectors_sha256')}))
if __name__=='__main__':main()
