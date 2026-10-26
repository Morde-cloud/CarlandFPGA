"""New DDR-only offline controls. Mutated fixtures are never build authority."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import platform
import sys
import traceback
import tkinter
import xml.etree.ElementTree as ET

import build_g05 as g


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write('\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def rejected(fn, message):
    try:
        fn()
    except RuntimeError as e:
        assert message in str(e), (message, str(e))
        return str(e)
    raise AssertionError('accepted invalid fixture')


def no_process(*args, **kwargs):
    raise AssertionError('process launch forbidden in offline DDR controls')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--tcl', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    g.run_owned = no_process
    # Pure parser/Tcl controls must not launch subprocesses or use the network.
    def audit(event, values):
        if event in ('subprocess.Popen', 'os.system', 'socket.connect'):
            raise AssertionError('forbidden offline event: ' + event)
    sys.addaudithook(audit)
    board = (args.inputs / 'tul_preset.xml').read_bytes()
    vendor = (args.inputs / 'vendor_ddr_preset.xml').read_bytes()
    tcl_text = args.tcl.read_text(encoding='utf-8')
    resolution = g.resolve_ddr(board, vendor)
    results = []

    def run(name, fn):
        directory = args.output / name
        directory.mkdir()
        try:
            detail = fn(directory)
            result = {'name': name, 'passed': True, 'detail': detail}
        except Exception:
            result = {'name': name, 'passed': False, 'traceback': traceback.format_exc()}
        save(directory / 'RESULT.json', result)
        results.append(result)
        print(('PASS ' if result['passed'] else 'FAIL ') + name, flush=True)
        if not result['passed']:
            print(result['traceback'], flush=True)

    def pinned(d):
        assert resolution['counts'] == dict(raw_board=771, literal_ddr=72, resolved_ddr=72,
                                            model_set=13, model_disable=13, model_unchanged=10, overrides=3)
        expected = {g.DDR_PREFIX+k: {'board_literal': old, 'named_model': new}
                    for k, (old, new) in g.DDR_OVERRIDES.items()}
        assert resolution['differences'] == expected
        assert sum(resolution['literal_ddr'][k] == v for k, v in resolution['resolved_ddr'].items()) == 69
        assert resolution['scope'] == 'pinned_named_model_resolution_not_physical_proof'
        assert len(g.BUILD_FILES) == 8 and not any(p.endswith('test_ddr_resolution.py') for p in g.BUILD_FILES)
        save(d/'resolution.json', resolution)
        return resolution['counts']
    run('01_pinned_sources_771_72_13_10_3', pinned)
    run('02_production_vendor_hash_rejected', lambda d: rejected(lambda: g.resolve_ddr(board, vendor+b'\n'), 'vendor DDR preset hash'))
    run('03_production_board_hash_rejected', lambda d: rejected(lambda: g.resolve_ddr(board+b'\n', vendor), 'TUL board preset hash'))

    def mutate_vendor(d, action, message):
        root = ET.fromstring(vendor)
        selected = [p for p in root.findall('preset') if p.get('name') == g.DDR_SELECTOR['name']][0]
        action(root, selected)
        changed = ET.tostring(root)
        (d/'mutated_vendor_TEST_ONLY.xml').write_bytes(changed)
        return rejected(lambda: g.resolve_ddr_test_fixture(board, changed), message)

    def child(p, tag, suffix):
        return [x for x in p if x.tag == tag and x.get('param') == 'pcw_uiparam_ddr_'+suffix.lower()][0]
    vendor_cases = [
        ('04_duplicate_model', lambda r,p: r.append(copy.deepcopy(p)), 'unique exact named'),
        ('05_wrong_model', lambda r,p: p.set('name', 'MT41J256M16 OTHER'), 'unique exact named'),
        ('06_wrong_selector', lambda r,p: p.set('param', 'other_selector'), 'unique exact named'),
        ('07_wrong_strength', lambda r,p: p.set('strength', '10'), 'unique exact named'),
        ('08_missing_set', lambda r,p: p.remove(child(p,'set','CL')), 'exact13'),
        ('09_extra_set', lambda r,p: ET.SubElement(p,'set',param='pcw_uiparam_ddr_extra',value='1'), 'exact13'),
        ('10_duplicate_set', lambda r,p: p.append(copy.deepcopy(child(p,'set','CL'))), 'duplicate model set'),
        ('11_missing_disable', lambda r,p: p.remove(child(p,'disable','CL')), 'same13'),
        ('12_extra_disable', lambda r,p: ET.SubElement(p,'disable',param='pcw_uiparam_ddr_extra'), 'same13'),
        ('13_duplicate_disable', lambda r,p: p.append(copy.deepcopy(child(p,'disable','CL'))), 'duplicate model disable'),
        ('14_different_disable_key', lambda r,p: child(p,'disable','CL').set('param','pcw_uiparam_ddr_freq_mhz'), 'same13'),
        ('15_unexpected_entry', lambda r,p: ET.SubElement(p,'enable',param='pcw_uiparam_ddr_cl'), 'unexpected named-model'),
        ('16_fourth_value_change', lambda r,p: child(p,'set','CL').set('value','8'), 'exact three'),
        ('17_wrong_override', lambda r,p: child(p,'set','T_RC').set('value','48.9101'), 'exact three'),
        ('18_missing_override', lambda r,p: child(p,'set','T_RCD').set('value','13.125'), 'exact three'),
        ('19_extra_selector_attribute', lambda r,p: p.set('extra','1'), 'unique exact named'),
    ]
    for name, action, message in vendor_cases:
        run(name, lambda d, a=action, m=message: mutate_vendor(d,a,m))

    def board_mutation(d, kind):
        root = ET.fromstring(board)
        params = root.find("./ip_preset[@preset_proc_name='ps7_preset']/ip[@name='processing_system7']/user_parameters")
        p = [p for p in params if p.get('name') == g.DDR_PREFIX+'PARTNO'][0]
        if kind == 'duplicate':
            params.append(copy.deepcopy(p)); message='duplicate/malformed'
        elif kind == 'missing':
            params.remove(p); message='exact771'
        elif kind == 'ddr_count':
            p.set('name', 'CONFIG.NOT_A_DDR_KEY'); message='exact72'
        else:
            p.set('value','Custom'); message='board named model'
        raw = ET.tostring(root)
        (d/'mutated_board_TEST_ONLY.xml').write_bytes(raw)
        return rejected(lambda: g.resolve_ddr_test_fixture(raw,vendor),message)
    for number, kind in enumerate(('duplicate','missing','ddr_count','wrong_model'),20):
        run(f'{number}_board_{kind}', lambda d,k=kind: board_mutation(d,k))

    def fixture_label(d):
        r=g.resolve_ddr_test_fixture(board,vendor)
        assert r['scope']=='synthetic_parser_fixture_not_build_authority'
        assert r['resolved_ddr']==resolution['resolved_ddr']
        return {'scope':r['scope'],'cli_bypass_option':False}
    run('24_explicit_fixture_label',fixture_label)

    def make_inputs(d):
        inputs=d/'inputs'
        path=inputs/'board_repo/pynq-z2/A.0/preset.xml'
        path.parent.mkdir(parents=True)
        path.write_bytes(board)
        r=g.write_ddr_inputs(path,args.inputs/'vendor_ddr_preset.xml',inputs)
        assert g.verify_ddr_inputs(inputs)==r==resolution
        return inputs

    def snapshots(d):
        inputs=make_inputs(d)
        index={p.relative_to(d).as_posix():g.record(p) for p in sorted(inputs.rglob('*')) if p.is_file()}
        assert 'inputs/vendor_ddr_preset.xml' in index
        assert index['inputs/vendor_ddr_preset.xml']['sha256']==g.DDR_VENDOR_SHA
        assert (inputs/'vendor_ddr_preset.xml').read_bytes()==vendor
        save(d/'SIMULATED_LAUNCH_INPUTS_NOT_A_BUILD.json',index)
        t=tkinter.Tcl();t.call('source',str(inputs/'ddr_expected.tcl'))
        for var,key in [('literal_ddr','literal_ddr'),('expected_ddr','resolved_ddr')]:
            raw=t.getvar(var)
            assert int(t.call('dict','size',raw))==72
            assert {k:str(t.call('dict','get',raw,k)) for k in resolution[key]}==resolution[key]
        return {'snapshotted_files':len(index),'raw_vendor_identical':True,'Tcl_tables':{'literal':72,'resolved':72}}
    run('25_snapshots_and_Tcl_tables',snapshots)

    def tamper(d):
        errors={}
        for name in ('vendor_ddr_preset.xml','board_repo/pynq-z2/A.0/preset.xml','ps7_preset_parameters.json',
                     'ddr_literal.json','ddr_resolved.json','ddr_resolution.json','ddr_expected.tcl'):
            sub=d/str(len(errors));sub.mkdir()
            inputs=make_inputs(sub);path=inputs/name
            if name.endswith('.json'):
                value=json.loads(path.read_text());value['tampered']='TEST_ONLY'
                path.write_text(json.dumps(value),encoding='utf-8')
            else:
                path.write_bytes(path.read_bytes()+b'\n')
            errors[name]=rejected(lambda:g.verify_ddr_inputs(inputs),'')
        return errors
    run('26_all_seven_DDR_inputs_reverified',tamper)

    def interpreter():
        t=tkinter.Tcl();t.setvar('g05_library_only',1);t.call('source',str(args.tcl))
        t.eval(g.ddr_expected_text(resolution))
        t.eval('''
            set mock_actual $expected_ddr
            set mock_properties [dict keys $expected_ddr]
            set mock_calls {}; set mock_fail_key {}; set mock_inventory_fail 0
            proc list_property {ps} {
                if {$::mock_inventory_fail} {error {injected inventory failure}}
                return $::mock_properties
            }
            proc get_property {key ps} {
                lappend ::mock_calls $key
                if {$key eq $::mock_fail_key} {error {injected read failure}}
                return [dict get $::mock_actual $key]
            }
        ''')
        return t

    def evidence(t,d,stage):
        t.call('source',str(d/(stage+'_ddr72.tcl')))
        e=t.getvar('ddr_stage_evidence')
        def get(key):return t.call('dict','get',e,key)
        actual=get('actual_ddr')
        count=int(t.call('dict','size',actual))
        errors=list(t.splitlist(get('errors')))
        differences=int(t.call('dict','size',get('differences')))
        assert len((d/(stage+'_ddr72.tsv')).read_text().splitlines())==count+1
        assert len((d/(stage+'_ddr_differences.tsv')).read_text().splitlines())==differences+1
        return {'stage':stage,'actual_count':count,'differences':differences,'errors':errors,
                'get_property_calls':int(t.call('llength',t.getvar('mock_calls')))}

    def gate(d,kind):
        t=interpreter();stage='after_board_fclk'
        if kind=='both_pass':
            result=[]
            for stage in ('after_board_fclk','after_validate'):
                t.setvar('mock_calls','')
                t.call('check_ddr72','ps',t.getvar('literal_ddr'),t.getvar('expected_ddr'),str(d),stage)
                e=evidence(t,d,stage)
                assert e['get_property_calls']==e['actual_count']==72 and e['differences']==3 and not e['errors']
                result.append(e)
            return result
        key=g.DDR_PREFIX+'CL'
        if kind in ('mismatch','numeric_near','numeric_format'):
            key=g.DDR_PREFIX+('T_RC' if kind!='mismatch' else 'CL')
            value={'mismatch':'8','numeric_near':'48.91001','numeric_format':'48.910'}[kind]
            t.call('dict','set','mock_actual',key,value)
        elif kind=='missing':
            t.eval('set mock_properties [lrange $mock_properties 1 end]')
        elif kind=='extra':
            t.call('lappend','mock_properties',g.DDR_PREFIX+'EXTRA')
            t.call('dict','set','mock_actual',g.DDR_PREFIX+'EXTRA','TEST_ONLY')
        elif kind=='read_error':t.setvar('mock_fail_key',key)
        elif kind=='inventory_error':t.setvar('mock_inventory_fail',1)
        try:
            t.call('check_ddr72','ps',t.getvar('literal_ddr'),t.getvar('expected_ddr'),str(d),stage)
        except tkinter.TclError as err:
            assert 'DDR72 mismatch' in str(err)
            error=str(err)
        else:raise AssertionError('bad DDR gate passed')
        e=evidence(t,d,stage)
        assert e['actual_count']==(73 if kind=='extra' else 72) and e['errors']
        assert e['get_property_calls']=={'missing':71,'extra':73,'inventory_error':0}.get(kind,72)
        assert not (d/'after_validate_ddr72.tcl').exists()
        return {'gate_error':error,'retained':e,'unreached_second_stage':'not fabricated'}
    for number,kind in enumerate(('both_pass','mismatch','numeric_near','numeric_format','missing','extra','read_error','inventory_error'),27):
        run(f'{number}_Tcl_{kind}',lambda d,k=kind:gate(d,k))

    def validation(d,kind):
        t=interpreter();reports=d/'reports';reports.mkdir()
        start=tcl_text.index('    set validation_code [catch {validate_bd_design}')
        end=tcl_text.index('    require {[get_property CONFIG.C_EXT_RESET_HIGH',start)
        block=tcl_text[start:end]
        (d/'exact_validation_block.tcl').write_text(block,encoding='utf-8')
        t.setvar('run_root',str(d));t.setvar('ps','ps');t.setvar('generated',0)
        if kind!='validation_ok_ddr_bad':
            t.eval('proc validate_bd_design {} {error {injected validation failure}}')
        else:t.eval('proc validate_bd_design {} {return}')
        if kind!='validation_bad_ddr_ok':t.call('dict','set','mock_actual',g.DDR_PREFIX+'CL','8')
        t.eval('proc validation_probe {} {global run_root ps literal_ddr expected_ddr\n'+block+'\nset ::generated 1\n}')
        try:t.call('validation_probe')
        except tkinter.TclError as err:error=str(err)
        else:raise AssertionError('invalid validation continued')
        if kind!='validation_ok_ddr_bad':assert error=='injected validation failure'
        else:assert 'DDR72 mismatch' in error
        assert int(t.getvar('generated'))==0
        e=evidence(t,reports,'after_validate')
        assert e['get_property_calls']==e['actual_count']==72
        assert bool(e['errors'])==(kind!='validation_bad_ddr_ok')
        t.call('source',str(reports/'bd_validation_status.tcl'))
        status=t.getvar('bd_validation_status')
        assert int(t.call('dict','get',status,'return_code'))==int(kind!='validation_ok_ddr_bad')
        return {'primary_error':error,'retained':e,'generation_reached':False}
    for number,kind in enumerate(('validation_bad_ddr_ok','validation_ok_ddr_bad','both_bad'),35):
        run(f'{number}_{kind}',lambda d,k=kind:validation(d,k))

    def integration(d):
        source=Path(g.__file__).read_text(encoding='utf-8')
        tree=ast.parse(source)
        build=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='build')
        text=ast.get_source_segment(source,build)
        assert text.index('verify_ddr_inputs') < text.index('launch_inputs=') < text.index('process=run_owned')
        assert "digest(args.tool_root/DDR_VENDOR_REL)==DDR_VENDOR_SHA" in text
        assert "for name,value in launch_inputs.items():require(digest(out/name)==value['sha256']" in text
        assert tcl_text.index('after_board_fclk',tcl_text.index('proc full_build')) < tcl_text.index('set validation_code')
        assert tcl_text.index('set ddr_code') < tcl_text.index('generate_target all')
        t=interpreter()
        assert t.call('ddr_tsv','a\tb\nc\\d')=='a\\tb\\nc\\\\d'
        return {'kind':'static production wiring plus actual Tcl escaping control',
                'build_invoked':False,'launch_inventory_fixture_only':True}
    run('38_launch_and_gate_order',integration)
    run('39_unknown_DTD_rejected',lambda d:rejected(lambda:g.resolve_ddr_test_fixture(
        board,vendor.replace(b'"presets.dtd"',b'"unknown.dtd"')),'unexpected DTD/entity'))
    run('40_entity_declaration_rejected',lambda d:rejected(lambda:g.resolve_ddr_test_fixture(
        board,vendor.replace(b'<presets>',b'<!ENTITY x "injected">\n<presets>',1)),'unexpected DTD/entity'))
    failed=sum(not r['passed'] for r in results)
    summary={'scope':'new offline DDR parser and mocked Tcl only; not build/board acceptance',
             'python':platform.python_version(),'Tcl':tkinter.Tcl().eval('info patchlevel'),
             'argv':sys.argv,'controls':len(results),'passed':len(results)-failed,'failed':failed,
             'board_sha256':sha(board),'vendor_sha256':sha(vendor),
             'requirements_sha256':g.CONTRACT,'frozen_design':g.DESIGN,
             'build_source_sha256':sha(Path(g.__file__).read_bytes()),'tcl_source_sha256':sha(args.tcl.read_bytes()),
             'test_source_sha256':sha(Path(__file__).read_bytes()),'results':results}
    save(args.output/'SUMMARY.json',summary)
    print(f'DDR_TARGETED_CONTROLS total={len(results)} passed={len(results)-failed} failed={failed}',flush=True)
    return int(bool(failed))


if __name__=='__main__':
    raise SystemExit(main())
