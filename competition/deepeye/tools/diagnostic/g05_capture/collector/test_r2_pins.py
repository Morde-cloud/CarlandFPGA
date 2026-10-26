"""New R2 pin/layout controls only; synthetic offline packages, never hardware."""
import argparse
import builtins
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

import collector as c
import pins
from fixtures_author import CAPTURED_DDR, encoded, package_bytes


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo',type=Path,required=True)
    ap.add_argument('--product',type=Path,required=True)
    ap.add_argument('--ddr-inputs',type=Path,required=True)
    ap.add_argument('--baseline-pins',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    original_import=builtins.__import__;attempts=[]
    def no_pynq(name,*args,**kwargs):
        if name=='pynq' or name.startswith('pynq.'):
            attempts.append(name);raise AssertionError('PYNQ import forbidden in R2 offline controls')
        return original_import(name,*args,**kwargs)
    builtins.__import__=no_pynq
    here=Path(__file__).resolve().parent
    guard_raw=(here/'hwh_guard_pinned.py').read_bytes();assert c.sha(guard_raw)==pins.GUARD_SHA
    guard=c.module_bytes(guard_raw,'r2_test_guard')
    old_raw=a.baseline_pins.read_bytes()
    assert c.sha(old_raw)=='1d84dcd51ca66827d4214a764d382fab1cb7608725a1c106c94f40af300e029b'
    old=c.module_bytes(old_raw,'r2_test_old_pins')
    seed=package_bytes(a.repo,a.product,guard,ddr_inputs=a.ddr_inputs)
    new_files=('inputs/vendor_ddr_preset.xml','inputs/ddr_literal.json',
               'inputs/ddr_resolved.json','inputs/ddr_resolution.json')
    changed_tools={n:old.BUILD_FILES[n] for n,h in pins.BUILD_FILES.items() if old.BUILD_FILES[n]!=h}
    assert len(changed_tools)==3 and old.SOURCES==pins.SOURCES
    assert set(pins.LAUNCH_PINS)-set(old.LAUNCH_PINS)=={'inputs/vendor_ddr_preset.xml'}
    results=[]

    def make(label,*,remove=(),extra=False,vendor_bad=False,old_tool=None,post_tamper=None,launch_bad=False):
        home=a.out/label;home.mkdir();package=home/'SYNTHETIC_PACKAGE';package.mkdir()
        blobs=dict(seed)
        acceptance={'schema':1,'TEST_FIXTURE':'synthetic-not-authority','accepted':True,
            'task_id':pins.TASK,'task_version':1,'director_thread_id':pins.MAIN,
            'requirements_sha256':pins.CONTRACT,'frozen_design':pins.DESIGN,'source_commit':'a'*40,
            'sources':dict(pins.SOURCES),'build_files':dict(pins.BUILD_FILES),
            'cdc_bindings':{n:[f'g05_diag_i/SYNTHETIC/{n}/stage{i}/D' for i in range(3)] for n in guard.PORTS if n.endswith('_i')},
            'cdc_source_review':{'reviewed_by':pins.MAIN,'path':'SYNTHETIC-NOT-AUTHORITY',
                                 'sha256':c.sha(blobs['inputs/main_cdc_review'])}}
        if old_tool:acceptance['build_files'][old_tool]=changed_tools[old_tool]
        blobs['inputs/main_source_acceptance.json']=encoded(acceptance)
        auth={'TEST_FIXTURE':'synthetic-not-authority','task_id':pins.TASK,'task_version':1,'director_thread_id':pins.MAIN,
            'authorized':True,'action':'full_g05_diagnostic_build','source_commit':'a'*40,
            'source_acceptance_sha256':c.sha(blobs['inputs/main_source_acceptance.json']),
            'requirements_sha256':pins.CONTRACT,'physical_unknowns_acknowledged':pins.UNKNOWN_PHYSICAL,
            'work_id':'SYNTHETIC-R2-FULLBUILD-NEVER-RUN','operation_id':'SYNTHETIC-R2-BUILD',
            'output_directory':str(package)}
        blobs['inputs/main_build_authorization.json']=encoded(auth)
        for name in remove:del blobs[name]
        if extra:blobs['inputs/ddr_unapproved.json']=encoded({'TEST_FIXTURE':'synthetic-not-authority'})
        if vendor_bad:blobs['inputs/vendor_ddr_preset.xml']+=b'\n'
        def records(names):return {n:{'path':str(package/n),'bytes':len(blobs[n]),'sha256':c.sha(blobs[n])} for n in names}
        launch=records(sorted(n for n in blobs if n.startswith('inputs/')))
        if launch_bad:launch['inputs/ddr_resolution.json']['sha256']='0'*64
        blobs['LAUNCH_INPUTS.json']=encoded(launch)
        identity=guard.verify_hwh(io.BytesIO(seed['artifacts/g05_diag.hwh']),json.loads(seed['BD_MAPPING.json']),fixture=True)
        manifest={'TEST_FIXTURE':'synthetic-not-authority','status':'completed_build_pending_main_review','run_id':'1'*32,
            'task_id':pins.TASK,'work_id':auth['work_id'],'operation_id':auth['operation_id'],
            'main_attested_source_commit':'a'*40,'requirements_sha256':pins.CONTRACT,'hwh':identity,
            'source_acceptance':records(['inputs/main_source_acceptance.json'])['inputs/main_source_acceptance.json'],
            'raw_synthesis_runs':['synth_1','SYNTHETIC-NOT-RUN'],'unmeasured_physical_inputs':pins.UNKNOWN_PHYSICAL,
            'formal_G05_B06':'not_accepted','board':'not_run; A-only','files':records(sorted(blobs))}
        blobs['ARTIFACT_MANIFEST.json']=encoded(manifest)
        for name,raw in blobs.items():
            path=package/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        if post_tamper:
            path=package/post_tamper
            raw=path.read_bytes();assert b'48.91' in raw
            path.write_bytes(raw.replace(b'48.91',b'48.92',1))
        digest=c.sha(blobs['ARTIFACT_MANIFEST.json'])
        fixture={'schema_version':1,'task_id':pins.TASK,'task_version':1,'requirements_sha256':pins.CONTRACT,
            'operation_id':'SYNTHETIC-NEW-R2-OPERATION','run_id':'2'*64,'nonce':'3'*32,'session':7,
            'expected_build_manifest_sha256':digest,
            'commands':[{'command_id':1,'tag':41,'profile':1,'yaw':0,'pitch':0,'speed':0,'ttl_ms':100}]}
        fixture_path=home/'SYNTHETIC_FIXTURE.json';fixture_path.write_bytes(encoded(fixture))
        return home,package,digest,fixture_path

    def check(label,expected=None,*,cli=False,production=False,**options):
        try:
            home,package,digest,fixture=make(label,**options)
            output=home/'collector_output'
            if cli:
                # Actual default-offline CLI. Test provenance does not enable runtime.
                argv=[sys.executable,'-B','-X','utf8',str(here/'collector.py'),'--package',str(package),
                      '--expected-manifest-sha256',digest,'--fixture',str(fixture),'--output',str(output)]
                if not production:argv.append('--synthetic-test-only')
                with (home/'cli.stdout.bin').open('xb') as stdout,(home/'cli.stderr.bin').open('xb') as stderr:
                    process=subprocess.Popen(argv,stdout=stdout,stderr=stderr,stdin=subprocess.DEVNULL,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    terminated=False
                    try:code=process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        terminated=True;process.kill();code=process.wait(timeout=5)
                (home/'CLI_PROCESS.json').write_bytes(encoded({'argv':argv,'pid':process.pid,'exit_code':code,
                    'terminal':process.poll() is not None,'timeout_seconds':15,'automatic_retry':False,
                    'termination_attempted':terminated}))
                assert not terminated,'CLI exceeded bounded wait'
                report=json.loads((output/'RECEIPT.json').read_bytes());assert code==report['exit_code']
            else:
                report=c.collect(package,digest,fixture,output,synthetic_test_only=not production)
            assert report['exit_code']==(2 if expected else 0),report
            if expected:assert expected in report.get('primary_error',''),report
            else:
                assert report['status']=='synthetic_test_offline_only'
                for name in new_files+('inputs/ps7_preset_parameters.json','inputs/ddr_expected.tcl'):
                    assert (output/'snapshots/package'/name).read_bytes()==seed[name]
                assert len(report['validation']['selected_files'])==46
            for flag in ('runtime_import_attempted','overlay_construct_attempted','download_attempted','mmio_construct_attempted'):
                assert report[flag] is False
            assert report['movement_authorized'] is False and report['cleanup']['attempted'] is False
            detail={'name':label,'passed':True,'collector_exit_code':report['exit_code'],
                    'status':report['status'],'error':report.get('primary_error'),'runtime_import_attempted':False}
        except Exception:
            detail={'name':label,'passed':False,'traceback':traceback.format_exc()}
        results.append(detail);print(json.dumps(detail),flush=True)

    check('01_valid_marked_R2_offline')
    for i,name in enumerate(new_files+('inputs/ps7_preset_parameters.json','inputs/ddr_expected.tcl'),2):
        check(f'{i:02}_missing_{Path(name).name}','unknown/missing actual launch',remove=(name,))
    check('08_extra_launch_input','unknown/missing actual launch',extra=True)
    check('09_vendor_bad_even_with_rebound_manifest','known launch dependency changed',vendor_bad=True)
    check('10_resolved_bytes_changed','selected hash/size mismatch',post_tamper='inputs/ddr_resolved.json')
    check('11_provenance_bytes_changed','selected hash/size mismatch',post_tamper='inputs/ddr_resolution.json')
    for i,name in enumerate(changed_tools,12):
        check(f'{i:02}_old_pin_{Path(name).name}','unknown exact source/tool version',old_tool=name)
    check('15_old_launch_layout','unknown/missing actual launch',remove=new_files)
    check('16_provenance_launch_binding','launch/manifest same-run hash mismatch',launch_bad=True)
    check('17_valid_marked_CLI',cli=True)
    check('18_production_rejects_synthetic_CLI','manifest schema/version',cli=True,production=True)
    assert not attempts and 'pynq' not in sys.modules
    failed=sum(not r['passed'] for r in results)
    summary={'scope':'new R2 pin/layout software-only; no actual R2 package or hardware proof',
             'total':len(results),'passed':len(results)-failed,'failed':failed,'runtime_import_attempts':attempts,
             'new_inputs':list(new_files),'captured_DDR_fixture_pins':CAPTURED_DDR,
             'requirements_sha256':pins.CONTRACT,'frozen_design':pins.DESIGN,'results':results}
    (a.out/'SUMMARY.json').write_bytes(encoded(summary))
    print(f'R2_PIN_LAYOUT_CONTROLS total={len(results)} passed={len(results)-failed} failed={failed}',flush=True)
    return int(bool(failed))


if __name__=='__main__':raise SystemExit(main())
