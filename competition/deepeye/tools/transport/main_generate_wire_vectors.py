"""Main-only wire reference, frozen before inspection of op28/29 RTL.

Packets come from struct.pack and Python's CRC library, not author functions.
Models describe public accepted input histories. No RTL files are read here.
"""
from pathlib import Path
import argparse,binascii,hashlib,json,random,struct

def packet(typ,epoch,seq,tick,payload):
 body=struct.pack('<BBBBHI',3,typ,len(payload),epoch,seq,tick)+bytes(payload)
 return b'\xa5\x5a'+body+struct.pack('<H',binascii.crc_hqx(body,65535))

SER_IN=[('rst',1),('cancel',1),('cfg_valid',1),('cfg_type',8),('cfg_epoch',8),('cfg_seq',16),('cfg_tick',32),('cfg_len',6),('p_valid',1),('p_data',8),('p_last',1),('out_ready',1)]
SER_OUT=[('cfg_ready',1),('p_ready',1),('out_valid',1),('out_data',8),('out_last',1),('out_count',6),('busy',1),('receiving',1),('faulted',1),('fault_event',1),('fault_code',2)]+[(x,32) for x in ('stat_admitted','stat_sent','stat_aborted','stat_faults')]
PAR_IN=[('rst',1),('cancel',1),('in_valid',1),('in_data',8),('out_ready',1)]
PAR_OUT=[('in_ready',1),('out_valid',1),('out_type',8),('out_epoch',8),('out_seq',16),('out_tick',32),('out_len',6),('out_payload',256),('receiving',1),('error_event',1),('error_code',2)]+[(x,32) for x in ('stat_bytes','stat_frames','stat_retired','stat_version','stat_length','stat_crc','stat_aborted')]

class Serializer:
 def __init__(self,stat):self.limit=(1<<stat)-1;self.reset();self.history=[]
 def reset(self):self.state='idle';self.meta=None;self.payload=[];self.wire=b'';self.pos=0;self.code=0;self.event=0;self.counts=[0]*4
 def inc(self,i):self.counts[i]=min(self.limit,self.counts[i]+1)
 def ports(self,x):
  gate=not(x['rst'] or x['cancel']);valid=self.state=='send' and gate;busy=self.state!='idle'
  count=(self.meta[4]+14) if busy and self.meta and self.meta[4]<=32 else 0
  return [int(self.state=='idle' and gate),int(self.state=='collect' and gate),int(valid),self.wire[self.pos] if valid else 0,int(valid and self.pos==len(self.wire)-1),count,int(busy),int(self.state=='collect'),int(self.state=='fault'),self.event,self.code,*self.counts]
 def step(self,x):
  if x['rst']:self.reset();return
  self.event=0
  if x['cancel']:
   if self.state!='idle':self.inc(2)
   self.state='idle';self.meta=None;self.payload=[];self.wire=b'';self.pos=0;self.code=0;return
  if self.state=='idle':
   if x['cfg_valid']:
    self.inc(0);self.meta=tuple(x[n] for n in ('cfg_type','cfg_epoch','cfg_seq','cfg_tick','cfg_len'));self.payload=[];self.pos=0
    if x['cfg_len']>32:self.state='fault';self.code=1;self.event=1;self.inc(3)
    elif x['cfg_len']==0:self.wire=packet(*self.meta[:4],[]);self.state='send';self.history.append(self.wire.hex())
    else:self.state='collect'
  elif self.state=='collect' and x['p_valid']:
   if bool(x['p_last'])!=(len(self.payload)==self.meta[4]-1):self.state='fault';self.code=2;self.event=1;self.inc(3)
   else:
    self.payload.append(x['p_data'])
    if len(self.payload)==self.meta[4]:self.wire=packet(*self.meta[:4],self.payload);self.state='send';self.history.append(self.wire.hex())
  elif self.state=='send' and x['out_ready']:
   self.pos+=1
   if self.pos==len(self.wire):self.state='idle';self.meta=None;self.inc(1)

class Parser:
 def __init__(self,stat):self.limit=(1<<stat)-1;self.reset();self.history=[]
 def reset(self):self.buf=bytearray();self.slot=None;self.event=0;self.code=0;self.counts=[0]*7
 def inc(self,i):self.counts[i]=min(self.limit,self.counts[i]+1)
 def ports(self,x):
  gate=not(x['rst'] or x['cancel']);v=self.slot is not None and gate
  fields=self.slot if v else (0,0,0,0,0,0)
  return [int(self.slot is None and gate),int(v),*fields,int(bool(self.buf)),self.event,self.code,*self.counts]
 def bad(self,code,b):self.event=1;self.code=code;self.inc(code+2);self.buf=bytearray([165] if b==165 else [])
 def step(self,x):
  if x['rst']:self.reset();return
  self.event=0;self.code=0
  if x['cancel']:
   if self.buf or self.slot is not None:self.inc(6)
   self.buf=bytearray();self.slot=None;return
  if self.slot is not None:
   if x['out_ready']:self.slot=None;self.inc(2)
   return
  if not x['in_valid']:return
  b=x['in_data'];self.inc(0)
  if not self.buf:
   if b==165:self.buf.append(b)
   return
  if len(self.buf)==1:
   if b==90:self.buf.append(b)
   elif b!=165:self.buf.clear()
   return
  if len(self.buf)==2 and b!=3:self.bad(1,b);return
  if len(self.buf)==4 and b>32:self.bad(2,b);return
  self.buf.append(b)
  if len(self.buf)>=5 and len(self.buf)==14+self.buf[4]:
   f=bytes(self.buf)
   if binascii.crc_hqx(f[2:-2],65535)!=int.from_bytes(f[-2:],'little'):self.bad(3,b);return
   self.slot=(f[3],f[5],int.from_bytes(f[6:8],'little'),int.from_bytes(f[8:12],'little'),f[4],int.from_bytes(f[12:-2].ljust(32,b'\0'),'little'))
   self.inc(1);self.buf.clear();self.history.append(f.hex())

def bench(stem,ins,outs):
 module='deepeye_'+stem;total=sum(w for _,w in ins)+2*sum(w for _,w in outs)
 def decl(kind,n,w):return f'{kind} '+(f'[{w-1}:0] ' if w>1 else '')+n+';'
 lines=['`timescale 1ns/1ps','// Main vector checker: all expectations come from frozen Python public-history reference.',f'module main_tb_{stem};','parameter integer STAT_W=32;','localparam integer SW=(STAT_W<2)?2:((STAT_W>32)?32:STAT_W);','reg clk=0;always #5 clk=~clk;']
 lines += [decl('reg',n,w) for n,w in ins]
 lines += [('wire [SW-1:0] '+n+';' if n.startswith('stat_') else decl('wire',n,w)) for n,w in outs]
 lines += [decl('reg',tag+'_'+n,w) for tag in ('pre','post') for n,w in outs]
 lines += [f'{module} #(.STAT_W(STAT_W)) dut(.*);',f'reg [{total-1}:0] row;','integer fd,got,cycles=0,checks=0;','task automatic eq(input string field,input logic[255:0] actual,input logic[255:0] expected);','begin checks++;if(actual!==expected)begin $display("MAIN_MISMATCH cycle=%0d field=%s got=%0h expected=%0h",cycles,field,actual,expected);$fatal(1,"main numeric mismatch");end end endtask','initial begin']
 lines += [f'{n}='+('1' if n=='rst' else '0')+';' for n,_ in ins]
 lines += [f'$display("MAIN_BEGIN kind={stem} stat=%0d",STAT_W);','fd=$fopen("vectors.hex","r");if(!fd)$fatal(1,"missing vectors");','while(!$feof(fd))begin','got=$fscanf(fd,"%h\\n",row);if(got==1)begin','@(negedge clk);{'+','.join([n for n,_ in ins]+[tag+'_'+n for tag in ('pre','post') for n,_ in outs])+'}=row;#1;']
 for tag in ('pre','post'):
  if tag=='post':lines += ['@(posedge clk);#1;cycles++;']
  for n,_ in outs:
   mask=n in ('out_data','out_last') if stem=='wire_serializer' else n in ('out_type','out_epoch','out_seq','out_tick','out_len','out_payload')
   actual=f'(out_valid?{n}:0)' if mask else n
   lines.append(f'eq("{tag}_{n}",{actual},{tag}_{n});')
 lines += ['end else if(!$feof(fd))$fatal(1,"malformed vector row");','end','$fclose(fd);',f'$display("MAIN_STATS cycles=%0d checks=%0d",cycles,checks);','$display("MAIN_PASS");$finish;end','endmodule']
 return '\n'.join(lines)+'\n'

def generate(kind,stat,out,tb):
 out.mkdir(parents=True,exist_ok=False);rng=random.Random(2026102400+stat+(kind=='wire_parser'));m=Serializer(stat) if kind=='wire_serializer' else Parser(stat);ins=SER_IN if kind=='wire_serializer' else PAR_IN;outs=SER_OUT if kind=='wire_serializer' else PAR_OUT
 lines=[];labels=[]
 def tick(label='',**kw):
  x={n:0 for n,_ in ins};x.update(kw);pre=m.ports(x);m.step(x);post=m.ports(x)
  values=[x[n] for n,_ in ins]+pre+post;widths=[w for _,w in ins]+[w for _,w in outs]*2;v=0
  for value,w in zip(values,widths):assert 0<=value<(1<<w),(value,w);v=(v<<w)|value
  lines.append(f'{v:0{(sum(widths)+3)//4}x}\n')
  if label:labels.append({'cycle':len(lines),'label':label})
 def idle(n=1,ready=0):
  for _ in range(n):tick(out_ready=ready)
 tick('initial_reset',rst=1)
 if kind=='wire_serializer':
  def cfg(n,k=0):tick('config',cfg_valid=1,cfg_type=k&255,cfg_epoch=(k*17)&255,cfg_seq=(65535-k)&65535,cfg_tick=(0xffffffff-k*257)&0xffffffff,cfg_len=n,p_valid=1,p_data=91,p_last=1)
  def load(n,k):
   cfg(n,k)
   for j in range(n):
    idle(rng.randrange(3));tick(p_valid=1,p_data=(k+j*37)&255,p_last=int(j==n-1),out_ready=rng.randrange(2))
  def drain():
   while m.state=='send':tick(out_ready=int(rng.randrange(4)!=0),cfg_valid=1,cfg_len=32,p_valid=1,p_data=rng.randrange(256),p_last=rng.randrange(2))
  for n in range(33):load(n,n);drain()
  for b in range(256):load(1,b);drain()
  for n in range(33,64):cfg(n,n);idle(4);tick(cancel=1,out_ready=1)
  for n in (1,2,16,32):
   cfg(n);tick(p_valid=1,p_data=165,p_last=int(n!=1));idle(3);tick(cancel=1)
   cfg(n);idle(37);tick(rst=1)
  for rr in (0,1):
   for n in (0,1,16,32):
    for stop in range(n+14):
     load(n,stop)
     while m.pos<stop:tick(out_ready=1)
     tick('abort_output_phase',rst=rr,cancel=1,out_ready=1,cfg_valid=1,cfg_len=0);tick(rst=rr,cancel=1);idle()
  for j in range(1000):
   if m.state=='idle':cfg(rng.randrange(64),j)
   elif m.state=='collect':tick(p_valid=rng.randrange(2),p_data=rng.randrange(256),p_last=rng.randrange(2),cancel=int(rng.randrange(10)==0))
   elif m.state=='fault':tick(cancel=int(rng.randrange(4)==0),out_ready=1)
   else:tick(out_ready=rng.randrange(2),cancel=int(rng.randrange(20)==0))
  tick(cancel=1);idle();tick(rst=1,cancel=1)
 else:
  def send(blob,ready=True):
   for b in blob:
    while m.slot is not None:tick(in_valid=1,in_data=b,out_ready=1)
    idle(rng.randrange(2),int(ready));tick(in_valid=1,in_data=b,out_ready=int(ready))
   idle(2,int(ready))
  for n in range(33):send(packet(n,255-n,65535-n,0xffffffff-n*65537,[(n+i*37)&255 for i in range(n)]),False);idle(5,0);idle(1,1)
  for b in range(256):send(packet(b,b,(b<<8)|b,b*0x01010101,[b]))
  send(b'noise\xa5\xa5\x5a\xff\xa5\x5a\x03\x01\xff')
  for n in (0,1,16,32):
   good=packet(165,90,0xa55a,0x01234567,list(range(n)))
   for pos in range(len(good)):
    for bit in (0,7):
     bad=bytearray(good);bad[pos]^=1<<bit;send(bad);send(b'\x00'*48);send(good)
   for cutoff in range(1,len(good)+1):
    for rr in (0,1):
     send(good[:cutoff],False);tick('abort_input_phase',rst=rr,cancel=1,in_valid=1,in_data=165,out_ready=1);tick(rst=rr,cancel=1);idle()
  for _ in range(12000):tick(in_valid=int(rng.randrange(4)!=0),in_data=rng.randrange(256),out_ready=rng.randrange(2),cancel=int(rng.randrange(113)==0))
  send(packet(255,0,65535,0xffffffff,list(range(32))),False);idle(5);idle(1,1);send(packet(0,255,0,0,[]),False);idle(5);tick(cancel=1);tick(rst=1,cancel=1)
 data=''.join(lines).encode();(out/'vectors.hex').write_bytes(data);tbtext=bench(kind,ins,outs)
 if tb.exists():assert tb.read_text(encoding='utf-8')==tbtext
 else:tb.parent.mkdir(parents=True,exist_ok=True);tb.write_text(tbtext,encoding='utf-8',newline='\n')
 receipt={'kind':kind,'stat':stat,'cycles':len(lines),'checks':len(lines)*2*len(outs),'vectors_sha256':hashlib.sha256(data).hexdigest(),'tb_sha256':hashlib.sha256(tb.read_bytes()).hexdigest(),'oracle_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'packet_history':m.history,'labels':labels,'author_RTL_read':False,'source':'struct.pack plus binascii.crc_hqx; public histories only'}
 (out/'FREEZE.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ('packet_history','labels')}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=('wire_serializer','wire_parser'),required=True);p.add_argument('--stat',type=int,choices=(2,32),default=32);p.add_argument('--out',type=Path,required=True);p.add_argument('--tb',type=Path,required=True);a=p.parse_args();generate(a.kind,a.stat,a.out,a.tb)
