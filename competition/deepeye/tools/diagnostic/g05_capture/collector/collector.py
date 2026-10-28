"""Default-OFFLINE, bounded revision59 G05 package verifier and A-only executor."""
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
import time
import types
import uuid

import pins
from transport import run_transport, stop_once

JSON_LIMIT = 1024*1024
BIT_LIMIT = 16*1024*1024
HWH_LIMIT = 8*1024*1024
BOARD_IMAGE_LIMIT = 4*1024*1024
SELECTED_LIMIT = 64*1024*1024
FILE_LIMIT = 128
INDEX_LIMIT = 4096
INDEX_BYTES_LIMIT = 8*1024**3
FIXTURE_KEYS = ('schema_version','task_id','task_version','requirements_sha256','operation_id',
                'run_id','nonce','session','expected_build_manifest_sha256','commands')


class Rejected(ValueError):
    pass


def require(ok,message):
    if not ok:
        raise Rejected(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def hexhash(value,n=64):
    require(type(value) is str and re.fullmatch('[0-9a-f]{'+str(n)+'}',value), 'exact lowercase hash required')
    return value


def integer(value,minimum,maximum):
    require(type(value) is int and minimum <= value <= maximum,'integer outside bounds')
    return value


def no_links(path):
    p=Path(os.path.abspath(path))
    for part in (p,)+tuple(p.parents):
        try:
            s=part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(s.st_mode) and not (getattr(s,'st_file_attributes',0)&0x400),
                'symlink/reparse path rejected: '+str(part))
    return p


def relative(value):
    require(type(value) is str and len(value)<=512 and value, 'package path required')
    require(not any(c in value for c in '\\:\x00') and not value.startswith('/'),'unsafe package path')
    for part in value.split('/'):
        require(part not in ('','.','..') and part==part.rstrip(' .'),'traversal/alias path')
        require(not re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',part),'reserved path')
        require(not any(ord(c)<32 for c in part),'control character in path')
    return value


def overlaps(a,b):
    return a.is_relative_to(b) or b.is_relative_to(a)


def durable_bytes(path,data):
    no_links(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    with path.open('xb') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    if os.name=='posix':
        os.chmod(path,0o400)


def write_json(path,obj):
    durable_bytes(path,(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8'))


class Reader:
    """Stat-sized n+1 reads (the work57 fix), bounded count/total, no aliasing.

    Path and descriptor checks detect common replacement races; an adversarial
    same-UID process is outside the private-output boundary, not cryptographically
    excluded. Original files are never reread for import or download.
    """
    def __init__(self,output,opener=None):
        self.output=output;self.opener=opener or (lambda p:p.open('rb'))
        self.identities=set();self.total=0;self.records=[]

    def read(self,path,limit=JSON_LIMIT,*,empty=False):
        p=no_links(path)
        require(not overlaps(self.output,p),'input/output overlap')
        before=p.lstat()
        require(stat.S_ISREG(before.st_mode),'regular input required')
        with self.opener(p) as f:
            s=os.fstat(f.fileno());identity=(s.st_dev,s.st_ino)
            require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and identity not in self.identities,'input hardlink/path alias')
            require((before.st_dev,before.st_ino)==identity,'path replaced at open')
            require((0 if empty else 1)<=s.st_size<=limit,'file size bound: '+str(p))
            require(len(self.records)<FILE_LIMIT and self.total+s.st_size<=SELECTED_LIMIT,'selected package budget')
            data=f.read(s.st_size+1)
            after=os.fstat(f.fileno())
        current=no_links(p).lstat()
        require(len(data)==s.st_size and (s.st_size,s.st_mtime_ns,s.st_ino,s.st_dev)==
                (after.st_size,after.st_mtime_ns,after.st_ino,after.st_dev)==
                (current.st_size,current.st_mtime_ns,current.st_ino,current.st_dev),'input changed during snapshot')
        self.identities.add(identity);self.total+=len(data)
        self.records.append({'path':str(p),'bytes':len(data),'sha256':sha(data),'requested_read_bytes':s.st_size+1})
        return data


def module_bytes(raw,name):
    key='_g05_'+name+'_'+uuid.uuid4().hex
    m=types.ModuleType(key);m.__file__=name;sys.modules[key]=m
    exec(compile(raw,name,'exec'),m.__dict__)
    return m


def trusted(reader,out):
    here=Path(__file__).resolve().parent
    modules=[]
    for name,digest in (('protocol_pinned.py',pins.PROTOCOL_SHA),('hwh_guard_pinned.py',pins.GUARD_SHA)):
        raw=reader.read(here/name)
        require(sha(raw)==digest,'trusted code pin mismatch: '+name)
        durable_bytes(out/'snapshots/trusted'/name,raw)
        modules.append(module_bytes(raw,name))
    return tuple(modules)


def fixture_from(raw,protocol,manifest_sha):
    obj=protocol.parse_json(raw)
    protocol.exact(obj,FIXTURE_KEYS,'fixture')
    require(type(obj['schema_version']) is int and obj['schema_version']==1,'fixture schema')
    require(obj['task_id']==pins.TASK and type(obj['task_version']) is int and obj['task_version']==1,'fixture task')
    require(obj['requirements_sha256']==pins.CONTRACT,'fixture contract')
    require(type(obj['operation_id']) is str and re.fullmatch('[A-Za-z0-9_.-]{1,128}',obj['operation_id']),'operation ID')
    require(hexhash(obj['expected_build_manifest_sha256'])==manifest_sha,'fixture manifest pin')
    protocol.identity_words(obj['run_id'],obj['nonce'],obj['session'])
    require(type(obj['commands']) is list and 1<=len(obj['commands'])<=16,'bounded command list')
    commands=tuple(protocol.validate_command(c) for c in obj['commands'])
    require(all(a.command_id<b.command_id for a,b in zip(commands,commands[1:])),'strict command order')
    require(len({c.profile for c in commands})==1,'one locked profile')
    return obj


def index_map(obj,max_count):
    require(type(obj) is dict and 0<len(obj)<=max_count,'manifest/launch file-count bound')
    aliases=set();total=0
    for name,entry in obj.items():
        relative(name)
        require(name.casefold() not in aliases,'case-insensitive path alias')
        aliases.add(name.casefold())
        require(type(entry) is dict and set(entry)=={'path','bytes','sha256'},'file record schema')
        hexhash(entry['sha256']);total+=integer(entry['bytes'],0,INDEX_BYTES_LIMIT)
        require(type(entry['path']) is str and len(entry['path'])<=4096,'informational original path')
    require(total<=INDEX_BYTES_LIMIT,'indexed package declared-byte bound')
    return obj


def validate(package,expected_manifest_sha256,fixture_path,out,*,synthetic_test_only=False,opener=None):
    """Use only selected manifest names; never walk the original build/vendor tree."""
    expected=hexhash(expected_manifest_sha256)
    package=no_links(package);fixture_path=no_links(fixture_path);out=no_links(out)
    require(package.is_dir() and not overlaps(package,out) and not overlaps(fixture_path,out),'package/output overlap')
    reader=Reader(out,opener)
    protocol,guard=trusted(reader,out)
    raw_manifest=reader.read(package/'ARTIFACT_MANIFEST.json')
    require(sha(raw_manifest)==expected,'manifest hash mismatch')
    manifest=protocol.parse_json(raw_manifest)
    required={'status','run_id','task_id','work_id','operation_id','main_attested_source_commit',
              'requirements_sha256','hwh','source_acceptance','raw_synthesis_runs',
              'unmeasured_physical_inputs','formal_G05_B06','board','files'}
    require(type(manifest) is dict and set(manifest)==required|({'TEST_FIXTURE'} if synthetic_test_only else set()),'manifest schema/version')
    require((manifest.get('TEST_FIXTURE')=='synthetic-not-authority')==synthetic_test_only,'synthetic manifest provenance')
    require(manifest['status']=='completed_build_pending_main_review' and manifest['task_id']==pins.TASK and
            manifest['requirements_sha256']==pins.CONTRACT,'completed build/contract required')
    require(type(manifest['run_id']) is str and re.fullmatch('[0-9a-f]{32}',manifest['run_id']),'build run ID')
    commit=hexhash(manifest['main_attested_source_commit'],40)
    require(manifest['unmeasured_physical_inputs']==pins.UNKNOWN_PHYSICAL and manifest['formal_G05_B06']=='not_accepted' and
            manifest['board']=='not_run; A-only','unmeasured physical limitations must remain')
    files=index_map(manifest['files'],INDEX_LIMIT)
    require('ARTIFACT_MANIFEST.json' not in files,'self-referential manifest')
    durable_bytes(out/'snapshots/ARTIFACT_MANIFEST.json',raw_manifest)
    cache={}

    def get(name):
        relative(name)
        if name in cache:
            return cache[name]
        require(name in files,'selected file missing: '+name)
        limit=(BIT_LIMIT if name.endswith('.bit') else HWH_LIMIT if name.endswith('.hwh') else
               BOARD_IMAGE_LIMIT if name=='inputs/board_repo/pynq-z2/A.0/pynq_z2.jpg' else
               8*JSON_LIMIT if name.endswith('.bin') else JSON_LIMIT)
        raw=reader.read(package/name,limit,empty=name.endswith('.bin'))
        require(len(raw)==files[name]['bytes'] and sha(raw)==files[name]['sha256'],'selected hash/size mismatch: '+name)
        # Numerical config JSON always uses the parent strict integer parser.
        # PROCESS.json contains fractional elapsed times. The exactly pinned
        # reference pin map contains fractional analog voltages. Both remain
        # opaque hash-checked bytes and supply no collector decisions. Actual
        # mapping comes only from the checked BD/HWH, never that reference.
        # vendor_ddr_preset.xml is opaque pinned XML, never parsed as JSON.
        if name.endswith('.json') and name not in ('PROCESS.json','inputs/io_reference/candidate-pinmap.json'):
            protocol.parse_json(raw)
        durable_bytes(out/'snapshots/package'/name,raw)
        cache[name]=raw
        return raw

    def doc(name):
        return protocol.parse_json(get(name))

    acceptance=doc('inputs/main_source_acceptance.json')
    keys={'schema','accepted','task_id','task_version','director_thread_id','requirements_sha256',
          'frozen_design','source_commit','sources','build_files','cdc_bindings','cdc_source_review'}
    protocol.exact(acceptance,keys|({'TEST_FIXTURE'} if synthetic_test_only else set()),'source acceptance')
    require((acceptance.get('TEST_FIXTURE')=='synthetic-not-authority')==synthetic_test_only,'synthetic acceptance provenance')
    require(type(acceptance['schema']) is int and acceptance['schema']==1 and acceptance['accepted'] is True and
            acceptance['task_id']==pins.TASK and type(acceptance['task_version']) is int and acceptance['task_version']==1 and
            acceptance['director_thread_id']==pins.MAIN and acceptance['requirements_sha256']==pins.CONTRACT and
            acceptance['frozen_design']==pins.DESIGN and acceptance['source_commit']==commit,'main source acceptance mismatch')
    require(acceptance['sources']==pins.SOURCES and acceptance['build_files']==pins.BUILD_FILES,'unknown exact source/tool version')
    require(manifest['source_acceptance']==files['inputs/main_source_acceptance.json'],'acceptance manifest binding')
    cdc=acceptance['cdc_source_review'];bindings=acceptance['cdc_bindings']
    protocol.exact(cdc,('path','sha256','reviewed_by'),'CDC review')
    require(cdc['reviewed_by']==pins.MAIN and sha(get('inputs/main_cdc_review'))==hexhash(cdc['sha256']),'CDC source evidence')
    require(type(bindings) is dict and set(bindings)=={n for n in guard.PORTS if n.endswith('_i')},'CDC bindings')
    endpoints=[]
    for chain in bindings.values():
        require(type(chain) is list and len(chain)==3,'three CDC stages')
        for endpoint in chain:
            require(type(endpoint) is str and re.fullmatch(r'g05_diag_i/[A-Za-z0-9_./\[\]-]+/D',endpoint),'explicit CDC endpoint')
            endpoints.append(endpoint)
    require(len(set(endpoints))==9,'shared CDC stages')
    auth=doc('inputs/main_build_authorization.json')
    require((auth.get('TEST_FIXTURE')=='synthetic-not-authority')==synthetic_test_only,'synthetic build authorization')
    checks={'task_id':pins.TASK,'task_version':1,'director_thread_id':pins.MAIN,'authorized':True,
            'action':'full_g05_diagnostic_build','source_commit':commit,
            'source_acceptance_sha256':sha(cache['inputs/main_source_acceptance.json']),
            'requirements_sha256':pins.CONTRACT,'physical_unknowns_acknowledged':pins.UNKNOWN_PHYSICAL,
            'work_id':manifest['work_id'],'operation_id':manifest['operation_id']}
    protocol.exact(auth,set(checks)|{'output_directory'}|({'TEST_FIXTURE'} if synthetic_test_only else set()),'build authorization')
    require(all(type(auth[k]) is type(v) and auth[k]==v for k,v in checks.items()),'build authorization binding')
    require(type(auth['output_directory']) is str and len(auth['output_directory'])>1 and
            type(auth['work_id']) is str and auth['work_id'] and auth['work_id']!='B-G05-BUILD-PREP-20261026-59-v1' and
            type(auth['operation_id']) is str and auth['operation_id'],'new build operation required')
    launch=index_map(doc('LAUNCH_INPUTS.json'),96)
    require(all(n.startswith('inputs/') for n in launch),'launch inputs outside selected input scope')
    required_launch={'inputs/main_source_acceptance.json','inputs/main_build_authorization.json','inputs/main_cdc_review'}
    required_launch|={'inputs/rtl_flat/'+Path(n).name for n in pins.SOURCES}
    required_launch|={'inputs/tooling/'+n for n in pins.BUILD_FILES}
    required_launch|={'inputs/'+n for n in ('build_g05.tcl','g05_ports.xdc','g05_cdc.tcl')}
    required_launch|=set(pins.LAUNCH_PINS)
    required_launch|={'inputs/readonly_primitives/'+n for n in list(pins.SOURCES)[:2]}
    required_launch|={'inputs/'+n for n in ('immutable_scope.json','ddr_expected.tcl','ps7_preset_parameters.json',
                                          'ddr_literal.json','ddr_resolved.json','ddr_resolution.json',
                                          'rtl_sources.txt','build_config.tcl')}
    require(required_launch==set(launch),'unknown/missing actual launch source/tool snapshot set')
    for name,entry in launch.items():
        require(name in files and entry==files[name],'launch/manifest same-run hash mismatch')
        get(name)
    for name,digest in pins.SOURCES.items():
        require(sha(get('inputs/rtl_flat/'+Path(name).name))==digest,'six-source snapshot changed')
    for name,digest in list(pins.SOURCES.items())[:2]:
        require(sha(get('inputs/readonly_primitives/'+name))==digest,'readonly primitive snapshot changed')
    for name,digest in pins.LAUNCH_PINS.items():
        require(sha(get(name))==digest,'known launch dependency changed')
    contract=doc('inputs/immutable_scope.json')
    require(contract.get('revision')==1 and contract.get('contract_id')=='DEEPEYE-HUMAN-LOCK-20261014' and
            sha(json.dumps(contract['requirements'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())==pins.CONTRACT,
            'pinned H01-H15 requirements differ')
    for name,digest in pins.BUILD_FILES.items():
        require(sha(get('inputs/tooling/'+name))==digest,'build tool snapshot changed')
    for name in ('build_g05.tcl','g05_ports.xdc','g05_cdc.tcl'):
        require(sha(get('inputs/'+name))==pins.BUILD_FILES['fpga/diagnostic/g05_capture/build/'+name],'actual executable build copy changed')
    done=doc('VIVADO_COMPLETE.json')
    require(done=={'run_id':manifest['run_id'],'top':'g05_diag_wrapper','bd':'g05_diag','part':'xc7z020clg400-1',
                   'version':'2026.1','status':'bitstream_complete_pending_hwh_check_and_main_review'},'same-run completion identity')
    # Hash/snapshot original process evidence; never execute or reinterpret it as
    # a new build or a hardware proof. The main-selected manifest pins it.
    for name in ('PROCESS.json','process.stdout.bin','process.stderr.bin'):
        get(name)
    stdout=cache['process.stdout.bin'].decode('utf-8',errors='replace')
    require([line for line in stdout.splitlines() if line.startswith('G05_DIAG_COMPLETE|')]==
            ['G05_DIAG_COMPLETE|'+manifest['run_id']],'same-run completion marker')
    require(not re.search(r'^\s*ERROR:',stdout+'\n'+cache['process.stderr.bin'].decode('utf-8',errors='replace'),re.M),'build ERROR diagnostic')
    mapping=doc('BD_MAPPING.json')
    bit=get('artifacts/g05_diag.bit');hwh=get('artifacts/g05_diag.hwh')
    require(1024<=len(bit)<=BIT_LIMIT,'sane bitstream size bound')
    require(b'<!DOCTYPE' not in hwh.upper() and b'<!ENTITY' not in hwh.upper(),'HWH DTD/entity forbidden')
    identity=guard.verify_hwh(io.BytesIO(hwh),mapping,fixture=synthetic_test_only)
    require(identity==manifest['hwh'],'HWH result differs from manifest')
    raw_fixture=reader.read(fixture_path)
    fixture=fixture_from(raw_fixture,protocol,expected)
    durable_bytes(out/'snapshots/fixture.json',raw_fixture)
    return {'protocol':protocol,'reader':reader,'fixture':fixture,'fixture_sha256':sha(raw_fixture),
            'manifest_sha256':expected,'build_run_id':manifest['run_id'],'source_commit':commit,
            'mapping':identity,'bit_path':out/'snapshots/package/artifacts/g05_diag.bit',
            'pair_hashes':{'g05_diag.bit':sha(bit),'g05_diag.hwh':sha(hwh)},'synthetic_test_only':synthetic_test_only,
            'selected_files':{n:{'sha256':sha(raw),'bytes':len(raw)} for n,raw in cache.items()}}


def authorize(raw,v,now):
    p=v['protocol'];a=p.parse_json(raw);f=v['fixture']
    expected={'schema_version':1,'task_id':pins.TASK,'task_version':1,'requirements_sha256':pins.CONTRACT,
              'node_id':'A','action':'execute_g05_private_diagnostic','authorized':True,'build_reviewed':True,
              'fresh_operation':True,'reset_confirmed':True,'confirmed_board_clock_hz':100000000,
              'operation_id':f['operation_id'],'run_id':f['run_id'],'nonce':f['nonce'],'session':f['session'],
              'expected_build_manifest_sha256':v['manifest_sha256'],'source_commit':v['source_commit'],
              'fixture_sha256':v['fixture_sha256']}
    p.exact(a,set(expected)|{'reset_operation_id','issued_unix_s','expires_unix_s'},'A authorization')
    require(not v['synthetic_test_only'],'synthetic package cannot authorize production')
    require(all(type(a[k]) is type(value) and a[k]==value for k,value in expected.items()),'A authorization binding')
    require(type(a['reset_operation_id']) is str and re.fullmatch('[A-Za-z0-9_.-]{1,128}',a['reset_operation_id']) and
            a['reset_operation_id']!=f['operation_id'],'fresh reset operation ID')
    issued=integer(a['issued_unix_s'],1,2**63-1);expires=integer(a['expires_unix_s'],1,2**63-1)
    require(issued<=now<expires<=issued+900,'A authorization expired/future/unbounded')
    return a


def runtime_facts():
    # Metadata lookup does not import pynq. Hostname supplies no authorization.
    facts={'system':platform.system(),'machine':platform.machine(),'python':platform.python_version(),
           'euid':os.geteuid() if hasattr(os,'geteuid') else None}
    try:
        facts['pynq_distribution']=importlib.metadata.version('pynq')
    except importlib.metadata.PackageNotFoundError:
        facts['pynq_distribution']=None
    return facts


def check_facts(facts):
    require(facts['system']=='Linux' and facts['machine'].lower() in ('armv7l','armv8l','aarch64') and
            facts['euid']==0 and facts['pynq_distribution']=='3.0.1','A ARM/Linux/euid0/PYNQ3.0.1 runtime facts required')


def import_runtime():
    from pynq import MMIO, Overlay
    return Overlay,MMIO


def check_overlay(overlay,mapping):
    ips=overlay.ip_dict
    require(isinstance(ips, dict),'actual ip_dict missing')
    matches=[(key,item) for key,item in ips.items() if key.strip('/')==mapping['instance'] or
             (type(item) is dict and (str(item.get('fullpath','')).strip('/')==mapping['instance'] or item.get('type')==mapping['vlnv']))]
    require(len(matches)==1,'actual G05 ip_dict identity ambiguous/missing')
    key,item=matches[0]
    require(type(item) is dict and key==mapping['instance'] and item.get('fullpath')==mapping['instance'] and
            item.get('type')==mapping['vlnv'] and type(item.get('phys_addr')) is int and
            item['phys_addr']==int(mapping['base'],16) and type(item.get('addr_range')) is int and
            item['addr_range']==mapping['span'],'actual ip_dict differs from verified HWH')


def verify_pair(v):
    for name,digest in v['pair_hashes'].items():
        p=no_links(v['bit_path'].parent/name);s=p.stat()
        require(s.st_nlink==1 and s.st_size<=BIT_LIMIT,'snapshot pair alias/size')
        with p.open('rb') as f:
            raw=f.read(s.st_size+1)
        require(len(raw)==s.st_size and sha(raw)==digest,'snapshot pair changed before runtime')


class Journal:
    def __init__(self,path):
        self.f=path.open('xb');self.count=0;self.size=0

    def event(self,kind,**fields):
        raw=(json.dumps({'event':kind,'monotonic_ns':time.monotonic_ns(),**fields},sort_keys=True,allow_nan=False)+'\n').encode()
        require(self.count<41000 and len(raw)<=16384 and self.size+len(raw)<=16*1024*1024,'finite event log bound')
        self.f.write(raw);self.f.flush();os.fsync(self.f.fileno());self.count+=1;self.size+=len(raw)

    def close(self):
        self.f.close()


def collect(package,expected_manifest_sha256,fixture,output,*,execute_on_a=False,authorization=None,
            synthetic_test_only=False,total_seconds=30,max_polls=4096):
    out=no_links(output);package=no_links(package);fixture=no_links(fixture)
    require(not out.exists() and not overlaps(package,out) and not overlaps(fixture,out),'exclusive nonoverlapping output required')
    if authorization is not None:
        authorization=no_links(authorization)
        require(not overlaps(authorization,out),'authorization/output overlap')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    report={'status':'failed','exit_code':2,'task_id':pins.TASK,'task_version':1,'work_id':pins.WORK,
            'requirements_sha256':pins.CONTRACT,'requirement_ids':[f'H{i:02}' for i in range(1,16)],
            'movement_authorized':False,'formal_acceptance':'not_run','automatic_replay':False,
            'runtime_import_attempted':False,'overlay_construct_attempted':False,'overlay_construct_returned':False,
            'download_attempted':False,'download_returned':False,'mmio_construct_attempted':False,'mmio_construct_returned':False,
            'cleanup':{'attempted':False,'confirmed':False,'reason':'MMIO not created'}}
    write_json(out/'INTENT.json',{**report,'package':str(package),'expected_manifest_sha256':expected_manifest_sha256,
               'fixture':str(fixture),'execute_on_a':execute_on_a,'synthetic_test_only':synthetic_test_only,
               'argv':sys.argv,'pid':os.getpid(),'python':sys.version,'total_seconds':total_seconds,'max_polls':max_polls})
    journal=None;mmio=None
    try:
        journal=Journal(out/'events.jsonl')
        require(type(execute_on_a) is bool and type(synthetic_test_only) is bool,'explicit boolean mode')
        require(not (execute_on_a and synthetic_test_only),'synthetic mode is strictly offline')
        require((authorization is not None)==execute_on_a,'A execution requires exactly one local authorization')
        integer(total_seconds,1,180);integer(max_polls,1,4096)
        v=validate(package,expected_manifest_sha256,fixture,out,synthetic_test_only=synthetic_test_only)
        report['validation']={k:v[k] for k in ('fixture_sha256','manifest_sha256','build_run_id','source_commit','mapping','pair_hashes','selected_files')}
        report['input_reads']=v['reader'].records
        journal.event('validation_complete',manifest_sha256=v['manifest_sha256'],movement_authorized=False)
        if execute_on_a:
            raw=v['reader'].read(authorization)
            a=authorize(raw,v,int(time.time()))
            durable_bytes(out/'snapshots/A_AUTHORIZATION.json',raw)
            report['authorization_sha256']=sha(raw)
            report['runtime_facts']=runtime_facts();check_facts(report['runtime_facts'])
            report['node_boundary']='explicit local A authorization plus checked platform; not cryptographic machine identity'
            write_json(out/'RUNTIME_INTENT.json',{'authorization':a,'authorization_sha256':sha(raw),
                       'validated':report['validation'],'facts':report['runtime_facts'],'movement_authorized':False})
            verify_pair(v)
            journal.event('runtime_import_attempt');report['runtime_import_attempted']=True
            Overlay,MMIO=import_runtime()
            journal.event('overlay_construct_attempt',download=False,bit_snapshot=str(v['bit_path']))
            report['overlay_construct_attempted']=True
            overlay=Overlay(str(v['bit_path']),download=False)
            report['overlay_construct_returned']=True
            check_overlay(overlay,v['mapping']);verify_pair(v)
            journal.event('download_attempt',bit_snapshot=str(v['bit_path']));report['download_attempted']=True
            overlay.download()
            report['download_returned']=True;journal.event('download_returned')
            check_overlay(overlay,v['mapping'])
            journal.event('mmio_construct_attempt',base=v['mapping']['base'],span=v['mapping']['span'])
            report['mmio_construct_attempted']=True
            mmio=MMIO(int(v['mapping']['base'],16),v['mapping']['span'])
            report['mmio_construct_returned']=True
            report['cleanup'].pop('reason',None)
            report['transport']=run_transport(v['protocol'],v['fixture'],mmio.read,mmio.write,journal.event,
                lambda n,record:write_json(out/'captures'/f'{n:02}.json',record),
                total_seconds=total_seconds,max_polls=max_polls,cleanup=report['cleanup'])
            report.update(status=report['transport']['status'],exit_code=report['transport']['exit_code'])
        else:
            report.update(status='synthetic_test_offline_only' if synthetic_test_only else 'validated_offline_only',exit_code=0)
    except BaseException as error:
        report['primary_error']=type(error).__name__+': '+str(error)
    finally:
        # Covers even failures between MMIO return and transport entry.
        if mmio is not None:
            stop_once(mmio.read,mmio.write,report['cleanup'])
            if not report['cleanup']['confirmed']:
                report.update(status='failed',exit_code=2)
        if journal is not None:
            try:
                journal.close()
            except BaseException as error:
                report['journal_close_error']=type(error).__name__+': '+str(error)
                report.update(status='failed',exit_code=2)
    try:
        write_json(out/'RECEIPT.json',report)
    except BaseException as error:
        # MMIO cleanup has already run even if the filesystem is unavailable.
        report['receipt_error']=type(error).__name__+': '+str(error)
        report.update(status='failed',exit_code=2)
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',type=Path,required=True)
    p.add_argument('--expected-manifest-sha256',required=True)
    p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--execute-on-a',action='store_true')
    p.add_argument('--authorization',type=Path)
    p.add_argument('--synthetic-test-only',action='store_true')
    p.add_argument('--total-seconds',type=int,default=30)
    p.add_argument('--max-polls',type=int,default=4096)
    args=p.parse_args(argv)
    try:
        report=collect(args.package,args.expected_manifest_sha256,args.fixture,args.output,
                       execute_on_a=args.execute_on_a,authorization=args.authorization,
                       synthetic_test_only=args.synthetic_test_only,total_seconds=args.total_seconds,max_polls=args.max_polls)
    except BaseException as error:
        report={'status':'rejected','exit_code':2,'primary_error':type(error).__name__+': '+str(error),'movement_authorized':False}
    print(json.dumps(report,sort_keys=True,allow_nan=False))
    return report['exit_code']


if __name__=='__main__':
    raise SystemExit(main())
