"""Portable, hand-computable checks for main findings TC01 and TC02."""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--module', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
source = Path(a.module).resolve()
data = source.read_bytes()
sys.path.insert(0, str(source.parent))
spec = importlib.util.spec_from_file_location('regression_subject', source)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
points = [dict(index=i, tick_ms=i*10, value=x, valid=True, saturated=False,
               held=False, source_fault=False, source_tick_ms=i*10)
          for i,x in enumerate([10000,10001,10002,10004])]
binding = {'session':1,'config_epoch':0,'e':0}
# ZigZag [2,2,4]: k0 costs11 residual bits; k1 costs10; k2 costs10.
# The unchanged inner convention selects k1, then byte comparison chooses Rice.
expected = bytes.fromhex('a55a03071d00000000000000011004041a0100000000000000000000000000000001000a0010274880a94b')
actual = m.encode_frame(points, binding, 0, 0)
issues = []
if actual != expected:
    issues.append({'id':'TC01','expected_frame_hex':expected.hex(),'actual_frame_hex':actual.hex(),
                   'reason':'k must minimize significant bits before comparing padded Rice/RAW bytes'})
underflow = bytes.fromhex('a55a030719020900e803000001081401100403020107000000e803000000000000e9036400a811')
binding2 = {'session':16909060,'config_epoch':2,'e':0}
rx = m.TraceReceiver(binding2)
before = rx.state_snapshot()
try:
    decoded = rx.accept(underflow)
except ValueError:
    assert rx.state_snapshot() == before
else:
    issues.append({'id':'TC02','accepted_points':decoded['points'],
                   'state_mutated':rx.state_snapshot() != before,
                   'reason':'uint16 source age1001 cannot be subtracted from uint64 first_tick1000'})
result = {'source_sha256':hashlib.sha256(data).hexdigest(),'checks':2,'failures':len(issues),
          'issues':issues,'status':'FAIL' if issues else 'PASS',
          'scope':'offline proposal correctness, no runtime/board acceptance'}
assert data == source.read_bytes()
with Path(a.output).open('x',encoding='utf-8') as f:
    json.dump(result,f,indent=2)
print(json.dumps(result))
raise SystemExit(bool(issues))
