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
MAIN='01a18824-4172-74e2-a13f-f3e3d1e3ed99'
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
DDR_VENDOR_REL='data/PS/7series/data/zynqconfig/ddr/ddr_preset.xml'
DDR_VENDOR_SHA='73566a941b442804a9c6b0eb42385b6c1cb82f12e354c138f8868005b91c52ed'
DDR_SELECTOR={'param':'pcw_uiparam_ddr_partno','name':'MT41J256M16 RE-125','strength':'8'}
DDR_PREFIX='CONFIG.PCW_UIPARAM_DDR_'
DDR_MODEL_KEYS=frozenset('DRAM_WIDTH DEVICE_CAPACITY SPEED_BIN BANK_ADDR_COUNT ROW_ADDR_COUNT COL_ADDR_COUNT CL CWL T_RCD T_RP T_RC T_RAS_MIN T_FAW'.split())
DDR_OVERRIDES={'T_RC':('50.625','48.91'),'T_RCD':('13.125','7'),'T_RP':('13.125','7')}


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


def _resolve_ddr_tables(board_raw,vendor_raw,*,test_fixture):
    """Structural parser; production callers must use resolve_ddr(), never this helper."""
    parsed_inputs=[]
    vendor_declaration=b'<!DOCTYPE presets PUBLIC "presets" "presets.dtd" >'
    for index,raw in enumerate((board_raw,vendor_raw)):
        require(type(raw) is bytes and 0<len(raw)<=1048576,'bounded DDR XML bytes required')
        # The pinned vendor XML contains this exact external declaration. Keep
        # raw evidence intact, but remove it from the parser copy: no DTD fetch.
        parsed=raw.replace(vendor_declaration,b'',1) if index==1 else raw
        require(b'<!DOCTYPE' not in parsed.upper() and b'<!ENTITY' not in parsed.upper(),'DDR XML unexpected DTD/entity forbidden')
        parsed_inputs.append(parsed)
    board=ET.fromstring(parsed_inputs[0])
    require(board.tag=='ip_presets','board preset root')
    presets=board.findall("./ip_preset[@preset_proc_name='ps7_preset']")
    require(len(presets)==1,'unique PS7 board preset required')
    ips=presets[0].findall("./ip[@name='processing_system7']")
    require(len(ips)==1,'unique board PS7 IP required')
    params={}
    for p in ips[0].findall('./user_parameters/user_parameter'):
        require(set(p.attrib)=={'name','value'} and p.get('name') not in params,'duplicate/malformed board parameter')
        params[p.attrib['name']]=p.attrib['value']
    require(len(params)==771,'exact771 raw board parameters required')
    raw_ddr={k:v for k,v in params.items() if k.startswith(DDR_PREFIX)}
    require(len(raw_ddr)==72,'exact72 literal board DDR parameters required')
    require(raw_ddr.get(DDR_PREFIX+'PARTNO')==DDR_SELECTOR['name'],'board named model mismatch')
    vendor=ET.fromstring(parsed_inputs[1])
    require(vendor.tag=='presets','vendor DDR preset root')
    # Search by name first so a duplicate with a changed selector/strength is
    # rejected too, rather than silently selecting one of two same-name entries.
    matches=[p for p in vendor.findall('./preset') if p.get('name')==DDR_SELECTOR['name']]
    require(len(matches)==1 and matches[0].attrib==DDR_SELECTOR,'unique exact named DDR selector/strength required')
    selected=matches[0];sets={};disabled=[]
    for entry in selected:
        require(entry.tag in ('set','disable'),'unexpected named-model entry')
        expected={'param','value'} if entry.tag=='set' else {'param'}
        require(set(entry.attrib)==expected and len(entry)==0,'malformed named-model entry')
        name=entry.attrib['param']
        require(name.startswith('pcw_uiparam_ddr_') and name==name.lower(),'model parameter naming')
        key='CONFIG.'+name.upper()
        if entry.tag=='set':
            require(key not in sets,'duplicate model set entry');sets[key]=entry.attrib['value']
        else:
            require(key not in disabled,'duplicate model disable entry');disabled.append(key)
    expected_keys={DDR_PREFIX+k for k in DDR_MODEL_KEYS}
    require(len(sets)==13 and set(sets)==expected_keys,'exact13 named-model set keys required')
    require(len(disabled)==13 and set(disabled)==set(sets),'same13 unique set/disable entries required')
    require(set(sets)<=set(raw_ddr),'named model must be board DDR key subset')
    differences={k:{'board_literal':raw_ddr[k],'named_model':v} for k,v in sets.items() if raw_ddr[k]!=v}
    expected_diff={DDR_PREFIX+k:{'board_literal':old,'named_model':new} for k,(old,new) in DDR_OVERRIDES.items()}
    require(differences==expected_diff,'exact three main-decided DDR differences required; no additional change')
    require(sum(raw_ddr[k]==v for k,v in sets.items())==10,'ten unchanged model values required')
    resolved={**raw_ddr,**sets}
    require(len(resolved)==72 and all(resolved[k]==raw_ddr[k] for k in raw_ddr if k not in expected_diff),'nonoverride DDR changed')
    return {'schema':1,'scope':'synthetic_parser_fixture_not_build_authority' if test_fixture else 'pinned_named_model_resolution_not_physical_proof',
        'board_sha256':hashlib.sha256(board_raw).hexdigest(),'vendor_ddr_sha256':hashlib.sha256(vendor_raw).hexdigest(),
        'selector':dict(DDR_SELECTOR),'selected_entry_xml':ET.tostring(selected,encoding='unicode'),
        'raw_board_parameters':params,'literal_ddr':raw_ddr,'model_set':sets,'model_disable':sorted(disabled),
        'resolved_ddr':resolved,'differences':differences,'counts':{'raw_board':771,'literal_ddr':72,'resolved_ddr':72,'model_set':13,'model_disable':13,'model_unchanged':10,'overrides':3},
        'units':{'T_RC':'ns explicitly named in installed parameter metadata','T_RP':'clock cycles explicitly described',
                 'T_RCD':'unit unproven; installed node does not explicitly name a unit','T_RAS_MIN':'metadata name says ns but description also says cycles'},
        'conversion':'none; retain exact raw string values',
        'xml_parse_policy':'remove only exact pinned vendor PUBLIC declaration from parser copy; never load DTD; raw snapshot unchanged',
        'requirements_sha256':CONTRACT,'frozen_design':DESIGN}


def resolve_ddr(board_raw,vendor_raw):
    """Production entry always enforces both immutable source hashes."""
    require(hashlib.sha256(board_raw).hexdigest()==BOARD_HASHES['preset.xml'],'TUL board preset hash mismatch')
    require(hashlib.sha256(vendor_raw).hexdigest()==DDR_VENDOR_SHA,'installed vendor DDR preset hash mismatch')
    return _resolve_ddr_tables(board_raw,vendor_raw,test_fixture=False)


def resolve_ddr_test_fixture(board_raw,vendor_raw):
    """Explicit mutated-XML parser control only; cannot be selected by the build CLI."""
    return _resolve_ddr_tables(board_raw,vendor_raw,test_fixture=True)


def ddr_expected_text(resolution):
    return ''.join('set '+var+' [dict create '+' '.join(literal(k)+' '+literal(v) for k,v in sorted(resolution[key].items()))+']\n'
                   for var,key in (('literal_ddr','literal_ddr'),('expected_ddr','resolved_ddr')))


def write_ddr_inputs(board_snapshot,vendor_source,inputs):
    copy(vendor_source,inputs/'vendor_ddr_preset.xml',DDR_VENDOR_SHA)
    resolution=resolve_ddr(Path(board_snapshot).read_bytes(),(inputs/'vendor_ddr_preset.xml').read_bytes())
    write_json(inputs/'ps7_preset_parameters.json',resolution['raw_board_parameters'])
    write_json(inputs/'ddr_literal.json',resolution['literal_ddr'])
    write_json(inputs/'ddr_resolved.json',resolution['resolved_ddr'])
    write_json(inputs/'ddr_resolution.json',resolution)
    with (inputs/'ddr_expected.tcl').open('x',encoding='utf-8',newline='\n') as f:f.write(ddr_expected_text(resolution))
    return resolution


def verify_ddr_inputs(inputs):
    resolution=resolve_ddr((inputs/'board_repo/pynq-z2/A.0/preset.xml').read_bytes(),(inputs/'vendor_ddr_preset.xml').read_bytes())
    for name,key in (('ps7_preset_parameters.json','raw_board_parameters'),('ddr_literal.json','literal_ddr'),('ddr_resolved.json','resolved_ddr')):
        require(load(inputs/name)==resolution[key],'generated DDR table changed: '+name)
    require(load(inputs/'ddr_resolution.json')==resolution,'DDR provenance changed')
    require((inputs/'ddr_expected.tcl').read_bytes()==ddr_expected_text(resolution).encode('utf-8'),'executable DDR table changed')
    return resolution


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
    resolution=write_ddr_inputs(out/'inputs/board_repo/pynq-z2/A.0/preset.xml',args.tool_root/DDR_VENDOR_REL,out/'inputs')
    params=resolution['raw_board_parameters'];ddr=resolution['resolved_ddr']
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
        'ddr_model_resolution':{'vendor_sha256':DDR_VENDOR_SHA,'selector':DDR_SELECTOR,'counts':resolution['counts'],'differences':resolution['differences']},
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
    require(digest(args.tool_root/DDR_VENDOR_REL)==DDR_VENDOR_SHA,'installed vendor DDR input changed')
    verify_ddr_inputs(out/'inputs')
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
