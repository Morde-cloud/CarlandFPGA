"""Isolated faulty-wrapper counterexamples selected from pre-author frozen rows.

No new input or expected value is synthesized after author review. Selection only
narrows complete reset-bounded segments of the existing c3/w6/t64 frozen trace.
All 34 expected public fields remain checked. Correct-source subset controls run
first; each faulty copy must compile and fail at the named transport field.
"""
from pathlib import Path
import json,hashlib,subprocess,datetime,re,shutil
E=Path(__file__).parent;W=E.parents[5];tool=Path('D:/modelsim1/win64')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
fields=json.loads((E/'frozen-oracle/result.json').read_bytes())['fields'];base=12
frozen=E/'frozen-oracle/c3_w6_t64.vectors.txt';lines=frozen.read_text().splitlines();rows=[[int(v,16) for v in s.split()] for s in lines[1:]]
assert len(rows)==int(lines[0]);idx={s:base+i for i,s in enumerate(fields)}
assert sha(E/'author-first-read/source.sv')=='d8c33ebad98acca113e18dbc5831643646663b946714af139d8b1637047356f3'
source=(E/'author-first-read/source.sv').read_text();tb=E/'frozen-oracle/tb.sv'
target=None
for i in range(1,len(rows)):
    r=rows[i];old=rows[i-1]
    if r[0]==1 and r[1:4]==[0,0,1] and r[11]==1 and old[idx['out_valid']]==1 and old[11]==0:
        if r[4:9]==[old[idx[k]] for k in ['expected_period','expected_high0','expected_high1','expected_high2','expected_tag']]:target=i;break
assert target is not None
start=max(i for i in range(target) if rows[i][1])
obs=next(i for i in range(target+1,len(rows)) if rows[i][idx['window_started']])
assert not any(r[1] for r in rows[target+1:obs+1]) and rows[obs][idx['out_valid']]==0
mis=None
for i,r in enumerate(rows):
    raw=[r[idx[x]] for x in ['out_period','out_high0','out_high1','out_high2','out_tag']]
    exp=[r[idx[x]] for x in ['expected_period','expected_high0','expected_high1','expected_high2','expected_tag']]
    if r[idx['window_active']] and not r[idx['raw_fault_events']] and raw[0]>0 and raw!=exp and not r[idx['out_valid']]:mis=i;break
assert mis is not None
misstart=max(i for i in range(mis) if rows[i][1])

late=source.replace('assign transfer_now = cfg_valid && g_cfg_ready;','assign transfer_now = accepted || rejected; // DELIBERATELY WRONG registered-late invalidation')
assert late!=source
cache='''
    // DELIBERATELY WRONG: retain an old raw slot across transfers and replay it
    // after a same-tag application, without a new complete sampled interval.
    logic bad_saved_valid;
    logic [COUNT_AW-1:0] bad_period,bad_high0,bad_high1,bad_high2;
    logic [WITNESS_AW-1:0] bad_start,bad_end;
    logic [TAG_AW-1:0] bad_tag;
    wire bad_replay = window_started_q && bad_saved_valid &&
                      (expected_tag_q == bad_tag);
    always_ff @(posedge clk) begin
        if (rst || stop) begin
            bad_saved_valid <= 0;
            bad_period <= 0; bad_high0 <= 0; bad_high1 <= 0; bad_high2 <= 0;
            bad_start <= 0; bad_end <= 0; bad_tag <= 0;
        end else if (c_out_period != 0) begin
            bad_saved_valid <= 1;
            bad_period <= c_out_period; bad_high0 <= c_out_high0;
            bad_high1 <= c_out_high1; bad_high2 <= c_out_high2;
            bad_start <= c_out_start; bad_end <= c_out_end; bad_tag <= c_out_tag;
        end
    end
'''
aba=source.replace('endmodule',cache+'\nendmodule')
for f in ['period','high0','high1','high2','start','end','tag']:
    aba,n=re.subn(r'assign out_'+f+r'\s*= c_out_'+f+r';','assign out_'+f+' = bad_replay ? bad_'+f+' : c_out_'+f+';',aba);assert n==1
old='assign out_valid = transport_window && c_armed && !raw_fault &&\n                       c_out_valid && raw_equal;'
assert old in aba
aba=aba.replace(old,'assign out_valid = (transport_window && c_armed && !raw_fault && c_out_valid && raw_equal) || bad_replay;')
mismatch=source.replace(old,'assign out_valid = transport_window && c_armed && !raw_fault && c_out_valid; // DELIBERATELY WRONG: ignore comparison')
assert mismatch!=source
cases=[('late-transfer',late,start,target,'pre'),('same-tag-cache',aba,start,obs,'field=18'),('mismatch-admitted',mismatch,misstart,mis,'field=18')]
out=E/'negative-controls';out.mkdir();report={'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'frozen_vectors_sha256':sha(frozen),'original_source_sha256':sha(E/'author-first-read/source.sv'),'original_tb_sha256':sha(tb),'selection':'exact contiguous reset-bounded original frozen rows; no expected/input edits; all fields checked','cases':[],'commands':[],'status':'started'}
def save():(out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
def run(d,name,cmd):
    p=subprocess.run([str(x) for x in cmd],cwd=d,capture_output=True,timeout=180)
    (d/(name+'.stdout.txt')).write_bytes(p.stdout);(d/(name+'.stderr.txt')).write_bytes(p.stderr)
    report['commands'].append({'name':str(d.relative_to(out))+'/'+name,'command':[str(x) for x in cmd],'cwd':str(d),'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()});save();return p
try:
    for name,mutant,first,last,marker in cases:
        d=out/name;d.mkdir();selected=rows[first:last+1]
        v=(str(len(selected))+'\n'+'\n'.join(' '.join(format(x,'x') for x in r) for r in selected)+'\n').encode('ascii')
        (d/'vectors.txt').write_bytes(v);(d/'correct.sv').write_bytes((E/'author-first-read/source.sv').read_bytes());(d/'mutant.sv').write_text(mutant,encoding='utf-8',newline='\n');shutil.copyfile(tb,d/'tb.sv')
        for name0 in ('generator','capture'):shutil.copyfile(E/'run-01'/(name0+'.sv'),d/(name0+'.sv'))
        (d/'run.do').write_bytes(b'onerror {quit -code 1}\nrun -all\nquit -code 0\n')
        assert run(d,'vlib',[tool/'vlib.exe','work']).returncode==0
        p=run(d,'compile-correct',[tool/'vlog.exe','-sv','-work','work','generator.sv','capture.sv','correct.sv','tb.sv']);assert p.returncode==0 and b'** Error' not in p.stdout+p.stderr
        args=[tool/'vsim.exe','-c','-onfinish','stop','work.main_tb_pwm_applied_capture','-gCOUNT_W=3','-gWITNESS_W=6','-gTAG_W=64','+VECTORS=vectors.txt','-do','run.do']
        p=run(d,'correct',[*args,'+TRACE=correct.ports.txt']);assert p.returncode==0 and b'MAIN_APPLIED_CAPTURE_PASS' in p.stdout and not re.search(rb'\*\* (?:Error|Fatal)',p.stdout+p.stderr)
        p=run(d,'compile-mutant',[tool/'vlog.exe','-sv','-work','work','mutant.sv']);assert p.returncode==0 and b'** Error' not in p.stdout+p.stderr
        p=run(d,'mutant',[*args,'+TRACE=mutant.ports.txt']);raw=p.stdout+p.stderr
        fatal=re.search(rb'\*\* Fatal:[^\r\n]*PUBLIC_PORT_MISMATCH[^\r\n]*',raw)
        assert fatal and marker.encode() in fatal.group() and b'MAIN_APPLIED_CAPTURE_PASS' not in raw,(name,raw)
        rec={'name':name,'frozen_first_row':first,'frozen_last_row':last,'selected_sampled_edges':sum(r[0] for r in selected),'selected_rows':len(selected),'vectors_sha256':sha(d/'vectors.txt'),'mutant_sha256':sha(d/'mutant.sv'),'correct_control':'passed','mutant_compiled':True,'actual_public_counterexample':fatal.group().decode(),'mutant_exit_code':p.returncode,'expected_rejection':True}
        report['cases'].append(rec);save()
    report['status']='three_actual_public_port_rejections';save();print(json.dumps(report['cases']))
except Exception as e:report.update(status='failed',error=repr(e));save();raise
