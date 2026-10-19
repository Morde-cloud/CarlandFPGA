'''Offline register transaction reference for the B07 candidate layout.

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-REGISTER-TRANSACTION-20261019-10-v1
Operation: B-DEEPEYE-REGISTER-TRANSACTION-20261019-10
Contract: DEEPEYE-HUMAN-LOCK-20261014 revision 1 (H01-H15)
Requirements SHA256:
    c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804
Lock commit: f5989cd5defce561f9ba98e6b18fc2682945f0a2
Design commit: 1011259415a0916054eb580687612580bc1e5f09
B07 owner decision input SHA256:
    5cb049b28da33eea74e8a30365962d731b3f2d198065086daab1998ff747e116

This is a bounded, deterministic, candidate-only software transaction model.
It is NOT RTL, a CDC/RDC model, an AXI/WSTRB implementation, a public register
ABI, a driver, a board result, a physical calibration authority, or acceptance
evidence.  It never grants hardware authority: hardware_enable_eligible and
movement_authorized are always False, including for explicitly named software
fixtures.  There is no default real domain.  A alone owns the final ABI and the
physical board.

The reviewed B07 layout, access classes, reset values and command-priority
rules are preserved.  The API details in REGISTER_TRANSACTION_REFERENCE.md are
B fixture proposals pending the complete ABI freeze; they create no authority.
'''

from collections import namedtuple
from collections.abc import Mapping
import uuid

TASK_ID = 'DEEPEYE-IMPLEMENTATION-20261014'
TASK_VERSION = 1
WORK_ID = 'B-REGISTER-TRANSACTION-20261019-10-v1'
OPERATION_ID = 'B-DEEPEYE-REGISTER-TRANSACTION-20261019-10'
CONTRACT_ID = 'DEEPEYE-HUMAN-LOCK-20261014'
CONTRACT_REVISION = 1
REQUIREMENTS_SHA256 = (
    'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
)
LOCK_COMMIT = 'f5989cd5defce561f9ba98e6b18fc2682945f0a2'
DESIGN_COMMIT = '1011259415a0916054eb580687612580bc1e5f09'
BASE_COMMIT = '433db2a82854a669778eb8c3cd35c309623a087e'
OWNER_DECISION_SHA256 = (
    '5cb049b28da33eea74e8a30365962d731b3f2d198065086daab1998ff747e116'
)

UINT8_MAX = 0xff
UINT16_MAX = 0xffff
UINT32_MAX = 0xffffffff
UINT64_MAX = 0xffffffffffffffff

ABI_VERSION = 3
STATUS_MASK = 0x00ff07ff
CONFIG_EPOCH_MAX = 255
PAIR_CAPACITY = 64
REQUEST_TYPE_MOTION = 0x0e

SOFTWARE_FIXTURE = True
HARDWARE_ENABLE_ELIGIBLE = False
MOVEMENT_AUTHORIZED = False

_OFFSETS = (
    0x00, 0x04, 0x08, 0x0c, 0x10, 0x14, 0x18, 0x1c, 0x20, 0x24,
    0x28, 0x2c, 0x30, 0x34, 0x38, 0x3c, 0x40, 0x44, 0x48, 0x4c,
    0x50, 0x54, 0x58, 0x5c, 0x60, 0x64, 0x68, 0x6c, 0x70,
)
_SNAPSHOT_OFFSETS = (
    0x30, 0x34, 0x38, 0x3c, 0x40, 0x44, 0x48, 0x4c, 0x50, 0x54,
    0x58, 0x5c, 0x60, 0x64, 0x68, 0x6c, 0x70,
)
_WRITABLE_OFFSETS = frozenset((0x08, 0x10, 0x14, 0x18, 0x1c, 0x20))
_SHADOW_OFFSETS = (0x10, 0x18, 0x1c, 0x20)
_DOMAIN_KEYS = frozenset((
    'fixture_id', 'identity', 'rate_codes', 'sensor_profiles',
    'motion_profiles', 'apply_blocks', 'queue_capacity', 'clock_id',
))
_CONTEXT_KEYS = frozenset((
    'session', 'boot_digest', 'config_epoch', 'control_epoch', 'request_seq',
))
_VALUE_KEYS = frozenset((
    'yaw_q', 'pitch_q', 'speed_code', 'wire_capture_seq', 'sample_tick',
    'yaw_period', 'pitch_period', 'speed_period', 'quality', 'gain_code',
    'ratio_q8_8', 'ratio_valid', 'motion_profile', 'last_observed_sequence',
))


class RegisterTransactionError(ValueError):
    '''Rejected command or invalid input for the offline model.'''

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class CaptureTicket:
    '''Opaque one-shot ticket issued by one model instance.'''

    __slots__ = ('_owner', '_token')

    def __init__(self, owner, token):
        self._owner = owner
        self._token = token

    def __repr__(self):
        return '<CaptureTicket opaque>'


_Context = namedtuple(
    '_Context', 'session boot_digest config_epoch control_epoch request_seq'
)
_ConfigPayload = namedtuple(
    '_ConfigPayload',
    'threshold apply_block rate_code error_bound sensor_profile',
)
_CaptureValues = namedtuple(
    '_CaptureValues',
    'yaw_q pitch_q speed_code wire_capture_seq sample_tick yaw_period '
    'pitch_period speed_period quality gain_code ratio_q8_8 ratio_valid '
    'motion_profile last_observed_sequence',
)


def _fail(code, message):
    raise RegisterTransactionError(code, message)


def _int(value, name, low, high, code='argument'):
    if type(value) is not int:
        _fail(code, '%s must be an integer, not %s'
              % (name, type(value).__name__))
    if value < low or value > high:
        _fail(code, '%s is outside [%d, %d]' % (name, low, high))
    return value


def _bool(value, name, code='argument'):
    if type(value) is not bool:
        _fail(code, '%s must be a bool, not %s'
              % (name, type(value).__name__))
    return value


def _text(value, name, code='argument'):
    if type(value) is not str or not value:
        _fail(code, '%s must be a nonempty string' % name)
    return value


def _u8_list(value, name, code='domain'):
    if type(value) not in (list, tuple):
        _fail(code, '%s must be a list or tuple of u8 values' % name)
    if not value:
        _fail(code, '%s must not be empty' % name)
    result = []
    seen = set()
    for index, item in enumerate(value):
        item = _int(item, '%s[%d]' % (name, index), 0, UINT8_MAX, code)
        if item in seen:
            _fail(code, '%s contains duplicate value %d' % (name, item))
        seen.add(item)
        result.append(item)
    return tuple(result)


def _exact_mapping(value, name, expected, code='argument'):
    if not isinstance(value, Mapping):
        _fail(code, '%s must be a mapping' % name)
    keys = set(value.keys())
    missing = expected - keys
    unknown = keys - expected
    if missing:
        _fail(code, '%s is missing fields: %s'
              % (name, ', '.join(sorted(str(key) for key in missing))))
    if unknown:
        _fail(code, '%s has unknown fields: %s'
              % (name, ', '.join(sorted(str(key) for key in unknown))))
    return value


def _validate_domain(domain):
    if domain is None:
        return None
    mapping = _exact_mapping(domain, 'domain', _DOMAIN_KEYS, 'domain')
    return {
        'fixture_id': _text(mapping['fixture_id'], 'domain.fixture_id',
                            'domain'),
        'identity': _int(mapping['identity'], 'domain.identity', 0,
                         UINT32_MAX, 'domain'),
        'rate_codes': _u8_list(mapping['rate_codes'], 'domain.rate_codes'),
        'sensor_profiles': _u8_list(mapping['sensor_profiles'],
                                    'domain.sensor_profiles'),
        'motion_profiles': _u8_list(mapping['motion_profiles'],
                                    'domain.motion_profiles'),
        'apply_blocks': _u8_list(mapping['apply_blocks'],
                                 'domain.apply_blocks'),
        'queue_capacity': _int(mapping['queue_capacity'],
                               'domain.queue_capacity', 0, UINT16_MAX,
                               'domain'),
        'clock_id': _text(mapping['clock_id'], 'domain.clock_id', 'domain'),
    }


def _validate_context(context):
    mapping = _exact_mapping(context, 'context', _CONTEXT_KEYS, 'context')
    session = _int(mapping['session'], 'context.session', 0, UINT32_MAX,
                   'context')
    boot_digest = mapping['boot_digest']
    if type(boot_digest) is not str or len(boot_digest) != 64:
        _fail('context', 'context.boot_digest must be 64 lowercase hex chars')
    if any(char not in '0123456789abcdef' for char in boot_digest):
        _fail('context', 'context.boot_digest must be lowercase hex only')
    config_epoch = _int(mapping['config_epoch'], 'context.config_epoch', 0,
                        CONFIG_EPOCH_MAX, 'context')
    control_epoch = _int(mapping['control_epoch'], 'context.control_epoch', 0,
                         UINT8_MAX, 'context')
    request_seq = _int(mapping['request_seq'], 'context.request_seq', 0,
                       UINT16_MAX, 'context')
    return _Context(session, boot_digest, config_epoch, control_epoch,
                    request_seq)


def _validate_values(values, domain):
    mapping = _exact_mapping(values, 'values', _VALUE_KEYS, 'capture')
    yaw_q = _int(mapping['yaw_q'], 'values.yaw_q', -15000, 15000, 'capture')
    pitch_q = _int(mapping['pitch_q'], 'values.pitch_q', -15000, 15000,
                   'capture')
    speed_code = _int(mapping['speed_code'], 'values.speed_code', 0, 20,
                      'capture')
    wire_capture_seq = _int(mapping['wire_capture_seq'],
                            'values.wire_capture_seq', 0, UINT16_MAX,
                            'capture')
    sample_tick = _int(mapping['sample_tick'], 'values.sample_tick', 0,
                       UINT64_MAX, 'capture')
    yaw_period = _int(mapping['yaw_period'], 'values.yaw_period', 0,
                      UINT64_MAX, 'capture')
    pitch_period = _int(mapping['pitch_period'], 'values.pitch_period', 0,
                        UINT32_MAX, 'capture')
    speed_period = _int(mapping['speed_period'], 'values.speed_period', 0,
                        UINT32_MAX, 'capture')
    quality = _int(mapping['quality'], 'values.quality', 0, 0x0f, 'capture')
    gain_code = _int(mapping['gain_code'], 'values.gain_code', 0, UINT8_MAX,
                     'capture')
    if gain_code not in (0, 1, 2, 4):
        _fail('capture', 'values.gain_code must be one of 0, 1, 2, 4')
    ratio_q8_8 = _int(mapping['ratio_q8_8'], 'values.ratio_q8_8', 0,
                      UINT16_MAX, 'capture')
    ratio_valid = _bool(mapping['ratio_valid'], 'values.ratio_valid',
                        'capture')
    motion_profile = _int(mapping['motion_profile'],
                          'values.motion_profile', 0, UINT8_MAX, 'capture')
    last_observed_sequence = _int(mapping['last_observed_sequence'],
                                  'values.last_observed_sequence', 0,
                                  UINT16_MAX, 'capture')
    if domain is None:
        _fail('domain', 'a fixture domain is required for motion_profile')
    if motion_profile not in domain['motion_profiles']:
        _fail('domain', 'values.motion_profile is not in the fixture domain')
    if quality & 0x01 and yaw_period == 0:
        _fail('capture', 'quality yaw_valid requires a positive yaw period')
    if quality & 0x02 and pitch_period == 0:
        _fail('capture',
              'quality pitch_valid requires a positive pitch period')
    if quality & 0x04 and speed_period == 0:
        _fail('capture',
              'quality speed_valid requires a positive speed period')
    if quality & 0x08 and not (yaw_period > 0 and pitch_period > 0 and
                               speed_period > 0):
        _fail('capture',
              'quality all_periods_valid requires all three periods positive')
    return _CaptureValues(
        yaw_q, pitch_q, speed_code, wire_capture_seq, sample_tick,
        yaw_period, pitch_period, speed_period, quality, gain_code,
        ratio_q8_8, ratio_valid, motion_profile, last_observed_sequence,
    )


def _byte_mask(wstrb):
    mask = 0
    for index in range(4):
        if wstrb & (1 << index):
            mask |= 0xff << (8 * index)
    return mask


def _sign32(word):
    return word - 0x100000000 if word & 0x80000000 else word


def _context_dict(context):
    if context is None:
        return None
    return {
        'session': context.session,
        'boot_digest': context.boot_digest,
        'config_epoch': context.config_epoch,
        'control_epoch': context.control_epoch,
        'request_seq': context.request_seq,
    }


def _payload_dict(payload):
    if payload is None:
        return None
    return {
        'threshold': payload.threshold,
        'apply_block': payload.apply_block,
        'rate_code': payload.rate_code,
        'error_bound': payload.error_bound,
        'sensor_profile': payload.sensor_profile,
    }


def _request_dict(record):
    if record is None:
        return None
    return {
        'seq': record['seq'],
        'payload': _payload_dict(record['payload']),
        'context': _context_dict(record['context']),
        'generation': record['generation'],
        'status': record['status'],
    }


def _domain_dict(domain):
    if domain is None:
        return None
    return {
        'fixture_id': domain['fixture_id'],
        'identity': domain['identity'],
        'rate_codes': tuple(domain['rate_codes']),
        'sensor_profiles': tuple(domain['sensor_profiles']),
        'motion_profiles': tuple(domain['motion_profiles']),
        'apply_blocks': tuple(domain['apply_blocks']),
        'queue_capacity': domain['queue_capacity'],
        'clock_id': domain['clock_id'],
    }


class RegisterTransactionModel:
    '''Deterministic offline B07 register transaction fixture.'''

    def __init__(self, domain=None):
        self._domain = _validate_domain(domain)
        self._generation = 0
        self._context = None
        self._last_pair = None
        self._used_pairs = set()
        self._pair_state = {}
        self._shadow = {offset: 0 for offset in _SHADOW_OFFSETS}
        self._shadow_initialized = {
            offset: False for offset in _SHADOW_OFFSETS
        }
        self._active_payload = None
        self._pending = None
        self._stopped = True
        self._enabled = False
        self._fault_latched = False
        self._fault_flags = 0
        self._enable_gate = False
        self._recovery_gate = False
        self._cdc_online = False
        self._cdc_busy = False
        self._queue_configured = False
        self._queue_used = 0
        self._queue_capacity = 0
        self._overflow_events = 0
        self._merged_events = 0
        self._bank = {offset: 0 for offset in _SNAPSHOT_OFFSETS}
        self._publication = None
        self._publication_valid = False
        self._snapshot_latched = False
        self._latch = None
        self._latch_coherent = False
        self._gain_ratio_valid = False
        self._tickets = {}
        self._model_nonce = uuid.uuid4().hex

    @property
    def hardware_enable_eligible(self):
        return False

    @property
    def movement_authorized(self):
        return False

    def _pair(self, context):
        return (context.session, context.boot_digest)

    def _current_state(self):
        if self._context is None:
            return None
        return self._pair_state[self._pair(self._context)]

    def _advance_generation(self):
        self._generation += 1
        return self._generation

    def _revoke_snapshot(self, advance):
        self._publication = None
        self._publication_valid = False
        self._latch = None
        self._latch_coherent = False
        self._gain_ratio_valid = False
        self._tickets.clear()
        if advance:
            self._advance_generation()

    def _discard_pending_config(self):
        if self._pending is not None:
            self._pending['status'] = 'revoked'
            self._pending = None

    def _revoke_config_history(self):
        if self._context is not None:
            state = self._pair_state[self._pair(self._context)]
            record = state['last_request']
            if record is not None:
                record['status'] = 'revoked'
        self._discard_pending_config()

    def _config_payload_from_shadow(self):
        word = self._shadow[0x10]
        return _ConfigPayload(
            word & 0xffff,
            (word >> 16) & 0xff,
            self._shadow[0x18] & 0xff,
            self._shadow[0x1c] & 0xff,
            self._shadow[0x20] & 0xff,
        )

    def _validate_payload(self, payload):
        if self._domain is None:
            _fail('domain', 'a fixture domain is required for CONFIG')
        if payload.apply_block not in self._domain['apply_blocks']:
            _fail('domain', 'apply_block is not in the fixture domain')
        if payload.rate_code not in self._domain['rate_codes']:
            _fail('domain', 'rate_code is not in the fixture domain')
        if payload.sensor_profile not in self._domain['sensor_profiles']:
            _fail('domain', 'sensor_profile is not in the fixture domain')
        if payload.error_bound not in (0, 1, 2, 4, 8):
            _fail('shadow', 'error_bound must be one of 0, 1, 2, 4, 8')

    def _config_dirty(self):
        staged = self._config_payload_from_shadow()
        if self._active_payload is None:
            return any(self._shadow_initialized.values())
        return staged != self._active_payload

    def _status_word(self):
        value = 0
        if self._stopped:
            value |= 1 << 0
        if self._fault_latched:
            value |= 1 << 1
        if self._snapshot_latched:
            value |= 1 << 2
        if self._latch_coherent:
            value |= 1 << 3
        if self._publication_valid or self._latch_coherent:
            value |= 1 << 4
        if self._cdc_busy:
            value |= 1 << 5
        if self._cdc_online:
            value |= 1 << 6
        if self._config_dirty():
            value |= 1 << 7
        if self._pending is not None:
            value |= 1 << 8
        if self._gain_ratio_valid:
            value |= 1 << 9
        if self._enabled:
            value |= 1 << 10
        value |= (self._fault_flags & 0xff) << 16
        return value & STATUS_MASK

    def _validate_address(self, addr):
        if type(addr) is not int:
            _fail('address', 'address must be an integer')
        if addr < 0:
            _fail('address', 'negative address')
        if addr > _OFFSETS[-1]:
            _fail('address', 'oversized address')
        if addr % 4:
            _fail('address', 'unaligned address')
        if addr not in _OFFSETS:
            _fail('address', 'unknown address')
        return addr

    def _context_matches_request(self, record):
        current = self._context
        original = record['context']
        if current is None:
            return False
        if current.session != original.session:
            return False
        if current.boot_digest != original.boot_digest:
            return False
        if current.control_epoch != original.control_epoch:
            return False
        if current.request_seq != original.request_seq:
            return False
        if current.config_epoch == original.config_epoch:
            return True
        return (record['status'] == 'completed' and
                current.config_epoch == original.config_epoch + 1)

    def write(self, addr, data, wstrb=15):
        addr = self._validate_address(addr)
        if addr == 0x2c:
            _fail('access', '0x2c is NO_ACCESS even with WSTRB zero')
        if addr not in _WRITABLE_OFFSETS:
            _fail('access', 'write to a read-only register')
        data = _int(data, 'data', 0, UINT32_MAX)
        wstrb = _int(wstrb, 'wstrb', 0, 0x0f)
        if wstrb == 0:
            return None
        masked = data & _byte_mask(wstrb)
        if addr == 0x08:
            return self._write_control(masked, wstrb)
        if addr == 0x14:
            return self._write_apply(data, wstrb)
        return self._write_shadow(addr, data, wstrb)

    def _write_control(self, masked, wstrb):
        reserved = masked & 0xffffffe0
        if (wstrb & 0x01) and (masked & 0x01):
            self._stopped = True
            self._enabled = False
            self._advance_generation()
            self._revoke_snapshot(False)
            self._revoke_config_history()
            if reserved:
                _fail('reserved',
                      'reserved control bits strobed after STOP revocation')
            return None
        if reserved:
            _fail('reserved', 'reserved control bits strobed')
        command = masked & 0x1f
        if command == 0:
            return None
        if wstrb != 0x0f:
            _fail('command', 'non-STOP command requires full-word strobe')
        if command not in (0x02, 0x04, 0x08, 0x10):
            _fail('command', 'exactly one of CLEAR_FAULT, ENABLE, LATCH, '
                             'RELEASE is required')
        if command == 0x02:
            self._clear_fault()
        elif command == 0x04:
            self._enable()
        elif command == 0x08:
            self._latch_snapshot()
        else:
            self._release()
        return None

    def _clear_fault(self):
        if not self._stopped or self._enabled:
            _fail('state', 'CLEAR_FAULT requires stopped/disabled state')
        if not self._recovery_gate:
            _fail('state', 'CLEAR_FAULT requires the recovery fixture gate')
        self._fault_latched = False
        self._fault_flags = 0

    def _enable(self):
        if self._domain is None:
            _fail('domain', 'ENABLE requires a fixture domain')
        if self._context is None:
            _fail('context', 'ENABLE requires a context')
        if self._active_payload is None:
            _fail('state', 'ENABLE requires an active complete CONFIG')
        if not self._enable_gate:
            _fail('state', 'ENABLE requires the enable fixture gate')
        if not (self._cdc_online and not self._cdc_busy):
            _fail('state', 'ENABLE requires CDC online and nonbusy')
        if self._fault_latched:
            _fail('state', 'ENABLE is blocked by a latched fault')
        self._stopped = False
        self._enabled = True

    def _latch_snapshot(self):
        if self._snapshot_latched:
            self._revoke_snapshot(True)
            _fail('snapshot',
                  'conflicting LATCH revoked existing coherence and rejected')
        publication = self._publication
        if publication is None or not self._publication_valid:
            _fail('snapshot', 'LATCH requires an eligible current publication')
        if self._context is None or self._context != publication['context']:
            _fail('snapshot', 'LATCH context does not match the publication')
        if self._generation != publication['generation']:
            _fail('snapshot', 'LATCH generation does not match the publication')
        if not (self._cdc_online and not self._cdc_busy):
            _fail('snapshot', 'LATCH requires CDC online and nonbusy')
        self._latch = publication
        self._snapshot_latched = True
        self._latch_coherent = True
        self._publication = None
        self._publication_valid = False
        self._gain_ratio_valid = publication['ratio_valid']

    def _release(self):
        self._advance_generation()
        self._discard_pending_config()
        self._revoke_snapshot(False)
        self._snapshot_latched = False

    def _write_shadow(self, addr, data, wstrb):
        defined_mask = 0x00ffffff if addr == 0x10 else 0x000000ff
        mask = _byte_mask(wstrb)
        word = (self._shadow[addr] & (UINT32_MAX ^ mask)) | (data & mask)
        if word & (UINT32_MAX ^ defined_mask):
            _fail('reserved', 'reserved bits set in the merged shadow word')
        if self._domain is None and addr in (0x10, 0x18, 0x20):
            _fail('domain', 'this shadow register requires a fixture domain')
        if addr == 0x10:
            apply_block = (word >> 16) & 0xff
            if apply_block not in self._domain['apply_blocks']:
                _fail('domain', 'apply_block is not in the fixture domain')
        elif addr == 0x18:
            rate_code = word & 0xff
            if rate_code not in self._domain['rate_codes']:
                _fail('domain', 'rate_code is not in the fixture domain')
        elif addr == 0x1c:
            error_bound = word & 0xff
            if error_bound not in (0, 1, 2, 4, 8):
                _fail('shadow',
                      'error_bound must be one of 0, 1, 2, 4, 8')
        else:
            sensor_profile = word & 0xff
            if sensor_profile not in self._domain['sensor_profiles']:
                _fail('domain',
                      'sensor_profile is not in the fixture domain')
        self._shadow[addr] = word
        self._shadow_initialized[addr] = True
        return None

    def _write_apply(self, data, wstrb):
        if wstrb != 0x0f:
            _fail('strobe', 'apply_request requires full-word strobe')
        if data & 0xffff0000:
            _fail('reserved', 'apply_request high 16 bits are reserved')
        seq = data & 0xffff
        if self._domain is None:
            _fail('domain', 'CONFIG apply requires a fixture domain')
        if self._context is None:
            _fail('context', 'CONFIG apply requires a context')
        if not all(self._shadow_initialized.values()):
            _fail('shadow', 'all four shadow registers must be initialized')
        payload = self._config_payload_from_shadow()
        self._validate_payload(payload)
        if self._context.config_epoch >= CONFIG_EPOCH_MAX:
            _fail('apply', 'CONFIG apply is rejected at epoch 255')
        if self._pending is not None:
            pending = self._pending
            if (seq == pending['seq'] and payload == pending['payload'] and
                    self._context == pending['context']):
                return None
            _fail('apply', 'conflicting CONFIG request is pending')
        state = self._current_state()
        last = state['last_request']
        if last is not None:
            if (seq == last['seq'] and payload == last['payload'] and
                    self._context_matches_request(last)):
                if last['status'] in ('pending', 'completed'):
                    return None
            if seq <= last['seq']:
                _fail('apply',
                      'CONFIG request sequence must strictly increase')
        self._revoke_snapshot(True)
        record = {
            'seq': seq,
            'payload': payload,
            'context': self._context,
            'generation': self._generation,
            'status': 'pending',
        }
        state['last_request'] = record
        state['apply_seq'] = seq
        self._pending = record
        return None

    def read(self, addr):
        addr = self._validate_address(addr)
        if addr == 0x2c:
            _fail('access', '0x2c is NO_ACCESS')
        if addr in (0x08, 0x14):
            return 0
        if addr == 0x00:
            if self._domain is None:
                _fail('domain', 'identity is unknown without a fixture domain')
            return self._domain['identity']
        if addr == 0x04:
            return ABI_VERSION
        if addr == 0x0c:
            return self._status_word()
        if addr in _SHADOW_OFFSETS:
            return self._shadow[addr]
        if addr == 0x24:
            if not self._queue_configured:
                return 0
            return (self._queue_used & UINT16_MAX) | (
                (self._queue_capacity & UINT16_MAX) << 16)
        if addr == 0x28:
            return (self._overflow_events & UINT16_MAX) | (
                (self._merged_events & UINT16_MAX) << 16)
        return self._bank[addr]

    def reset(self):
        self._advance_generation()
        self._revoke_config_history()
        self._context = None
        self._active_payload = None
        self._shadow = {offset: 0 for offset in _SHADOW_OFFSETS}
        self._shadow_initialized = {
            offset: False for offset in _SHADOW_OFFSETS
        }
        self._pending = None
        self._stopped = True
        self._enabled = False
        self._fault_latched = False
        self._fault_flags = 0
        self._enable_gate = False
        self._recovery_gate = False
        self._cdc_online = False
        self._cdc_busy = False
        self._queue_configured = False
        self._queue_used = 0
        self._queue_capacity = 0
        self._overflow_events = 0
        self._merged_events = 0
        self._bank = {offset: 0 for offset in _SNAPSHOT_OFFSETS}
        self._publication = None
        self._publication_valid = False
        self._snapshot_latched = False
        self._latch = None
        self._latch_coherent = False
        self._gain_ratio_valid = False
        self._tickets.clear()
        return None

    def set_context(self, context):
        new_context = _validate_context(context)
        if self._context == new_context:
            return None
        pair = (new_context.session, new_context.boot_digest)
        if self._context is not None:
            current_pair = self._pair(self._context)
            if pair == current_pair:
                state = self._pair_state[pair]
                self._check_context_progress(new_context, state)
            elif pair in self._used_pairs:
                _fail('context',
                      'a previously used session/BOOT pair cannot be reused')
            elif len(self._used_pairs) >= PAIR_CAPACITY:
                _fail('context',
                      'session/BOOT identity capacity is exhausted')
        elif self._last_pair is not None and pair == self._last_pair:
            state = self._pair_state[pair]
            self._check_context_progress(new_context, state)
        elif pair in self._used_pairs:
            _fail('context',
                  'a previously used session/BOOT pair cannot be reused')
        elif len(self._used_pairs) >= PAIR_CAPACITY:
            _fail('context', 'session/BOOT identity capacity is exhausted')
        previous = self._context
        clear_configuration = (previous is None or
                               self._pair(previous) != pair or
                               previous.config_epoch != new_context.config_epoch)
        self._revoke_config_history()
        self._revoke_snapshot(True)
        self._stopped = True
        self._enabled = False
        self._enable_gate = False
        self._recovery_gate = False
        if clear_configuration:
            self._active_payload = None
            self._shadow = {offset: 0 for offset in _SHADOW_OFFSETS}
            self._shadow_initialized = {offset: False for offset in _SHADOW_OFFSETS}
        self._context = new_context
        self._last_pair = pair
        state = self._pair_state.get(pair)
        if state is None:
            state = {
                'config_epoch': new_context.config_epoch,
                'control_epoch': new_context.control_epoch,
                'context_request_seq': new_context.request_seq,
                'apply_seq': -1,
                'batch_seq': -1,
                'wire_seq': -1,
                'sample_tick': None,
                'last_request': None,
            }
            self._pair_state[pair] = state
            self._used_pairs.add(pair)
        else:
            old_control = state['control_epoch']
            state['config_epoch'] = new_context.config_epoch
            if new_context.control_epoch > old_control:
                state['context_request_seq'] = new_context.request_seq
            else:
                state['context_request_seq'] = max(
                    state['context_request_seq'], new_context.request_seq)
            state['control_epoch'] = new_context.control_epoch
        return None

    def _check_context_progress(self, context, state):
        if context.config_epoch < state['config_epoch']:
            _fail('context', 'config_epoch must not decrease within a pair')
        if context.control_epoch < state['control_epoch']:
            _fail('context', 'control_epoch must not decrease within a pair')
        if (context.control_epoch == state['control_epoch'] and
                context.request_seq < state['context_request_seq']):
            _fail('context',
                  'request_seq must not decrease without a control epoch '
                  'increase')

    def set_fixture_gates(self, enable, recovery):
        enable = _bool(enable, 'enable')
        recovery = _bool(recovery, 'recovery')
        if self._enable_gate and not enable:
            self._stopped = True
            self._enabled = False
            self._revoke_config_history()
            self._revoke_snapshot(True)
        self._enable_gate = enable
        self._recovery_gate = recovery
        return None

    def set_cdc(self, online, busy):
        online = _bool(online, 'online')
        busy = _bool(busy, 'busy')
        new_eligible = online and not busy
        if online == self._cdc_online and busy == self._cdc_busy:
            return None
        self._cdc_online = online
        self._cdc_busy = busy
        if not new_eligible:
            self._stopped = True
            self._enabled = False
            self._enable_gate = False
            self._revoke_config_history()
            self._revoke_snapshot(True)
        return None

    def set_queue(self, used, overflow_increment=0, merged_increment=0):
        if self._domain is None:
            _fail('domain', 'the queue fixture requires a fixture domain')
        used = _int(used, 'used', 0, UINT16_MAX)
        overflow_increment = _int(overflow_increment,
                                  'overflow_increment', 0, UINT16_MAX)
        merged_increment = _int(merged_increment,
                                'merged_increment', 0, UINT16_MAX)
        capacity = self._domain['queue_capacity']
        if used > capacity:
            _fail('queue', 'used entries exceed the fixture queue capacity')
        self._queue_configured = True
        self._queue_capacity = capacity
        self._queue_used = used
        self._overflow_events = min(
            UINT16_MAX, self._overflow_events + overflow_increment)
        self._merged_events = min(
            UINT16_MAX, self._merged_events + merged_increment)
        return None

    def raise_fault(self, flags):
        flags = _int(flags, 'flags', 0, UINT8_MAX)
        self._fault_latched = True
        self._fault_flags = flags
        self._stopped = True
        self._enabled = False
        self._revoke_config_history()
        self._revoke_snapshot(True)
        return None

    def block_boundary(self, block):
        block = _int(block, 'block', 0, UINT8_MAX)
        if self._pending is None:
            return None
        pending = self._pending
        if pending['payload'].apply_block != block:
            return None
        if (self._context is None or
                self._context != pending['context'] or
                self._generation != pending['generation']):
            self._discard_pending_config()
            _fail('apply',
                  'stale pending CONFIG cannot publish at a block boundary')
        if self._context.config_epoch >= CONFIG_EPOCH_MAX:
            self._discard_pending_config()
            _fail('apply',
                  'CONFIG epoch 255 cannot be incremented at a boundary')
        new_epoch = self._context.config_epoch + 1
        self._context = self._context._replace(config_epoch=new_epoch)
        state = self._pair_state[self._pair(self._context)]
        state['config_epoch'] = new_epoch
        self._active_payload = pending['payload']
        pending['status'] = 'completed'
        self._pending = None
        self._revoke_snapshot(True)
        return None

    def begin_capture(self, batch_seq):
        batch_seq = _int(batch_seq, 'batch_seq', 0, UINT32_MAX)
        if self._domain is None:
            _fail('domain', 'capture requires a fixture domain')
        if self._context is None:
            _fail('context', 'capture requires a context')
        if self._active_payload is None:
            _fail('state', 'capture requires an active complete CONFIG')
        if not (self._cdc_online and not self._cdc_busy):
            _fail('state', 'capture requires CDC online and nonbusy')
        state = self._current_state()
        if batch_seq <= state['batch_seq']:
            _fail('capture',
                  'local batch sequence must strictly increase within a pair')
        self._discard_pending_config()
        self._revoke_snapshot(True)
        state['batch_seq'] = batch_seq
        token = uuid.uuid4().hex
        self._tickets[token] = {
            'context': self._context,
            'generation': self._generation,
            'batch_seq': batch_seq,
        }
        return CaptureTicket(self._model_nonce, token)

    def complete_capture(self, ticket, values):
        if type(ticket) is not CaptureTicket:
            _fail('ticket', 'fabricated or foreign ticket type rejected')
        if ticket._owner != self._model_nonce:
            _fail('ticket', 'ticket belongs to a different model instance')
        record = self._tickets.pop(ticket._token, None)
        if record is None:
            _fail('ticket', 'ticket is late, duplicate, or already consumed')
        if self._context is None or self._context != record['context']:
            _fail('ticket', 'ticket context is no longer current')
        if self._generation != record['generation']:
            _fail('ticket', 'ticket generation is no longer current')
        state = self._pair_state[self._pair(self._context)]
        if state['batch_seq'] != record['batch_seq']:
            _fail('ticket', 'ticket batch is no longer current')
        validated = _validate_values(values, self._domain)
        # Mapping access may execute caller code. Revalidate the issued ticket
        # after every such access, before publishing any fields or high-water marks.
        if (self._context != record['context'] or
                self._generation != record['generation'] or
                self._current_state() is not state or
                state['batch_seq'] != record['batch_seq'] or
                not self._cdc_online or self._cdc_busy):
            _fail('ticket', 'capture revoked during input extraction')
        if validated.wire_capture_seq <= state['wire_seq']:
            _fail('capture',
                  'wire capture sequence must strictly increase within a pair')
        if (state['sample_tick'] is not None and
                validated.sample_tick < state['sample_tick']):
            _fail('capture',
                  'sample tick must not decrease within the same clock/session')
        bank = {
            0x30: validated.yaw_q & UINT32_MAX,
            0x34: validated.speed_code,
            0x38: (self._context.request_seq
                   | (self._context.control_epoch << 16)
                   | (REQUEST_TYPE_MOTION << 24)),
            0x3c: self._context.session,
            0x40: validated.sample_tick & UINT32_MAX,
            0x44: (validated.sample_tick >> 32) & UINT32_MAX,
            0x48: validated.yaw_period & UINT32_MAX,
            0x4c: (validated.yaw_period >> 32) & UINT32_MAX,
            0x50: validated.wire_capture_seq,
            0x54: validated.quality,
            0x58: validated.gain_code,
            0x5c: validated.ratio_q8_8,
            0x60: validated.pitch_q & UINT32_MAX,
            0x64: validated.pitch_period,
            0x68: validated.speed_period,
            0x6c: validated.motion_profile,
            0x70: validated.last_observed_sequence,
        }
        publication = {
            'bank': bank,
            'context': self._context,
            'generation': self._generation,
            'batch_seq': record['batch_seq'],
            'ratio_valid': validated.ratio_valid,
        }
        self._bank = bank
        self._publication = publication
        self._publication_valid = True
        self._gain_ratio_valid = False
        state['wire_seq'] = validated.wire_capture_seq
        state['sample_tick'] = validated.sample_tick
        return None

    def _assert_latch_valid(self, latch):
        if self._latch is not latch or not self._latch_coherent:
            _fail('snapshot', 'latch coherence was revoked')
        if self._context is None or self._context != latch['context']:
            _fail('snapshot', 'snapshot context is no longer current')
        if self._generation != latch['generation']:
            _fail('snapshot', 'snapshot generation is no longer current')
        if not (self._cdc_online and not self._cdc_busy):
            _fail('snapshot', 'CDC is busy or offline')
        if self._bank.get(0x3c) != latch['bank'][0x3c]:
            _fail('snapshot', 'session word changed during snapshot read')
        if self._bank.get(0x50) != latch['bank'][0x50]:
            _fail('snapshot',
                  'capture sequence word changed during snapshot read')

    def read_snapshot(self, interleave=None):
        if interleave is not None and not callable(interleave):
            _fail('argument', 'interleave must be callable or None')
        latch = self._latch
        if latch is None or not self._latch_coherent:
            _fail('snapshot', 'no coherent latched snapshot')
        self._assert_latch_valid(latch)
        session_before = latch['bank'][0x3c]
        sequence_before = latch['bank'][0x50]
        words = {}
        for offset in _SNAPSHOT_OFFSETS:
            words[offset] = latch['bank'][offset]
            if interleave is not None:
                interleave(offset, self)
            self._assert_latch_valid(latch)
        session_after = latch['bank'][0x3c]
        sequence_after = latch['bank'][0x50]
        if (session_before, sequence_before) != (session_after,
                                                 sequence_after):
            _fail('snapshot',
                  'session/sequence changed during the snapshot read')
        if session_after != latch['context'].session:
            _fail('snapshot', 'session word does not match the bound context')
        decoded = {
            'yaw_q': _sign32(words[0x30]),
            'pitch_q': _sign32(words[0x60]),
            'speed_code': words[0x34] & 0xff,
            'request_seq': words[0x38] & 0xffff,
            'control_epoch': (words[0x38] >> 16) & 0xff,
            'request_type': (words[0x38] >> 24) & 0xff,
            'session': words[0x3c],
            'sample_tick': words[0x40] | (words[0x44] << 32),
            'yaw_period': words[0x48] | (words[0x4c] << 32),
            'wire_capture_seq': words[0x50] & 0xffff,
            'quality': words[0x54] & 0x0f,
            'gain_code': words[0x58] & 0xff,
            'ratio_q8_8': words[0x5c] & 0xffff,
            'pitch_period': words[0x64],
            'speed_period': words[0x68],
            'motion_profile': words[0x6c] & 0xff,
            'last_observed_sequence': words[0x70] & 0xffff,
        }
        return {
            'software_fixture': True,
            'hardware_enable_eligible': False,
            'movement_authorized': False,
            'generation': latch['generation'],
            'batch_seq': latch['batch_seq'],
            'context': _context_dict(latch['context']),
            'words': dict(words),
            'decoded': decoded,
            'gain_ratio_valid': bool(latch['ratio_valid']),
            'ratio_valid': bool(latch['ratio_valid']),
        }

    def inspect(self):
        context = self._context
        if context is not None:
            state = self._pair_state[self._pair(context)]
        elif self._last_pair is not None:
            state = self._pair_state.get(self._last_pair)
        else:
            state = None
        latch = self._latch
        return {
            'software_fixture': True,
            'hardware_enable_eligible': False,
            'movement_authorized': False,
            'task_id': TASK_ID,
            'task_version': TASK_VERSION,
            'work_id': WORK_ID,
            'operation_id': OPERATION_ID,
            'source': {
                'contract_id': CONTRACT_ID,
                'contract_revision': CONTRACT_REVISION,
                'requirements_sha256': REQUIREMENTS_SHA256,
                'lock_commit': LOCK_COMMIT,
                'design_commit': DESIGN_COMMIT,
                'base_commit': BASE_COMMIT,
                'owner_decision_sha256': OWNER_DECISION_SHA256,
            },
            'stage': 'offline software reference; not RTL, MMIO, AXI, board '
                     'or public-ABI acceptance',
            'domain': _domain_dict(self._domain),
            'context': _context_dict(context),
            'generation': self._generation,
            'state': {
                'stopped': self._stopped,
                'enabled': self._enabled,
                'fault_latched': self._fault_latched,
                'fault_flags': self._fault_flags,
            },
            'fixture_gates': {
                'enable': self._enable_gate,
                'recovery': self._recovery_gate,
            },
            'cdc': {
                'online': self._cdc_online,
                'busy': self._cdc_busy,
            },
            'queue': {
                'configured': self._queue_configured,
                'used': self._queue_used,
                'capacity': self._queue_capacity,
                'overflow_events': self._overflow_events,
                'merged_events': self._merged_events,
                'missing_binding': (
                    None if self._queue_configured else
                    'fixture domain and set_queue() required'
                ),
            },
            'configuration': {
                'shadow': dict(self._shadow),
                'shadow_initialized': dict(self._shadow_initialized),
                'dirty': self._config_dirty(),
                'active': _payload_dict(self._active_payload),
                'pending': _request_dict(self._pending),
                'last_request': (
                    _request_dict(state['last_request'])
                    if state is not None else None
                ),
                'config_epoch': (
                    context.config_epoch if context is not None else None
                ),
            },
            'snapshot': {
                'bank': dict(self._bank),
                'publication_valid': self._publication_valid,
                'latched': self._snapshot_latched,
                'coherent': self._latch_coherent,
                'available': bool(
                    self._publication_valid or self._latch_coherent
                ),
                'gain_ratio_valid': self._gain_ratio_valid,
                'latch': (
                    None if latch is None else {
                        'batch_seq': latch['batch_seq'],
                        'generation': latch['generation'],
                        'context': _context_dict(latch['context']),
                        'words': dict(latch['bank']),
                        'ratio_valid': bool(latch['ratio_valid']),
                    }
                ),
            },
            'capture': {
                'batch_seq_high': (
                    state['batch_seq'] if state is not None else None
                ),
                'wire_seq_high': (
                    state['wire_seq'] if state is not None else None
                ),
                'sample_tick_high': (
                    state['sample_tick'] if state is not None else None
                ),
                'pending_ticket_count': len(self._tickets),
            },
            'anti_reuse': {
                'used_pair_count': len(self._used_pairs),
                'pair_capacity': PAIR_CAPACITY,
                'last_pair': (
                    None if self._last_pair is None else {
                        'session': self._last_pair[0],
                        'boot_digest': self._last_pair[1],
                    }
                ),
            },
        }


__all__ = [
    'CaptureTicket',
    'RegisterTransactionError',
    'RegisterTransactionModel',
    'SOFTWARE_FIXTURE',
    'HARDWARE_ENABLE_ELIGIBLE',
    'MOVEMENT_AUTHORIZED',
    'ABI_VERSION',
    'STATUS_MASK',
    'TASK_ID',
    'TASK_VERSION',
    'WORK_ID',
    'OPERATION_ID',
    'CONTRACT_ID',
    'CONTRACT_REVISION',
    'REQUIREMENTS_SHA256',
    'LOCK_COMMIT',
    'DESIGN_COMMIT',
    'BASE_COMMIT',
    'OWNER_DECISION_SHA256',
]
