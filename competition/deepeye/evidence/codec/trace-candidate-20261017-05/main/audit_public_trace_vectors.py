"""Decode/check every published fixture with the main independent reference."""
import argparse
import binascii
import hashlib
import json
from collections import Counter
from pathlib import Path
from independent_trace_reference import frame_reference, decode_reference, pack_reference

p = argparse.ArgumentParser()
p.add_argument('--vectors', required=True)
p.add_argument('--manual', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
raw = Path(a.vectors).read_bytes()
d = json.loads(raw)
manual = json.loads(Path(a.manual).read_bytes())['vectors']
assert d['manual_vectors']['source_sha256'] == hashlib.sha256(Path(a.manual).read_bytes()).hexdigest() == '36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24'
enrichment = {'byte_ledger', 'restored_points', 'implementation_reproduction'}
assert len(d['manual_vectors']['vectors']) == len(manual) == 8
rename = {'selected_raw_bytes':'selected_valid_raw_bytes', 'stored_code_bytes':'code_bytes',
          'outer_overhead_bytes':'outer_bytes', 'line_bits_8n1':'line_bits_8N1'}
counts = Counter()
for v, published in zip(manual, d['manual_vectors']['vectors'], strict=True):
    assert set(published) == set(v) | enrichment
    assert {key:published[key] for key in v} == v
    frame, restored = frame_reference(v['points'], v['binding'], v['channel'], v['sequence'])
    assert frame.hex() == v['frame_hex']
    got = decode_reference(frame, v['binding'])
    assert got['points'] == restored == v['expected_points'] == published['restored_points']
    ledger = published['byte_ledger']
    assert set(ledger) == {'count', 'value_count', 'selected_raw_bytes', 'significant_bits',
                           'stored_code_bytes', 'padding_bits', 'metadata_bytes', 'payload_bytes',
                           'outer_overhead_bytes', 'frame_bytes', 'line_bits_8n1'}
    assert ledger['count'] == len(restored)
    assert ledger['value_count'] == sum(p['valid'] for p in restored)
    for key, value in ledger.items():
        if key not in ('count', 'value_count'):
            assert value == got['ledger'][rename.get(key,key)], (v['name'],key)
    assert published['implementation_reproduction'] == {
        'payload_matches_main_bytes':True,'frame_matches_main_bytes':True}
    counts['manual'] += 1
    counts['independent_manual_enrichments'] += 1

rename = {'selected_raw_bytes':'selected_valid_raw_bytes', 'stored_code_bytes':'code_bytes',
          'outer_overhead_bytes':'outer_bytes', 'line_bits_8n1':'line_bits_8N1'}
for v in d['synthetic_vectors']:
    frames = pack_reference(v['source_points'], v['binding'], v['channel'], v['start_sequence'])
    assert [x.hex() for x in frames] == v['frames_hex'], v['id']
    restored = []
    aggregate = Counter(frame_count=len(frames))
    for packet, ledger in zip(frames, v['ledger_per_frame'], strict=True):
        got = decode_reference(packet, v['binding'])
        restored.extend(got['points'])
        assert ledger['count'] == len(got['points'])
        value_count = sum(p['valid'] for p in got['points'])
        assert ledger['value_count'] == value_count
        for key, value in ledger.items():
            if key not in ('count', 'value_count'):
                assert value == got['ledger'][rename.get(key,key)], (v['id'],key)
            if key not in ('count', 'outer_overhead_bytes'):
                aggregate[key+'_total'] += value
        counts['independent_frame_ledgers'] += 1
    assert restored == v['restored_points'], v['id']
    assert dict(aggregate) == v['aggregate_ledger'], (v['id'], aggregate, v['aggregate_ledger'])
    for original, recovered in zip(v['source_points'], restored, strict=True):
        assert dict(original, value=recovered['value']) == recovered
        if original['valid']:
            assert abs(original['value']-recovered['value']) <= v['binding']['e']
    counts['synthetic_streams'] += 1
    counts['source_points'] += len(v['source_points'])

for v in d['packer_verification']:
    if 'frames_hex' in v:
        frames = pack_reference(v['source_points'], v['binding'], v['channel'], v['start_sequence'])
        assert [x.hex() for x in frames] == v['frames_hex']
    else:
        try:
            pack_reference(v['source_points'], v['binding'], v['channel'], v['start_sequence'])
        except AssertionError:
            pass
        else:
            raise AssertionError(('packer should reject',v['id']))
    counts['packer_vectors'] += 1

for v in d['malformed_payloads'] + d['malformed_frames']:
    if 'frame_hex' in v:
        packet = bytes.fromhex(v['frame_hex'])
    else:
        payload = bytes.fromhex(v['payload_hex'])
        tick = int.from_bytes(payload[13:21], 'little') & 0xffffffff
        prefix = b'\xa5\x5a' + bytes((3, 7, len(payload), v['binding']['config_epoch']))
        prefix += bytes(2) + tick.to_bytes(4,'little') + payload
        packet = prefix + binascii.crc_hqx(prefix[2:],65535).to_bytes(2,'little')
    try:
        decode_reference(packet, v['binding'])
    except (AssertionError, IndexError, ValueError):
        counts['malformed_rejected'] += 1
    else:
        raise AssertionError(('negative vector is independently valid',v['id']))

result = {'status':'PASS', 'candidate_only':True, 'counts':dict(counts),
          'vectors_sha256':hashlib.sha256(raw).hexdigest(),
          'reference_imports_product':False, 'scope':'every published raw fixture checked independently'}
assert raw == Path(a.vectors).read_bytes()
with Path(a.output).open('x',encoding='utf-8') as f:
    json.dump(result,f,indent=2)
print(json.dumps(result))
