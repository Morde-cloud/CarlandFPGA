"""Independent real-composition ModelSim runner. New attempts only; no production edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import traceback
import types

REPO=Path('D:/pynq/CarlandFPGA')
PRODUCT=REPO/'.local/worktrees/deepeye-implementation-20261014/competition/deepeye'
SOURCE=PRODUCT/'fpga/diagnostic/g05_capture/composition_independent'
EVIDENCE=REPO/'.local/deployment/node-b/evidence/g05-capture-20261026-59/composition-independent'
MODEL=Path('D:/modelsim1/win64')
OWNED=PRODUCT/'tools/diagnostic/g05_capture/build/owned_process.py'
OWNED_SHA='1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692'
PINS={
 'fpga/control3d/deepeye_atomic_pwm.sv':'9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428',
 'fpga/control3d/deepeye_pwm_coherent_capture.sv':'4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456',
 'fpga/diagnostic/g05_capture/mapper/deepeye_g05_command_map.sv':'51f2ef228bf531e1476fd59e4068a2f1ad0b83110601104d3d1ad6764948beb4',
 'fpga/diagnostic/g05_capture/mapper/deepeye_g05_curvature_rom.svh':'d462859e6893cd90fb33ad9ddd481aaa7ee46937ba3d197431f81b602357a83c',
 'fpga/diagnostic/g05_capture/engine/deepeye_g05_capture_engine.sv':'6bc6db70e3c9e7d1e1f69846b2321ca561e5330c655d2e419cad64a6f7a15c2b',
 'fpga/diagnostic/g05_capture/axi/deepeye_g05_axi.sv':'e4016741b8d127c363b6b2ff691798869e0071336d392d3481a017eab2ff97af'}
CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
CASES={0:'full_capture_latch_read_stall_duplicate_stop_reset',1:'identity_staging_changed_duplicate',
 2:'pending_atomic_boundary_full_capture',3:'old_TTL_expires_with_pending',4:'same_edge_STOP_expiry_pending',
 5:'profile_lock_combined_curvature_signed_min',6:'missing_all_inputs_watchdog',7:'stuck_high_input',
 8:'wrong_high_plus3',9:'wrong_period_plus3',10:'crossframe_witnesses',11:'skew3_rejection',
 12:'skew2_and_high2_tolerance',13:'distinct_code_wrong_wiring',99:'width_oracle_mutation_baseline'}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')
def require(condition,message):
    if not condition:raise RuntimeError(message)


def parse_success(transcript,case_id,raw):
    lines=[line[2:] if line.startswith('# ') else line for line in transcript.splitlines()]
    passes=[s for s in lines if s.startswith('G05_COMPOSITION_PASS')]
    stats=[s for s in lines if s.startswith('G05_COMPOSITION_STATS')]
    require(len(passes)==len(stats)==1,'unique line-anchored PASS and STATS required')
    p=re.fullmatch(r'G05_COMPOSITION_PASS case=(\d+) assertions=(\d+)',passes[0])
    s=re.fullmatch(r'G05_COMPOSITION_STATS case=(\d+) assertions=(\d+) stall_cycles=(\d+) pwm_edges=(\d+) pin_edges=(\d+) cycles=(\d+)',stats[0])
    require(p is not None and s is not None,'complete exact statistics format required')
    values=dict(zip(('case','assertions','stall_cycles','pwm_edges','pin_edges','cycles'),map(int,s.groups())))
    require(int(p[1])==values['case']==case_id and int(p[2])==values['assertions']>=50,'PASS/STATS case/assertion mismatch')
    ends=re.findall(r'^END,(\d+),(\d+),assertions=(\d+)\s*$',raw,re.M)
    require(len(ends)==1 and int(ends[0][2])==values['assertions'],'raw trace end/statistics mismatch')
    require(values['cycles']>0 and values['stall_cycles']<=values['cycles'],'invalid cycle statistics')
    require(not re.search(r'(?:\*\*\s+(?:Fatal|Error):|G05_COMPOSITION_FAIL)',transcript),'error/failure in transcript')
    return values


def parser_controls(out):
    good='G05_COMPOSITION_STATS case=99 assertions=50 stall_cycles=0 pwm_edges=6 pin_edges=6 cycles=100\nG05_COMPOSITION_PASS case=99 assertions=50\n'
    raw='END,1000,100,assertions=50\n'
    mutations={'substring_marker':good.replace('G05_COMPOSITION_PASS','noise G05_COMPOSITION_PASS'),
        'duplicate_stats':good+good.splitlines()[0]+'\n','duplicate_pass':good+good.splitlines()[1]+'\n',
        'mismatched_assertions':good.replace('PASS case=99 assertions=50','PASS case=99 assertions=51'),
        'trailing_marker_text':good.replace('PASS case=99 assertions=50','PASS case=99 assertions=50 ignored'),
        'missing_stats':good.splitlines()[1]+'\n','fatal_after_pass':good+'** Fatal: injected\n',
        'wrong_case':good.replace('case=99','case=98')}
    rows=[{'case':'valid_exact','result':parse_success(good,99,raw)}]
    for name,value in mutations.items():
        try:parse_success(value,99,raw)
        except RuntimeError as error:rows.append({'case':name,'rejected':True,'reason':str(error)})
        else:raise AssertionError('bad parser control accepted: '+name)
    for name,value in (('duplicate_raw_end',raw+raw),('inconsistent_raw_end',raw.replace('50','51'))):
        try:parse_success(good,99,value)
        except RuntimeError as error:rows.append({'case':name,'rejected':True,'reason':str(error)})
        else:raise AssertionError('bad raw stats control accepted')
    save(out/'PARSER_CONTROLS.json',rows)
    return len(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--attempt',required=True)
    ap.add_argument('--cases',default='99,1,5,3,4,0,2,6,7,8,9,10,11,12,13')
    args=ap.parse_args()
    require(re.fullmatch(r'attempt-[0-9]{2}',args.attempt),'new numbered attempt required')
    selected=[int(c) for c in args.cases.split(',')]
    require(len(set(selected))==len(selected) and set(selected)<=set(CASES),'unique known cases only')
    out=EVIDENCE/args.attempt;out.mkdir(parents=True,exist_ok=False)
    result={'status':'failed','task':'DEEPEYE-IMPLEMENTATION-20261014/v1',
        'work_id':'B-G05-REAL-COMPOSITION-REVIEW-20261026-59-v1','requirements_sha256':CONTRACT,
        'commands':[],'cases':[],'selected_cases':selected,'production_pins':PINS,
        'scope':'real RTL composition simulation; external pins are synthetic fixtures; no board or G05 acceptance'}
    try:
        require(sha(OWNED)==OWNED_SHA,'read-only owned_process helper changed')
        helper=types.ModuleType('composition_owned_process');exec(compile(OWNED.read_bytes(),str(OWNED),'exec'),helper.__dict__)
        shutil.copyfile(OWNED,out/'owned_process.snapshot.py')
        job_helper=REPO/'fpga_mesh/windows_job.py';shutil.copyfile(job_helper,out/'windows_job.snapshot.py')
        src=out/'rtl';src.mkdir()
        for name,value in PINS.items():
            require(sha(PRODUCT/name)==value,'finalized source changed: '+name)
            shutil.copyfile(PRODUCT/name,src/Path(name).name)
        bench=out/'bench';bench.mkdir()
        for p in SOURCE.iterdir():
            require(p.is_file(),'unexpected author source subdirectory');shutil.copyfile(p,bench/p.name)
        result['author_sources']={p.name:sha(p) for p in bench.iterdir()}
        result['parser_controls']=parser_controls(out)
        ini=out/'modelsim.ini'
        library=out/'library'
        ini.write_text('[Library]\nwork = '+library.as_posix()+'\nothers = D:/modelsim1/modelsim.ini\n',encoding='ascii')
        os.environ['MODELSIM']=str(ini)
        def run(label,argv,timeout=60):
            d=out/label;d.mkdir()
            r=helper.run_owned([str(x) for x in argv],d,timeout,out/'windows_job.snapshot.py')
            result['commands'].append({'label':label,'pid':r.get('original_pid'),'exit':r.get('exit_code'),
                'job_terminal_confirmed':r.get('job_terminal_confirmed'),'timed_out':r.get('timed_out')})
            save(d/'source_use.json',{'production_pins':PINS,'author_sources':result['author_sources']})
            require(r.get('termination_confirmed') is True and r.get('job_terminal_confirmed') is True and not r.get('timed_out'),label+': owned process termination failure')
            print(json.dumps({'command':label,'pid':r.get('original_pid'),'exit':r.get('exit_code'),'whole_job_empty':True}),flush=True)
            return r,d
        def successful(label,argv):
            r,d=run(label,argv);require(r.get('exit_code')==0,label+': nonzero exit');return d
        successful('01-vlog-version',[MODEL/'vlog.exe','-version'])
        successful('02-vsim-version',[MODEL/'vsim.exe','-version'])
        successful('03-vlib',[MODEL/'vlib.exe',library])
        sv=[src/Path(n).name for n in PINS if n.endswith('.sv')]+[bench/'tb_g05_real_composition.sv']
        successful('04-compile',[MODEL/'vlog.exe','-sv','-work','work','+incdir+'+str(src),*sv])
        do=out/'run.do'
        do.write_text('onerror {quit -code 1}\nonbreak {\n  if {[catch {examine -radix decimal sim:/tb_g05_real_composition/completion_status} done]} {quit -code 3}\n  if {$done == 1} {quit -code 0}\n  quit -code 2\n}\nonfinish stop\nrun -all\nquit -code 4\n',encoding='ascii')
        def simulate(case,label,lib='work'):
            folder=out/label
            argv=[MODEL/'vsim.exe','-c','-voptargs=+acc','-lib',lib,'tb_g05_real_composition',
                '+CASE='+str(case),'+TRACE='+(folder/'ports.csv').as_posix(),'-do',do,'-l',folder/'transcript.log']
            r,d=run(label,argv,240)
            transcript=(d/'transcript.log').read_text(encoding='utf-8',errors='replace') if (d/'transcript.log').exists() else ''
            raw=(d/'ports.csv').read_text(encoding='utf-8',errors='replace') if (d/'ports.csv').exists() else ''
            return r,transcript,raw
        for case in selected:
            r,transcript,raw=simulate(case,f'case-{case:02}')
            case_result={'case':case,'name':CASES[case],'exit':r.get('exit_code')}
            try:
                require(r.get('exit_code')==0,'simulation nonzero exit')
                case_result['stats']=parse_success(transcript,case,raw);case_result['status']='passed'
            except RuntimeError as error:case_result.update(status='failed',reason=str(error))
            result['cases'].append(case_result)
            save(out/f'case-{case:02}'/'RESULT.json',case_result)
            print(json.dumps(case_result),flush=True)
        # One deliberate, isolated defect: speed high +1 tick. Production bytes stay untouched.
        mutant=out/'mutation';shutil.copytree(src,mutant)
        mp=mutant/'deepeye_g05_command_map.sv';original=mp.read_text(encoding='utf-8')
        needle="high_speed = 32'd50000 + 32'd1000"
        require(original.count(needle)==1,'isolated mutation site mismatch')
        mp.write_text(original.replace(needle,"high_speed = 32'd50001 + 32'd1000"),encoding='utf-8',newline='\n')
        save(out/'MUTATION.json',{'type':'isolated RTL mutation','original_sha256':PINS['fpga/diagnostic/g05_capture/mapper/deepeye_g05_command_map.sv'],
            'mutated_sha256':sha(mp),'change':'speed PWM high base50000 ->50001; period remains2000000',
            'production_modified':False,'oracle':'public speed output high must be70000 for code20'})
        mutlib=out/'mutant_library'
        with ini.open('a',encoding='ascii') as f:f.write('mutant = '+mutlib.as_posix()+'\n')
        successful('05-mutant-vlib',[MODEL/'vlib.exe',mutlib])
        msv=[mutant/Path(n).name for n in PINS if n.endswith('.sv')]+[bench/'tb_g05_real_composition.sv']
        successful('06-mutant-compile',[MODEL/'vlog.exe','-sv','-work','mutant','+incdir+'+str(mutant),*msv])
        r,transcript,raw=simulate(99,'mutation-control','mutant')
        detected=r.get('exit_code')!=0 and 'G05_COMPOSITION_ASSERTION_FAILED' in transcript and 'output high channel2 expected70000 actual70001' in transcript and not re.search(r'^#?\s*G05_COMPOSITION_PASS',transcript,re.M)
        result['mutation_detected']=detected
        require(all(sha(PRODUCT/n)==v and sha(src/Path(n).name)==v for n,v in PINS.items()),'production or immutable snapshot changed')
        require(result['author_sources']=={p.name:sha(p) for p in SOURCE.iterdir()},'author source changed during run')
        result['status']='passed' if detected and all(c['status']=='passed' for c in result['cases']) else 'findings_or_failures'
        result['assertions']=sum(c.get('stats',{}).get('assertions',0) for c in result['cases'])
    except BaseException:
        result['failure']=traceback.format_exc()
    finally:
        save(out/'RESULT.json',result)
        save(out/'FILE_MANIFEST.json',{p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file()})
        print(json.dumps({'status':result['status'],'out':str(out),'cases':len(result['cases']),'assertions':result.get('assertions'),
                          'mutation_detected':result.get('mutation_detected'),'failure':result.get('failure')},indent=2),flush=True)
    return 0 if result['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
