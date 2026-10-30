'''DeepEye offline TRACE candidate revision 1 - pure serializer (candidate only).

Task DEEPEYE-IMPLEMENTATION-20261014/v1; work B-TRACE-OFFLINE-PAYLOAD-20261017-05-v1
implementing the B main decision 'offline TRACE candidate revision 1' (spec sha256
7bc33ebc28c9f08e200c539a1a59c07b42b36211cb49b08ac449875bf75f9a73) on base commit
c5d079c24e45d97d6bd8181a7414a64c7c110860.  The B main hand-derived expected bytes
(main_manual_vectors.json sha256 36b8e3fdb53e3c8fc911cc44b4f4151d62863d2e05b189f68c42fefe869b2d24)
were copied verbatim as golden inputs; this module was implemented from the spec
text, not derived from them.

Corrections B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1 (B main
decisions TC01/TC02, offline correctness only): stage 1 now chooses the Rice k
by the FEWEST SIGNIFICANT BITS (quotient <= 31, ties lowest k - exactly the
unchanged inner codec k rule) and only stage 2 compares stored bytes for the
Rice/RAW choice with RAW winning byte ties; the short held source age must
satisfy 1 <= age <= first_tick so the uint64 origin cannot underflow.

Contract DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15) pinned at
f5989cd5defce561f9ba98e6b18fc2682945f0a2; canonical requirements SHA256
c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804; design
1011259415a0916054eb580687612580bc1e5f09.

Status CANDIDATE-ONLY, OFFLINE, B-SIDE PROPOSAL.  This module emits and parses
candidate type7 fixture bytes for independent review.  It is NOT a public ABI
freeze, defines no production transport/scanner/scheduling/authentication, and
carries no board or system acceptance claim.  A alone owns the public schema,
the only production type7 enable decision and the physical board; A's wire.py
keeps rejecting type7 and is intentionally not imported or modified here.
Every call is a pure computation over its arguments with no network, process,
board, clock, filesystem or other side effect.

Wire summary (see TRACE_CANDIDATE.md and trace_candidate_layout.json):
  * Outer frame: existing ABI3 header copied literally '<2sBBBBHI' (magic
    A5 5A, version 3, type 7, payload length, config_epoch uint8, frame
    sequence uint16, tick_ms uint32 = low 32 bits of the FIRST acquisition
    tick in the payload) + payload (<=32 B) + CRC16/CCITT-FALSE over
    version..payload end stored little-endian; frame <= 46 B, overhead 14 B.
  * Payload prefix 21 B: revision 1, settings byte, quality byte, point count
    1..128, significant code bits, session uint32, first acquisition index
    uint32, first acquisition tick_ms uint64.  Then optional uniform strides
    (uint16 x2, count>1 only), optional held source extension (uint16 age or
    uint64 absolute source tick) and the code section.
  * Settings byte: bits0..2 E code (0->0, 1->1, 2->2, 3->4, 4->8; 5..7
    invalid), bit3 RAW flag (RAW requires k=0), bits4..7 Rice k 0..15.
  * Quality byte: bits0..1 channel 0..3, bit2 valid, bit3 saturated,
    bit4 held, bit5 source_fault, bit6 long_source_tick, bit7 reserved 0
    (rejected when set).  The four quality flags are common to every point
    of one block; the per-point mask is recovered by expansion.
  * All multi-byte numeric fields, including the anchor and the RAW sample
    words, are little-endian.  The Rice residual bitstream is MSB-first
    inside the code section, which starts at a byte boundary.  This adapts
    the existing inner-codec fixture representation (big-endian anchor/RAW
    words): the inner codec module and its frozen vectors are unchanged and
    their bytes must not be reused as candidate bytes.
  * Canonical selection is two-stage, differing from the inner codec only in
    stage 2: stage 1 chooses the Rice k with the FEWEST SIGNIFICANT BITS
    (quotient <= 31, ties lowest k - exactly the unchanged inner codec k
    rule); stage 2 then compares STORED BYTES and uses Rice only when its
    padded code-byte count is STRICTLY smaller than RAW's 2*count bytes; a
    stored-byte tie selects RAW even where the inner bit rule keeps Rice
    (values [0, 64], E0: k=6 = 25 bits = 4 stored bytes; candidate RAW = 4
    bytes wins the tie).
  * Quality-only invalid blocks carry zero significant bits/bytes, the RAW
    flag with k=0, and no fabricated sample or anchor; saturated/held/long
    are zero when invalid; source_fault may accompany valid or invalid
    blocks because it is reported source quality, not a runtime permission.
  * Saturation is a reported status only and never implies endpoint values.

Input discipline: all numeric API inputs must be exact built-in ints and all
flags exact bools; point/binding mappings must be exact dicts with exact str
keys; point sequences must be exact list or tuple; payload/packet data must
be exact bytes.  bool, IntEnum, int subclasses, dict/list/tuple/bytes
subclasses and str-subclass keys are rejected on type before any user
operator could run.  Inputs are snapshotted and all returned records are
detached from caller and receiver state.

Scope limits: no source/profile authentication, calibration, runtime clock
acquisition, observation lease, scheduling or motion authorization is
provided or implied.  Indices are actual per-channel acquisition indices,
never frame sequence numbers or selected-point ordinals; frame sequence is a
separate non-wrapping uint16.  This serializer makes no compression,
throughput, latency or 100 Hz/continuous-sampling claim.  The current A
source records ADC tick values of at most 2**31-1 that are multiples of 10,
and EM tick values are multiples of 50 ms; the uint64 tick and low32-rollover
vectors here are
synthetic future-layout proposals, not accepted current-source records.
'''

from __future__ import annotations

import binascii
import struct

__all__ = [
    'TraceError',
    'encode_payload',
    'decode_payload',
    'encode_frame',
    'decode_frame',
    'pack_channel',
    'TraceReceiver',
]

CANDIDATE_REVISION = 1
OUTER_MAGIC = b'\xa5\x5a'
OUTER_VERSION = 3
OUTER_TYPE = 7
HEADER_FORMAT = '<2sBBBBHI'
HEADER_BYTES = 12
CRC_BYTES = 2
OUTER_OVERHEAD_BYTES = HEADER_BYTES + CRC_BYTES
PAYLOAD_PREFIX_BYTES = 21
PAYLOAD_MAX_BYTES = 32
FRAME_MAX_BYTES = 46
MIN_POINTS = 1
MAX_POINTS = 128
U8_MAX = 0xFF
U16_MAX = 0xFFFF
U32_MAX = 0xFFFFFFFF
U64_MAX = 0xFFFFFFFFFFFFFFFF
SAMPLE_BITS = 16
SAMPLE_MAX = 0xFFFF
MAX_K = 15
MAX_QUOTIENT = 31
QUALITY_RESERVED_BIT = 0x80
CACHE_LIMIT = 16
CHANNELS = 4

E_VALUES = (0, 1, 2, 4, 8)
E_CODE = {0: 0, 1: 1, 2: 2, 4: 3, 8: 4}
E_BY_CODE = (0, 1, 2, 4, 8)

POINT_KEYS = frozenset((
    'index', 'tick_ms', 'value', 'valid', 'saturated', 'held',
    'source_fault', 'source_tick_ms',
))
BINDING_KEYS = frozenset(('session', 'config_epoch', 'e'))


class TraceError(ValueError):
    '''Deterministic rejection of invalid candidate input, bytes or state.'''


def _require_int(value, what, minimum=None, maximum=None):
    '''Accept only exact built-in ints, checked before any comparison.'''
    if type(value) is not int:
        raise TraceError('%s must be an exact built-in int, got %s'
                         % (what, type(value).__name__))
    if minimum is not None and value < minimum:
        raise TraceError('%s=%d is below %d' % (what, value, minimum))
    if maximum is not None and value > maximum:
        raise TraceError('%s=%d is above %d' % (what, value, maximum))
    return value


def _require_bool(value, what):
    if type(value) is not bool:
        raise TraceError('%s must be an exact bool, got %s'
                         % (what, type(value).__name__))
    return value


def _check_exact_keys(mapping, expected, what):
    '''Reject non-str keys on type before any set/equality comparison.'''
    keys = list(mapping.keys())
    for key in keys:
        if type(key) is not str:
            raise TraceError('%s has a non-str key of type %s'
                             % (what, type(key).__name__))
    if len(keys) != len(expected) or set(keys) != expected:
        raise TraceError('%s must have exactly the keys %s'
                         % (what, sorted(expected)))


def _check_binding(binding):
    '''Snapshot one expected-binding fixture (offline trust is not implied).'''
    if type(binding) is not dict:
        raise TraceError('binding must be an exact dict, got %s'
                         % type(binding).__name__)
    _check_exact_keys(binding, BINDING_KEYS, 'binding')
    session = _require_int(binding['session'], 'binding.session', 0, U32_MAX)
    config_epoch = _require_int(binding['config_epoch'], 'binding.config_epoch',
                                0, U8_MAX)
    e = _require_int(binding['e'], 'binding.e')
    if e not in E_VALUES:
        raise TraceError('binding.e=%d is not one of %s' % (e, (E_VALUES,)))
    return {'session': session, 'config_epoch': config_epoch, 'e': e}


def _check_point(point, where):
    '''Validate one input point on exact types and return a detached copy.'''
    if type(point) is not dict:
        raise TraceError('%s must be an exact dict, got %s'
                         % (where, type(point).__name__))
    _check_exact_keys(point, POINT_KEYS, where)
    index = _require_int(point['index'], '%s.index' % where, 0, U32_MAX)
    tick = _require_int(point['tick_ms'], '%s.tick_ms' % where, 0, U64_MAX)
    valid = _require_bool(point['valid'], '%s.valid' % where)
    saturated = _require_bool(point['saturated'], '%s.saturated' % where)
    held = _require_bool(point['held'], '%s.held' % where)
    source_fault = _require_bool(point['source_fault'], '%s.source_fault' % where)
    value = point['value']
    source_tick = point['source_tick_ms']
    if valid:
        value = _require_int(value, '%s.value' % where, 0, SAMPLE_MAX)
        source_tick = _require_int(source_tick, '%s.source_tick_ms' % where,
                                   0, U64_MAX)
        if held:
            if source_tick >= tick:
                raise TraceError('%s held valid point requires '
                                 'source_tick_ms < tick_ms' % where)
        elif source_tick != tick:
            raise TraceError('%s fresh valid point requires '
                             'source_tick_ms == tick_ms' % where)
    else:
        if value is not None:
            raise TraceError('%s invalid point must carry value None' % where)
        if source_tick is not None:
            raise TraceError('%s invalid point must carry source_tick_ms None'
                             % where)
        if saturated:
            raise TraceError('%s invalid point cannot be saturated' % where)
        if held:
            raise TraceError('%s invalid point cannot be held' % where)
    return {
        'index': index,
        'tick_ms': tick,
        'value': value,
        'valid': valid,
        'saturated': saturated,
        'held': held,
        'source_fault': source_fault,
        'source_tick_ms': source_tick,
    }


def _validate_points(points):
    if type(points) is not list and type(points) is not tuple:
        raise TraceError('points must be an exact list or tuple, got %s'
                         % type(points).__name__)
    if len(points) < MIN_POINTS or len(points) > MAX_POINTS:
        raise TraceError('points count %d outside %d..%d'
                         % (len(points), MIN_POINTS, MAX_POINTS))
    return [_check_point(point, 'points[%d]' % position)
            for position, point in enumerate(points)]


def _residual_zvalues(values, e):
    step = 2 * e + 1
    z_values = []
    previous = values[0]
    for value in values[1:]:
        quotient = (value - previous + e) // step
        z_values.append(2 * quotient if quotient >= 0 else -2 * quotient - 1)
        reconstructed = previous + quotient * step
        if reconstructed > SAMPLE_MAX:
            reconstructed = SAMPLE_MAX
        elif reconstructed < 0:
            reconstructed = 0
        previous = reconstructed
    return z_values


def _canonical_selection(z_values):
    '''Two-stage canonical mode/k.

    Stage 1 chooses the Rice k with the fewest significant bits (quotient
    <= 31, ties lowest k - exactly the unchanged inner codec k choice);
    stage 2 then keeps Rice only when its padded code-byte count is strictly
    smaller than RAW's 2*count bytes, so a stored-byte tie selects RAW.
    '''
    count = len(z_values) + 1
    raw_bytes = 2 * count
    best_k = None
    best_bits = None
    for k in range(MAX_K + 1):
        total = 0
        legal = True
        for z in z_values:
            quotient = z >> k
            if quotient > MAX_QUOTIENT:
                legal = False
                break
            total += quotient + 1 + k
        if not legal:
            continue
        bits = SAMPLE_BITS + total
        if best_bits is None or bits < best_bits:
            best_k = k
            best_bits = bits
    if best_k is None:
        return {'mode': 'raw', 'k': 0, 'code_bits': SAMPLE_BITS * count,
                'code_bytes': raw_bytes}
    best_bytes = (best_bits + 7) // 8
    if best_bytes >= raw_bytes:
        return {'mode': 'raw', 'k': 0, 'code_bits': SAMPLE_BITS * count,
                'code_bytes': raw_bytes}
    return {'mode': 'rice', 'k': best_k, 'code_bits': best_bits,
            'code_bytes': best_bytes}


class _BitWriter:
    '''MSB-first bit writer for the Rice body; final low bits stay zero.'''

    def __init__(self):
        self._data = bytearray()
        self._partial = 0
        self._filled = 0

    def write_bits(self, value, width):
        for shift in range(width - 1, -1, -1):
            self._partial = (self._partial << 1) | ((value >> shift) & 1)
            self._filled += 1
            if self._filled == 8:
                self._data.append(self._partial)
                self._partial = 0
                self._filled = 0

    def write_unary(self, quotient):
        for _ in range(quotient):
            self.write_bits(0, 1)
        self.write_bits(1, 1)

    def to_bytes(self):
        data = bytearray(self._data)
        if self._filled:
            data.append(self._partial << (8 - self._filled))
        return bytes(data)


class _BitReader:
    '''MSB-first bit reader bounded by a valid-bit count.'''

    def __init__(self, data, valid_bits):
        self._data = data
        self._valid = valid_bits
        self._position = 0

    def remaining(self):
        return self._valid - self._position

    def read_bits(self, width):
        if width > self.remaining():
            raise TraceError('truncated Rice body: need %d bit(s), %d left'
                             % (width, self.remaining()))
        value = 0
        for _ in range(width):
            byte = self._data[self._position >> 3]
            value = (value << 1) | ((byte >> (7 - (self._position & 7))) & 1)
            self._position += 1
        return value

    def read_unary(self):
        zeros = 0
        while zeros <= MAX_QUOTIENT:
            if self.remaining() == 0:
                raise TraceError('truncated Rice body: unary terminator missing')
            if self.read_bits(1):
                return zeros
            zeros += 1
        raise TraceError('overlong unary: quotient exceeds %d' % MAX_QUOTIENT)


def _build_code(values, z_values, selection):
    '''Anchor first (little-endian), then the selected body.'''
    data = bytearray(struct.pack('<H', values[0]))
    if selection['mode'] == 'raw':
        for value in values[1:]:
            data += struct.pack('<H', value)
        return bytes(data)
    k = selection['k']
    mask = (1 << k) - 1
    writer = _BitWriter()
    for z in z_values:
        writer.write_unary(z >> k)
        if k:
            writer.write_bits(z & mask, k)
    data += writer.to_bytes()
    return bytes(data)


def _prepare_block(points, binding, channel):
    '''Encode one validated block; points are detached snapshots (1..128).'''
    count = len(points)
    first = points[0]
    valid = first['valid']
    saturated = first['saturated']
    held = first['held']
    source_fault = first['source_fault']
    for position in range(1, count):
        point = points[position]
        if (point['valid'] != valid or point['saturated'] != saturated
                or point['held'] != held or point['source_fault'] != source_fault):
            raise TraceError('quality flags are not uniform across the block '
                             '(point %d)' % position)
    extension = b''
    long_source = False
    if held:
        origin = first['source_tick_ms']
        for position in range(count):
            point = points[position]
            if point['source_tick_ms'] != origin:
                raise TraceError('held source update origin changes at point %d'
                                 % position)
            if origin >= point['tick_ms']:
                raise TraceError('held origin must be below every tick '
                                 '(point %d)' % position)
        age = first['tick_ms'] - origin
        if age <= U16_MAX:
            extension = struct.pack('<H', age)
        else:
            extension = struct.pack('<Q', origin)
            long_source = True
    cadence = b''
    if count > 1:
        index_stride = points[1]['index'] - first['index']
        tick_stride = points[1]['tick_ms'] - first['tick_ms']
        if index_stride < 1 or index_stride > U16_MAX:
            raise TraceError('index stride %d not representable in 1..%d'
                             % (index_stride, U16_MAX))
        if tick_stride < 1 or tick_stride > U16_MAX:
            raise TraceError('tick stride %d not representable in 1..%d'
                             % (tick_stride, U16_MAX))
        for position in range(1, count):
            if points[position]['index'] != first['index'] + position * index_stride:
                raise TraceError('index spacing is not uniform at point %d'
                                 % position)
            if points[position]['tick_ms'] != first['tick_ms'] + position * tick_stride:
                raise TraceError('tick spacing is not uniform at point %d'
                                 % position)
        if first['index'] + (count - 1) * index_stride > U32_MAX:
            raise TraceError('index progression overflows uint32')
        if first['tick_ms'] + (count - 1) * tick_stride > U64_MAX:
            raise TraceError('tick progression overflows uint64')
        cadence = struct.pack('<HH', index_stride, tick_stride)
    metadata_bytes = PAYLOAD_PREFIX_BYTES + len(cadence) + len(extension)
    if metadata_bytes > PAYLOAD_MAX_BYTES:
        raise TraceError('metadata %d B exceeds the %d B payload budget'
                         % (metadata_bytes, PAYLOAD_MAX_BYTES))
    if valid:
        values = [point['value'] for point in points]
        z_values = _residual_zvalues(values, binding['e'])
        selection = _canonical_selection(z_values)
        raw_flag = selection['mode'] == 'raw'
        k = selection['k'] if not raw_flag else 0
        bits = selection['code_bits']
        code = _build_code(values, z_values, selection)
    else:
        raw_flag = True
        k = 0
        bits = 0
        code = b''
    if bits > U8_MAX:
        raise TraceError('significant bits %d exceed the uint8 field' % bits)
    code_bytes = (bits + 7) // 8
    if len(code) != code_bytes:
        raise AssertionError('internal code byte count mismatch')
    if metadata_bytes + code_bytes > PAYLOAD_MAX_BYTES:
        raise TraceError('payload %d B exceeds the %d B candidate budget'
                         % (metadata_bytes + code_bytes, PAYLOAD_MAX_BYTES))
    settings = (k << 4) | (0x08 if raw_flag else 0x00) | E_CODE[binding['e']]
    quality = (channel | (0x04 if valid else 0) | (0x08 if saturated else 0)
               | (0x10 if held else 0) | (0x20 if source_fault else 0)
               | (0x40 if long_source else 0))
    payload = struct.pack('<BBBBBIIQ', CANDIDATE_REVISION, settings, quality,
                          count, bits, binding['session'], first['index'],
                          first['tick_ms']) + cadence + extension + code
    if len(payload) > PAYLOAD_MAX_BYTES:
        raise AssertionError('internal payload bound mismatch')
    return payload, first['tick_ms']


def encode_payload(points, binding, channel):
    '''Encode one complete candidate block; never splits silently.'''
    binding_snapshot = _check_binding(binding)
    _require_int(channel, 'channel', 0, CHANNELS - 1)
    snapshots = _validate_points(points)
    payload, _first_tick = _prepare_block(snapshots, binding_snapshot, channel)
    return payload


def _build_ledger(count, valid, significant_bits, stored_code_bytes,
                  metadata_bytes, payload_bytes):
    return {
        'count': count,
        'value_count': count if valid else 0,
        'selected_raw_bytes': 2 * count if valid else 0,
        'significant_bits': significant_bits,
        'stored_code_bytes': stored_code_bytes,
        'padding_bits': 8 * stored_code_bytes - significant_bits,
        'metadata_bytes': metadata_bytes,
        'payload_bytes': payload_bytes,
        'outer_overhead_bytes': OUTER_OVERHEAD_BYTES,
        'frame_bytes': payload_bytes + OUTER_OVERHEAD_BYTES,
        'line_bits_8n1': 10 * (payload_bytes + OUTER_OVERHEAD_BYTES),
    }


def decode_payload(payload, binding):
    '''Strictly decode one candidate payload into a detached record.'''
    binding_snapshot = _check_binding(binding)
    if type(payload) is not bytes:
        raise TraceError('payload must be exact bytes, got %s'
                         % type(payload).__name__)
    if len(payload) < PAYLOAD_PREFIX_BYTES:
        raise TraceError('payload %d B shorter than the %d B prefix'
                         % (len(payload), PAYLOAD_PREFIX_BYTES))
    if len(payload) > PAYLOAD_MAX_BYTES:
        raise TraceError('payload %d B exceeds the %d B candidate budget'
                         % (len(payload), PAYLOAD_MAX_BYTES))
    (revision, settings, quality, count, bits, session, first_index,
     first_tick) = struct.unpack_from('<BBBBBIIQ', payload, 0)
    if revision != CANDIDATE_REVISION:
        raise TraceError('candidate revision %d is not %d'
                         % (revision, CANDIDATE_REVISION))
    if quality & QUALITY_RESERVED_BIT:
        raise TraceError('quality bit7 (reserved) must be zero')
    e_code = settings & 0x07
    if e_code > 4:
        raise TraceError('E code %d is not defined' % e_code)
    e = E_BY_CODE[e_code]
    if e != binding_snapshot['e']:
        raise TraceError('payload E=%d does not match binding.e=%d'
                         % (e, binding_snapshot['e']))
    raw_flag = bool(settings & 0x08)
    k = settings >> 4
    if raw_flag and k != 0:
        raise TraceError('RAW blocks require k=0, got %d' % k)
    channel = quality & 0x03
    valid = bool(quality & 0x04)
    saturated = bool(quality & 0x08)
    held = bool(quality & 0x10)
    source_fault = bool(quality & 0x20)
    long_source = bool(quality & 0x40)
    if session != binding_snapshot['session']:
        raise TraceError('payload session %d does not match binding.session %d'
                         % (session, binding_snapshot['session']))
    if count < MIN_POINTS or count > MAX_POINTS:
        raise TraceError('point count %d outside %d..%d'
                         % (count, MIN_POINTS, MAX_POINTS))
    offset = PAYLOAD_PREFIX_BYTES
    index_stride = None
    tick_stride = None
    if count > 1:
        if len(payload) < offset + 4:
            raise TraceError('payload ends inside the stride fields')
        index_stride, tick_stride = struct.unpack_from('<HH', payload, offset)
        offset += 4
        if index_stride < 1:
            raise TraceError('index stride must be positive')
        if tick_stride < 1:
            raise TraceError('tick stride must be positive')
        if first_index + (count - 1) * index_stride > U32_MAX:
            raise TraceError('index progression overflows uint32')
        if first_tick + (count - 1) * tick_stride > U64_MAX:
            raise TraceError('tick progression overflows uint64')
    origin = None
    if held:
        if long_source:
            if len(payload) < offset + 8:
                raise TraceError('payload ends inside the long source-tick field')
            origin = struct.unpack_from('<Q', payload, offset)[0]
            offset += 8
            if origin >= first_tick:
                raise TraceError('long source tick must precede the first tick')
            if first_tick - origin <= U16_MAX:
                raise TraceError('long source-tick form is not canonical '
                                 'for a short age')
        else:
            if len(payload) < offset + 2:
                raise TraceError('payload ends inside the short source-age field')
            age = struct.unpack_from('<H', payload, offset)[0]
            offset += 2
            if age < 1:
                raise TraceError('short source-age form requires a positive age')
            if age > first_tick:
                raise TraceError('short source age %d exceeds the first tick %d; '
                                 'the source origin would be negative'
                                 % (age, first_tick))
            origin = first_tick - age
    elif long_source:
        raise TraceError('long source-tick bit requires the held flag')
    metadata_bytes = offset
    if not valid:
        if not raw_flag:
            raise TraceError('quality-only invalid blocks must carry the RAW flag')
        if bits != 0:
            raise TraceError('invalid blocks must carry zero significant bits')
        if saturated:
            raise TraceError('invalid blocks cannot be saturated')
        if held:
            raise TraceError('invalid blocks cannot be held')
        if len(payload) != offset:
            raise TraceError('invalid block carries %d unexpected trailing byte(s)'
                             % (len(payload) - offset))
        points = []
        for position in range(count):
            points.append({
                'index': first_index + (position * index_stride if count > 1 else 0),
                'tick_ms': first_tick + (position * tick_stride if count > 1 else 0),
                'value': None,
                'valid': False,
                'saturated': False,
                'held': False,
                'source_fault': source_fault,
                'source_tick_ms': None,
            })
        return {
            'channel': channel, 'mode': 'raw', 'k': 0, 'e': e,
            'valid': False, 'saturated': False, 'held': False,
            'source_fault': source_fault, 'long_source_tick': False,
            'count': count, 'significant_bits': 0,
            'first_index': first_index, 'first_tick_ms': first_tick,
            'index_stride': index_stride, 'tick_stride_ms': tick_stride,
            'held_origin_tick_ms': None, 'settings_byte': settings,
            'quality_byte': quality, 'points': points,
            'ledger': _build_ledger(count, False, 0, 0, metadata_bytes,
                                    len(payload)),
        }
    if bits < SAMPLE_BITS:
        raise TraceError('valid blocks must carry at least the %d anchor bits'
                         % SAMPLE_BITS)
    code_bytes = (bits + 7) // 8
    if len(payload) != offset + code_bytes:
        raise TraceError('payload length does not match metadata plus %d '
                         'code byte(s)' % code_bytes)
    code = payload[offset:]
    for position in range(bits, 8 * code_bytes):
        if (code[position >> 3] >> (7 - (position & 7))) & 1:
            raise TraceError('nonzero padding bit at code bit %d' % position)
    values = [struct.unpack_from('<H', code, 0)[0]]
    if raw_flag:
        if len(code) < 2 * count:
            raise TraceError('RAW code section too short for %d samples' % count)
        for position in range(1, count):
            values.append(struct.unpack_from('<H', code, 2 * position)[0])
    else:
        reader = _BitReader(code[2:], bits - SAMPLE_BITS)
        previous = values[0]
        step = 2 * e + 1
        for _ in range(count - 1):
            quotient = reader.read_unary()
            remainder = reader.read_bits(k) if k else 0
            z = (quotient << k) | remainder
            signed = z >> 1 if z % 2 == 0 else -((z + 1) >> 1)
            reconstructed = previous + signed * step
            if reconstructed > SAMPLE_MAX:
                reconstructed = SAMPLE_MAX
            elif reconstructed < 0:
                reconstructed = 0
            values.append(reconstructed)
            previous = reconstructed
        if reader.remaining() != 0:
            raise TraceError('Rice body left %d unused significant bit(s)'
                             % reader.remaining())
    z_values = _residual_zvalues(values, e)
    selection = _canonical_selection(z_values)
    expected_mode = 'raw' if raw_flag else 'rice'
    if selection['mode'] != expected_mode:
        raise TraceError('noncanonical mode: %s declared, %s selected'
                         % (expected_mode, selection['mode']))
    if selection['k'] != k:
        raise TraceError('noncanonical k: declared %d, selected %d'
                         % (k, selection['k']))
    if selection['code_bits'] != bits:
        raise TraceError('noncanonical significant bits: declared %d, '
                         'selected %d' % (bits, selection['code_bits']))
    if _build_code(values, z_values, selection) != code:
        raise TraceError('code bytes do not match the canonical re-encoding')
    points = []
    for position in range(count):
        index = first_index + (position * index_stride if count > 1 else 0)
        tick = first_tick + (position * tick_stride if count > 1 else 0)
        source_tick = origin if held else tick
        if held and source_tick >= tick:
            raise TraceError('held source tick must precede the tick at '
                             'point %d' % position)
        points.append({
            'index': index,
            'tick_ms': tick,
            'value': values[position],
            'valid': True,
            'saturated': saturated,
            'held': held,
            'source_fault': source_fault,
            'source_tick_ms': source_tick,
        })
    return {
        'channel': channel, 'mode': selection['mode'], 'k': k, 'e': e,
        'valid': True, 'saturated': saturated, 'held': held,
        'source_fault': source_fault, 'long_source_tick': long_source,
        'count': count, 'significant_bits': bits,
        'first_index': first_index, 'first_tick_ms': first_tick,
        'index_stride': index_stride, 'tick_stride_ms': tick_stride,
        'held_origin_tick_ms': origin if held else None,
        'settings_byte': settings, 'quality_byte': quality, 'points': points,
        'ledger': _build_ledger(count, True, bits, code_bytes, metadata_bytes,
                                len(payload)),
    }


def decode_frame(packet, binding):
    '''Strict outer decode: header, CRC, epoch/session/E/tick-low checks.'''
    binding_snapshot = _check_binding(binding)
    if type(packet) is not bytes:
        raise TraceError('packet must be exact bytes, got %s'
                         % type(packet).__name__)
    if len(packet) < HEADER_BYTES + PAYLOAD_PREFIX_BYTES + CRC_BYTES:
        raise TraceError('packet %d B shorter than the smallest candidate frame'
                         % len(packet))
    if len(packet) > FRAME_MAX_BYTES:
        raise TraceError('packet %d B exceeds the %d B candidate frame budget'
                         % (len(packet), FRAME_MAX_BYTES))
    (magic, version, type_code, payload_len, config_epoch, sequence,
     tick_low) = struct.unpack_from(HEADER_FORMAT, packet, 0)
    if magic != OUTER_MAGIC:
        raise TraceError('bad candidate magic %s' % magic.hex())
    if version != OUTER_VERSION:
        raise TraceError('outer version %d is not %d' % (version, OUTER_VERSION))
    if type_code != OUTER_TYPE:
        raise TraceError('outer type %d is not the candidate type %d'
                         % (type_code, OUTER_TYPE))
    if payload_len > PAYLOAD_MAX_BYTES:
        raise TraceError('declared payload %d B exceeds the %d B budget'
                         % (payload_len, PAYLOAD_MAX_BYTES))
    if len(packet) != HEADER_BYTES + payload_len + CRC_BYTES:
        raise TraceError('packet length does not match the declared payload')
    if config_epoch != binding_snapshot['config_epoch']:
        raise TraceError('frame config_epoch %d does not match binding %d'
                         % (config_epoch, binding_snapshot['config_epoch']))
    stored_crc = struct.unpack_from('<H', packet, len(packet) - CRC_BYTES)[0]
    computed_crc = binascii.crc_hqx(packet[2:len(packet) - CRC_BYTES], 0xFFFF)
    if stored_crc != computed_crc:
        raise TraceError('CRC mismatch: stored 0x%04x, computed 0x%04x'
                         % (stored_crc, computed_crc))
    payload = packet[HEADER_BYTES:len(packet) - CRC_BYTES]
    record = decode_payload(payload, binding_snapshot)
    if tick_low != record['first_tick_ms'] & U32_MAX:
        raise TraceError('header tick %d is not the low32 of the first tick %d'
                         % (tick_low, record['first_tick_ms']))
    record['sequence'] = sequence
    record['config_epoch'] = config_epoch
    return record


def encode_frame(points, binding, channel, sequence):
    '''Encode one candidate frame: ABI3 header + payload + CRC/CCITT-FALSE.'''
    binding_snapshot = _check_binding(binding)
    _require_int(channel, 'channel', 0, CHANNELS - 1)
    _require_int(sequence, 'sequence', 0, U16_MAX)
    payload, first_tick = _prepare_block(_validate_points(points),
                                         binding_snapshot, channel)
    header = struct.pack(HEADER_FORMAT, OUTER_MAGIC, OUTER_VERSION, OUTER_TYPE,
                         len(payload), binding_snapshot['config_epoch'], sequence,
                         first_tick & U32_MAX)
    crc = binascii.crc_hqx(header[2:] + payload, 0xFFFF)
    frame = header + payload + struct.pack('<H', crc)
    if len(frame) > FRAME_MAX_BYTES:
        raise AssertionError('internal frame bound mismatch')
    return frame


def pack_channel(points, binding, channel, start_sequence):
    '''Greedy longest-prefix packer; returns independently decodable frames.'''
    binding_snapshot = _check_binding(binding)
    _require_int(channel, 'channel', 0, CHANNELS - 1)
    _require_int(start_sequence, 'start_sequence', 0, U16_MAX)
    snapshots = _validate_points(points)
    for position in range(1, len(snapshots)):
        if snapshots[position]['index'] <= snapshots[position - 1]['index']:
            raise TraceError('pack_channel requires strictly increasing indices '
                             '(point %d)' % position)
        if snapshots[position]['tick_ms'] <= snapshots[position - 1]['tick_ms']:
            raise TraceError('pack_channel requires strictly increasing ticks '
                             '(point %d)' % position)
    blocks = []
    position = 0
    total = len(snapshots)
    while position < total:
        best_length = 0
        best_payload = None
        best_tick = None
        for length in range(1, total - position + 1):
            try:
                payload, first_tick = _prepare_block(
                    snapshots[position:position + length], binding_snapshot,
                    channel)
            except TraceError:
                break
            best_length = length
            best_payload = payload
            best_tick = first_tick
        if best_length == 0:
            raise TraceError('internal error: no legal block starts at point %d'
                             % position)
        blocks.append((best_payload, best_tick))
        position += best_length
    if start_sequence + len(blocks) - 1 > U16_MAX:
        raise TraceError('sequence capacity %d..%d cannot hold %d frame(s); '
                         'no partial output is emitted'
                         % (start_sequence, U16_MAX, len(blocks)))
    frames = []
    for offset, (payload, first_tick) in enumerate(blocks):
        header = struct.pack(HEADER_FORMAT, OUTER_MAGIC, OUTER_VERSION,
                             OUTER_TYPE, len(payload),
                             binding_snapshot['config_epoch'],
                             start_sequence + offset, first_tick & U32_MAX)
        crc = binascii.crc_hqx(header[2:] + payload, 0xFFFF)
        frames.append(header + payload + struct.pack('<H', crc))
    return frames


class TraceReceiver:
    '''Bounded offline candidate receiver: one immutable binding per instance.

    State: at most CACHE_LIMIT packet byte strings keyed by sequence, a global
    non-wrapping last sequence, and four per-channel (last index, last tick)
    high-water pairs.  Decoder validation happens before any state commit, so
    a bad CRC/payload/binding, a sequence conflict, a stale sequence or a
    channel order violation never partially advances the high waters.

    This offline class cannot attest that a caller performed a real
    handshake, that session IDs are unique, or that bytes came from a trusted
    source; it makes no runtime authorization claim.
    '''

    def __init__(self, binding):
        self._binding = _check_binding(binding)
        self._closed = False
        self._last_sequence = None
        self._cache = {}
        self._cache_order = []
        self._high_water = {}

    def close(self):
        '''Terminal close; idempotent, and accept() then rejects.'''
        self._closed = True

    def accept(self, packet):
        if self._closed:
            raise TraceError('receiver is closed; no further frames are accepted')
        record = decode_frame(packet, self._binding)
        sequence = record['sequence']
        cached = self._cache.get(sequence)
        if cached is not None:
            if cached == packet:
                return {'status': 'duplicate', 'sequence': sequence, 'points': []}
            raise TraceError('sequence %d conflicts with cached packet bytes'
                             % sequence)
        if (self._last_sequence is not None
                and sequence <= self._last_sequence):
            raise TraceError('sequence %d is not newer than the last accepted '
                             '%d and is outside the cache'
                             % (sequence, self._last_sequence))
        channel = record['channel']
        first_index = record['first_index']
        first_tick = record['first_tick_ms']
        water = self._high_water.get(channel)
        if water is not None:
            if first_index <= water['last_index']:
                raise TraceError('channel %d index order violated: first %d '
                                 'not above %d'
                                 % (channel, first_index, water['last_index']))
            if first_tick <= water['last_tick_ms']:
                raise TraceError('channel %d tick order violated: first %d '
                                 'not above %d'
                                 % (channel, first_tick, water['last_tick_ms']))
        self._cache[sequence] = packet
        self._cache_order.append(sequence)
        if len(self._cache_order) > CACHE_LIMIT:
            evicted = self._cache_order.pop(0)
            del self._cache[evicted]
        self._last_sequence = sequence
        last_point = record['points'][-1]
        self._high_water[channel] = {'last_index': last_point['index'],
                                     'last_tick_ms': last_point['tick_ms']}
        return {
            'status': 'ok',
            'sequence': sequence,
            'channel': channel,
            'mode': record['mode'],
            'k': record['k'],
            'e': record['e'],
            'significant_bits': record['significant_bits'],
            'first_index': first_index,
            'first_tick_ms': first_tick,
            'points': list(record['points']),
            'ledger': dict(record['ledger']),
        }

    def state_snapshot(self):
        '''Detached snapshot; caller mutation cannot change receiver state.'''
        return {
            'binding': dict(self._binding),
            'closed': self._closed,
            'last_sequence': self._last_sequence,
            'packet_cache': [(seq, bytes(self._cache[seq]))
                             for seq in self._cache_order],
            'channel_high_water': {
                channel: dict(values)
                for channel, values in sorted(self._high_water.items())
            },
        }
