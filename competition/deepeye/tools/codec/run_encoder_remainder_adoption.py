#!/usr/bin/env python3
"""Bounded author ModelSim run of exact main-approved production bytes.

Reuses op36 candidate, TB, fixture generator, pinned golden and strict checker.
No main oracle/cases are imported. Comparator shares the adopted arithmetic;
this run is bounded author fixture evidence, not independent old-chain proof.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
BASE = '51e2090ebaa601a928a522f11677c6689e7d5a1a'
PRODUCTION_SHA256 = '4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532'
DEPENDENCIES = {
    'candidate':('fpga/codec/deepeye_block_encoder_remainder_candidate.sv','9cd6f8347139b19db318ef2e0a349784e452f9703773afebae689875bc180018'),
    'tb':('tests/rtl/codec/tb_encoder_remainder_candidate.sv','f772f6bae060e8585d24f969aec9a2f70847768bb6a27c7bc1d9d85344236772'),
    'helper':('tools/codec/run_encoder_remainder_candidate.py','559a315f4c0d7a5f51912a66d207629e5defe282930d05390bce913dffb7db43'),
    'golden':('golden/codec/codec_reference.py','2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5'),
}


def utc(): return datetime.now(timezone.utc).isoformat()
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda:handle.read(1 << 20),b''): h.update(chunk)
    return h.hexdigest()
def save(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def require(value,message):
    if not value: raise RuntimeError(message)
def load_module(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    require(spec is not None and spec.loader is not None,'module load '+str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--modelsim-home',type=Path,required=True)
    ap.add_argument('--thread-id',required=True)
    ap.add_argument('--turn-id',required=True)
    ap.add_argument('--job-id',required=True)
    args = ap.parse_args()
    p = Path(__file__).resolve().parents[2]
    w = p.parents[1]
    author = p/'evidence/codec/encoder-remainder-adoption-20261024-37/author'
    output = args.output.resolve()
    require(output.is_relative_to(author.resolve()) and output != author.resolve(),
            'output must be a new child of the owned author directory')
    require(not output.exists(),'refusing existing output; preserve prior evidence')
    output.mkdir(parents=True)
    for name in ('inputs','logs','terminal-probes'): (output/name).mkdir()
    commands = []
    result = {
        'schema':1,'task_id':'DEEPEYE-IMPLEMENTATION-20261014','task_version':1,
        'work_id':'B-ENCODER-REMAINDER-ADOPTION-20261024-37-v1',
        'operation_id':'B-DEEPEYE-ENCODER-REMAINDER-ADOPTION-20261024-37',
        'thread_id':args.thread_id,'turn_id':args.turn_id,'job_id':args.job_id,
        'quality_main_thread_id':'01a13b55-095b-7461-8dd5-5476a130bd82',
        'pid':os.getpid(),'argv':[sys.executable]+sys.argv,'cwd':str(Path.cwd()),
        'python_version':sys.version,'started_utc':utc(),'status':'running',
        'contract':{'id':'DEEPEYE-HUMAN-LOCK-20261014','revision':1,
                    'requirements_ids':['H%02d'%i for i in range(1,16)],
                    'requirements_sha256':'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804',
                    'commit':'f5989cd5defce561f9ba98e6b18fc2682945f0a2',
                    'design_commit':'1011259415a0916054eb580687612580bc1e5f09'},
        'sources':{},'commands':commands,'implemented_source':'not_run','adopted_software':'not_run',
        'formal_29':'not_run','B01':'not_run','B03':'not_run','B06':'not_run','R03':'not_run',
        'integrated_wrapper':'not_run','synthesis':'not_run','OOC':'not_run','implementation':'not_run',
        'timing_closure':'not_run','CDC':'not_run','board':'not_run','system':'not_run','final_acceptance':'not_run',
        'reused_references':{'operation':'B-DEEPEYE-ENCODER-REMAINDER-20261024-36',
                             'candidate_tb_golden_checker':'unchanged published op36',
                             'fixtures':'same make_cases/write_fixtures functions and deterministic seed; original op36 fixture coverage reused explicitly'},
        'limitations':['Candidate comparator shares the adopted reconstruction arithmetic; not independent old-chain equivalence.',
                       'Expected payload bytes reuse published golden; no new independent codec oracle.',
                       'Trace omits candidate metadata/data and config payload/s_last; offline checker cannot reconstruct unrecorded ports.',
                       'No integrated wrapper, OOC, timing closure, CDC, board, system or final acceptance by this worker.'],
    }

    def run(name,argv,cwd=output,timeout=120):
        rec = {'name':name,'argv':[str(a) for a in argv],'cwd':str(cwd),'pid':None,
               'started_utc':utc(),'stdout':'logs/'+name+'.stdout.txt',
               'stderr':'logs/'+name+'.stderr.txt','exit_code':None}
        commands.append(rec); save(output/'RESULT.json',result)
        t0 = time.monotonic()
        with (output/rec['stdout']).open('wb') as stdout, (output/rec['stderr']).open('wb') as stderr:
            try:
                proc = subprocess.Popen(rec['argv'],cwd=cwd,stdout=stdout,stderr=stderr,shell=False)
                rec['pid'] = proc.pid
                save(output/'RESULT.json',result)
                try: rec['exit_code'] = proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    rec['timed_out'] = True
                    proc.kill(); rec['exit_code'] = proc.wait()
                    raise RuntimeError('timeout: '+name)
            finally:
                rec['finished_utc'] = utc(); rec['duration_seconds'] = time.monotonic()-t0
                rec['stdout_sha256'] = sha(output/rec['stdout'])
                rec['stderr_sha256'] = sha(output/rec['stderr'])
                save(output/'RESULT.json',result)
        require(rec['exit_code'] == 0,'%s exit %s' % (name,rec['exit_code']))
        return (output/rec['stdout']).read_bytes()

    exit_code = 1
    try:
        adoption = json.loads((author/'ADOPTION.json').read_bytes())
        require(adoption['state'] == 'exact_main_bytes_applied','missing exact-byte adoption receipt')
        result['adoption_receipt'] = {'path':str(author/'ADOPTION.json'),'sha256':sha(author/'ADOPTION.json')}
        result['old_production_sha256'] = adoption['old_production_sha256']
        result['production_diff'] = {'path':str(author/'production.diff.txt'),'sha256':sha(author/'production.diff.txt')}
        result['publication_gate'] = adoption['publication_gate']
        result['source_head'] = run('git_head',['git','rev-parse','HEAD'],cwd=w).decode().strip()
        require(result['source_head'] == BASE,'base HEAD drift')
        for name,(rel,expected) in DEPENDENCIES.items():
            path = p/rel
            require(sha(path) == expected,'dependency hash drift: '+name)
            blob = run('git_show_'+name,['git','show',BASE+':competition/deepeye/'+rel],cwd=w)
            require(hashlib.sha256(blob).hexdigest() == expected and blob == path.read_bytes(),
                    'fixed op36 Git bytes mismatch: '+name)
            snapshot = output/'inputs'/path.name
            shutil.copyfile(path,snapshot)
            result['sources'][name] = {'path':str(path),'sha256':expected,'snapshot':str(snapshot.relative_to(output)),
                                       'git_commit':BASE,'git_bytes_match':True}
        for name,rel,expected in (
            ('production','fpga/codec/deepeye_block_encoder.sv',PRODUCTION_SHA256),
            ('notes','fpga/codec/encoder_remainder_adoption.md',None),
            ('runner','tools/codec/run_encoder_remainder_adoption.py',None)):
            path = p/rel
            actual = sha(path)
            if expected: require(actual == expected,'production main byte hash mismatch')
            snapshot = output/'inputs'/path.name
            shutil.copyfile(path,snapshot)
            require(snapshot.read_bytes() == path.read_bytes(),'snapshot byte mismatch')
            result['sources'][name] = {'path':str(path),'sha256':actual,'snapshot':str(snapshot.relative_to(output))}
        result['implemented_source'] = 'exact_main_bytes_applied'
        helper = load_module('op36_author_fixture_and_checker',output/'inputs/run_encoder_remainder_candidate.py')
        golden = load_module('op36_published_codec_reference',output/'inputs/codec_reference.py')
        cases = helper.make_cases(golden)
        require(len(cases) == 297,'planned valid fixture count changed')
        save(output/'fixtures.json',cases)
        helper.write_fixtures(output/'fixtures.txt',cases)
        original_fixture = p/'evidence/codec/encoder-remainder-20261024-36/author/attempt-01/fixtures.txt'
        require((output/'fixtures.txt').read_bytes() == original_fixture.read_bytes(),
                'reused op36 deterministic fixture bytes differ')
        result['fixtures'] = {'valid_cases':len(cases),'modes':dict(Counter(c['fixture']['mode'] for c in cases)),
                               'counts':sorted({len(c['samples']) for c in cases}),
                               'e':sorted({c['e'] for c in cases}),'sha256':sha(output/'fixtures.txt'),
                               'json_sha256':sha(output/'fixtures.json'),
                               'original_op36_fixture':str(original_fixture),
                               'original_op36_fixture_sha256':sha(original_fixture),'same_bytes':True}
        home = args.modelsim_home.resolve()
        exe = {name:home/(name+'.exe') for name in ('vlib','vmap','vlog','vsim')}
        require(all(path.is_file() for path in exe.values()),'ModelSim executable missing')
        result['tools'] = {name:{'path':str(path),'sha256':sha(path)} for name,path in exe.items()}
        for name in ('vlog','vsim'):
            result['tools'][name]['version'] = run(name+'_version',[exe[name],'-version']).decode('utf-8',errors='replace').strip()
        run('vmap_init',[exe['vmap'],'-c'])
        run('vlib',[exe['vlib'],output/'work'])
        run('vmap_work',[exe['vmap'],'work',output/'work'])
        run('vlog',[exe['vlog'],'-sv','-work','work',output/'inputs/deepeye_block_encoder.sv',
                    output/'inputs/deepeye_block_encoder_remainder_candidate.sv',
                    output/'inputs/tb_encoder_remainder_candidate.sv'])
        dofile = output/'run.do'
        dofile.write_text('onerror {quit -f -code 2}\nonbreak {quit -f -code 3}\nrun -all\nquit -f -code 0\n',encoding='ascii')
        print('START fresh production compile/run; reused op36 fixtures=297',flush=True)
        transcript = run('vsim',[exe['vsim'],'-c','-t','1ns','-l',output/'transcript.txt','-wlf',output/'simulation.wlf',
                                'work.tb_encoder_remainder_candidate','+INPUT='+(output/'fixtures.txt').as_posix(),
                                '+TRACE='+(output/'public_ports.txt').as_posix(),'-do',dofile],timeout=600).decode('utf-8',errors='strict')
        trace = output/'public_ports.txt'
        with trace.open('r',encoding='ascii',newline='') as rows:
            parsed = helper.check_saved_run(transcript,rows,cases)
        summary = parsed['summary']
        require(summary['valid'] == 297 and summary['invalid'] == 6 and summary['abort'] == 24 and summary['recovery'] == 24,
                'planned coverage missing')
        result['strict_reconciliation'] = parsed
        result['public_ports'] = {'path':str(trace),'sha256':sha(trace),'rows':parsed['trace_rows']}
        lines = transcript.splitlines()
        done_index = lines.index('# TB_DONE encoder_remainder_candidate PASS')
        negative = {
            'missing_done':lines[:done_index]+lines[done_index+1:],
            'duplicate_done':lines[:done_index]+[lines[done_index]]+lines[done_index:],
            'truncated_terminal':lines[:-1],
        }
        probes = []
        for name,changed in negative.items():
            bad = '\n'.join(changed)+'\n'
            path = output/'terminal-probes'/(name+'.stdout.txt')
            path.write_bytes(bad.encode('utf-8'))
            try:
                with trace.open('r',encoding='ascii',newline='') as rows:
                    helper.check_saved_run(bad,rows,cases)
            except helper.EvidenceError as exc:
                probes.append({'name':name,'accepted':False,'error':str(exc),'path':str(path.relative_to(output)),
                               'sha256':sha(path)})
            else: raise RuntimeError('strict checker accepted terminal mutation: '+name)
        result['terminal_probes'] = probes
        result['adopted_software'] = 'author_bounded_pass'
        result['status'] = 'author_adoption_bounded_pass'
        exit_code = 0
        print('PASS '+json.dumps(summary,sort_keys=True),flush=True)
    except Exception as exc:
        result['status'] = 'failed'; result['error'] = str(exc); result['traceback'] = traceback.format_exc()
        (output/'failure.txt').write_text(result['traceback'],encoding='utf-8')
        print(result['traceback'],file=sys.stderr,flush=True)
    finally:
        result['source_hashes_after'] = {name:sha(info['path']) for name,info in result['sources'].items()}
        result['source_drift'] = [name for name,info in result['sources'].items()
                                  if result['source_hashes_after'][name] != info['sha256']]
        adoption_path = author/'ADOPTION.json'
        protected = json.loads(adoption_path.read_bytes())['protected_dependencies'] if adoption_path.exists() else {}
        result['protected_dependency_hashes_after'] = {name:sha(name) for name in protected}
        result['protected_drift'] = [name for name,digest in protected.items()
                                     if result['protected_dependency_hashes_after'][name] != digest]
        if result['source_drift'] or result['protected_drift']:
            result['status'] = 'failed'; result['error'] = 'source/protected dependency drift'; exit_code = 1
        result['finished_utc'] = utc(); result['exit_code'] = exit_code
        save(output/'RESULT.json',result)
        save(output/'artifact_hashes.json',{f.relative_to(output).as_posix():sha(f) for f in sorted(output.rglob('*'))
                                          if f.is_file() and f.name != 'artifact_hashes.json'})
    print('RESULT '+str(output/'RESULT.json'),flush=True)
    return exit_code


if __name__ == '__main__': raise SystemExit(main())
