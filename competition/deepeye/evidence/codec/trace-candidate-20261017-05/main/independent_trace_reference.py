"""B-main independent proposal oracle. Imports no product codec or TRACE module.

Integer equations, bit strings and LE integer slices implement the saved main
proposal. This is software_fixture review code, not a public ABI/transport.
"""
import binascii
import json
import struct
from pathlib import Path

E_VALUES = (0, 1, 2, 4, 8)
U32, U64 = 2**32 - 1, 2**64 - 1
POINT_KEYS = {'index', 'tick_ms', 'value', 'valid', 'saturated', 'held',
              'source_fault', 'source_tick_ms'}


def checked(value, maximum):
    assert type(value) is int and 0 <= value <= maximum
    return value


def binding_check(binding):
    assert type(binding) is dict and all(type(k) is str for k in binding)
    assert set(binding) == {'session', 'config_epoch', 'e'}
    checked(binding['session'], U32)
    checked(binding['config_epoch'], 255)
    assert type(binding['e']) is int and binding['e'] in E_VALUES


def points_check(points):
    assert type(points) in (list, tuple) and 1 <= len(points) <= 128
    for p in points:
        assert type(p) is dict and all(type(k) is str for k in p)
        assert set(p) == POINT_KEYS
        checked(p['index'], U32)
        checked(p['tick_ms'], U64)
        for name in ('valid', 'saturated', 'held', 'source_fault'):
            assert type(p[name]) is bool
        if p['valid']:
            checked(p['value'], 65535)
            checked(p['source_tick_ms'], U64)
            if p['held']:
                assert p['source_tick_ms'] < p['tick_ms']
            else:
                assert p['source_tick_ms'] == p['tick_ms']
        else:
            assert p['value'] is None and p['source_tick_ms'] is None
            assert not p['saturated'] and not p['held']


def code_reference(values, e):
    """Direct independent exhaustive-k minimization with stored-byte RAW tie."""
    assert values and e in E_VALUES
    predicted = values[0]
    zs = []
    recovered = [predicted]
    for x in values[1:]:
        q = (x - predicted + e) // (2*e + 1)
        predicted = min(65535, max(0, predicted + q*(2*e + 1)))
        zs.append(2*q if q >= 0 else -2*q-1)
        recovered.append(predicted)
    options = [(sum((z >> k) + 1 + k for z in zs), k)
               for k in range(16) if all(z >> k <= 31 for z in zs)]
    raw = b''.join(x.to_bytes(2, 'little') for x in values)
    if not options:
        return 'raw', 0, 16*len(values), raw, list(values)
    residual_bits, k = min(options)
    bits = 16 + residual_bits
    if (bits + 7)//8 >= len(raw):
        return 'raw', 0, 16*len(values), raw, list(values)
    words = ['0' * (z >> k) + '1' + (format(z & ((1 << k)-1), '0%db' % k) if k else '') for z in zs]
    tail = ''.join(words)
    tail += '0' * ((-len(tail)) % 8)
    body = values[0].to_bytes(2, 'little') + bytes(int(tail[i:i+8], 2) for i in range(0, len(tail), 8))
    return 'rice', k, bits, body, recovered


def payload_reference(points, binding, channel):
    binding_check(binding)
    points_check(points)
    checked(channel, 3)
    first = points[0]
    flags = ('valid', 'saturated', 'held', 'source_fault')
    assert all(all(p[k] == first[k] for k in flags) for p in points)
    quality = channel + sum(int(first[k]) << (2+i) for i, k in enumerate(flags))
    ext = b''
    if len(points) > 1:
        di = points[1]['index'] - first['index']
        dt = points[1]['tick_ms'] - first['tick_ms']
        assert 1 <= di <= 65535 and 1 <= dt <= 65535
        assert all(p['index'] == first['index'] + i*di and p['tick_ms'] == first['tick_ms'] + i*dt for i, p in enumerate(points))
        ext += di.to_bytes(2, 'little') + dt.to_bytes(2, 'little')
    if first['held']:
        origin = first['source_tick_ms']
        assert all(p['source_tick_ms'] == origin for p in points)
        age = first['tick_ms'] - origin
        if age <= 65535:
            ext += age.to_bytes(2, 'little')
        else:
            quality |= 64
            ext += origin.to_bytes(8, 'little')
    if first['valid']:
        mode, k, bits, body, values = code_reference([p['value'] for p in points], binding['e'])
    else:
        mode, k, bits, body, values = 'raw', 0, 0, b'', [None]*len(points)
    metadata = 21 + len(ext)
    assert metadata + len(body) <= 32
    setting = E_VALUES.index(binding['e']) + (8 if mode == 'raw' else k << 4)
    header = bytes((1, setting, quality, len(points), bits))
    header += binding['session'].to_bytes(4, 'little')
    header += first['index'].to_bytes(4, 'little') + first['tick_ms'].to_bytes(8, 'little')
    restored = [dict(p, value=y) for p, y in zip(points, values)]
    return header + ext + body, restored


def frame_reference(points, binding, channel, sequence):
    checked(sequence, 65535)
    payload, restored = payload_reference(points, binding, channel)
    header = b'\xa5\x5a' + bytes((3, 7, len(payload), binding['config_epoch']))
    header += sequence.to_bytes(2, 'little') + (points[0]['tick_ms'] & U32).to_bytes(4, 'little')
    packet = header + payload
    return packet + binascii.crc_hqx(packet[2:], 65535).to_bytes(2, 'little'), restored


def decode_reference(packet, binding):
    binding_check(binding)
    assert type(packet) is bytes and 35 <= len(packet) <= 46
    assert packet[:4] == b'\xa5\x5a\x03\x07'
    assert packet[4] <= 32 and len(packet) == packet[4] + 14
    assert packet[5] == binding['config_epoch']
    assert int.from_bytes(packet[-2:], 'little') == binascii.crc_hqx(packet[2:-2], 65535)
    payload = packet[12:-2]
    rev, setting, quality, n, bits = payload[:5]
    assert rev == 1 and 1 <= n <= 128 and quality & 128 == 0
    ecode, raw, k = setting & 7, bool(setting & 8), setting >> 4
    assert ecode <= 4 and E_VALUES[ecode] == binding['e']
    assert not raw or k == 0
    assert int.from_bytes(payload[5:9], 'little') == binding['session']
    index = int.from_bytes(payload[9:13], 'little')
    tick = int.from_bytes(payload[13:21], 'little')
    assert int.from_bytes(packet[8:12], 'little') == tick & U32
    valid, saturated, held, fault, long_tick = [bool(quality & (1 << bit)) for bit in range(2, 7)]
    offset = 21
    di, dt = 0, 0
    if n > 1:
        assert len(payload) >= offset + 4
        di = int.from_bytes(payload[offset:offset+2], 'little')
        dt = int.from_bytes(payload[offset+2:offset+4], 'little')
        assert di > 0 and dt > 0
        offset += 4
    assert index + (n-1)*di <= U32 and tick + (n-1)*dt <= U64
    assert not long_tick or held
    source = None
    if held:
        size = 8 if long_tick else 2
        assert len(payload) >= offset + size
        origin_or_age = int.from_bytes(payload[offset:offset+size], 'little')
        offset += size
        if long_tick:
            source = origin_or_age
            assert source < tick and tick - source > 65535
        else:
            assert 1 <= origin_or_age <= tick
            source = tick - origin_or_age
    body = payload[offset:]
    assert len(body) == (bits+7)//8
    if not valid:
        assert not saturated and not held and raw and not bits and not body
        values = [None]*n
    else:
        assert bits >= 16 and len(body) >= 2
        if raw:
            assert bits == 16*n
            values = [int.from_bytes(body[i:i+2], 'little') for i in range(0, len(body), 2)]
        else:
            bittext = ''.join(format(b, '08b') for b in body[2:])
            meaningful = bits - 16
            assert all(b == '0' for b in bittext[meaningful:])
            bittext = bittext[:meaningful]
            pos = 0
            values = [int.from_bytes(body[:2], 'little')]
            for _ in range(n-1):
                term = bittext.find('1', pos)
                assert term >= pos and term-pos <= 31 and term+1+k <= len(bittext)
                z = ((term-pos) << k) + (int(bittext[term+1:term+1+k], 2) if k else 0)
                q = z//2 if z % 2 == 0 else -(z+1)//2
                values.append(min(65535, max(0, values[-1] + q*(2*binding['e']+1))))
                pos = term+1+k
            assert pos == len(bittext)
        mode2, k2, bits2, body2, _ = code_reference(values, binding['e'])
        assert (mode2, k2, bits2, body2) == ('raw' if raw else 'rice', k, bits, body)
    points = [dict(index=index+i*di, tick_ms=tick+i*dt, value=y, valid=valid,
                   saturated=saturated, held=held, source_fault=fault,
                   source_tick_ms=(source if held else tick+i*dt) if valid else None)
              for i, y in enumerate(values)]
    return {'channel': quality & 3, 'sequence': int.from_bytes(packet[6:8], 'little'),
            'points': points, 'mode': 'raw' if raw else 'rice', 'k': k,
            'ledger': {'selected_valid_raw_bytes': 2*n if valid else 0,
                       'significant_bits': bits, 'code_bytes': len(body),
                       'padding_bits': 8*len(body)-bits, 'metadata_bytes': offset,
                       'payload_bytes': len(payload), 'outer_bytes': 14,
                       'frame_bytes': len(packet), 'line_bits_8N1': 10*len(packet)}}


def pack_reference(points, binding, channel, sequence):
    """Exhaustive longest-prefix selection; does not use early-overflow stop."""
    points_check(points)
    assert all(a['index'] < b['index'] and a['tick_ms'] < b['tick_ms'] for a, b in zip(points, points[1:]))
    packets = []
    cursor = 0
    while cursor < len(points):
        possible = []
        for stop in range(cursor+1, len(points)+1):
            try:
                packet, _ = frame_reference(points[cursor:stop], binding, channel, sequence+len(packets))
                possible.append((stop, packet))
            except AssertionError:
                pass
        assert possible
        cursor, packet = possible[-1]
        packets.append(packet)
    return packets


if __name__ == '__main__':
    directory = Path(__file__).resolve().parent
    vectors = json.loads((directory/'main_manual_vectors.json').read_text())['vectors']
    for v in vectors:
        frame, restored = frame_reference(v['points'], v['binding'], v['channel'], v['sequence'])
        assert frame.hex() == v['frame_hex'], v['name']
        assert frame[12:-2].hex() == v['payload_hex'], v['name']
        got = decode_reference(frame, v['binding'])
        assert got['points'] == v['expected_points'] == restored, v['name']
        for field in ('payload_bytes', 'metadata_bytes', 'code_bytes', 'significant_bits', 'padding_bits', 'frame_bytes', 'line_bits_8N1'):
            assert got['ledger'][field] == v[field], (v['name'], field)
    print(json.dumps({'manual_vectors': len(vectors), 'status': 'PASS',
                      'reference_imports_product': False, 'candidate_only': True}))
