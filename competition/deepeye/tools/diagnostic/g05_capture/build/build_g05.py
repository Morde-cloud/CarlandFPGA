"""Offline by default. A future full G05 build needs a new exact main authorization."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import uuid
import xml.etree.ElementTree as ET
from hwh_guard import INSTANCE, VLNV, PORTS, verify_hwh
from owned_process import run_owned, require_owned_success, utc, digest, record, write_json, require

TASK='DEEPEYE-IMPLEMENTATION-20261014'
WORK='B-G05-BUILD-PREP-20261026-59-v1'
MAIN='01a13b55-095b-7461-8dd5-5476a130bd82'
CONTRACT='c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
DESIGN='1011259415a0916054eb580687612580bc1e5f09'
PART='xc7z020clg400-1'
FPGA='fpga/diagnostic/g05_capture/build/'
TOOLS='tools/diagnostic/g05_capture/build/'
SOURCES=('fpga/control3d/deepeye_atomic_pwm.sv','fpga/control3d/deepeye_pwm_coherent_capture.sv',
    'fpga/diagnostic/g05_capture/mapper/deepeye_g05_command_map.sv',
    'fpga/diagnostic/g05_capture/mapper/deepeye_g05_curvature_rom.svh',
    'fpga/diagnostic/g05_capture/engine/deepeye_g05_capture_engine.sv',
    'fpga/diagnostic/g05_capture/axi/deepeye_g05_axi.sv')
DEPENDENCIES=dict(zip(SOURCES[:2],('9dc8ecf96e59a2ae8467bda64572f62eb602d52db535733f236f64ff97c43428',
    '4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456')))
BUILD_FILES=tuple(FPGA+n for n in ('build_g05.tcl','g05_ports.xdc','g05_cdc.tcl','README.md'))+tuple(
    TOOLS+n for n in ('build_g05.py','hwh_guard.py','owned_process.py','test_offline.py'))
BOARD_HASHES={'board.xml':'a565dcb39737d551cbbbb73c0053b973c40bb3dce2274943370d3032c0fea9ae',
    'preset.xml':'18528f84aea4da503cdb3104f7706fabfb3b6ad09b78b25199cc316afa4c8cfe',
    'part0_pins.xml':'3c809473938e135a925b563b5371c8687ee05c4089376e7318c0c56524cc8a0f',
    'pynq_z2.jpg':'54b4bb2da4a38a647d3df030ec13fe63e427235980ce9ae1ca44ce9a91af4546'}
TOOL_HASHES={'bin/vivado.bat':'a5f91ee867cea61be4355caf9f7a784c6c34351c5c1d1618562ddda299e38a8b',
    'bin/unwrapped/win64.o/vivado.exe':'3a4e9e3f03d20cd1994dc2eff44566af7a10eaaae04429e9d460bffe3b0e86e4'}
IO_HASHES={'candidate-pinmap.json':'4d1887278b2f84475997a323f1601258fddd4b0e5a1483de398f900847371093',
    'candidate.xdc':'2877efc625c96b869b979ca8589518a066f61666868c0a9d73f5ac000628ac75'}
HELPER_SHA='3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3'
PHYSICAL_UNKNOWNS=['external_output_propagation','input_flight_time','physical_cross_channel_skew']


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def copy(source,target,expected=None):
    data=Path(source).read_bytes()
    require(expected is None or hashlib.sha256(data).hexdigest()==expected,'input hash mismatch: '+str(source))
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:stream.write(data)
    return record(target)


def literal(value):
    value=str(value).replace('\\','/')
    require(not any(c in value for c in '{}\n\r\x00'),'unsafe Tcl literal')
    return '{'+value+'}'


def hash_map(value,keys):
    require(isinstance(value,dict) and set(value)==set(keys),'exact source/tool path set required')
    require(all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in value.values()),'SHA256 required')
    return value


def acceptance(path, *, fixture=False):
    a=load(path)
    require((a.get('TEST_FIXTURE')=='synthetic-not-authority')==fixture,'synthetic acceptance cannot authorize a build')
    require(a.get('schema')==1 and a.get('task_id')==TASK and a.get('task_version')==1,'source acceptance task')
    require(a.get('director_thread_id')==MAIN and a.get('accepted') is True,'main exact source acceptance required')
    require(a.get('requirements_sha256')==CONTRACT and a.get('frozen_design')==DESIGN,'fixed contract/design')
    require(isinstance(a.get('source_commit'),str) and re.fullmatch('[0-9a-f]{40}',a['source_commit']),'exact source commit required')
    pins=hash_map(a.get('sources'),SOURCES)
    hash_map(a.get('build_files'),BUILD_FILES)
    require(all(pins[k]==v for k,v in DEPENDENCIES.items()),'immutable primitive pin changed')
    bindings=a.get('cdc_bindings')
    require(isinstance(bindings,dict) and set(bindings)=={p for p in PORTS if p.endswith('_i')},'unresolved exact CDC bindings')
    names=[]
    for port,stages in bindings.items():
        require(isinstance(stages,list) and len(stages)==3,'three exact FF D pins required')
        for name in stages:
            require(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_./\[\]-]+/D',name) and name.startswith('g05_diag_i/'),'exact final G05 hierarchy required')
            names.append(name)
    require(len(set(names))==9,'shared CDC FF pins forbidden')
    evidence=a.get('cdc_source_review')
    require(isinstance(evidence,dict) and evidence.get('reviewed_by')==MAIN,'main CDC source review required')
    require(isinstance(evidence.get('path'),str) and re.fullmatch('[0-9a-f]{64}',evidence.get('sha256','')),'CDC evidence pin required')
    require(digest(Path(evidence['path']))==evidence['sha256'],'CDC review evidence changed')
    return a


def authorization(path,accepted_path,a,out, *, fixture=False):
    auth=load(path)
    require((auth.get('TEST_FIXTURE')=='synthetic-not-authority')==fixture,'synthetic authorization cannot authorize a build')
    exact={'task_id':TASK,'task_version':1,'director_thread_id':MAIN,'authorized':True,
        'action':'full_g05_diagnostic_build','source_commit':a['source_commit'],
        'source_acceptance_sha256':digest(accepted_path),'requirements_sha256':CONTRACT,
        'physical_unknowns_acknowledged':PHYSICAL_UNKNOWNS}
    require(all(auth.get(k)==v for k,v in exact.items()),'separate exact main full-build authorization required')
    require(auth.get('work_id') and auth['work_id']!=WORK and auth.get('operation_id'),'new build work/operation required')
    require(Path(auth.get('output_directory','')).resolve()==out,'authorization bound to one new output directory')
    return auth


def verify_files(root,pins):
    for name,value in pins.items():
        require(digest(root/name)==value,'accepted file changed: '+name)


def prepare(args,out):
    root=args.product_root.resolve()
    require(not out.exists(),'existing attempt cannot be reused')
    out.mkdir(parents=True,exist_ok=False)
    write_json(out/'INTENT.json',{'task_id':TASK,'task_version':1,'work_id':WORK,'at_utc':utc(),
        'argv':sys.argv,'python':sys.executable,'python_version':platform.python_version(),
        'mode':args.mode,'requirements_sha256':CONTRACT,'requirement_ids':[f'H{i:02}' for i in range(1,16)]})
    contract=load(args.contract_json)
    require(hashlib.sha256(json.dumps(contract['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()==CONTRACT,'H01-H15 fixed hash')
    require(contract['revision']==1 and contract['contract_id']=='DEEPEYE-HUMAN-LOCK-20261014','contract identity')
    copy(args.contract_json,out/'inputs/immutable_scope.json')
    for name,value in IO_HASHES.items():copy(args.io_map_dir/name,out/'inputs/io_reference'/name,value)
    signals={r['port']:r for r in load(args.io_map_dir/'candidate-pinmap.json')['digital_signals']}
    for name,(direction,pin) in PORTS.items():
        r=signals[name]
        require(r['package_pin']==pin and r['iostandard']=='LVCMOS33' and r['bank']==34 and r['direction']=={'I':'in','O':'out'}[direction],'six-pin map mismatch')
    tooling={name:copy(root/name,out/'inputs/tooling'/name) for name in BUILD_FILES}
    dependencies={name:copy(root/name,out/'inputs/readonly_primitives'/name,value) for name,value in DEPENDENCIES.items()}
    # No changing mapper/engine/AXI bytes are frozen or accepted during default preparation.
    for name,value in BOARD_HASHES.items():copy(args.board_dir/name,out/'inputs/board_repo/pynq-z2/A.0'/name,value)
    board=ET.parse(args.board_dir/'board.xml').getroot()
    require(board.get('vendor')=='tul.com.tw' and board.find("./components/component[@name='part0']").get('part_name')==PART,'TUL board identity')
    preset=ET.parse(args.board_dir/'preset.xml').getroot()
    ps=preset.find("./ip_preset[@preset_proc_name='ps7_preset']/ip[@name='processing_system7']")
    require(ps is not None,'PS7 board preset absent')
    params={p.get('name'):p.get('value') for p in ps.findall('./user_parameters/user_parameter')}
    require(len(params)==771,'TUL preset parameter count')
    # Compare the entire original DDR setting family after applying the board preset.
    ddr={k:v for k,v in params.items() if k.startswith('CONFIG.PCW_UIPARAM_DDR_')}
    require(len(ddr)>=7,'DDR preset parameters absent')
    (out/'inputs/ddr_expected.tcl').write_text('set expected_ddr [dict create '+' '.join(literal(k)+' '+literal(v) for k,v in sorted(ddr.items()))+']\n',encoding='utf-8')
    write_json(out/'inputs/ps7_preset_parameters.json',params)
    tools={name:record(args.tool_root/name) for name in TOOL_HASHES}
    require(all(tools[n]['sha256']==h for n,h in TOOL_HASHES.items()),'installed tool hash changed')
    ips={}
    for directory,name,version in (('processing_system7_v5_5','processing_system7','5.5'),('axi_interconnect_v2_1','axi_interconnect','2.1'),('proc_sys_reset_v5_0','proc_sys_reset','5.0'),('xlconstant_v1_1','xlconstant','1.1')):
        path=args.tool_root/'data/ip/xilinx'/directory/'component.xml'
        xml=ET.parse(path).getroot();ns={'s':'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009'}
        identity=':'.join(xml.findtext('s:'+key,namespaces=ns) or '' for key in ('vendor','library','name','version'))
        require(identity==f'xilinx.com:ip:{name}:{version}','installed component identity')
        ips[identity]=record(path)
    copy(root.parents[1]/'fpga_mesh/windows_job.py',out/'inputs/windows_job.py',HELPER_SHA)
    for name in ('build_g05.tcl','g05_ports.xdc','g05_cdc.tcl'):
        copy(root/(FPGA+name),out/'inputs'/name)
    write_json(out/'SOURCE_ACCEPTANCE_TEMPLATE.json',{'schema':1,'accepted':False,'task_id':TASK,'task_version':1,
        'director_thread_id':MAIN,'requirements_sha256':CONTRACT,'frozen_design':DESIGN,'source_commit':None,
        'sources':{p:DEPENDENCIES.get(p) for p in SOURCES},'build_files':{p:tooling[p]['sha256'] for p in BUILD_FILES},
        'cdc_bindings':{p:None for p in PORTS if p.endswith('_i')},'cdc_source_review':None})
    summary={'status':'prepared_only','source_acceptance':'not_claimed','full_build_executed':False,
        'tooling':tooling,'readonly_primitives':dependencies,'tools':tools,'installed_components_read_only':ips,
        'board_hashes':BOARD_HASHES,'io_hashes':IO_HASHES,'preset_parameter_count':len(params),'ddr_parameter_count':len(ddr),
        'missing_build_inputs':['main accepted exact commit and six-file source/hash map','main accepted tooling hashes',
            'exact reviewed three-stage CDC pin bindings','separate new work/operation full-build authorization'],
        'unmeasured_physical_inputs':PHYSICAL_UNKNOWNS,'runtime_vivado_catalog':'not_queried',
        'synthesis':'not_run','implementation':'not_run','bitstream':'not_run','board':'not_run; A-only'}
    write_json(out/'PREPARATION.json',summary)
    return summary


def completion(stdout,stderr,run_id,done):
    require([line for line in stdout.splitlines() if line.startswith('G05_DIAG_COMPLETE|')]==['G05_DIAG_COMPLETE|'+run_id],'exact completion marker missing/duplicated')
    require(done.get('run_id')==run_id and done.get('top')=='g05_diag_wrapper' and done.get('bd')=='g05_diag' and done.get('part')==PART and done.get('version')=='2026.1','completed run identity')
    require(done.get('status')=='bitstream_complete_pending_hwh_check_and_main_review','completed run stage')
    require(not re.search(r'^\s*ERROR:',stdout+'\n'+stderr,re.M),'Vivado ERROR recorded')


def build(args,out,a,auth,prepared):
    root=args.product_root.resolve()
    copy(args.source_acceptance,out/'inputs/main_source_acceptance.json')
    copy(args.authorization,out/'inputs/main_build_authorization.json')
    copy(Path(a['cdc_source_review']['path']),out/'inputs/main_cdc_review',a['cdc_source_review']['sha256'])
    verify_files(root,a['sources']);verify_files(root,a['build_files'])
    flat=out/'inputs/rtl_flat'
    for name,value in a['sources'].items():copy(root/name,flat/Path(name).name,value)
    for name in SOURCES:
        text=(flat/Path(name).name).read_text(encoding='utf-8')
        includes=re.findall(r'`include\s+"([^"]+)"',text)
        expected=['deepeye_g05_curvature_rom.svh'] if name.endswith('deepeye_g05_command_map.sv') else []
        require(includes==expected,'unapproved include dependency: '+name)
    source_list=out/'inputs/rtl_sources.txt'
    source_list.write_text('\n'.join((flat/Path(n).name).as_posix() for n in SOURCES)+'\n',encoding='utf-8')
    run_id=uuid.uuid4().hex
    config=out/'inputs/build_config.tcl'
    config.write_text('\n'.join(['set run_root '+literal(out),'set run_id '+literal(run_id),
        'set build_authorized_for_run '+literal(run_id),'set source_list '+literal(source_list),
        'set board_repo '+literal(out/'inputs/board_repo'),
        'set cdc_bindings [dict create '+' '.join(literal(k)+' [list '+' '.join(literal(p) for p in v)+']' for k,v in sorted(a['cdc_bindings'].items()))+']'])+'\n',encoding='utf-8')
    argv=[r'C:\Windows\System32\cmd.exe','/d','/c',str(args.tool_root/'bin/vivado.bat'),'-mode','batch','-notrace',
        '-journal',str(out/'vivado.jou'),'-log',str(out/'vivado.log'),'-source',str(out/'inputs/build_g05.tcl'),'-tclargs',str(config)]
    # Recheck acceptance/authorization and every launch input immediately before the owned process starts.
    require(acceptance(args.source_acceptance)==a,'source acceptance changed')
    require(authorization(args.authorization,args.source_acceptance,a,out)==auth,'authorization changed')
    verify_files(root,a['sources']);verify_files(root,a['build_files'])
    for name,value in a['sources'].items():require(digest(flat/Path(name).name)==value,'snapshot changed')
    for name,value in a['build_files'].items():require(digest(out/'inputs/tooling'/name)==value,'tooling snapshot changed')
    for name in ('build_g05.tcl','g05_ports.xdc','g05_cdc.tcl'):
        require(digest(out/'inputs'/name)==a['build_files'][FPGA+name],'actual executable Tcl/XDC copy changed')
    for name,value in TOOL_HASHES.items():require(digest(args.tool_root/name)==value,'tool changed')
    for name,value in BOARD_HASHES.items():require(digest(out/'inputs/board_repo/pynq-z2/A.0'/name)==value,'board snapshot changed')
    launch_inputs={p.relative_to(out).as_posix():record(p) for p in sorted((out/'inputs').rglob('*')) if p.is_file()}
    write_json(out/'LAUNCH_INPUTS.json',launch_inputs)
    process=run_owned(argv,out,args.timeout_seconds,out/'inputs/windows_job.py')
    require_owned_success(process)
    for name,value in launch_inputs.items():require(digest(out/name)==value['sha256'],'launch input changed during build: '+name)
    verify_files(root,a['sources']);verify_files(root,a['build_files'])
    for name,value in a['sources'].items():require(digest(flat/Path(name).name)==value,'source snapshot changed during build')
    done=load(out/'VIVADO_COMPLETE.json')
    completion((out/'process.stdout.bin').read_text(encoding='utf-8',errors='replace'),
               (out/'process.stderr.bin').read_text(encoding='utf-8',errors='replace'),run_id,done)
    identity=verify_hwh(out/'artifacts/g05_diag.hwh',load(out/'BD_MAPPING.json'))
    # Require raw journals and logs for every completed synthesis run, including child OOC IP runs.
    journal_runs=[]
    for line in (out/'SYNTHESIS_RUNS.tsv').read_text(encoding='utf-8').splitlines():
        name,directory,status=line.split('\t')
        require(status=='synth_design Complete!','incomplete child synthesis run')
        directory=Path(directory).resolve()
        require(directory.is_relative_to(out),'synthesis run escaped current output')
        for filename in ('vivado.jou','runme.log'):require((directory/filename).is_file(),'missing raw child log/journal: '+name+'/'+filename)
        journal_runs.append(name)
    require('synth_1' in journal_runs and len(journal_runs)==len(set(journal_runs)),'synthesis run inventory')
    for name in ('g05_diag.bit','g05_diag.hwh','g05_diag_routed.dcp','g05_diag_synth.dcp'):
        require((out/'artifacts'/name).stat().st_size>0,'empty paired artifact')
    manifest={'status':'completed_build_pending_main_review','run_id':run_id,'task_id':TASK,
        'work_id':auth['work_id'],'operation_id':auth['operation_id'],'main_attested_source_commit':a['source_commit'],
        'requirements_sha256':CONTRACT,'hwh':identity,'source_acceptance':record(out/'inputs/main_source_acceptance.json'),
        'raw_synthesis_runs':journal_runs,'unmeasured_physical_inputs':PHYSICAL_UNKNOWNS,
        'formal_G05_B06':'not_accepted','board':'not_run; A-only',
        'files':{p.relative_to(out).as_posix():record(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    write_json(out/'ARTIFACT_MANIFEST.json',manifest)
    return manifest['status']


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('prepare','build'),default='prepare')
    parser.add_argument('--product-root',type=Path,default=Path(__file__).resolve().parents[4])
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--contract-json',type=Path,required=True)
    parser.add_argument('--source-acceptance',type=Path)
    parser.add_argument('--authorization',type=Path)
    parser.add_argument('--board-dir',type=Path,default=Path('D:/pynq/AMD2026/2026.1/Vivado/data/boards/board_files/pynq-z2/A.0'))
    parser.add_argument('--tool-root',type=Path,default=Path('D:/pynq/AMD2026/2026.1/Vivado'))
    parser.add_argument('--io-map-dir',type=Path,default=Path('D:/pynq/CarlandFPGA/.local/deployment/node-b/evidence/task-resume-20261026/a-g05-inputs/files/competition/deepeye/evidence/system/a-r02-io-map-20261021'))
    parser.add_argument('--timeout-seconds',type=int,default=7200)
    args=parser.parse_args(argv)
    out=args.out.resolve()
    require(60<=args.timeout_seconds<=14400,'finite build timeout 60..14400 seconds')
    require(not out.exists(),'existing output is never reused; no automatic replay')
    accepted=auth=None
    if args.mode=='build':
        require(args.source_acceptance is not None and args.authorization is not None,'separate main source acceptance AND build authorization required')
        accepted=acceptance(args.source_acceptance)
        auth=authorization(args.authorization,args.source_acceptance,accepted,out)
        require(out.is_relative_to(args.product_root.resolve()/'evidence/diagnostic/g05-capture'),'future build output must be a new G05 diagnostic evidence directory')
    else:
        require(args.source_acceptance is None and args.authorization is None,'default preparation does not accept/freeze changing RTL')
    try:
        summary=prepare(args,out)
        status='prepared_only' if args.mode=='prepare' else build(args,out,accepted,auth,summary)
        write_json(out/'RESULT.json',{'status':status,'at_utc':utc(),'full_build_executed':args.mode=='build',
            'requirements_sha256':CONTRACT,'product_acceptance':'not_claimed'})
        print(json.dumps({'status':status,'out':str(out),'full_build_executed':args.mode=='build'}))
        return 0
    except BaseException as error:
        if out.is_dir():
            write_json(out/'FAILURE.json',{'at_utc':utc(),'error':f'{type(error).__name__}: {error}',
                                         'artifacts_accepted':False,'automatic_retry':False})
            write_json(out/'FAILURE_FILE_MANIFEST.json',{'files':{p.relative_to(out).as_posix():record(p)
                for p in sorted(out.rglob('*')) if p.is_file()},'accepted':False})
        raise


if __name__=='__main__':
    raise SystemExit(main())
