'''DeepEye integer inner-codec candidate - reference foundation (candidate only).

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-CODEC-INTEGER-FOUNDATION-20261015-01-v1
Contract: DEEPEYE-HUMAN-LOCK-20261014/revision1 (H01-H15),
requirements SHA256 c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804.

Status: CANDIDATE-ONLY.  This module is a B-side integer foundation for the
inner codec block body.  It is NOT a production TRACE encoder, defines no
public TRACE byte layout/schema, no payload offset, tick, mask, block id,
saturation or 32-byte total accounting rule, and carries no acceptance
claim.  R03 and B01 remain not_run; A alone operates the physical board.

Implemented candidate rules:
  * uint16 scalar samples; bool/non-int/out-of-range rejected; block length
    1..128; every block starts with the exact absolute uint16 anchor; the
    predictor resets at every block start.
  * E in {0,1,2,4,8}; D = 2E+1; q = (x - p + E) // D with mathematical
    floor; y = min(65535, max(0, p + q*D)); p = y.  E=0 is exact.
  * ZigZag: z = 2q if q >= 0 else -2q-1.
  * Per-block Rice, single k in 0..15, MSB-first: quotient zero bits then a
    one terminator, then k remainder bits MSB-first; quotient > 31 is
    illegal for that k (no escape).
  * Per-block selection: minimum Rice body bit count over legal k, ties
    choose the lowest k; the whole block falls back to RAW (original
    remaining uint16 samples) when the best Rice body is >= 16*(n-1) bits
    or when no k is legal.
  * Candidate fixture stores valid_bit_count separately from payload bytes;
    unused low bits of the final payload byte must be zero.

The candidate fixture dictionary is candidate-internal and is not a TRACE
layout field set.  See README.md and integer_candidate_rules.json in this
directory for the frozen candidate description.
'''

from __future__ import annotations

E_VALUES = (0, 1, 2, 4, 8)
MAX_BLOCK_SAMPLES = 128
SAMPLE_BITS = 16
SAMPLE_MIN = 0
SAMPLE_MAX = 65535
MAX_K = 15
MAX_QUOTIENT = 31


class CodecError(ValueError):
    '''Deterministic rejection of invalid samples or candidate fixtures.'''


def _require_int(value, what):
    if isinstance(value, bool) or not isinstance(value, int):
        raise CodecError('%s must be an int, got %s' % (what, type(value).__name__))
    return value


def _check_sample_values(samples):
    if isinstance(samples, (str, bytes)) or not isinstance(samples, (list, tuple)):
        raise CodecError('samples must be a list or tuple of ints')
    values = []
    for index, value in enumerate(samples):
        if isinstance(value, bool) or not isinstance(value, int):
            raise CodecError('sample[%d] must be an int, got %s'
                             % (index, type(value).__name__))
        if value < SAMPLE_MIN or value > SAMPLE_MAX:
            raise CodecError('sample[%d]=%d outside uint16 range' % (index, value))
        values.append(value)
    return values


def check_samples(samples):
    '''Validate one candidate block (1..128 uint16 samples) and copy it.'''
    values = _check_sample_values(samples)
    if not values:
        raise CodecError('block must contain at least 1 sample')
    if len(values) > MAX_BLOCK_SAMPLES:
        raise CodecError('block length %d exceeds %d samples'
                         % (len(values), MAX_BLOCK_SAMPLES))
    return values


def check_sample_sequence(samples):
    '''Validate one uint16 sample stream (length >= 1) and copy it.'''
    values = _check_sample_values(samples)
    if not values:
        raise CodecError('sample sequence must not be empty')
    return values


def check_e(e):
    '''E must be exactly one of 0, 1, 2, 4, 8 (bool is rejected).'''
    _require_int(e, 'E')
    if e not in E_VALUES:
        raise CodecError('E=%d not in %s' % (e, (E_VALUES,)))
    return e


def zigzag(q):
    '''Map a signed quotient to a non-negative candidate ZigZag value.'''
    _require_int(q, 'q')
    return 2 * q if q >= 0 else -2 * q - 1


def unzigzag(z):
    '''Inverse ZigZag for a non-negative candidate ZigZag value.'''
    _require_int(z, 'z')
    if z < 0:
        raise CodecError('zigzag value must be non-negative')
    return z >> 1 if z % 2 == 0 else -((z + 1) >> 1)


def quantize(x, previous, e):
    '''Candidate residual q = (x - previous + E) // (2E+1), floor division.'''
    d = 2 * e + 1
    return (x - previous + e) // d


def reconstruct(previous, q, e):
    '''Candidate reconstruction y = clamp(previous + q*(2E+1)).'''
    y = previous + q * (2 * e + 1)
    if y > SAMPLE_MAX:
        return SAMPLE_MAX
    if y < SAMPLE_MIN:
        return SAMPLE_MIN
    return y


def select_body_encoding(z_values):
    '''Choose the candidate body encoding for one block.

    Input: the ZigZag value of every coded residual (n-1 values, n >= 1).
    Candidate selection: minimum total Rice body bits over legal k
    (quotient <= 31), ties choose the lowest k; RAW when no k is legal or
    when the best Rice body is >= 16*(n-1) bits (RAW wins ties).
    '''
    zs = []
    for z in z_values:
        z = _require_int(z, 'zigzag value')
        if z < 0:
            raise CodecError('zigzag value must be non-negative')
        zs.append(z)
    raw_bits = SAMPLE_BITS * len(zs)
    best_k = None
    best_bits = None
    legal_k = []
    for k in range(MAX_K + 1):
        total = 0
        legal = True
        for z in zs:
            quotient = z >> k
            if quotient > MAX_QUOTIENT:
                legal = False
                break
            total += quotient + 1 + k
        if not legal:
            continue
        legal_k.append(k)
        if best_bits is None or total < best_bits:
            best_k = k
            best_bits = total
    if best_bits is None or best_bits >= raw_bits:
        return {'mode': 'raw', 'k': None, 'body_bits': raw_bits,
                'legal_k': legal_k, 'best_rice_bits': best_bits}
    return {'mode': 'rice', 'k': best_k, 'body_bits': best_bits,
            'legal_k': legal_k, 'best_rice_bits': best_bits}


class _BitWriter:
    '''MSB-first bit writer; unused low bits of the final byte stay zero.'''

    def __init__(self):
        self._bytes = bytearray()
        self._partial = 0
        self._filled = 0
        self.bits_written = 0

    def write(self, value, width):
        _require_int(value, 'bit field value')
        _require_int(width, 'bit width')
        if width < 0:
            raise CodecError('bit width must be non-negative')
        if value < 0 or value >= (1 << width):
            raise CodecError('value %d does not fit in %d bit(s)' % (value, width))
        for shift in range(width - 1, -1, -1):
            self._partial = (self._partial << 1) | ((value >> shift) & 1)
            self._filled += 1
            self.bits_written += 1
            if self._filled == 8:
                self._bytes.append(self._partial)
                self._partial = 0
                self._filled = 0

    def write_unary(self, quotient):
        _require_int(quotient, 'unary quotient')
        if quotient < 0 or quotient > MAX_QUOTIENT:
            raise CodecError('unary quotient %d outside 0..%d'
                             % (quotient, MAX_QUOTIENT))
        for _ in range(quotient):
            self.write(0, 1)
        self.write(1, 1)

    def to_payload(self):
        data = bytearray(self._bytes)
        if self._filled:
            data.append(self._partial << (8 - self._filled))
        return bytes(data)


class _BitReader:
    '''MSB-first bit reader bounded by the fixture valid_bit_count.'''

    def __init__(self, payload, valid_bit_count):
        self._payload = payload
        self._valid = valid_bit_count
        self._position = 0

    def remaining(self):
        return self._valid - self._position

    def read(self, width):
        if width > self.remaining():
            raise CodecError('truncated bitstream: need %d bit(s), %d left'
                             % (width, self.remaining()))
        value = 0
        for _ in range(width):
            byte = self._payload[self._position >> 3]
            value = (value << 1) | ((byte >> (7 - (self._position & 7))) & 1)
            self._position += 1
        return value

    def read_unary(self):
        zeros = 0
        while zeros <= MAX_QUOTIENT:
            if self.remaining() == 0:
                raise CodecError('truncated bitstream: unary terminator missing')
            if self.read(1):
                return zeros
            zeros += 1
        raise CodecError('overlong unary: quotient exceeds %d' % MAX_QUOTIENT)


def _residuals(values, e):
    z_values = []
    previous = values[0]
    for x in values[1:]:
        q = quantize(x, previous, e)
        z_values.append(zigzag(q))
        previous = reconstruct(previous, q, e)
    return z_values


def encode_block(samples, e):
    '''Encode one candidate block and return the candidate fixture dict.'''
    values = check_samples(samples)
    e = check_e(e)
    writer = _BitWriter()
    writer.write(values[0], SAMPLE_BITS)
    z_values = _residuals(values, e)
    selection = select_body_encoding(z_values)
    if selection['mode'] == 'rice':
        k = selection['k']
        mask = (1 << k) - 1
        for z in z_values:
            writer.write_unary(z >> k)
            if k:
                writer.write(z & mask, k)
    else:
        for x in values[1:]:
            writer.write(x, SAMPLE_BITS)
    valid_bit_count = SAMPLE_BITS + selection['body_bits']
    if writer.bits_written != valid_bit_count:
        raise AssertionError('internal bit accounting mismatch')
    return {
        'mode': selection['mode'],
        'e': e,
        'k': selection['k'],
        'sample_count': len(values),
        'valid_bit_count': valid_bit_count,
        'payload_hex': writer.to_payload().hex(),
    }


_HEX_DIGITS = set('0123456789abcdefABCDEF')


def _parse_fixture(fixture):
    '''Validate every candidate fixture invariant and split it into parts.'''
    if not isinstance(fixture, dict):
        raise CodecError('fixture must be a dict')
    mode = fixture.get('mode')
    if mode not in ('rice', 'raw'):
        raise CodecError('mode must be rice or raw, got %r' % (mode,))
    e = check_e(fixture.get('e'))
    k = fixture.get('k')
    if mode == 'rice':
        _require_int(k, 'k')
        if k < 0 or k > MAX_K:
            raise CodecError('k=%d outside 0..%d' % (k, MAX_K))
    elif k is not None:
        raise CodecError('RAW fixture must carry k=null')
    count = _require_int(fixture.get('sample_count'), 'sample_count')
    if count < 1 or count > MAX_BLOCK_SAMPLES:
        raise CodecError('sample_count=%d outside 1..%d' % (count, MAX_BLOCK_SAMPLES))
    valid_bit_count = _require_int(fixture.get('valid_bit_count'), 'valid_bit_count')
    payload_hex = fixture.get('payload_hex')
    if not isinstance(payload_hex, str):
        raise CodecError('payload_hex must be a hex string')
    if len(payload_hex) % 2 != 0:
        raise CodecError('payload_hex must have an even number of digits')
    if any(ch not in _HEX_DIGITS for ch in payload_hex):
        raise CodecError('payload_hex contains a non-hex character')
    payload = bytes.fromhex(payload_hex)
    if valid_bit_count < SAMPLE_BITS:
        raise CodecError('valid_bit_count=%d does not cover the %d-bit anchor'
                         % (valid_bit_count, SAMPLE_BITS))
    if valid_bit_count > 8 * len(payload):
        raise CodecError('valid_bit_count=%d exceeds %d payload byte(s)'
                         % (valid_bit_count, len(payload)))
    if (valid_bit_count + 7) // 8 != len(payload):
        raise CodecError('payload has excess bytes beyond valid_bit_count')
    for position in range(valid_bit_count, 8 * len(payload)):
        byte = payload[position >> 3]
        if (byte >> (7 - (position & 7))) & 1:
            raise CodecError('nonzero padding bit at payload bit %d' % position)
    return mode, e, k, count, valid_bit_count, payload


def decode_block(fixture):
    '''Decode one candidate fixture back to uint16 samples (strict).'''
    mode, e, k, count, valid_bit_count, payload = _parse_fixture(fixture)
    reader = _BitReader(payload, valid_bit_count)
    anchor = reader.read(SAMPLE_BITS)
    samples = [anchor]
    previous = anchor
    for _ in range(count - 1):
        if mode == 'rice':
            quotient = reader.read_unary()
            remainder = reader.read(k) if k else 0
            y = reconstruct(previous, unzigzag((quotient << k) | remainder), e)
        else:
            y = reader.read(SAMPLE_BITS)
        samples.append(y)
        previous = y
    if reader.remaining() != 0:
        raise CodecError('extra bits: %d valid bit(s) left after %d sample(s)'
                         % (reader.remaining(), count))
    return samples


def split_blocks(samples, block_len=MAX_BLOCK_SAMPLES):
    '''Split one sample stream into candidate blocks of at most block_len.'''
    values = check_sample_sequence(samples)
    _require_int(block_len, 'block_len')
    if block_len < 1 or block_len > MAX_BLOCK_SAMPLES:
        raise CodecError('block_len=%d outside 1..%d' % (block_len, MAX_BLOCK_SAMPLES))
    return [values[i:i + block_len] for i in range(0, len(values), block_len)]


def encode_blocks(samples, e, block_len=MAX_BLOCK_SAMPLES):
    '''Encode one sample stream as independent candidate blocks.'''
    return [encode_block(block, e) for block in split_blocks(samples, block_len)]


def decode_blocks(fixtures):
    '''Decode a list of independent candidate fixtures into one stream.'''
    if isinstance(fixtures, (str, bytes)) or not isinstance(fixtures, (list, tuple)):
        raise CodecError('fixtures must be a list or tuple')
    samples = []
    for fixture in fixtures:
        samples.extend(decode_block(fixture))
    return samples
