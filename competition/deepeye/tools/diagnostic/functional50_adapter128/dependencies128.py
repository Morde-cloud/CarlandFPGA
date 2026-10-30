"""Fixed local Python data dependencies; no device/provider discovery."""
import hashlib
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[5]
INPUT_REL = 'competition/deepeye/tools/diagnostic/functional50_input113/input113.py'
INPUT_SHA = '95b46940767d3be4dbe3d885a4852119161ea5e4567ab3bda51798c39109ea49'
CODEC_REL = 'competition/deepeye/golden/codec/trace_candidate.py'
CODEC_SHA = 'a489ac34b49976532803b34f006f8bc24103548f34ddd55cc2ecaedc529a9642'

def _fixed(rel, digest, name):
    path = ROOT / rel
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError('fixed dependency bytes mismatch: ' + rel)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

input113 = _fixed(INPUT_REL, INPUT_SHA, '_adapter128_input113')
codec = _fixed(CODEC_REL, CODEC_SHA, '_adapter128_trace_codec')
