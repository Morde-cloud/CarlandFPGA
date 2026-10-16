"""Independent B-main tests of the offline proposal; no live transport/board."""
import argparse
import binascii
import copy
import hashlib
import importlib.util
import json
import random
import sys
from collections import Counter
from pathlib import Path
from independent_trace_reference import (E_VALUES, U32, U64, code_reference,
    payload_reference, frame_reference, decode_reference, pack_reference)


def point(i, tick, value=100, **kw):
    d = dict(index=i, tick_ms=tick, value=value, valid=True, saturated=False,
             held=False, source_fault=False, source_tick_ms=tick)
    d.update(kw)
    return d


def re_crc(packet):
    return bytes(packet[:-2]) + binascii.crc_hqx(bytes(packet[2:-2]), 65535).to_bytes(2, 'little')


def run(module, vectors, out):
    counts = Counter()
    rng = random.Random(2026101705)
    totals = Counter()
    binding = {'session': 0x01020304, 'config_epoch': 2, 'e': 0}

    def check_ledger(actual, expected):
        fields = {'selected_raw_bytes':'selected_valid_raw_bytes',
                  'stored_code_bytes':'code_bytes',
                  'outer_overhead_bytes':'outer_bytes',
                  'line_bits_8n1':'line_bits_8N1'}
        for key in ('selected_raw_bytes', 'significant_bits', 'stored_code_bytes',
                    'padding_bits', 'metadata_bytes', 'payload_bytes',
                    'outer_overhead_bytes', 'frame_bytes', 'line_bits_8n1'):
            assert actual[key] == expected[fields.get(key, key)], (key, actual, expected)
        counts['independent_ledgers'] += 1

    def reject(function, *args):
        try:
            function(*args)
        except ValueError:
            counts['expected_rejections'] += 1
        else:
            raise AssertionError(('accepted invalid input', function.__name__))

    def one(points, bind, ch, seq):
        expected, restored = frame_reference(points, bind, ch, seq)
        actual = module.encode_frame(points, bind, ch, seq)
        assert type(actual) is bytes and actual == expected
        assert module.encode_payload(points, bind, ch) == expected[12:-2]
        parsed = decode_reference(actual, bind)
        got = module.decode_frame(actual, bind)
        check_ledger(got['ledger'], parsed['ledger'])
        assert got['points'] == parsed['points'] == restored
        assert got['channel'] == ch and got['sequence'] == seq
        assert module.decode_payload(actual[12:-2], bind)['points'] == restored
        assert len(actual) <= 46 and actual[4] <= 32
        for original, decoded in zip(points, restored):
            if original['valid']:
                assert abs(original['value'] - decoded['value']) <= bind['e']
            assert {k:v for k,v in original.items() if k != 'value'} == {k:v for k,v in decoded.items() if k != 'value'}
        counts['independent_frames'] += 1
        counts['recovered_points'] += len(points)
        counts['mode_' + parsed['mode']] += 1
        if parsed['mode'] == 'rice':
            counts['k_%d' % parsed['k']] += 1
        return actual, parsed

    for v in vectors:
        packet, parsed = one(v['points'], v['binding'], v['channel'], v['sequence'])
        assert packet.hex() == v['frame_hex']
        assert parsed['points'] == v['expected_points']
        counts['manual_vectors'] += 1

    # Boundary and random arithmetic, constructed independently before product import.
    for e in E_VALUES:
        bind = dict(binding, e=e)
        for z in (0, 1, 2, 3, 4, 7, 15, 31, 63, 127, 255, 511, 1023, 2047, 3072, 6144):
            values = [10000]
            for qz in (z, z, min(2*z, 12000)):
                q = qz//2 if qz % 2 == 0 else -(qz+1)//2
                values.append(min(65535, max(0, values[-1]+q*(2*e+1))))
            pts = [point(i, i*10, x) for i,x in enumerate(values)]
            packets = module.pack_channel(pts, bind, z % 4, 0)
            assert packets == pack_reference(pts, bind, z % 4, 0)
            for packet in packets:
                decoded = decode_reference(packet, bind)
                # RAW values/original source selected by independent partition lengths.
                n = len(decoded['points'])
                part, pts = pts[:n], pts[n:]
                one(part, bind, z % 4, decoded['sequence'])
            counts['constructed_residual_streams'] += 1
        for case in range(160):
            n = rng.randint(1, 45)
            di, dt = rng.choice([1, 3, 65535]), rng.choice([1, 10, 65535])
            start_index = rng.choice([0, 17, U32-(n-1)*di])
            tick = rng.choice([0, 100000, U32-5, U64-(n-1)*dt])
            invalid = case % 17 == 0
            held = case % 7 == 0 and tick > 0 and not invalid
            origin = max(0, tick-rng.choice([1, 65535, 65536, 100000])) if held else None
            x = rng.choice([0, 65535, 32768, rng.randrange(65536)])
            pts = []
            for i in range(n):
                if case % 4 == 0:
                    x = rng.randrange(65536)
                elif case % 4 == 1:
                    x = min(65535, max(0, x+rng.randrange(-15, 16)))
                elif case % 4 == 2:
                    x = rng.choice([0, 1, 2, 65533, 65534, 65535])
                at = tick+i*dt
                pts.append(point(start_index+i*di, at, None if invalid else x,
                    valid=not invalid, saturated=not invalid and case % 9 == 0,
                    source_fault=case % 11 == 0, held=held,
                    source_tick_ms=None if invalid else origin if held else at))
            try:
                payload_reference(pts, bind, case % 4)
            except AssertionError:
                reject(module.encode_payload, pts, bind, case % 4)
                counts['oversize_or_nonrepresentable_blocks'] += 1
            else:
                one(pts, bind, case % 4, case)
            counts['arithmetic_blocks'] += 1

    # Four channels x128 selected sparse synthetic points; preserve all source metadata.
    selected = []
    sequence = 0
    receiver = module.TraceReceiver(binding)
    for channel in range(4):
        pts = []
        idx, tick, origin = channel, 2**32-200, None
        for i in range(128):
            idx += (1, 1, 3, 7)[(i//11) % 4]
            tick += (10, 10, 35, 100000)[(i//13) % 4]
            valid = i % 19 != 0
            held = valid and i % 17 in (2, 3, 4)
            if held and (origin is None or i % 17 == 2):
                origin = tick - (100000 if i % 2 else 10)
            pts.append(point(idx, tick, (1000+channel*100+i*3) % 65536 if valid else None,
                valid=valid, held=held, saturated=valid and i % 23 == 0,
                source_fault=i % 29 == 0, source_tick_ms=None if not valid else origin if held else tick))
        expected = pack_reference(pts, binding, channel, sequence)
        actual = module.pack_channel(pts, binding, channel, sequence)
        assert actual == expected
        restored = []
        frames = []
        for packet in actual:
            parsed = decode_reference(packet, binding)
            accepted = receiver.accept(packet)
            assert accepted['points'] == parsed['points']
            check_ledger(accepted['ledger'], parsed['ledger'])
            restored.extend(parsed['points'])
            totals.update(parsed['ledger'])
            frames.append({'frame_hex': packet.hex(), **parsed})
        assert restored == pts
        selected.append({'channel': channel, 'source_points': pts, 'restored_points': restored, 'frames': frames})
        sequence += len(actual)
    counts['four_channel_selected_points'] = 512
    counts['four_channel_frames'] = sequence
    assert totals['frame_bytes'] == totals['payload_bytes'] + 14*sequence
    assert totals['line_bits_8N1'] == 10*totals['frame_bytes']
    assert totals['code_bytes']*8 == totals['significant_bits']+totals['padding_bits']
    (out/'four-channel-recovery.json').write_text(json.dumps({'fixture': 'software_fixture', 'channels':selected, 'totals':dict(totals)}, indent=2)+'\n')

    # Exhaustive prefix oracle versus greedy product packer with irregular streams.
    for case in range(40):
        bind = dict(binding, e=E_VALUES[case % 5])
        pts = []
        idx, tick = 0, 1000
        for i in range(30+case % 17):
            idx += rng.choice([1, 1, 3, 65536])
            tick += rng.choice([10, 10, 11, 70000])
            valid = rng.randrange(8) != 0
            pts.append(point(idx, tick, rng.randrange(65536) if valid else None,
                valid=valid, source_tick_ms=tick if valid else None,
                source_fault=case % 3 == 0))
        assert module.pack_channel(pts, bind, case % 4, 100) == pack_reference(pts, bind, case % 4, 100)
        counts['exhaustive_prefix_streams'] += 1

    # Uniform 128-point profiles exercise actual budget splitting, independent anchors,
    # and early-overflow termination against an exhaustive prefix reference.
    uniform_ledgers = []
    for e in E_VALUES:
        bind = dict(binding, e=e)
        for kind in ('flat', 'ramp', 'noise', 'endpoints', 'held_short', 'held_long', 'invalid'):
            pts = []
            for i in range(128):
                value = {'flat':100, 'ramp':100+i, 'noise':rng.randrange(65536),
                         'endpoints':65535 if i % 2 else 0,
                         'held_short':100, 'held_long':100, 'invalid':None}[kind]
                held = kind.startswith('held')
                valid = kind != 'invalid'
                tick = 100000+i*10
                pts.append(point(i, tick, value, valid=valid, held=held,
                    source_tick_ms=None if not valid else 99999 if kind == 'held_short' else 0 if held else tick))
            packets = module.pack_channel(pts, bind, 0, 0)
            assert packets == pack_reference(pts, bind, 0, 0)
            restored = []
            ledger = Counter()
            sizes = []
            for packet in packets:
                got = decode_reference(packet, bind)
                actual = module.decode_frame(packet, bind)
                assert actual['points'] == got['points']
                check_ledger(actual['ledger'], got['ledger'])
                restored.extend(got['points'])
                ledger.update(got['ledger'])
                sizes.append(len(got['points']))
            assert len(restored) == 128
            for original, recovered in zip(pts, restored):
                if original['valid']:
                    assert abs(original['value'] - recovered['value']) <= e
                assert dict(original, value=recovered['value']) == recovered
            if kind == 'flat':
                assert sizes == [41, 41, 41, 5]
            if kind == 'held_short':
                assert sizes == [25, 25, 25, 25, 25, 3]
            if kind == 'held_long':
                assert sizes == [1]*128
            if kind == 'invalid':
                assert sizes == [128]
            uniform_ledgers.append({'e':e, 'pattern':kind, 'points':128,
                'frame_count':len(packets), 'block_counts':sizes, 'ledger':dict(ledger)})
            counts['uniform_128_point_profiles'] += 1
    (out/'uniform-profile-ledgers.json').write_text(json.dumps(uniform_ledgers, indent=2)+'\n')

    # Every bit mutation of eight manual packets; re-CRC isolates semantic checks.
    for v in vectors:
        original = bytes.fromhex(v['frame_hex'])
        for offset in range(len(original)):
            for bit in range(8):
                corrupted = bytearray(original)
                corrupted[offset] ^= 1 << bit
                # Test both raw corruption and correctly framed but malformed content.
                for packet in (bytes(corrupted), re_crc(corrupted)):
                    try:
                        reference = decode_reference(packet, v['binding'])
                    except (AssertionError, IndexError, ValueError):
                        reject(module.decode_frame, packet, v['binding'])
                        counts['mutation_rejected'] += 1
                    else:
                        actual = module.decode_frame(packet, v['binding'])
                        assert actual['points'] == reference['points']
                        assert actual['channel'] == reference['channel'] and actual['sequence'] == reference['sequence']
                        counts['mutation_legal_alternative'] += 1
                    counts['mutation_cases'] += 1

    # Bounded, atomic offline receiver behavior: no clock renewal or motion authority.
    rx = module.TraceReceiver(binding)
    b0 = frame_reference([point(1, 10)], binding, 0, 0)[0]
    snapshot0 = copy.deepcopy(rx.state_snapshot())
    reject(rx.accept, b0[:-1]+bytes([b0[-1]^1]))
    assert rx.state_snapshot() == snapshot0
    accepted = rx.accept(b0)
    accepted['points'][0]['index'] = 900
    snapshot1 = copy.deepcopy(rx.state_snapshot())
    exposed = rx.state_snapshot()
    exposed.clear()
    assert rx.state_snapshot() == snapshot1
    assert rx.accept(b0)['points'] == []
    assert rx.state_snapshot() == snapshot1
    reject(rx.accept, frame_reference([point(2, 20, 999)], binding, 0, 0)[0])
    assert rx.state_snapshot() == snapshot1
    reject(rx.accept, frame_reference([point(1, 20)], binding, 0, 1)[0])
    reject(rx.accept, frame_reference([point(2, 10)], binding, 0, 1)[0])
    assert rx.state_snapshot() == snapshot1
    for seq in range(1, 200):
        ch = seq % 4
        packet = frame_reference([point(seq+1, (seq+1)*10)], binding, ch, seq)[0]
        assert rx.accept(packet)['points'] == decode_reference(packet, binding)['points']
    snapshot2 = copy.deepcopy(rx.state_snapshot())
    reject(rx.accept, b0)
    assert rx.state_snapshot() == snapshot2
    # Snapshot must remain small; detailed cache length checked by source inspection.
    assert len(json.dumps(snapshot2, default=str)) < 12000
    rx.close()
    reject(rx.accept, frame_reference([point(1000, 10000)], binding, 0, 200)[0])
    rx2 = module.TraceReceiver(binding)
    rx2.accept(frame_reference([point(1, 1)], binding, 0, 65535)[0])
    reject(rx2.accept, frame_reference([point(2, 2)], binding, 0, 0)[0])
    counts['receiver_accepted_forward_frames'] = 201
    counts['receiver_atomic_and_alias_checks'] = 9

    # Ingress exact scalars/containers; no overloaded operators are allowed to run.
    calls = []
    class BadInt(int):
        def trap(self, *a):
            calls.append('int operator')
            raise RuntimeError('unexpected user operator')
        __lt__ = __le__ = __gt__ = __ge__ = __eq__ = __ne__ = __add__ = __sub__ = __index__ = trap
        __hash__ = int.__hash__
    class BadStr(str):
        def __eq__(self, other):
            calls.append('key equality')
            raise RuntimeError('unexpected key operator')
        __hash__ = str.__hash__
    class BadList(list):
        def __iter__(self):
            calls.append('list iteration')
            raise RuntimeError('unexpected container')
    class BadDict(dict):
        def __iter__(self):
            calls.append('dict iteration')
            raise RuntimeError('unexpected container')
    base = [point(1, 100)]
    for field in ('session', 'config_epoch', 'e'):
        for value in (True, BadInt(binding[field]), 1.0, '1'):
            reject(module.encode_payload, base, dict(binding, **{field:value}), 0)
            counts['strict_scalar_cases'] += 1
    for field in ('index', 'tick_ms', 'value', 'source_tick_ms'):
        for value in (True, BadInt(base[0][field]), 1.0, '1'):
            reject(module.encode_payload, [dict(base[0], **{field:value})], binding, 0)
            counts['strict_scalar_cases'] += 1
    for field in ('valid', 'saturated', 'held', 'source_fault'):
        reject(module.encode_payload, [dict(base[0], **{field:1})], binding, 0)
        counts['strict_scalar_cases'] += 1
    for value in (True, BadInt(0), 0.0):
        reject(module.encode_payload, base, binding, value)
        reject(module.encode_frame, base, binding, 0, value)
        reject(module.pack_channel, base, binding, 0, value)
    for bad in (BadList(base), (p for p in base), 'x'):
        reject(module.encode_payload, bad, binding, 0)
    reject(module.encode_payload, [BadDict(base[0])], binding, 0)
    reject(module.encode_payload, base, BadDict(binding), 0)
    badkeys = {BadStr(k):v for k,v in binding.items()}
    reject(module.encode_payload, base, badkeys, 0)
    badpoint = {BadStr(k):v for k,v in base[0].items()}
    reject(module.encode_payload, [badpoint], binding, 0)
    reject(module.decode_frame, bytearray(b0), binding)
    reject(module.decode_frame, memoryview(b0), binding)
    assert calls == [], calls
    counts['overloaded_operator_calls'] = len(calls)
    reject(module.pack_channel, [point(0, 0), point(2, 100000)], binding, 0, 65535)
    assert len(module.pack_channel(base, binding, 0, 65535)) == 1
    result = {'status': 'PASS', 'scope': 'independent offline candidate review only',
        'counts':dict(counts), 'four_channel_totals':dict(totals), 'candidate_only':True,
        'public_abi_frozen':False, 'board_run':False}
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--module', required=True)
    p.add_argument('--manual', required=True)
    p.add_argument('--output-root', required=True)
    a = p.parse_args()
    source = Path(a.module).resolve()
    original_bytes = source.read_bytes()
    out = Path(a.output_root)
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(source.parent))
    spec = importlib.util.spec_from_file_location('trace_review_subject', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    vectors = json.loads(Path(a.manual).read_bytes())['vectors']
    result = run(module, vectors, out)
    assert original_bytes == source.read_bytes()
    result['source_sha256'] = hashlib.sha256(original_bytes).hexdigest()
    result['manual_sha256'] = hashlib.sha256(Path(a.manual).read_bytes()).hexdigest()
    (out/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result))
