"""New bounded author controls only. Everything here is software/synthetic."""
import argparse
import builtins
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from unittest.mock import patch

import collector as c
import pins
import transport as t
from fixtures_author import SimulatedMMIO,encoded,package_bytes


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--product',type=Path,required=True)
    ap.add_argument('--groups',nargs='+',choices=('stopclock','package','transport','runtime'),required=True)
    args=ap.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent
    raw=(here/'protocol_pinned.py').read_bytes();assert c.sha(raw)==pins.PROTOCOL_SHA
    protocol=c.module_bytes(raw,'test_protocol')
    raw_guard=(here/'hwh_guard_pinned.py').read_bytes();assert c.sha(raw_guard)==pins.GUARD_SHA
    guard=c.module_bytes(raw_guard,'test_guard')
    cases=[];runtime_imports=[]
    original_import=builtins.__import__
    def forbid_runtime(name,*pos,**kw):
        if name=='pynq' or name.startswith('pynq.'):
            runtime_imports.append(name);raise AssertionError('actual PYNQ import forbidden in author controls')
        return original_import(name,*pos,**kw)
    builtins.__import__=forbid_runtime

    def check(name,fn):
        try:
            detail=fn()
            cases.append({'name':name,'status':'passed','detail':detail})
        except Exception:
            cases.append({'name':name,'status':'failed','traceback':traceback.format_exc()})
        print(json.dumps(cases[-1]),flush=True)

    def rejects(fn,contains=None):
        try:fn()
        except Exception as error:
            if contains:assert contains in str(error),(contains,str(error))
            return type(error).__name__+': '+str(error)
        raise AssertionError('unexpected acceptance')

    def fixture(digest):
        return {'schema_version':1,'task_id':pins.TASK,'task_version':1,'requirements_sha256':pins.CONTRACT,
                'operation_id':'SYNTHETIC-NEW-OPERATION','run_id':'2'*64,'nonce':'3'*32,'session':7,
                'expected_build_manifest_sha256':digest,
                'commands':[{'command_id':n,'tag':n+40,'profile':1,'yaw':0,'pitch':0,'speed':0,'ttl_ms':100} for n in (1,2)]}

    if 'stopclock' in args.groups:
        def stop_control(mode):
            mmio=SimulatedMMIO();state={'attempted':False,'confirmed':False};calls=[]
            n=0
            def clock():
                nonlocal n
                n+=1
                if mode=='initial_exception' and n==1:raise RuntimeError('injected initial clock failure')
                if mode=='always_exception':raise RuntimeError('injected unavailable clock')
                if mode=='regression':return 5.0 if n==1 else 4.0
                if mode=='nan' and n==1:return float('nan')
                if mode=='infinite' and n==1:return float('inf')
                return 5.0
            t.stop_once(mmio.read,mmio.write,state,clock=clock,sleep=lambda _:None)
            t.stop_once(mmio.read,mmio.write,state,clock=clock,sleep=lambda _:None)
            assert mmio.writes==[(12,3)] and state['write_attempted'] and state['write_returned'],state
            assert not state['confirmed'] and not state['bounded_time_verified'] and state['timing_errors'],state
            (out/(mode+'.json')).write_bytes(encoded({'scope':'software GC01 regression','stop_writes':mmio.writes,'state':state}))
            return state
        for mode in ('initial_exception','always_exception','regression','nan','infinite'):
            check('GC01-'+mode,lambda mode=mode:stop_control(mode))
        def primary_and_clock():
            mmio=SimulatedMMIO('write_fail')
            def clock():raise RuntimeError('clock unavailable at entry and cleanup')
            r=t.run_transport(protocol,fixture('0'*64),mmio.read,mmio.write,lambda *a,**k:None,
                              lambda *a:None,clock=clock,sleep=lambda _:None)
            assert 'clock unavailable' in r['primary_error'] and r['cleanup']['timing_errors']
            assert mmio.writes==[(12,3)] and r['exit_code']==2
            return r
        check('GC01-primary-clock-error-and-cleanup-remain-separate',primary_and_clock)
        def unknown_stop_write():
            mmio=SimulatedMMIO('stop_write_fail');s={'attempted':False,'confirmed':False}
            t.stop_once(mmio.read,mmio.write,s,clock=lambda:float('nan'),sleep=lambda _:None)
            t.stop_once(mmio.read,mmio.write,s,clock=lambda:0,sleep=lambda _:None)
            assert mmio.writes==[(12,3)] and s['write_attempted'] and not s['write_returned'] and not s['confirmed']
            assert s['timing_errors'] and 'STOP write failure' in s['error']
            return s
        check('GC01-unknown-write-never-repeated',unknown_stop_write)

    seed=None
    if 'package' in args.groups or 'runtime' in args.groups:
        seed=package_bytes(args.repo.resolve(),args.product.resolve(),guard)

    def make_package(label,blob_mutator=None,manifest_mutator=None,fixture_mutator=None):
        home=out/label;home.mkdir();package=home/'package';package.mkdir()
        blobs=dict(seed)
        acceptance={'schema':1,'TEST_FIXTURE':'synthetic-not-authority','accepted':True,'task_id':pins.TASK,'task_version':1,
            'director_thread_id':pins.MAIN,'requirements_sha256':pins.CONTRACT,'frozen_design':pins.DESIGN,'source_commit':'a'*40,
            'sources':dict(pins.SOURCES),'build_files':dict(pins.BUILD_FILES),
            'cdc_bindings':{n:[f'g05_diag_i/SYNTHETIC/{n}/stage{i}/D' for i in range(3)] for n in guard.PORTS if n.endswith('_i')},
            'cdc_source_review':{'reviewed_by':pins.MAIN,'path':str(package/'inputs/main_cdc_review'),'sha256':c.sha(blobs['inputs/main_cdc_review'])}}
        blobs['inputs/main_source_acceptance.json']=encoded(acceptance)
        auth={'TEST_FIXTURE':'synthetic-not-authority','task_id':pins.TASK,'task_version':1,'director_thread_id':pins.MAIN,
            'authorized':True,'action':'full_g05_diagnostic_build','source_commit':'a'*40,
            'source_acceptance_sha256':c.sha(blobs['inputs/main_source_acceptance.json']),'requirements_sha256':pins.CONTRACT,
            'physical_unknowns_acknowledged':pins.UNKNOWN_PHYSICAL,'work_id':'SYNTHETIC-FULLBUILD-NEVER-RUN',
            'operation_id':'SYNTHETIC-BUILD','output_directory':str(package)}
        blobs['inputs/main_build_authorization.json']=encoded(auth)
        if blob_mutator:blob_mutator(blobs)
        def records(names):return {n:{'path':str(package/n),'bytes':len(blobs[n]),'sha256':c.sha(blobs[n])} for n in names}
        blobs['LAUNCH_INPUTS.json']=encoded(records(sorted(n for n in blobs if n.startswith('inputs/'))))
        mapping=json.loads(blobs['BD_MAPPING.json'])
        identity=guard.verify_hwh(io.BytesIO(seed['artifacts/g05_diag.hwh']),json.loads(seed['BD_MAPPING.json']),fixture=True)
        manifest={'TEST_FIXTURE':'synthetic-not-authority','status':'completed_build_pending_main_review','run_id':'1'*32,
            'task_id':pins.TASK,'work_id':auth['work_id'],'operation_id':auth['operation_id'],'main_attested_source_commit':'a'*40,
            'requirements_sha256':pins.CONTRACT,'hwh':identity,
            'source_acceptance':records(['inputs/main_source_acceptance.json'])['inputs/main_source_acceptance.json'],
            'raw_synthesis_runs':['synth_1','SYNTHETIC-NOT-RUN'],'unmeasured_physical_inputs':pins.UNKNOWN_PHYSICAL,
            'formal_G05_B06':'not_accepted','board':'not_run; A-only','files':records(sorted(blobs))}
        if manifest_mutator:manifest_mutator(manifest)
        for name,raw in blobs.items():
            path=package/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        raw_manifest=encoded(manifest);(package/'ARTIFACT_MANIFEST.json').write_bytes(raw_manifest)
        digest=c.sha(raw_manifest);obj=fixture(digest)
        if fixture_mutator:fixture_mutator(obj)
        fp=home/'fixture.json';fp.write_bytes(encoded(obj))
        return package,digest,fp,home/'output'

    def run_package(label,expected_error=None,**options):
        package,digest,fp,dest=make_package(label,**options)
        report=c.collect(package,digest,fp,dest,synthetic_test_only=True)
        assert not report['runtime_import_attempted'] and not report['cleanup']['attempted'] and not runtime_imports
        if expected_error:
            assert report['exit_code']==2 and expected_error in report.get('primary_error',''),report
        else:
            assert report['exit_code']==0 and report['status']=='synthetic_test_offline_only',report
            assert report['validation']['mapping']['base']=='0x42000000'
            assert all(x['requested_read_bytes']==x['bytes']+1 for x in report['input_reads'])
        return {'status':report['status'],'primary_error':report.get('primary_error'),'receipt':str(dest/'RECEIPT.json')}

    if 'package' in args.groups:
        check('offline-synthetic-valid-no-runtime',lambda:run_package('valid'))
        def mutation_json(blobs,name,mutator):
            obj=json.loads(blobs[name]);mutator(obj);blobs[name]=encoded(obj)
        check('manifest-unknown-version',lambda:run_package('unknown-version','manifest schema',manifest_mutator=lambda m:m.update(schema_version=9)))
        check('traversal-path',lambda:run_package('traversal','traversal',manifest_mutator=lambda m:m['files'].update({'../outside':next(iter(m['files'].values()))})))
        check('case-path-alias',lambda:run_package('case-alias','path alias',manifest_mutator=lambda m:m['files'].update({'BD_MAPPING.JSON':m['files']['BD_MAPPING.json']})))
        check('unknown-source-hash',lambda:run_package('bad-source','unknown exact source',blob_mutator=lambda b:mutation_json(b,'inputs/main_source_acceptance.json',lambda a:a['sources'].update({next(iter(pins.SOURCES)):'0'*64}))))
        check('changed-six-source-snapshot',lambda:run_package('bad-rtl','six-source snapshot',blob_mutator=lambda b:b.update({'inputs/rtl_flat/deepeye_g05_axi.sv':b'wrong source'})))
        check('bad-HWH-mapping',lambda:run_package('bad-mapping','address mismatch',blob_mutator=lambda b:mutation_json(b,'BD_MAPPING.json',lambda m:m.update(base='0x43000000'))))
        check('HWH-entity-denied',lambda:run_package('entity','DTD/entity',blob_mutator=lambda b:b.update({'artifacts/g05_diag.hwh':b'<!DOCTYPE x>'+b['artifacts/g05_diag.hwh']})))
        check('launch-unknown-input',lambda:run_package('extra-input','snapshot set',blob_mutator=lambda b:b.update({'inputs/unknown.py':b'never execute'})))
        check('fixture-exp-number',lambda:run_package('exp','non-integer',fixture_mutator=lambda f:f['commands'][0].update(ttl_ms=1e2)))
        check('fixture-bool-integer',lambda:run_package('bool','command_id',fixture_mutator=lambda f:f['commands'][0].update(command_id=True)))
        check('fixture-extra-field',lambda:run_package('extra-fixture','fields mismatch',fixture_mutator=lambda f:f.update(unapproved=True)))
        check('fixture-repeated-command',lambda:run_package('repeat','strict command',fixture_mutator=lambda f:f['commands'][1].update(command_id=1)))
        check('fixture-profile-change',lambda:run_package('profile','one locked profile',fixture_mutator=lambda f:f['commands'][1].update(profile=2)))
        check('fixture-short-TTL-never-extended',lambda:run_package('short-TTL',fixture_mutator=lambda f:f['commands'][0].update(ttl_ms=1)))
        check('manifest-declared-byte-limit',lambda:run_package('too-many-bytes','indexed package',manifest_mutator=lambda m:[v.update(bytes=c.INDEX_BYTES_LIMIT) for v in m['files'].values()]))
        def file_count(m):
            entry={'path':'x','bytes':0,'sha256':'0'*64}
            m['files']={f'file{i}':entry for i in range(c.INDEX_LIMIT+1)}
        check('manifest-file-count-limit',lambda:run_package('too-many-files','file-count',manifest_mutator=file_count))
        def raw_variant(label,which):
            package,digest,fp,dest=make_package(label)
            if which=='bad_hash':digest='0'*64
            elif which=='duplicate':
                raw=fp.read_bytes();fp.write_bytes(raw.replace(b'"session": 7',b'"session": 7,"session": 7'))
            elif which=='large_json':fp.write_bytes(b' '* (c.JSON_LIMIT+1))
            elif which=='bit_changed':(package/'artifacts/g05_diag.bit').write_bytes(b'changed')
            elif which=='hardlink':os.link(package/'artifacts/g05_diag.bit',package/'bit.alias')
            elif which=='launch_changed':
                path=package/'LAUNCH_INPUTS.json';obj=json.loads(path.read_bytes());next(iter(obj.values()))['sha256']='0'*64
                raw=encoded(obj);path.write_bytes(raw)
                mpath=package/'ARTIFACT_MANIFEST.json';m=json.loads(mpath.read_bytes());m['files']['LAUNCH_INPUTS.json'].update(bytes=len(raw),sha256=c.sha(raw));raw=encoded(m);mpath.write_bytes(raw);digest=c.sha(raw)
                f=json.loads(fp.read_bytes());f['expected_build_manifest_sha256']=digest;fp.write_bytes(encoded(f))
            report=c.collect(package,digest,fp,dest,synthetic_test_only=True)
            assert report['exit_code']==2 and not report['runtime_import_attempted'],report
            reason={'bad_hash':'manifest hash','duplicate':'duplicate JSON','large_json':'file size bound',
                    'bit_changed':'selected hash/size','hardlink':'hardlink','launch_changed':'launch/manifest'}[which]
            assert reason in report['primary_error'],report
            return report['primary_error']
        for mode in ('bad_hash','duplicate','large_json','bit_changed','hardlink','launch_changed'):
            check(mode,lambda mode=mode:raw_variant(mode,mode))
        def output_alias():
            package,digest,fp,_=make_package('output-alias')
            return rejects(lambda:c.collect(package,digest,fp,package/'new-output',synthetic_test_only=True),'nonoverlapping')
        check('output-input-overlap-before-write',output_alias)
        def no_existing_output():
            package,digest,fp,dest=make_package('exclusive');dest.mkdir()
            return rejects(lambda:c.collect(package,digest,fp,dest,synthetic_test_only=True),'exclusive')
        check('existing-output-no-replay',no_existing_output)
        def junction():
            home=out/'link';home.mkdir();target=home/'original';target.mkdir();(target/'file').write_bytes(b'small')
            link=home/'linked'
            # Windows symbolic-link creation requires an unavailable privilege;
            # exercise a real directory junction/reparse point without elevation.
            argv=['powershell.exe','-NoProfile','-NonInteractive','-Command',
                  "New-Item -ItemType Junction -Path '"+str(link)+"' -Target '"+str(target)+"' | Out-Null"]
            proc=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            stdout,stderr=proc.communicate(timeout=10)
            (home/'creation.json').write_bytes(encoded({'argv':argv,'pid':proc.pid,'exit_code':proc.returncode,
                 'stdout':stdout.decode(errors='replace'),'stderr':stderr.decode(errors='replace')}))
            assert proc.returncode==0
            return rejects(lambda:c.Reader(home/'out').read(link/'file'),'symlink/reparse')
        check('real-Windows-junction-rejected',junction)
        def bounded_read():
            home=out/'reader';home.mkdir();file=home/'small.bin';file.write_bytes(b'1234567');requested=[]
            class Wrapped:
                def __init__(self,p):self.f=p.open('rb')
                def __enter__(self):return self
                def __exit__(self,*a):self.f.close()
                def fileno(self):return self.f.fileno()
                def read(self,n):requested.append(n);return self.f.read(n)
            reader=c.Reader(home/'output',opener=Wrapped)
            assert reader.read(file,c.BIT_LIMIT)==b'1234567' and requested==[8]
            return {'requested_bytes':requested,'class_limit':c.BIT_LIMIT}
        check('work57-stat-size-not-large-limit-allocation',bounded_read)

    if 'transport' in args.groups:
        def transport_case(mode,fail=True):
            mmio=SimulatedMMIO(mode);events=[];records=[];tick=[0.0]
            def clock():return tick[0]
            def sleep(n):tick[0]+=n
            def event(kind,**fields):
                events.append({'event':kind,**fields})
                if mode=='log_fail' and kind=='write32_returned' and fields['offset']==12 and fields['value']==2:
                    raise OSError('injected event serialization failure')
            def sink(n,record):
                if mode=='output_fail':raise OSError('injected snapshot serialization failure')
                records.append(record);mmio.saved=True
            read=mmio.read
            if mode=='slow_read':
                def read(offset):
                    value=mmio.read(offset);tick[0]+=0.3;return value
            report=t.run_transport(protocol,fixture('0'*64),read,mmio.write,event,sink,
                                   clock=clock,sleep=sleep,max_polls=12)
            assert report['exit_code']==(2 if fail else 0),report
            assert mmio.stop_count==1 and mmio.writes.count((12,3))==1
            assert mmio.writes.count((12,2))<=2 and 0x2c not in mmio.reads
            assert len(events)<500 and len(mmio.reads)<300
            if not fail:
                assert len(records)==2 and [r['decoded']['capture_seq'] for r in records]==[1,2]
                assert mmio.writes.count((12,1))==1 and mmio.writes.count((12,2))==2 and mmio.writes.count((12,5))==2
            if mode in ('output_fail','read_fail','cancel','bad_ttl','bad_causal','skew','changed_session'):
                assert (12,5) not in mmio.writes
            if mode in ('write_fail','commit_unknown','read_fail','cancel','output_fail','log_fail'):
                assert report['primary_error'] and report['cleanup']['confirmed'],report
            if mode in ('stop_write_fail','stop_read_fail'):
                assert report['primary_error'] is None and not report['cleanup']['confirmed'],report
            path=out/('transport-'+mode+'.json')
            path.write_bytes(encoded({'scope':'software fake MMIO only','result':report,'raw_events':events,'raw_writes':mmio.writes,'raw_read_offsets':mmio.reads}))
            return {'result':str(path),'exit_code':report['exit_code'],'STOP_count':mmio.stop_count,'transport_calls':report.get('transport_calls')}
        check('transport-fixed-two-command-success',lambda:transport_case('good',False))
        for mode in ('changed_session','old_seq','fault','pending','expiry','bad_ttl','bad_causal','skew','cancel','write_fail','commit_unknown','read_fail','output_fail','log_fail','stop_write_fail','stop_read_fail','slow_read'):
            check('transport-'+mode,lambda mode=mode:transport_case(mode))

    if 'runtime' in args.groups:
        def synth_cannot_run():
            package,digest,fp,dest=make_package('synthetic-runtime-denied')
            auth=dest.parent/'auth.json';auth.write_bytes(b'{}')
            r=c.collect(package,digest,fp,dest,execute_on_a=True,authorization=auth,synthetic_test_only=True)
            assert r['exit_code']==2 and not r['runtime_import_attempted'] and not r['cleanup']['attempted']
            return r['primary_error']
        check('synthetic-mode-cannot-execute',synth_cannot_run)
        def default_rejects_synthetic():
            package,digest,fp,dest=make_package('default-synthetic-denied')
            r=c.collect(package,digest,fp,dest)
            assert r['exit_code']==2 and not r['runtime_import_attempted']
            return r['primary_error']
        check('production-default-rejects-synthetic-package',default_rejects_synthetic)
        def bad_package_before_import():
            package,digest,fp,dest=make_package('runtime-badhash')
            auth=dest.parent/'auth.json';auth.write_bytes(b'{}')
            r=c.collect(package,'0'*64,fp,dest,execute_on_a=True,authorization=auth)
            assert r['exit_code']==2 and not r['runtime_import_attempted'] and 'manifest hash' in r['primary_error']
            return r['primary_error']
        check('bad-package-before-runtime-import',bad_package_before_import)
        goodfacts={'system':'Linux','machine':'armv7l','python':'test','euid':0,'pynq_distribution':'3.0.1'}
        check('pure-runtime-facts-positive-software-only',lambda:c.check_facts(goodfacts))
        for name,value in (('system','Windows'),('machine','x86_64'),('euid',1000),('pynq_distribution','3.1.0')):
            check('runtime-facts-reject-'+name,lambda name=name,value=value:rejects(lambda:c.check_facts({**goodfacts,name:value}),'runtime facts'))
        package,digest,fp,dest=make_package('authorization-parser');dest.mkdir()
        v=c.validate(package,digest,fp,dest,synthetic_test_only=True)
        f=v['fixture'];a={'schema_version':1,'task_id':pins.TASK,'task_version':1,'requirements_sha256':pins.CONTRACT,
            'node_id':'A','action':'execute_g05_private_diagnostic','authorized':True,'build_reviewed':True,'fresh_operation':True,
            'reset_confirmed':True,'confirmed_board_clock_hz':100000000,'operation_id':f['operation_id'],'run_id':f['run_id'],
            'nonce':f['nonce'],'session':f['session'],'expected_build_manifest_sha256':digest,'source_commit':v['source_commit'],
            'fixture_sha256':v['fixture_sha256'],'reset_operation_id':'SYNTHETIC-RESET','issued_unix_s':1000,'expires_unix_s':1100}
        # Pure parser controls only. This local object cannot enter production:
        # the package and HWH retain their synthetic provenance markers.
        parser_v={**v,'synthetic_test_only':False}
        check('A-authorization-parser-positive-only',lambda:bool(c.authorize(encoded(a),parser_v,1050)))
        check('A-authorization-synthetic-prohibited',lambda:rejects(lambda:c.authorize(encoded(a),v,1050),'synthetic'))
        for key,value in (('node_id','B'),('nonce','4'*32),('session',8),('source_commit','b'*40),('fixture_sha256','0'*64),('confirmed_board_clock_hz',99999999),('fresh_operation',False),('expires_unix_s',1049)):
            check('A-authorization-reject-'+key,lambda key=key,value=value:rejects(lambda:c.authorize(encoded({**a,key:value}),parser_v,1050)))
        class Overlay:
            ip_dict={guard.INSTANCE:{'fullpath':guard.INSTANCE,'type':guard.VLNV,'phys_addr':0x42000000,'addr_range':4096}}
        check('actual-ip-dict-match-software-only',lambda:c.check_overlay(Overlay(),v['mapping']))
        def bad_overlay():
            o=Overlay();o.ip_dict=copy.deepcopy(o.ip_dict);o.ip_dict[guard.INSTANCE]['phys_addr']=0x41000000
            return rejects(lambda:c.check_overlay(o,v['mapping']),'differs')
        check('actual-ip-dict-base-mismatch',bad_overlay)
    builtins.__import__=original_import
    assert not runtime_imports
    failed=sum(x['status']=='failed' for x in cases)
    result={'status':'passed' if not failed else 'failed','case_count':len(cases),'failed':failed,'cases':cases,
            'scope':'NEW software/synthetic author controls; no production package/build/runtime/board proof',
            'PYNQ_imports':runtime_imports,'pid':os.getpid(),'argv':sys.argv,'python':sys.version,
            'source_pins':{p.name:c.sha(p.read_bytes()) for p in sorted(here.glob('*.py'))}}
    (out/'RESULT.json').write_bytes(encoded(result))
    print(json.dumps({'status':result['status'],'case_count':len(cases),'failed':failed}),flush=True)
    return int(bool(failed))


if __name__=='__main__':raise SystemExit(main())
