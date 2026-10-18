import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
import argparse

p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--positive',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--tools',default='D:/modelsim1',type=Path);a=p.parse_args()
H=Path(__file__).resolve().parent;O=a.output.resolve();O.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('maincheck',H/'main_encoder_review.py');check=importlib.util.module_from_spec(spec);spec.loader.exec_module(check)
cases=json.loads((a.positive/'cases.json').read_bytes());original=(a.positive/'ports.txt').read_text();check.verify(cases,a.positive/'ports.txt')
lines=original.splitlines();changes=[]
def first(kind,predicate=lambda t:True):return next(i for i,x in enumerate(lines) if x.split()[0]==kind and predicate(x.split()))
for typ,index in [('C',3),('S',4),('S',5),('H',3),('H',4),('H',5),('H',6),('H',7),('H',8),('H',9),('O',3),('O',4),('O',5),('X',3),('X',4),('END',1),('END',2),('END',3),('END',4),('END',5),('END',6)]:
    i=first(typ);row=lines[i].split();row[index]=str(int(row[index])+1)
    mutant=lines.copy();mutant[i]=' '.join(row);changes.append((typ+'-field'+str(index),mutant))
for typ in ['C','S','H','O','X','D','END']:
    i=first(typ);mutant=lines.copy();mutant.pop(i);changes.append((typ+'-missing',mutant))
    mutant=lines.copy();mutant.insert(i,lines[i]);changes.append((typ+'-duplicate',mutant))
log_results=[]
for name,mutant in changes:
    file=O/(name+'.txt');file.write_text('\n'.join(mutant)+'\n',encoding='ascii')
    try:check.verify(cases,file)
    except (AssertionError,ValueError,KeyError,IndexError) as e:log_results.append({'name':name,'rejected':True,'error_type':type(e).__name__,'sha256':check.sha(file)})
    else:raise AssertionError('checker accepted corrupted log '+name)

source=a.source.read_bytes()
patches=[
 ('floor-truncation',b"q_bits = 18'd0 - ({1'b0, div_quot} + 18'd1);",b"q_bits = 18'd0 - {1'b0, div_quot};"),
 ('nonzero-padding',b'byte_mem[byte_wr[7:0]] <= cur_byte << (8 - fill);',b"byte_mem[byte_wr[7:0]] <= (cur_byte << (8 - fill)) | 8'd1;"),
 ('ignored-cancel',b'if (rst || cancel) begin',b'if (rst) begin'),
 ('ignored-output-backpressure',b'if (m_ready) begin',b"if (1'b1) begin")
]
rtl_results=[]
for name,old,new in patches:
    assert source.count(old)==1,(name,'source anchor changed')
    file=O/(name+'.sv');file.write_bytes(source.replace(old,new))
    dest=O/(name+'-run')
    argv=[sys.executable,'-B','-X','utf8',str(H/'main_encoder_review.py'),'--rtl',str(file),'--tb',str(H/'main_encoder_port_tb.sv'),'--modelsim-home',str(a.tools),'--output',str(dest)]
    r=subprocess.run(argv,capture_output=True,timeout=120)
    (O/(name+'.stdout.txt')).write_bytes(r.stdout);(O/(name+'.stderr.txt')).write_bytes(r.stderr)
    assert r.returncode!=0,(name,'defective RTL accepted')
    compile_result=json.loads((dest/'vlog.command.json').read_bytes());sim_result=json.loads((dest/'vsim.command.json').read_bytes())
    assert compile_result['exit_code']==0
    rtl_results.append({'name':name,'rtl_sha256':check.sha(file),'review_exit':r.returncode,'compile_exit':compile_result['exit_code'],'simulator_exit':sim_result['exit_code'],'stdout_sha256':check.sha(O/(name+'.stdout.txt')),'stderr_sha256':check.sha(O/(name+'.stderr.txt')),'argv':argv})
result={'status':'PASS_MAIN_NEGATIVE_CONTROLS','source_sha256':check.sha(a.source),'positive_ports_sha256':check.sha(a.positive/'ports.txt'),'corrupted_logs_rejected':len(log_results),'log_results':log_results,'defective_rtl_rejected':len(rtl_results),'rtl_results':rtl_results,'scope':'checker/monitor sensitivity only; mutants are not product source'}
(O/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':result['status'],'corrupted_logs_rejected':len(log_results),'defective_rtl_rejected':len(rtl_results)}))
