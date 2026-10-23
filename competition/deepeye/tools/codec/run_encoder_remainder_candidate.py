#!/usr/bin/env python3
"""Bounded author software/ModelSim evidence for the main-approved identity.

No main oracle is imported. Expected payload bytes reuse the pinned published
golden codec_reference.py, explicitly; the arithmetic sweep is independent.
All generated files, tool libraries and transcripts live inside --output.
An existing --output is refused. No synthesis, board or acceptance evaluation.
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
import random
import re
import shutil
import subprocess
import sys
import time
import traceback

sys.dont_write_bytecode = True
TASK_ID = 'DEEPEYE-IMPLEMENTATION-20261014'
WORK_ID = 'B-ENCODER-REMAINDER-CANDIDATE-20261024-36-v1'
OPERATION_ID = 'B-DEEPEYE-ENCODER-REMAINDER-20261024-36'
CONTRACT_COMMIT = 'f5989cd5defce561f9ba98e6b18fc2682945f0a2'
CONTRACT_HASH = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
ORIGINAL_HASH = '870bc5dcfe9a3a82124cf5d305082964b9a6ebf3447c13f1a92ec052a591d8a5'
GOLDEN_HASH = '2e24e01c7e8cc9a010f9c0f26d94091b33676b7394f0f7344ca5bf938fefbfd5'
CONTRACT = {
    'id': 'DEEPEYE-HUMAN-LOCK-20261014', 'revision': 1,
    'requirements_ids': ['H%02d' % i for i in range(1, 16)],
    'requirements_sha256': CONTRACT_HASH, 'commit': CONTRACT_COMMIT,
    'design_commit': '1011259415a0916054eb580687612580bc1e5f09',
}
E_VALUES = (0, 1, 2, 4, 8)
OWNED = (
    'fpga/codec/deepeye_block_encoder_remainder_candidate.sv',
    'fpga/codec/encoder_remainder_candidate.md',
    'tests/rtl/codec/tb_encoder_remainder_candidate.sv',
    'tools/codec/run_encoder_remainder_candidate.py',
    'evidence/codec/encoder-remainder-20261024-36/author/',
)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def arithmetic_sweep():
    """Every reachable n, each E, distinct feasible p endpoints/midpoint."""
    rows = []
    for e in E_VALUES:
        d = 2 * e + 1
        counts = Counter()
        remainders = set()
        min_y, max_y = 1 << 30, -(1 << 30)
        for n in range(e - 65535, e + 65536):
            a = abs(n)
            div_quot, r_abs = divmod(a, d)
            q_original = div_quot if n >= 0 else -(div_quot + int(r_abs != 0))
            r_euclid = d - r_abs if n < 0 and r_abs != 0 else r_abs
            assert q_original == n // d
            assert n == q_original * d + r_euclid
            assert 0 <= r_abs < d and 0 <= r_euclid < d
            assert -(1 << 17) <= n < (1 << 17) and a < (1 << 17)
            assert 0 <= (2*q_original if q_original >= 0 else -2*q_original-1) < (1 << 17)
            remainders.add(r_euclid)
            counts['reachable_n'] += 1
            counts['negative_divisible_n' if n < 0 and r_abs == 0 else
                   'negative_remainder_n' if n < 0 else 'nonnegative_n'] += 1
            lo, hi = max(0, e - n), min(65535, 65535 + e - n)
            assert lo <= hi
            for p in sorted({lo, (lo + hi)//2, hi}):
                x = n + p - e
                assert 0 <= x <= 65535 and 0 <= p <= 65535
                old_y = p + q_original * d
                new_y = x + e - r_euclid
                assert old_y == new_y
                # Check the specified signed 25-bit zero extensions and clamp.
                assert -8 <= new_y <= 65543 and x-e <= new_y <= x+e
                encoded25 = (x + e - r_euclid) & ((1 << 25)-1)
                signed25 = encoded25 - (1 << 25) if encoded25 & (1 << 24) else encoded25
                assert signed25 == old_y
                assert min(65535, max(0, old_y)) == min(65535, max(0, signed25))
                counts['feasible_x_p_cases'] += 1
                if old_y < 0: counts['low_clamp_cases'] += 1
                if old_y > 65535: counts['high_clamp_cases'] += 1
                min_y, max_y = min(min_y, new_y), max(max_y, new_y)
        assert counts['reachable_n'] == 131071
        rows.append({'e': e, 'd': d, 'counts': dict(counts),
                     'remainders_seen': sorted(remainders), 'preclamp_min': min_y,
                     'preclamp_max': max_y, 'n_range': [e-65535, e+65535]})
    return {'status': 'passed', 'method': 'all reachable n; distinct feasible p lo/mid/hi; actual x=n+p-E',
            'total_reachable_n': sum(r['counts']['reachable_n'] for r in rows),
            'total_feasible_x_p_cases': sum(r['counts']['feasible_x_p_cases'] for r in rows),
            'all_2_pow_32_x_p_pairs_enumerated': False, 'per_e': rows}


def make_cases(golden):
    rng = random.Random(0x2026102436)
    cases = []
    def add(label, samples, e):
        fixture = golden.encode_block(samples, e)
        golden.decode_block(fixture)
        cases.append({'id': len(cases), 'label': label, 'samples': samples, 'e': e,
                      'fixture': fixture})
    for e in E_VALUES:
        d = 2*e + 1
        for n in (1, 2, 127, 128):
            patterns = {
                'zero': [0]*n,
                'full': [65535]*n,
                'alternating_extrema': [0 if i % 2 == 0 else 65535 for i in range(n)],
                'ascending': [(100 + i*(e+1)) & 65535 for i in range(n)],
                'descending': [(65435 - i*(e+1)) & 65535 for i in range(n)],
                'sign_transitions': [(0,65535,32768,32767,1,65534,2,65533)[i%8] for i in range(n)],
                'random': [rng.randrange(65536) for _ in range(n)],
            }
            for label, samples in patterns.items():
                add('%s_n%d_e%d' % (label,n,e), samples, e)
        # Explicit anchor p=32768 gives n=-d, -(d+1), -1, 0, +1, +d.
        for num in (-2*d, -d-1, -d, -1, 0, 1, d-1, d, d+1):
            add('signed_n%d_e%d' % (num,e), [32768,32768-e+num], e)
        for p in (0,1,65534,65535):
            for x in (0,1,65534,65535):
                add('clamp_p%d_x%d_e%d' % (p,x,e), [p,x,0,65535,1,65534], e)
        for r in range(6):
            n = rng.choice((2,17,31,64,127,128))
            add('fixed_random_%d_e%d' % (r,e), [rng.randrange(65536) for _ in range(n)],e)
    # Exercise long legal unary fields in the unchanged Rice writer.
    for q in (9,15):
        add('unary_q%d' % q, [32768,32768+q]+[32768+q]*126, 0)
    assert {c['fixture']['mode'] for c in cases} == {'raw','rice'}
    return cases


def write_fixtures(path, cases):
    with path.open('w', encoding='ascii', newline='\n') as f:
        f.write('%d\n' % len(cases))
        for c in cases:
            v = c['fixture']; data = bytes.fromhex(v['payload_hex'])
            f.write('%d %d %d %d %d %d %d\n' % (
                c['id'], len(c['samples']), c['e'], int(v['mode']=='raw'),
                v['k'] if v['k'] is not None else 0, v['valid_bit_count'], len(data)))
            f.write(' '.join('%04x' % x for x in c['samples'])+'\n')
            f.write(' '.join('%02x' % x for x in data)+'\n')


class EvidenceError(ValueError):
    """Saved evidence is incomplete, contradictory or outside the pinned grammar."""


SUMMARY_FIELDS = ('valid', 'invalid', 'abort', 'recovery', 'completed', 'cycles',
                  'cfg', 'samples', 'meta', 'data', 'cfgstall', 'samplestall',
                  'metastall', 'datastall', 'reset', 'cancel')
DECIMAL = r'(0|[1-9][0-9]*)'
SUMMARY_RECORD = re.compile('# TB_SUMMARY ' + ' '.join(k+'='+DECIMAL for k in SUMMARY_FIELDS))
TRACE_RECORD = re.compile(' '.join([DECIMAL, DECIMAL] + [r'([01]{2})']*6 +
                         [r'([0-9a-f]{10})', r'([01][0-9a-f]{2})',
                          r'([0-9a-f]{4})', r'([0-3])']))


def require_evidence(condition, message):
    # Explicit checks remain effective under python -O; never qualify by assert/PASS substring.
    if not condition:
        raise EvidenceError(message)


def metadata_word(error, count, e, raw, k, bits, size):
    return (error << 38) | (count << 30) | (e << 26) | (raw << 25) | (k << 21) | (bits << 9) | size


def fixture_expectations(cases):
    require_evidence(type(cases) is list and len(cases) > 0, 'empty/non-list fixtures')
    expected = []
    for index, case in enumerate(cases):
        require_evidence(type(case) is dict and set(case) == {'id','label','samples','e','fixture'},
                         'fixture case fields')
        require_evidence(type(case['id']) is int and case['id'] == index and
                         type(case['label']) is str, 'fixture identity/order')
        samples, e, f = case['samples'], case['e'], case['fixture']
        require_evidence(type(samples) is list and 1 <= len(samples) <= 128 and
                         all(type(x) is int and 0 <= x <= 65535 for x in samples), 'fixture samples')
        require_evidence(type(e) is int and e in E_VALUES, 'fixture E')
        require_evidence(type(f) is dict and set(f) == {'mode','e','k','sample_count','valid_bit_count','payload_hex'},
                         'fixture output fields')
        require_evidence(type(f['e']) is int and f['e'] == e and type(f['sample_count']) is int and
                         f['sample_count'] == len(samples), 'fixture count/E mismatch')
        bits = f['valid_bit_count']
        require_evidence(type(bits) is int and 16 <= bits <= 16*len(samples), 'fixture bit count')
        require_evidence(type(f['payload_hex']) is str and
                         re.fullmatch(r'(?:[0-9a-f]{2})+', f['payload_hex']) is not None,
                         'fixture payload hex')
        data = bytes.fromhex(f['payload_hex'])
        require_evidence(len(data) == (bits+7)//8 and data[:2] == samples[0].to_bytes(2,'big'),
                         'fixture byte count/anchor')
        require_evidence(bits % 8 == 0 or data[-1] & ((1 << (8-bits%8))-1) == 0,
                         'fixture nonzero padding')
        raw = int(f['mode'] == 'raw')
        if raw:
            require_evidence(f['k'] is None and bits == 16*len(samples) and
                             data == b''.join(x.to_bytes(2,'big') for x in samples), 'fixture RAW')
            k = 0
        else:
            require_evidence(f['mode'] == 'rice' and type(f['k']) is int and 0 <= f['k'] <= 15,
                             'fixture Rice mode/k')
            k = f['k']
        expected.append({'id':index, 'kind':'valid', 'samples':samples, 'payload':data,
                         'metadata':metadata_word(0,len(samples),e,raw,k,bits,len(data)),
                         'record':'# TB_CASE id=%d n=%d e=%d raw=%d k=%d bits=%d bytes=%d PASS' %
                                  (index,len(samples),e,raw,k,bits,len(data)),
                         'cfg':1, 'meta':1, 'data':len(data), 'reset':0, 'cancel':0})
    return expected


def expected_trace_segments(valid):
    segments = list(valid)
    records = [c['record'] for c in valid]
    for i in range(6):
        samples = [] if i < 4 else [65535] if i == 4 else [65535,0]
        segments.append({'id':200000+i, 'kind':'invalid', 'samples':samples, 'payload':b'',
                         'metadata':metadata_word(1 if i<4 else 2,0,0,1,0,0,0),
                         'cfg':1,'meta':1,'data':0,'reset':0,'cancel':0})
        records.append('# TB_INVALID id=%d PASS' % (200000+i))
    # Independently specified aborted two-sample fixture [65535,0], E=8:
    # q=-3855, z=7709, lowest best k=12, 14 body bits, ffff7874 (30 valid bits).
    abort_metadata = metadata_word(0,2,8,0,12,30,4)
    recovery = {'kind':'recovery','samples':[0x1234], 'payload':bytes.fromhex('1234'),
                'metadata':metadata_word(0,1,8,1,0,16,2), 'cfg':1,'meta':1,'data':2,
                'reset':0,'cancel':0}
    for which in range(2):
        for stage in range(12):
            identifier = 300000 + 100*which + stage
            sample_count = 0 if stage in (0,1,11) else 1 if stage == 2 else 2
            metadata = (metadata_word(1,0,0,1,0,0,0) if stage == 11 else
                        abort_metadata if stage >= 7 else None)
            segments.append({'id':identifier, 'kind':'abort', 'samples':[65535,0][:sample_count],
                             'payload':bytes.fromhex('ffff7874'), 'metadata':metadata,
                             'cfg':int(stage != 0), 'meta':int(stage in (8,9,10)),
                             'data':int(stage == 10), 'reset':int(which == 0),
                             'cancel':int(which == 1)})
            segments.append(dict(recovery,id=100000+12*which+stage))
            records.append('# TB_ABORT id=%d which=%d stage=%d PASS' % (identifier,which,stage))
    return segments, records


def parse_saved_records(transcript, valid):
    require_evidence(type(transcript) is str and '\x00' not in transcript, 'invalid transcript text')
    lines = transcript.splitlines()
    require_evidence(not re.search(r'TB_FAIL|\*\*\s+(?:Error|Fatal|Warning)\b', transcript),
                     'simulator failure/warning diagnostic')
    attempted = [i for i,line in enumerate(lines) if 'TB_' in line]
    require_evidence(bool(attempted), 'missing TB records')
    segments, records = expected_trace_segments(valid)
    start = attempted[0]
    body = lines[start:]
    require_evidence(len(body) == len(records)+6, 'record/terminal placement or count')
    for i, wanted in enumerate(records):
        require_evidence(body[i] == wanted, 'record grammar/value/order at index %d' % i)
    summary_match = SUMMARY_RECORD.fullmatch(body[len(records)])
    require_evidence(summary_match is not None, 'summary grammar/duplicate/unknown field')
    summary = dict(zip(SUMMARY_FIELDS, map(int,summary_match.groups())))
    require_evidence(body[len(records)+1] == '# TB_DONE encoder_remainder_candidate PASS',
                     'completion grammar/uniqueness/order')
    finish, simtime, end, diagnostics = body[-4:]
    require_evidence(re.fullmatch(r'# \*\* Note: \$finish    : [^\r\n]+[/\\]tb_encoder_remainder_candidate\.sv\(329\)',finish)
                     is not None, 'finish file/line grammar')
    tm = re.fullmatch(r'#    Time: '+DECIMAL+r' ns  Iteration: 1  Instance: /tb_encoder_remainder_candidate',simtime)
    require_evidence(tm is not None, 'finish time/iteration/instance grammar')
    starts = [line for line in lines[:start] if line.startswith('# Start time:')]
    require_evidence(len(starts) == 1, 'simulator start-time uniqueness')
    date_pattern = r'([0-9]{2}:[0-9]{2}:[0-9]{2} on [A-Z][a-z]{2} [1-9][0-9]?,[0-9]{4})'
    sm = re.fullmatch('# Start time: '+date_pattern, starts[0])
    em = re.fullmatch('# End time: '+date_pattern+r', Elapsed time: ([0-9]+):([0-5][0-9]):([0-5][0-9])',end)
    require_evidence(sm is not None and em is not None, 'simulator date/elapsed grammar')
    begin_date = datetime.strptime(sm.group(1),'%H:%M:%S on %b %d,%Y')
    end_date = datetime.strptime(em.group(1),'%H:%M:%S on %b %d,%Y')
    elapsed = int(em.group(2))*3600+int(em.group(3))*60+int(em.group(4))
    require_evidence((end_date-begin_date).total_seconds() == elapsed, 'simulator elapsed/date conflict')
    require_evidence(diagnostics == '# Errors: 0, Warnings: 0', 'nonzero/malformed diagnostics')
    terminal_tokens = ('$finish','Iteration:','Instance:','# End time:','Errors:','Warnings:')
    for token in terminal_tokens:
        require_evidence(sum(line.count(token) for line in lines) == 1, 'terminal uniqueness: '+token)
    return summary, int(tm.group(1)), segments


def check_saved_run(transcript, trace_lines, cases):
    """Pure offline qualification of parsed records, iterable trace rows and fixtures.

    Does not launch tools, import the main oracle, write files or accept by hash.
    Trace contains original metadata/data and candidate ready/valid only. Candidate
    metadata/data and cfg_count/cfg_e/s_last are unrecorded and cannot be rechecked.
    """
    valid = fixture_expectations(cases)
    summary, finish_ns, segments = parse_saved_records(transcript, valid)
    totals = Counter({k:0 for k in SUMMARY_FIELDS if k not in
                      ('valid','invalid','abort','recovery','completed','cycles')})
    coverage = Counter()
    segment_index, previous_cycle, row_count = -1, 3, 0
    active, counts = None, Counter()

    def finish_segment():
        if active is None:
            return
        wanted = {'cfg':active['cfg'], 'samples':len(active['samples']), 'meta':active['meta'],
                  'data':active['data'], 'reset':active['reset'], 'cancel':active['cancel']}
        for key,value in wanted.items():
            require_evidence(counts[key] == value,
                             'case %d %s observed=%d expected=%d' % (active['id'],key,counts[key],value))
        coverage[active['kind']] += 1

    for line_number, line in enumerate(trace_lines,1):
        require_evidence(type(line) is str and line.endswith('\n'), 'truncated/non-text trace row')
        text = line[:-1]
        if text.endswith('\r'): text = text[:-1]
        match = TRACE_RECORD.fullmatch(text)
        require_evidence(match is not None, 'trace grammar/width at row %d' % line_number)
        cols = match.groups()
        cycle, case_id = int(cols[0]), int(cols[1])
        require_evidence(cycle == previous_cycle+1, 'trace continuous cycles at row %d' % line_number)
        previous_cycle, row_count = cycle, row_count+1
        if active is None or active['id'] != case_id:
            finish_segment()
            segment_index += 1
            require_evidence(segment_index < len(segments) and segments[segment_index]['id'] == case_id,
                             'trace case identity/transition/order')
            active, counts = segments[segment_index], Counter()
        rc, cfg, sample, meta, data, ready = cols[2:8]
        mv_dv = int(cols[11],16)
        require_evidence(ready == cfg[1]+sample[1] and
                         mv_dv == (int(meta[0])*2+int(data[0])), 'public ready/valid miter disagreement')
        require_evidence(rc == '00' or cfg[1]+sample[1]+meta[0]+data[0] == '0000',
                         'reset/cancel ready/valid gating')
        meta_word, data_word, sample_word = int(cols[8],16), int(cols[9],16), int(cols[10],16)
        require_evidence(meta[0] == '1' or meta_word == 0, 'unmasked invalid metadata')
        require_evidence(data[0] == '1' or data_word == 0, 'unmasked invalid data')
        if sample[0] == '1' and rc == '00':
            require_evidence(counts['cfg'] == 1 and counts['samples'] < len(active['samples']) and
                             sample_word == active['samples'][counts['samples']], 'sample value/order')
        if meta[0] == '1':
            require_evidence(counts['cfg'] == 1 and counts['samples'] == len(active['samples']) and
                             active['metadata'] is not None and meta_word == active['metadata'],
                             'fixture metadata/value/sequence')
        if data[0] == '1':
            index = counts['data']
            require_evidence(counts['meta'] == 1 and index < len(active['payload']), 'data sequence/count')
            expected_word = active['payload'][index]*2 + int(index == len(active['payload'])-1)
            require_evidence(data_word == expected_word, 'fixture byte/last mismatch')
        changes = {
            'cfg':int(cfg == '11'), 'samples':int(sample == '11'),
            'meta':int(meta == '11'), 'data':int(data == '11'),
            'cfgstall':int(cfg == '10'), 'samplestall':int(sample == '10'),
            'metastall':int(meta == '10'), 'datastall':int(data == '10'),
            'reset':int(rc[0]), 'cancel':int(rc[1]),
        }
        counts.update(changes)
        totals.update(changes)
    finish_segment()
    require_evidence(row_count > 0 and segment_index == len(segments)-1, 'missing/truncated trace segments')
    require_evidence(row_count == previous_cycle-3, 'trace row/cycle count')
    derived = dict(totals)
    derived.update({k:coverage[k] for k in ('valid','invalid','abort','recovery')})
    derived['completed'] = coverage['valid']+coverage['invalid']+coverage['recovery']
    derived['cycles'] = previous_cycle
    for key in SUMMARY_FIELDS:
        require_evidence(summary[key] == derived[key],
                         'summary %s observed=%d expected=%d' % (key,summary[key],derived[key]))
    require_evidence(finish_ns == previous_cycle*10, 'simulator finish time vs pinned 10ns TB clock')
    return {'summary':summary, 'trace_counters':derived, 'trace_rows':row_count,
            'first_cycle':4, 'last_cycle':previous_cycle, 'finish_ns':finish_ns,
            'segments':sum(coverage.values()), 'coverage':dict(coverage),
            'limitations':['Trace omits candidate metadata/data and config payload/s_last; independent offline validation of those values is unavailable.',
                           'Original metadata/data and accepted samples are checked against the saved fixture, not a newly independent codec oracle.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modelsim-home', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--thread-id', required=True)
    parser.add_argument('--turn-id', required=True)
    args = parser.parse_args()
    p = Path(__file__).resolve().parents[2]
    author = (p / OWNED[4]).resolve()
    out = args.output.resolve()
    if not out.is_relative_to(author) or out == author:
        parser.error('--output must be a new child directory of the owned author directory')
    if out.exists():
        parser.error('refusing pre-existing --output; preserve attempts')
    out.mkdir(parents=True)
    (out / 'logs').mkdir()
    (out / 'source').mkdir()
    records = []
    result = {
        'schema': 1, 'task_id': TASK_ID, 'task_version': 1, 'work_id': WORK_ID,
        'operation_id': OPERATION_ID, 'contract': CONTRACT,
        'thread_id': args.thread_id, 'turn_id': args.turn_id,
        'job_id': 'child-dbcdc099d56046d2808ad94838b0b4e4',
        'quality_main_thread_id': '01a13b55-095b-7461-8dd5-5476a130bd82',
        'at_utc': utc(), 'status': 'running', 'evidence_type': 'author_bounded_only',
        'argv': [sys.executable] + sys.argv, 'cwd': os.getcwd(),
        'ownership': list(OWNED), 'execution_allowed_before_project_work': True,
        'commands': records, 'sources': {}, 'python_version': sys.version,
        'author_software': 'not_run', 'author_modelsim': 'not_run',
        'formal_29': 'not_run', 'B01': 'not_run', 'B03': 'not_run', 'B06': 'not_run',
        'R03': 'not_run', 'synthesis': 'not_run', 'implementation': 'not_run',
        'timing_closure': 'not_run', 'CDC': 'not_run', 'board': 'not_run',
        'system': 'not_run', 'final_acceptance': 'not_run',
        'golden_reuse': 'Published golden/codec/codec_reference.py supplies expected metadata and bytes; disclosed non-independent payload oracle. No main oracle imported.',
        'limitations': ['Miter uses the original core as reference; shared bugs remain possible.',
                        'Arithmetic sweep covers every n and feasible p endpoints/midpoint, not every x,p pair.',
                        'No synthesis, timing, resource, physical-board or product-acceptance claim.'],
    }

    def run(name, cmd, cwd=out, timeout=120):
        record = {'name': name, 'argv': [str(a) for a in cmd], 'cwd': str(cwd),
                  'started_utc': utc(), 'stdout': 'logs/'+name+'.stdout.txt',
                  'stderr': 'logs/'+name+'.stderr.txt', 'exit_code': None}
        records.append(record)
        save_json(out/'RESULT.json',result)
        t0 = time.monotonic()
        with (out/record['stdout']).open('wb') as stdout, (out/record['stderr']).open('wb') as stderr:
            try:
                cp = subprocess.run(record['argv'], cwd=cwd, stdout=stdout, stderr=stderr,
                                    timeout=timeout, shell=False)
                record['exit_code'] = cp.returncode
            except subprocess.TimeoutExpired:
                record['timed_out'] = True
                raise RuntimeError('timeout: '+name)
            finally:
                record['duration_seconds'] = time.monotonic()-t0
                record['finished_utc'] = utc()
                record['stdout_sha256'] = sha(out/record['stdout'])
                record['stderr_sha256'] = sha(out/record['stderr'])
                save_json(out/'RESULT.json',result)
        if record['exit_code'] != 0:
            raise RuntimeError('%s exit %s' % (name,record['exit_code']))
        return (out/record['stdout']).read_bytes().decode('utf-8',errors='replace')

    exit_code = 1
    try:
        result['source_head'] = run('git_head',['git','rev-parse','HEAD'],cwd=p).strip()
        # Read pinned contract from local Git object; no network or editable-document trust.
        contract_text = run('contract_read',['git','show',CONTRACT_COMMIT+':docs/competition/deepeye-2026/immutable_scope.json'],cwd=p)
        contract = json.loads(contract_text)
        digest = hashlib.sha256(json.dumps(contract['requirements'],ensure_ascii=False,
                                sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
        assert digest == CONTRACT_HASH
        assert [r['id'] for r in contract['requirements']] == CONTRACT['requirements_ids']
        result['verified_contract_sha256'] = digest
        source_paths = {
            'original': p/'fpga/codec/deepeye_block_encoder.sv',
            'candidate': p/OWNED[0], 'notes': p/OWNED[1], 'tb': p/OWNED[2],
            'runner': Path(__file__).resolve(),
            'golden': p/'golden/codec/codec_reference.py',
        }
        for name, path in source_paths.items():
            target = out/'source'/path.name
            shutil.copyfile(path,target)
            result['sources'][name] = {'path': str(path), 'sha256': sha(path),
                                        'snapshot': str(target.relative_to(out))}
        assert result['sources']['original']['sha256'] == ORIGINAL_HASH
        assert result['sources']['golden']['sha256'] == GOLDEN_HASH
        print('START arithmetic all reachable n and feasible p endpoints/midpoint',flush=True)
        t0 = time.monotonic()
        math = arithmetic_sweep()
        math['duration_seconds'] = time.monotonic()-t0
        save_json(out/'arithmetic.json',math)
        result['arithmetic'] = math
        result['author_software'] = 'passed'
        print('ARITHMETIC PASS n=%d actual_x_p=%d' % (math['total_reachable_n'],math['total_feasible_x_p_cases']),flush=True)
        spec = importlib.util.spec_from_file_location('published_codec_reference',source_paths['golden'])
        golden = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(golden)
        cases = make_cases(golden)
        save_json(out/'fixtures.json',cases)
        write_fixtures(out/'fixtures.txt',cases)
        result['fixtures'] = {'count': len(cases), 'modes': dict(Counter(c['fixture']['mode'] for c in cases)),
                              'counts': sorted({len(c['samples']) for c in cases}),
                              'e': sorted({c['e'] for c in cases}), 'seed': '0x2026102436',
                              'json_sha256': sha(out/'fixtures.json'), 'text_sha256': sha(out/'fixtures.txt')}
        home = args.modelsim_home.resolve()
        exe = {name: home/(name+'.exe') for name in ('vlib','vmap','vlog','vsim')}
        for name,path in exe.items():
            if not path.is_file(): raise RuntimeError('missing tool '+str(path))
        result['tools'] = {name: {'path':str(path),'sha256':sha(path)} for name,path in exe.items()}
        result['tools']['vlog']['version'] = run('vlog_version',[exe['vlog'],'-version']).strip()
        result['tools']['vsim']['version'] = run('vsim_version',[exe['vsim'],'-version']).strip()
        run('vmap_init',[exe['vmap'],'-c'])
        run('vlib',[exe['vlib'],out/'work'])
        run('vmap_work',[exe['vmap'],'work',out/'work'])
        run('vlog',[exe['vlog'],'-sv','-work','work',out/'source'/source_paths['original'].name,
                    out/'source'/source_paths['candidate'].name,out/'source'/source_paths['tb'].name])
        dofile = out/'run.do'
        dofile.write_text('onerror {quit -f -code 2}\nonbreak {quit -f -code 3}\nrun -all\nquit -f -code 0\n',encoding='ascii')
        print('START ModelSim public-port miter cases=%d' % len(cases),flush=True)
        transcript = run('vsim',[exe['vsim'],'-c','-t','1ns','-l',out/'transcript.txt',
                                '-wlf',out/'simulation.wlf','work.tb_encoder_remainder_candidate',
                                '+INPUT='+(out/'fixtures.txt').as_posix(),
                                '+TRACE='+(out/'public_ports.txt').as_posix(),'-do',dofile],timeout=600)
        trace = out/'public_ports.txt'
        with trace.open('r',encoding='ascii',newline='') as f:
            qualification = check_saved_run(transcript, f, cases)
        summary = qualification['summary']
        result['offline_qualification'] = qualification
        result['simulation'] = summary
        result['public_trace'] = {'path':str(trace),'sha256':sha(trace),'cycles':qualification['trace_rows'],
                                  'first_cycle':qualification['first_cycle'],'last_cycle':qualification['last_cycle'],
                                  'metadata_and_data_masked_when_invalid':True}
        result['author_modelsim'] = 'passed'
        result['status'] = 'author_bounded_pass'
        exit_code = 0
        print('MODELSIM PASS '+json.dumps(summary,sort_keys=True),flush=True)
    except Exception as exc:
        result['status'] = 'failed'
        result['error'] = str(exc)
        result['traceback'] = traceback.format_exc()
        if result['author_software'] == 'not_run': result['author_software'] = 'failed'
        elif result['author_modelsim'] == 'not_run': result['author_modelsim'] = 'failed'
        (out/'failure.txt').write_text(result['traceback'],encoding='utf-8')
        print(result['traceback'],file=sys.stderr,flush=True)
    finally:
        original = p/'fpga/codec/deepeye_block_encoder.sv'
        result['original_sha256_after'] = sha(original)
        if result['original_sha256_after'] != ORIGINAL_HASH:
            result['status'] = 'failed'; result['error'] = 'original core changed'; exit_code = 1
        result['source_drift'] = [name for name, info in result['sources'].items()
                                  if sha(info['path']) != info['sha256']]
        if result['source_drift']:
            result['status'] = 'failed'; result['error'] = 'source drift'; exit_code = 1
        result['finished_utc'] = utc(); result['exit_code'] = exit_code
        save_json(out/'RESULT.json',result)
        artifacts = {str(f.relative_to(out).as_posix()):sha(f) for f in sorted(out.rglob('*'))
                     if f.is_file() and f.name != 'artifact_hashes.json'}
        save_json(out/'artifact_hashes.json',artifacts)
    print('RESULT '+str(out/'RESULT.json'),flush=True)
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
