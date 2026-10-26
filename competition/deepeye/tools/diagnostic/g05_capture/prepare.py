"""Default-offline G05 register plan. Never imports PYNQ or opens MMIO.

A new exact paired build and a separately reviewed A executor remain required.
This preparation cannot authorize a board operation or game motion.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import types

READER_SHA='840998d9065807fb031146521e5a29c7d10ae5e9941c3f4672fc8b339f6da382'

def sha(raw):return hashlib.sha256(raw).hexdigest()

def module_from_bytes(name,path,raw):
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    return module

def prepare(fixture,output):
    here=Path(__file__).resolve().parent
    reader_path=here.parent/'collect_private_diag.py'
    raw_reader=reader_path.read_bytes()
    if sha(raw_reader)!=READER_SHA:raise ValueError('reviewed bounded Reader source changed')
    safe=module_from_bytes('_g05_verified_bounded_reader',reader_path,raw_reader)
    output=safe.no_links(output);fixture=safe.no_links(fixture)
    safe.require(not output.exists(),'output exists; no replay/overwrite')
    reader=safe.Reader(output)
    raw_protocol=reader.read(here/'protocol.py',1048576)
    protocol=module_from_bytes('_g05_protocol_snapshot',here/'protocol.py',raw_protocol)
    raw=reader.read(fixture,1048576);obj=protocol.parse_json(raw)
    protocol.exact(obj,('schema_version','task_id','task_version','requirements_sha256',
        'operation_id','run_id','nonce','session','expected_build_manifest_sha256','commands'),'fixture')
    protocol.require(type(obj['schema_version']) is int and obj['schema_version']==1,'fixture schema')
    protocol.require(obj['task_id']=='DEEPEYE-IMPLEMENTATION-20261014' and type(obj['task_version']) is int and obj['task_version']==1,'task mismatch')
    protocol.require(obj['requirements_sha256']==protocol.CONTRACT,'contract mismatch')
    protocol.require(type(obj['operation_id']) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',obj['operation_id']),'operation ID')
    protocol.require(type(obj['expected_build_manifest_sha256']) is str and re.fullmatch(r'[0-9a-f]{64}',obj['expected_build_manifest_sha256']),'manifest pin')
    identity=protocol.identity_words(obj['run_id'],obj['nonce'],obj['session'])
    protocol.require(type(obj['commands']) is list and 1<=len(obj['commands'])<=16,'bounded command list')
    commands=[protocol.validate_command(x) for x in obj['commands']]
    protocol.require(all(a.command_id<b.command_id for a,b in zip(commands,commands[1:])),'commands strictly increase')
    protocol.require(len({c.profile for c in commands})==1,'one profile per diagnostic session')
    batches=[]
    for c in commands:
        batches.append({'command_id':c.command_id,'tag':c.tag,'writes':[
            {'offset':0x200+4*i,'value':v,'wstrb':15} for i,v in enumerate(protocol.command_words(c))],
            'commit':{'offset':0x0c,'value':2,'wstrb':15},
            'later_read_protocol':'Wait boundedly for eligible latest, LATCH4, read status/fullidentity/32wordrecord/status/fullidentity/heldseq, validate exact immutable command+TTL and raw decoder, ACK5. No deadline renewal.',
            'ttl_ms':c.ttl_ms})
    result={'status':'OFFLINE_PLAN_ONLY_BUILD_AND_BOARD_NOT_VALIDATED','task_id':obj['task_id'],'task_version':1,
        'operation_id':obj['operation_id'],'requirements_sha256':protocol.CONTRACT,
        'fixture_sha256':sha(raw),'protocol_executed_bytes_sha256':sha(raw_protocol),
        'reader_executed_bytes_sha256':sha(raw_reader),'expected_build_manifest_sha256':obj['expected_build_manifest_sha256'],
        'full_identity_words':identity,'identity_writes':[{'offset':0x100+4*i,'value':v,'wstrb':15} for i,v in enumerate(identity)],
        'begin':{'offset':0x0c,'value':1,'wstrb':15},'commands':batches,'finally_stop':{'offset':0x0c,'value':3,'wstrb':15},
        'movement_authorized':False,'hardware_enable_eligible':False,'board_execution':'not_run; A-only',
        'remaining':['exact new six-pin build/source/bit/HWH manifest validation','independent actual-composition RTL tests','A operation/physical wiring/clock/capture checks','reviewed bounded A executor and failure cleanup']}
    output.mkdir(parents=True,exist_ok=False)
    for name,payload in [('fixture.snapshot.json',raw),('protocol.snapshot.py',raw_protocol),('reader.snapshot.py',raw_reader)]:
        with (output/name).open('xb') as f:f.write(payload)
    with (output/'PLAN.json').open('x',encoding='utf8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    try:
        r=prepare(a.fixture,a.output)
        print(json.dumps({'status':r['status'],'commands':len(r['commands']),'output':str(a.output),'fixture_sha256':r['fixture_sha256']}));return 0
    except Exception as e:
        print(json.dumps({'status':'REJECTED','error':type(e).__name__+': '+str(e),'board_execution':'not_run'}),file=sys.stderr);return 2

if __name__=='__main__':sys.exit(main())
