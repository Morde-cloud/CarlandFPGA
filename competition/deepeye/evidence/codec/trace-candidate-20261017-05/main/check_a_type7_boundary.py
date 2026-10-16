"""Read-only check of exact A wire input; candidate bytes never enable type7."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--a-wire', required=True)
p.add_argument('--manual', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
path = Path(a.a_wire)
original = path.read_bytes()
digest = hashlib.sha256(original).hexdigest()
assert digest == '31533439f1bab32ca71fae138bb988f51ce1d043b4e364a6c33a09eab1d5f5ec'
spec = importlib.util.spec_from_file_location('pinned_a_wire', path)
wire = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wire
spec.loader.exec_module(wire)
vectors = json.loads(Path(a.manual).read_bytes())['vectors']
rejected = 0
crc_matches = 0
recoveries = 0
hello = wire.Frame(1, 2, 100, 1234, bytes(18))
hello_packet = wire.encode(hello)
for v in vectors:
    packet = bytes.fromhex(v['frame_hex'])
    assert wire.crc16(packet[2:-2]) == int.from_bytes(packet[-2:], 'little')
    crc_matches += 1
    for diagnostic in (False, True):
        try:
            wire.decode(packet, allow_legacy_diagnostic=diagnostic)
        except ValueError as error:
            assert 'unfrozen' in str(error)
            rejected += 1
        else:
            raise AssertionError('A unexpectedly accepts offline proposal')
    stream = packet + hello_packet
    for size in (1, 2, 3, 7, 17, 46):
        decoder = wire.FrameDecoder()
        decoded = []
        for start in range(0, len(stream), size):
            decoded.extend(decoder.feed(stream[start:start+size]))
            assert decoder.buffered_bytes <= 46
        assert decoded == [hello]
        recoveries += 1
assert path.read_bytes() == original
result = {'status':'PASS', 'a_commit':'66aa291d7f01cc3cfefb8c30c4e8ad3aec6547bd',
          'a_wire_sha256':digest, 'a_wire_unchanged':True, 'candidate_crc_matches':crc_matches,
          'type7_rejections':rejected, 'scanner_hello_recoveries':recoveries,
          'abi_acceptance':False, 'transport_or_board_execution':False}
with Path(a.output).open('x', encoding='utf-8') as f:
    json.dump(result, f, indent=2)
print(json.dumps(result))
