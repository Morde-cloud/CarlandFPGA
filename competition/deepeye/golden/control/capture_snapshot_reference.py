'''Candidate-only control capture/snapshot software reference (B side).

Task: DEEPEYE-IMPLEMENTATION-20261014/v1
Work: B-CONTROL-SNAPSHOT-FOUNDATION-20261015-01-v1
Correction: B-CONTROL-INGRESS-STOP-CORRECTION-20261016-02-v1
Contract: DEEPEYE-HUMAN-LOCK-20261014 revision 1 (H01-H15)
Requirements SHA256: c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804
Lock commit: f5989cd5defce561f9ba98e6b18fc2682945f0a2
Design commit: 1011259415a0916054eb580687612580bc1e5f09
Read-only A pin: 3b4736ff655b7fee35e79a5387f4118d1fff417c

This module is a bounded, deterministic, candidate-only software behavioral
model for three-channel atomic capture, batch binding and snapshot
publication, plus an exact 29-offset register inventory crosswalk.

It is NOT and must never be represented as: RTL, a public ABI, register bit
assignments, a CDC/RDC model, a WSTRB model, a sample-tick word order, a
capture diagnostic address map, a measured timing bound, a hardware enable
authorization, or acceptance evidence. Unknown hardware fields are left null
with explicit missing-dependency reasons; offset 0x2c reserved is no_access.

The candidate PWM tolerance of +/-2 ticks is an offline proposal only. No
state in this module permits hardware ENABLE; hardware_enable_eligible is a
constant False.

CLI (run from the worktree root):
  python -B -X utf8 competition/deepeye/golden/control/capture_snapshot_reference.py emit --inventory <path> --vectors <path>
  python -B -X utf8 competition/deepeye/golden/control/capture_snapshot_reference.py check --inventory <path> --vectors <path>
'''

import argparse
import hashlib
import json

TASK_ID = 'DEEPEYE-IMPLEMENTATION-20261014'
TASK_VERSION = 1
WORK_ID = 'B-CONTROL-SNAPSHOT-FOUNDATION-20261015-01-v1'
CORRECTION_WORK_ID = 'B-CONTROL-INGRESS-STOP-CORRECTION-20261016-02-v1'
CONTRACT_ID = 'DEEPEYE-HUMAN-LOCK-20261014'
CONTRACT_REVISION = 1
CONTRACT_COMMIT = 'f5989cd5defce561f9ba98e6b18fc2682945f0a2'
DESIGN_COMMIT = '1011259415a0916054eb580687612580bc1e5f09'
REQUIREMENTS_SHA256 = 'c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804'
REQUIREMENTS_IDS = ('H01', 'H02', 'H03', 'H04', 'H05', 'H06', 'H07', 'H08',
                    'H09', 'H10', 'H11', 'H12', 'H13', 'H14', 'H15')
A_PINNED_COMMIT = '3b4736ff655b7fee35e79a5387f4118d1fff417c'
INPUT_MANIFEST_SHA256 = 'c641f9f105d766efe8eac5aafd2e7a884d3e0bca845c8736ef13ae8a57e9c0f1'
CONTROL_PACKET_SHA256 = '926c087b5ffe219cb0cb7970f3661469db1f54be6f0e27dce160dcd18eb45f80'

SOURCE_SHA256 = {
    'inputs/a/competition/deepeye/docs/registers.csv':
        'fd3d69509776829a4e33ea4f1a6ce8b39679bd101080b33dc2ff1df38c0a4f33',
    'inputs/a/competition/deepeye/docs/interface.json':
        '0577cba5bfeda43171483abc73545e45806c44ea5546d1bcb1d581cd49b450cb',
    'inputs/a/competition/deepeye/docs/enums.json':
        'a52f3631d94d396c7da769f82a09e70d55c765b0c2651de27476e644c486573e',
    'inputs/a/competition/deepeye/docs/trace_contract_review.md':
        '0b96fd5845c49d10e38658f6fbbe9e87a0e9a0a5ef91a523028b0d2afbd7dd88',
    'inputs/a/competition/deepeye/docs/host_contract.json':
        'a291d48a8791757bf0d612bdcc08d4c5c0d2a133b57990e803063619f8a88f28',
    'inputs/a/competition/deepeye/docs/boot_profiles.json':
        '06588c82bdc803800c5891ca4aa46e184e6391ddd9045a77d99297878973bd74',
    'inputs/lock/docs/competition/deepeye-2026/immutable_scope.json':
        '6a86000e97d1571c0b7b89b9d3cf7facb11d2b6a06455eb1d53e0637676b6bc4',
    'inputs/lock/docs/competition/deepeye-2026/immutable_scope.md':
        '27c5bf0b194036cf4300dbec371b6abba42bc5fda604da0e6e06284e4c5a2ddd',
    'inputs/design/docs/competition/deepeye-2026/taskbook_final.md':
        '7f5c94f7fc73698236be954ae7818266d6dfe8b4949d1752dd045d76f4b71f18',
}

UINT8_MAX = 255
UINT16_MAX = 65535
UINT32_MAX = 4294967295

PWM_CLOCK_HZ = 100000000
PWM_PERIOD_TICKS = 2000000
ANGLE_HIGH_BASE = 10000
ANGLE_HIGH_STEP = 16
ANGLE_Q_MIN = -15000
ANGLE_Q_MAX = 15000
SPEED_HIGH_BASE = 50000
SPEED_HIGH_STEP = 1000
SPEED_CODE_MIN = 0
SPEED_CODE_MAX = 20
CAPTURE_TOLERANCE_TICKS = 2

CHANNELS = ('yaw', 'pitch', 'speed')
ANGLE_CHANNELS = ('yaw', 'pitch')

SNAPSHOT_WORD_COUNT = 8
HISTORY_LIMIT = 8
ALLOWED_RESET_SCOPES = ('fixture', 'authority', 'capture')

# Frozen enum meanings from inputs/a/.../enums.json (frozen design file).
# The model uses these codes but freezes no new public bits of its own.
PHASE_STOPPED = 0
PHASE_ACCEPTED = 1
PHASE_APPLIED = 2
PHASE_CAPTURED = 3
PHASE_REJECTED = 4
CAPTURE_QUALITY_YAW_VALID = 1 << 0
CAPTURE_QUALITY_PITCH_VALID = 1 << 1
CAPTURE_QUALITY_SPEED_VALID = 1 << 2
CAPTURE_QUALITY_ALL_PERIODS_VALID = 1 << 3
CAPTURE_QUALITY_ALL_VALID = (CAPTURE_QUALITY_YAW_VALID
                             | CAPTURE_QUALITY_PITCH_VALID
                             | CAPTURE_QUALITY_SPEED_VALID
                             | CAPTURE_QUALITY_ALL_PERIODS_VALID)
FAULT_BIT_MIN = 0
FAULT_BIT_MAX = 7

MISSING_DEPENDENCIES = (
    'R03: public control/status/config register bit numbering, access types and reset values are not frozen; no bit position is assigned here.',
    'R03: write-strobe (WSTRB) byte-enable semantics for partial-word writes are not frozen; this model refuses non-full-word strobes instead of guessing.',
    'R03: sample-tick word order and multiword read atomicity for 0x40/0x44 are not frozen; the model keeps an explicit candidate-local word view only.',
    'R03: capture diagnostic address map (capture_period0/1, capture_sequence, capture_quality and per-channel word mapping) is not frozen; no public mapping is claimed.',
    'CDC/RDC: physical reset/handshake and first-snapshot implementation, and any clock-domain crossing, are not modeled and not claimed.',
    'A: matched HWH/bit artifact and real per-register reset values are required before any register-value semantics claim.',
    'R03/G05/HIL: calibrated physical PWM timing and measured IO capture bounds are required before any tolerance or ENABLE claim.',
)

CANDIDATE_RULES = (
    'Batch key is exactly (session, control_epoch, request_seq, batch_seq); yaw, pitch and speed evidence must share one identical key before publication.',
    'Old evidence is never merged with a newer batch; a newer batch_seq starts a fresh pending batch and the older partial batch can never publish.',
    'Identical duplicate evidence for one key is idempotent; conflicting duplicate evidence permanently invalidates captured eligibility for that batch.',
    'A missing or invalid channel revokes captured eligibility; the immutable historical snapshot object itself is never mutated.',
    'Reset on the abstract fixture/authority/capture side invalidates pending and visible captured eligibility and requires a new strictly newer session before reuse.',
    'STOP dominates apply; clear_fault and enable are separate stopped-state transitions; no transition enables hardware.',
    'Candidate sequences (session, epoch, request_seq, batch_seq) are monotonic and non-wrapping with bounded pending state; wrap/unwrap requires a new session.',
)


class ControlCandidateError(Exception):
    '''Base class for candidate control-model errors.'''


class ValidationError(ControlCandidateError):
    '''Typed/range validation failure; bools are never accepted as ints.'''


class SessionStateError(ControlCandidateError):
    '''No active capture session exists in this model state.'''


class ForeignEvidenceError(ControlCandidateError):
    '''Evidence does not belong to the active session/epoch/request.'''


class SequenceViolationError(ControlCandidateError):
    '''Replay, regression or wrap of a candidate monotonic sequence.'''


class BatchConflictError(ControlCandidateError):
    '''Conflicting duplicate evidence for one batch key.'''


class PublishNotReadyError(ControlCandidateError):
    '''Snapshot publication refused: missing, invalid or poisoned batch.'''


class StopDominanceError(ControlCandidateError):
    '''Apply refused because STOP or a fault is latched.'''


class FaultStateError(ControlCandidateError):
    '''Enable refused while a fault is latched.'''


class ReservedRegisterAccessError(ControlCandidateError):
    '''0x2c reserved register is no_access for reads and writes.'''


def _require_int(name, value, lo=None, hi=None):
    '''Strict integer validation; bool is rejected as an int.'''
    if type(value) is not int:
        raise ValidationError(name + ' must be a plain int (bool rejected), got ' + repr(value))
    if lo is not None and value < lo:
        raise ValidationError(name + ' below minimum ' + str(lo) + ': ' + repr(value))
    if hi is not None and value > hi:
        raise ValidationError(name + ' above maximum ' + str(hi) + ': ' + repr(value))
    return value


def _require_channel(channel):
    if type(channel) is not str or channel not in CHANNELS:
        raise ValidationError('channel must be one of ' + repr(CHANNELS) + ', got ' + repr(channel))
    return channel


def _freeze_set(record, **fields):
    '''Set record slots once at construction; records reject later writes.'''
    for name, value in fields.items():
        object.__setattr__(record, name, value)


def angle_high_ticks(q):
    '''Candidate PWM high ticks for an angle code q (signed int, -15000..15000).'''
    _require_int('q', q, ANGLE_Q_MIN, ANGLE_Q_MAX)
    return ANGLE_HIGH_BASE + ANGLE_HIGH_STEP * (q - ANGLE_Q_MIN)


def speed_high_ticks(code):
    '''Candidate PWM high ticks for speed code 0..20.'''
    _require_int('code', code, SPEED_CODE_MIN, SPEED_CODE_MAX)
    return SPEED_HIGH_BASE + SPEED_HIGH_STEP * (code - SPEED_CODE_MIN)


def _nearest_code(value, base_lo, step, lo, hi):
    '''Decode by nearest legal high count; ties choose the lower code.'''
    index = lo + (value - base_lo) // step
    best_rank = None
    best = None
    for code in (index, index + 1):
        clamped = min(max(code, lo), hi)
        expected = base_lo + step * (clamped - lo)
        delta = value - expected
        rank = (abs(delta), clamped)
        if best_rank is None or rank < best_rank:
            best_rank = rank
            best = (clamped, expected, delta)
    return best


def decode_angle_count(high_ticks):
    '''Return (q, expected_ticks, delta_ticks) nearest-legal decode candidate.'''
    _require_int('high_ticks', high_ticks, 0, UINT32_MAX)
    return _nearest_code(high_ticks, ANGLE_HIGH_BASE, ANGLE_HIGH_STEP,
                         ANGLE_Q_MIN, ANGLE_Q_MAX)


def decode_speed_count(high_ticks):
    '''Return (speed_code, expected_ticks, delta_ticks) nearest-legal decode.'''
    _require_int('high_ticks', high_ticks, 0, UINT32_MAX)
    return _nearest_code(high_ticks, SPEED_HIGH_BASE, SPEED_HIGH_STEP,
                         SPEED_CODE_MIN, SPEED_CODE_MAX)


def period_valid(period_ticks):
    '''Candidate-only period check: |period - 2000000| <= 2 ticks.'''
    _require_int('period_ticks', period_ticks, 0, UINT32_MAX)
    return abs(period_ticks - PWM_PERIOD_TICKS) <= CAPTURE_TOLERANCE_TICKS


def _derive_ingress_fields(channel, period_ticks, high_ticks):
    '''Derive every decoded/validity field from the raw channel counts.

    Derived values (mode, decoded_code, expected_high_ticks, delta_ticks,
    within_candidate_tolerance, period_valid, valid) are never caller-authored;
    they are a pure function of (channel, period_ticks, high_ticks).
    '''
    _require_channel(channel)
    _require_int('period_ticks', period_ticks, 0, UINT32_MAX)
    _require_int('high_ticks', high_ticks, 0, UINT32_MAX)
    mode = 'angle' if channel in ANGLE_CHANNELS else 'speed'
    if mode == 'angle':
        decoded, expected, delta = decode_angle_count(high_ticks)
    else:
        decoded, expected, delta = decode_speed_count(high_ticks)
    within = abs(delta) <= CAPTURE_TOLERANCE_TICKS
    period_ok = abs(period_ticks - PWM_PERIOD_TICKS) <= CAPTURE_TOLERANCE_TICKS
    return {'decoded_code': decoded, 'delta_ticks': delta,
            'expected_high_ticks': expected, 'mode': mode,
            'period_valid': period_ok, 'valid': (within and period_ok),
            'within_candidate_tolerance': within}


def _require_derived_match(name, value, derived):
    '''Reject a caller-supplied derived field unless it is typed and derived.'''
    if isinstance(derived, bool):
        if not isinstance(value, bool):
            raise ValidationError('ChannelEvidence.' + name
                                  + ' must be a bool derived from the raw counts, got '
                                  + repr(value))
    elif isinstance(derived, str):
        if type(value) is not str or value != derived:
            raise ValidationError('ChannelEvidence.' + name
                                  + ' must be the derived string ' + repr(derived)
                                  + ', got ' + repr(value))
        return value
    elif type(value) is not int:
        raise ValidationError('ChannelEvidence.' + name
                              + ' must be a plain int derived from the raw counts, got '
                              + repr(value))
    if value != derived:
        raise ValidationError('ChannelEvidence.' + name
                              + ' must equal the value derived from the raw counts: expected '
                              + repr(derived) + ', got ' + repr(value))
    return value


def classify_high_count(channel, high_ticks, period_ticks=PWM_PERIOD_TICKS):
    '''Candidate-only classification of one channel capture count.

    Returns a machine-readable dict; accepted is true at |delta| <= 2 only
    when the period also matches the candidate bound. Candidate-only flags
    are always present and hardware_enable_eligible is always False.
    '''
    _require_channel(channel)
    mode = 'angle' if channel in ANGLE_CHANNELS else 'speed'
    if mode == 'angle':
        decoded, expected, delta = decode_angle_count(high_ticks)
    else:
        decoded, expected, delta = decode_speed_count(high_ticks)
    within = abs(delta) <= CAPTURE_TOLERANCE_TICKS
    period_ok = period_valid(period_ticks)
    return {
        'accepted': within and period_ok,
        'candidate_only': True,
        'channel': channel,
        'decoded_code': decoded,
        'delta_ticks': delta,
        'expected_high_ticks': expected,
        'hardware_enable_eligible': False,
        'mode': mode,
        'period_ticks': period_ticks,
        'period_valid': period_ok,
        'within_candidate_tolerance': within,
    }


def snapshot_word_view(snapshot):
    '''Candidate-local multiword view of one snapshot (atomic-read tests only).

    This order is a test fixture for torn-read detection; it is NOT a public
    register address map and does NOT claim the pending sample-tick word
    order or any capture diagnostic layout.
    '''
    if snapshot is None:
        return None
    key = snapshot.batch_key
    return (key.session, key.control_epoch, key.request_seq, key.batch_seq,
            snapshot.yaw_q - ANGLE_Q_MIN, snapshot.pitch_q - ANGLE_Q_MIN,
            snapshot.speed_code, snapshot.capture_quality_bits)


class BatchKey:
    '''Frozen candidate batch identity: session/epoch/request_seq/batch_seq.'''

    __slots__ = ('session', 'control_epoch', 'request_seq', 'batch_seq')

    def __init__(self, session, control_epoch, request_seq, batch_seq):
        _freeze_set(self,
                    session=_require_int('session', session, 0, UINT32_MAX),
                    control_epoch=_require_int('control_epoch', control_epoch, 0, UINT8_MAX),
                    request_seq=_require_int('request_seq', request_seq, 0, UINT16_MAX),
                    batch_seq=_require_int('batch_seq', batch_seq, 0, UINT32_MAX))

    def __setattr__(self, name, value):
        raise AttributeError('immutable BatchKey record: ' + name)

    def as_tuple(self):
        return (self.session, self.control_epoch, self.request_seq, self.batch_seq)

    def __eq__(self, other):
        if not isinstance(other, BatchKey):
            return NotImplemented
        return self.as_tuple() == other.as_tuple()

    def __hash__(self):
        return hash(self.as_tuple())

    def __repr__(self):
        return 'BatchKey' + repr(self.as_tuple())


class ChannelEvidence:
    '''Immutable validated evidence for one channel of one candidate batch.

    Derived fields (mode, decoded_code, expected_high_ticks, delta_ticks,
    within_candidate_tolerance, period_valid, valid) are never caller-authored:
    every construction path re-derives them from the raw channel, period_ticks
    and high_ticks and rejects inconsistent or wrongly-typed values. The model
    re-validates and copies a detached record at ingestion, so no caller object
    alias reaches model state.
    '''

    __slots__ = ('channel', 'batch_key', 'period_ticks', 'high_ticks', 'mode',
                 'decoded_code', 'expected_high_ticks', 'delta_ticks',
                 'within_candidate_tolerance', 'period_valid', 'valid')

    def __init__(self, channel, batch_key, period_ticks, high_ticks, mode,
                 decoded_code, expected_high_ticks, delta_ticks,
                 within_candidate_tolerance, period_valid, valid):
        _require_channel(channel)
        if type(batch_key) is not BatchKey:
            raise ValidationError('batch_key must be exactly a BatchKey, got '
                                  + repr(type(batch_key)))
        derived = _derive_ingress_fields(channel, period_ticks, high_ticks)
        if mode != derived['mode']:
            raise ValidationError('ChannelEvidence.mode must be derived from the channel: expected '
                                  + repr(derived['mode']) + ', got ' + repr(mode))
        _require_derived_match('decoded_code', decoded_code, derived['decoded_code'])
        _require_derived_match('expected_high_ticks', expected_high_ticks,
                               derived['expected_high_ticks'])
        _require_derived_match('delta_ticks', delta_ticks, derived['delta_ticks'])
        _require_derived_match('within_candidate_tolerance', within_candidate_tolerance,
                               derived['within_candidate_tolerance'])
        _require_derived_match('period_valid', period_valid, derived['period_valid'])
        _require_derived_match('valid', valid, derived['valid'])
        _freeze_set(self, channel=channel, batch_key=batch_key,
                    period_ticks=period_ticks, high_ticks=high_ticks,
                    mode=derived['mode'], decoded_code=derived['decoded_code'],
                    expected_high_ticks=derived['expected_high_ticks'],
                    delta_ticks=derived['delta_ticks'],
                    within_candidate_tolerance=derived['within_candidate_tolerance'],
                    period_valid=derived['period_valid'], valid=derived['valid'])

    def __setattr__(self, name, value):
        raise AttributeError('immutable ChannelEvidence record: ' + name)

    @classmethod
    def create(cls, channel, session, control_epoch, request_seq, batch_seq,
               period_ticks, high_ticks):
        '''Validate inputs and build one frozen evidence record.

        All numbers are strict plain ints; bool/float/str are rejected, so no
        bool-as-int or mutable caller alias can bypass validation.
        '''
        key = BatchKey(session, control_epoch, request_seq, batch_seq)
        derived = _derive_ingress_fields(channel, period_ticks, high_ticks)
        return cls(channel=channel, batch_key=key, period_ticks=period_ticks,
                   high_ticks=high_ticks, mode=derived['mode'],
                   decoded_code=derived['decoded_code'],
                   expected_high_ticks=derived['expected_high_ticks'],
                   delta_ticks=derived['delta_ticks'],
                   within_candidate_tolerance=derived['within_candidate_tolerance'],
                   period_valid=derived['period_valid'], valid=derived['valid'])

    def as_dict(self):
        return {
            'batch_key': list(self.batch_key.as_tuple()),
            'channel': self.channel,
            'decoded_code': self.decoded_code,
            'delta_ticks': self.delta_ticks,
            'expected_high_ticks': self.expected_high_ticks,
            'high_ticks': self.high_ticks,
            'mode': self.mode,
            'period_ticks': self.period_ticks,
            'period_valid': self.period_valid,
            'valid': self.valid,
            'within_candidate_tolerance': self.within_candidate_tolerance,
        }


def _detach_channel_evidence(evidence):
    '''Canonicalize a caller evidence record into a detached model-owned copy.

    The consuming boundary re-checks the exact record type, the exact batch key
    type, every raw count and every derived field; the returned record shares
    no object with the caller, so later mutation of a caller-retained record
    (including object.__setattr__ tampering) cannot rewrite model state.
    '''
    if type(evidence) is not ChannelEvidence:
        raise ValidationError('evidence must be exactly a ChannelEvidence record, got '
                              + repr(type(evidence)))
    try:
        channel = evidence.channel
        key = evidence.batch_key
        period_ticks = evidence.period_ticks
        high_ticks = evidence.high_ticks
    except AttributeError as exc:
        raise ValidationError('evidence record is incomplete: ' + repr(exc))
    if type(key) is not BatchKey:
        raise ValidationError('evidence.batch_key must be exactly a BatchKey, got '
                              + repr(type(key)))
    try:
        session = key.session
        control_epoch = key.control_epoch
        request_seq = key.request_seq
        batch_seq = key.batch_seq
    except AttributeError as exc:
        raise ValidationError('evidence batch_key is incomplete: ' + repr(exc))
    canonical = ChannelEvidence.create(channel=channel, session=session,
                                       control_epoch=control_epoch,
                                       request_seq=request_seq,
                                       batch_seq=batch_seq,
                                       period_ticks=period_ticks,
                                       high_ticks=high_ticks)
    for name in ('mode', 'decoded_code', 'expected_high_ticks', 'delta_ticks',
                 'within_candidate_tolerance', 'period_valid', 'valid'):
        try:
            value = getattr(evidence, name)
        except AttributeError as exc:
            raise ValidationError('evidence record is incomplete: ' + repr(exc))
        _require_derived_match(name, value, getattr(canonical, name))
    return canonical


class CaptureSnapshot:
    '''Immutable published capture snapshot; historical objects never mutate.

    Only detached primitives are stored; batch_key is rebuilt as a fresh
    validated key on every access, so no caller- or reader-held key object can
    alias into the historical record.
    '''

    __slots__ = ('_key_tuple', 'yaw_q', 'pitch_q', 'speed_code', 'high_yaw',
                 'high_pitch', 'high_speed', 'period_yaw', 'period_pitch',
                 'period_speed', 'capture_quality_bits', 'phase_code',
                 'hardware_enable_eligible')

    def __init__(self, batch_key, yaw_q, pitch_q, speed_code, high_yaw,
                 high_pitch, high_speed, period_yaw, period_pitch,
                 period_speed, capture_quality_bits, phase_code,
                 hardware_enable_eligible):
        if type(batch_key) is not BatchKey:
            raise ValidationError('batch_key must be exactly a BatchKey, got '
                                  + repr(type(batch_key)))
        _freeze_set(self, _key_tuple=batch_key.as_tuple(), yaw_q=yaw_q,
                    pitch_q=pitch_q, speed_code=speed_code, high_yaw=high_yaw,
                    high_pitch=high_pitch, high_speed=high_speed,
                    period_yaw=period_yaw, period_pitch=period_pitch,
                    period_speed=period_speed,
                    capture_quality_bits=capture_quality_bits,
                    phase_code=phase_code,
                    hardware_enable_eligible=hardware_enable_eligible)

    def __setattr__(self, name, value):
        raise AttributeError('immutable CaptureSnapshot record: ' + name)

    @property
    def batch_key(self):
        '''Fresh validated key rebuilt from stored primitives (detached copy).'''
        return BatchKey(*self._key_tuple)

    def decoded_for_channel(self, channel):
        _require_channel(channel)
        if channel == 'yaw':
            return self.yaw_q
        if channel == 'pitch':
            return self.pitch_q
        return self.speed_code

    def raw_for_channel(self, channel):
        _require_channel(channel)
        if channel == 'yaw':
            return (self.period_yaw, self.high_yaw)
        if channel == 'pitch':
            return (self.period_pitch, self.high_pitch)
        return (self.period_speed, self.high_speed)

    def word_view(self):
        return snapshot_word_view(self)

    def as_dict(self):
        return {
            'batch_key': list(self.batch_key.as_tuple()),
            'capture_quality_bits': self.capture_quality_bits,
            'hardware_enable_eligible': self.hardware_enable_eligible,
            'high_pitch': self.high_pitch,
            'high_speed': self.high_speed,
            'high_yaw': self.high_yaw,
            'period_pitch': self.period_pitch,
            'period_speed': self.period_speed,
            'period_yaw': self.period_yaw,
            'phase_code': self.phase_code,
            'pitch_q': self.pitch_q,
            'speed_code': self.speed_code,
            'words': list(self.word_view()),
            'yaw_q': self.yaw_q,
        }


def _copy_snapshot(snapshot):
    '''Detach a public read result from the model-owned historical record.

    Exact built-in scalar validation at ingress prevents overloaded arithmetic
    and mutable scalar subclasses. Readers receive a fresh record, so even
    object.__setattr__ on that returned record cannot change model history.
    This is an API alias boundary, not an arbitrary in-process security wall.
    '''
    if snapshot is None:
        return None
    return CaptureSnapshot(
        batch_key=snapshot.batch_key, yaw_q=snapshot.yaw_q,
        pitch_q=snapshot.pitch_q, speed_code=snapshot.speed_code,
        high_yaw=snapshot.high_yaw, high_pitch=snapshot.high_pitch,
        high_speed=snapshot.high_speed, period_yaw=snapshot.period_yaw,
        period_pitch=snapshot.period_pitch, period_speed=snapshot.period_speed,
        capture_quality_bits=snapshot.capture_quality_bits,
        phase_code=snapshot.phase_code,
        hardware_enable_eligible=snapshot.hardware_enable_eligible)


class FrozenRead:
    '''One latched multiword snapshot read transaction (candidate-local).

    The transaction latches its words once; concurrent shadow writes cannot
    mutate an already latched read. Chosen coherence semantics: coherent is
    True only while the bytes were latched from current published eligibility
    and no event has since revoked that eligibility. STOP, reset, fault, batch
    conflict, a new session, a new epoch, a new applied request and a new
    capture cycle (including invalid or delayed evidence) all revoke captured
    eligibility, so outstanding reads become explicitly INVALID: coherent
    turns False while the latched words stay unchanged as stale bytes. A newer
    publication never rewrites or restores an older latched read; a fresh
    latch taken from the new publication is coherent again while shadow
    register writes never disturb an existing latch.
    '''

    def __init__(self, model, words, batch_key, latch_mark, latched_current):
        self._model = model
        self._words = tuple(words) if words is not None else None
        self._batch_key = batch_key
        self._latch_mark = latch_mark
        self._latched_current = latched_current

    @property
    def words(self):
        return self._words

    @property
    def batch_key(self):
        return self._batch_key

    @property
    def latched_current(self):
        return self._latched_current

    @property
    def coherent(self):
        '''True only if current bytes were latched and nothing revoked them.

        The model bumps its validity mark on every event that revokes current
        published eligibility; a revocation makes all outstanding latches
        incoherent without touching their bytes.
        '''
        return (self._words is not None
                and self._latched_current
                and self._model._mark == self._latch_mark)

    def as_dict(self):
        return {
            'batch_key': list(self._batch_key.as_tuple()) if self._batch_key is not None else None,
            'coherent': self.coherent,
            'latched_current': self._latched_current,
            'words': list(self._words) if self._words is not None else None,
        }


class StateError(ControlCandidateError):
    '''Operation is not legal in the current latched model state.'''


REGISTER_ROWS = (
    (0x00, 'identification', 32, 'not_run'),
    (0x04, 'abi_version', 32, 'not_run'),
    (0x08, 'control', 32, 'bitfields_pending_A_freeze'),
    (0x0c, 'status', 32, 'bitfields_pending_A_freeze'),
    (0x10, 'shadow_configuration', 32, 'bitfields_pending_A_freeze'),
    (0x14, 'apply_request', 32, 'bitfields_pending_A_freeze'),
    (0x18, 'sample_rate', 32, 'not_run'),
    (0x1c, 'error_bound', 32, 'not_run'),
    (0x20, 'profile', 32, 'enum_pending_A_freeze'),
    (0x24, 'queue_status', 32, 'bitfields_pending_A_freeze'),
    (0x28, 'overflow_merge', 32, 'bitfields_pending_A_freeze'),
    (0x2c, 'reserved', 32, 'no_access'),
    (0x30, 'applied_yaw', 32, 'not_run'),
    (0x34, 'applied_speed', 32, 'not_run'),
    (0x38, 'applied_request', 32, 'bitfields_pending_A_freeze'),
    (0x3c, 'session', 32, 'not_run'),
    (0x40, 'sample_tick_word0', 32, 'semantics_pending_A_freeze'),
    (0x44, 'sample_tick_word1', 32, 'semantics_pending_A_freeze'),
    (0x48, 'capture_period0', 32, 'semantics_pending_A_freeze'),
    (0x4c, 'capture_period1', 32, 'semantics_pending_A_freeze'),
    (0x50, 'capture_sequence', 32, 'not_run'),
    (0x54, 'capture_quality', 32, 'bitfields_pending_A_freeze'),
    (0x58, 'gain', 32, 'not_run'),
    (0x5c, 'measured_ratio', 32, 'not_run'),
    (0x60, 'applied_pitch', 32, 'not_run'),
    (0x64, 'pitch_capture_period', 32, 'not_run'),
    (0x68, 'speed_capture_period', 32, 'not_run'),
    (0x6c, 'motion_profile_id', 32, 'enum_pending_A_freeze'),
    (0x70, 'last_observed_sequence', 32, 'not_run'),
)

REGISTER_AUTHORITY = 'matched_new_overlay_hwh_only'
RESERVED_OFFSET = 0x2c

UNKNOWN_REASON_BY_STATUS = {
    'not_run': 'value, bit and access semantics not established; status not_run; fields kept null',
    'bitfields_pending_A_freeze': 'public bit numbering, access type and reset value pending A freeze; fields kept null',
    'enum_pending_A_freeze': 'enum encoding pending A freeze; fields kept null',
    'semantics_pending_A_freeze': 'multiword / tick / diagnostic semantics pending A freeze; fields kept null',
    'no_access': 'reserved register: no read or write access; do not probe or write; fields kept null',
}


def register_row(offset):
    '''Exact pinned inventory row for one offset, or ValidationError.'''
    _require_int('offset', offset, 0, UINT32_MAX)
    for row in REGISTER_ROWS:
        if row[0] == offset:
            return row
    raise ValidationError('offset not in pinned 29-offset inventory: ' + repr(offset))


def register_entry(offset):
    '''Machine-readable inventory entry; unknown fields stay null with reason.'''
    offset, name, width, status = register_row(offset)
    no_access = (status == 'no_access')
    return {
        'access': 'no_access' if no_access else None,
        'authority': REGISTER_AUTHORITY,
        'bitfields': None,
        'implementation_status': status,
        'name': name,
        'offset': offset,
        'offset_hex': '0x' + format(offset, '02x'),
        'reset_value': None,
        'unknown_reason': UNKNOWN_REASON_BY_STATUS[status],
        'width_bits': width,
    }


class CandidateRegisterFile:
    '''Candidate-local 32-bit shadow file over exactly the 29 pinned offsets.

    This is not a bus or AXI model: no WSTRB semantics, no reset values, no
    timing, no CDC. Unwritten values are None (unknown); 0x2c reserved is
    no_access for both reads and writes. Only full-word writes are accepted
    because partial write-strobe semantics are pending A freeze.
    '''

    def __init__(self):
        self._values = dict((row[0], None) for row in REGISTER_ROWS)

    def addresses(self):
        return tuple(row[0] for row in REGISTER_ROWS)

    def names(self):
        return tuple(row[1] for row in REGISTER_ROWS)

    def read(self, offset):
        row = register_row(offset)
        if row[3] == 'no_access':
            raise ReservedRegisterAccessError('0x2c reserved register is no_access')
        return self._values[offset]

    def write(self, offset, value, write_strobes=0xF):
        row = register_row(offset)
        if row[3] == 'no_access':
            raise ReservedRegisterAccessError('0x2c reserved register is no_access')
        _require_int('value', value, 0, UINT32_MAX)
        _require_int('write_strobes', write_strobes, 0, 0xF)
        if write_strobes != 0xF:
            raise ValidationError('partial write strobes are pending A freeze; full-word writes only')
        self._values[offset] = value

    def describe(self, offset):
        return register_entry(offset)


def build_inventory_document():
    '''Emit the register candidate inventory document (machine-readable).'''
    return {
        'candidate_only': True,
        'contract': {
            'contract': CONTRACT_ID,
            'contract_commit': CONTRACT_COMMIT,
            'design_commit': DESIGN_COMMIT,
            'requirements_ids': list(REQUIREMENTS_IDS),
            'requirements_sha256': REQUIREMENTS_SHA256,
            'revision': CONTRACT_REVISION,
        },
        'control_packet_sha256': CONTROL_PACKET_SHA256,
        'crosswalk': {
            'ordering': 'exact source CSV row order preserved',
            'register_count': len(REGISTER_ROWS),
            'source': 'inputs/a/competition/deepeye/docs/registers.csv',
            'source_commit': A_PINNED_COMMIT,
            'source_sha256': SOURCE_SHA256['inputs/a/competition/deepeye/docs/registers.csv'],
        },
        'decisions': {
            'addresses_and_names': 'preserve source CSV offsets, names, widths and statuses only',
            'authority': 'A owns and finalizes the public ABI; source rows are candidate inventory, not implementation proof',
            'missing_public_bitfields': 'leave pending; never infer bit positions, access semantics, reset values, channel mapping, tick word order, CDC behavior or enum values',
            'reserved_0x2c': 'no access; never probe or write',
            'word_view': 'the capture word view is candidate-local for atomic-read tests only and is not a public address map',
        },
        'hardware_enable_eligible': False,
        'input_manifest_sha256': INPUT_MANIFEST_SHA256,
        'missing_dependencies': list(MISSING_DEPENDENCIES),
        'registers': [register_entry(row[0]) for row in REGISTER_ROWS],
        'schema': 1,
        'stages': {
            'board': 'not_run',
            'implementation': 'not_run',
            'simulation': 'not_run',
            'synthesis': 'not_run',
            'system': 'not_run',
        },
        'task': TASK_ID,
        'task_version': TASK_VERSION,
        'work_id': WORK_ID,
    }


class CaptureSnapshotModel:
    '''Bounded candidate model for three-channel atomic capture semantics.

    Deterministic software state machine only: no RTL, no CDC, no hardware
    behavior and no enable authority. Bounded state: one pending batch (at
    most three channels), one latest snapshot plus a bounded recent history,
    fixed-size counters - no unlimited tombstones.
    '''

    def __init__(self):
        self._session = None
        self._last_session_id = None
        self._control_epoch = None
        self._request_seq = None
        self._last_request_seq = None
        self._last_batch_seq = None
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published = None
        self._published_current = False
        self._published_count = 0
        self._history = []
        self._mark = 0
        self._faults = 0
        self._stopped = True
        self._enabled = False

    # -- read-only observable state -------------------------------------

    @property
    def session(self):
        return self._session

    @property
    def control_epoch(self):
        return self._control_epoch

    @property
    def request_seq(self):
        return self._request_seq

    @property
    def last_batch_seq(self):
        return self._last_batch_seq

    @property
    def pending_key(self):
        '''Detached copy of the pending batch key, or None.'''
        if self._pending_key is None:
            return None
        return BatchKey(*self._pending_key.as_tuple())

    @property
    def pending_channels(self):
        if self._pending is None:
            return ()
        return tuple(sorted(self._pending))

    @property
    def pending_poisoned(self):
        return self._pending_poisoned

    @property
    def eligibility(self):
        '''Visible captured eligibility: a published, still-current snapshot.'''
        return self._published is not None and self._published_current

    @property
    def published_current(self):
        return self._published_current

    @property
    def stopped(self):
        return self._stopped

    @property
    def enabled(self):
        return self._enabled

    @property
    def faults(self):
        return self._faults

    @property
    def needs_new_session(self):
        return self._session is None

    @property
    def hardware_enable_eligible(self):
        return False

    @property
    def history_len(self):
        return len(self._history)

    @property
    def published_count(self):
        return self._published_count

    # -- session / epoch / request transitions --------------------------

    def begin_session(self, session):
        '''Accept a genuinely newer candidate session id (non-wrapping).'''
        _require_int('session', session, 0, UINT32_MAX)
        if self._last_session_id is not None and session <= self._last_session_id:
            raise SequenceViolationError(
                'session replay/regression refused; candidate sessions must strictly '
                'increase and a reset/stop requires a new session: last='
                + str(self._last_session_id) + ' got=' + str(session))
        self._session = session
        self._last_session_id = session
        self._control_epoch = None
        self._request_seq = None
        self._last_request_seq = None
        self._last_batch_seq = None
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published_current = False
        self._stopped = True
        self._enabled = False
        self._mark += 1

    def begin_epoch(self, control_epoch):
        '''Advance the candidate control epoch by exactly one (no wrap).

        A new epoch retires the active request: late evidence for the old
        request is refused until a new apply_request, so an epoch change can
        never silently reuse the old request.
        '''
        if self._session is None:
            raise SessionStateError('no active session; begin_session first')
        _require_int('control_epoch', control_epoch, 0, UINT8_MAX)
        if self._control_epoch is not None:
            if control_epoch == self._control_epoch:
                raise SequenceViolationError('control_epoch replay refused: ' + str(control_epoch))
            if control_epoch < self._control_epoch:
                raise SequenceViolationError('control_epoch regression refused: got '
                                             + str(control_epoch) + ' after ' + str(self._control_epoch))
            if self._control_epoch == UINT8_MAX:
                raise SequenceViolationError('control_epoch wrap refused; stop and open a new session')
            if control_epoch != self._control_epoch + 1:
                raise SequenceViolationError('control_epoch must advance by exactly one: got '
                                             + str(control_epoch) + ' after ' + str(self._control_epoch))
        self._control_epoch = control_epoch
        self._request_seq = None
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published_current = False
        self._mark += 1

    def apply_request(self, request_seq):
        '''Apply one new candidate request; STOP/fault dominance is enforced.'''
        if self._session is None:
            raise SessionStateError('no active session; new handshake required')
        _require_int('request_seq', request_seq, 0, UINT16_MAX)
        if self._stopped or not self._enabled:
            raise StopDominanceError('apply refused: STOP or fault latched (no apply before enable)')
        if self._last_request_seq is not None:
            if request_seq == self._last_request_seq:
                raise SequenceViolationError('request_seq replay refused: ' + str(request_seq))
            if request_seq < self._last_request_seq:
                raise SequenceViolationError('request_seq regression refused: got '
                                             + str(request_seq) + ' after ' + str(self._last_request_seq))
            if self._last_request_seq == UINT16_MAX:
                raise SequenceViolationError('request_seq wrap refused; stop and open a new session')
        self._request_seq = request_seq
        self._last_request_seq = request_seq
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published_current = False
        self._mark += 1

    # -- evidence ingestion ---------------------------------------------

    def submit_evidence(self, evidence):
        '''Ingest one channel evidence record; returns a status string.

        The caller record is validated and canonicalized into a detached
        model-owned copy before any state check, so a caller-retained object
        (or a subclass) can never alias into or rewrite pending or published
        state. Statuses: stored, invalid_stored, duplicate_ignored.
        Conflicting duplicates raise BatchConflictError after invalidating
        eligibility.
        '''
        record = _detach_channel_evidence(evidence)
        if self._session is None:
            raise SessionStateError('no active session; new handshake required')
        key = record.batch_key
        if key.session != self._session:
            raise ForeignEvidenceError('evidence session ' + str(key.session)
                                       + ' does not match active session ' + str(self._session))
        if self._control_epoch is None or key.control_epoch != self._control_epoch:
            raise ForeignEvidenceError('evidence control_epoch ' + str(key.control_epoch)
                                       + ' does not match active epoch ' + str(self._control_epoch))
        if self._request_seq is None or key.request_seq != self._request_seq:
            raise ForeignEvidenceError('evidence request_seq ' + str(key.request_seq)
                                       + ' does not match active request ' + str(self._request_seq))
        if self._last_batch_seq is not None and key.batch_seq < self._last_batch_seq:
            raise SequenceViolationError('batch_seq regression refused: got '
                                         + str(key.batch_seq) + ' after ' + str(self._last_batch_seq))
        if self._last_batch_seq is not None and key.batch_seq == self._last_batch_seq:
            return self._submit_same_cycle(record)
        return self._start_cycle(record)

    def _start_cycle(self, record):
        '''Start a new pending cycle from a detached canonical record.

        A new cycle revokes current published eligibility, so outstanding
        frozen reads lose coherence even before the cycle publishes.
        '''
        self._pending = {}
        self._pending_key = record.batch_key
        self._pending_poisoned = False
        self._last_batch_seq = record.batch_key.batch_seq
        self._published_current = False
        self._mark += 1
        self._pending[record.channel] = record
        if not record.valid:
            self._pending_poisoned = True
            return 'invalid_stored'
        return 'stored'

    def _submit_same_cycle(self, record):
        if self._pending is not None:
            existing = self._pending.get(record.channel)
            if existing is not None:
                same_raw = (existing.period_ticks == record.period_ticks
                            and existing.high_ticks == record.high_ticks)
                if same_raw:
                    return 'duplicate_ignored'
                self._pending_poisoned = True
                self._published_current = False
                self._mark += 1
                raise BatchConflictError(
                    'conflicting duplicate evidence for channel ' + record.channel
                    + ' batch_seq ' + str(record.batch_key.batch_seq)
                    + ': ' + str((existing.period_ticks, existing.high_ticks))
                    + ' vs ' + str((record.period_ticks, record.high_ticks)))
            self._pending[record.channel] = record
            if not record.valid:
                self._pending_poisoned = True
                return 'invalid_stored'
            return 'stored'
        if self._published is not None and self._published.batch_key == record.batch_key:
            raw = self._published.raw_for_channel(record.channel)
            if raw == (record.period_ticks, record.high_ticks):
                return 'duplicate_ignored'
            self._published_current = False
            self._mark += 1
            raise BatchConflictError(
                'conflicting duplicate evidence for published batch; captured '
                'eligibility revoked for batch_seq ' + str(record.batch_key.batch_seq))
        raise SequenceViolationError(
            'batch_seq ' + str(record.batch_key.batch_seq)
            + ' repeats a discarded cycle; start a new batch sequence')

    # -- publication ------------------------------------------------------

    def publish_snapshot(self):
        '''Publish one immutable snapshot from a complete, valid pending batch.

        Refused outright while STOP is latched or software enable is absent;
        the snapshot and its batch key are rebuilt from detached model-owned
        primitives before publication.
        '''
        if self._session is None:
            raise SessionStateError('no active session; new handshake required')
        if self._stopped or not self._enabled:
            raise PublishNotReadyError(
                'publication refused: STOP latched or software enable absent')
        if self._pending is None or self._pending_poisoned:
            raise PublishNotReadyError('no publishable batch: missing, invalid or conflicted evidence')
        missing = [channel for channel in CHANNELS if channel not in self._pending]
        if missing:
            raise PublishNotReadyError('missing channels: ' + ','.join(missing))
        for channel in CHANNELS:
            if not self._pending[channel].valid:
                raise PublishNotReadyError('invalid channel evidence: ' + channel)
        snapshot = CaptureSnapshot(
            batch_key=BatchKey(*self._pending_key.as_tuple()),
            yaw_q=self._pending['yaw'].decoded_code,
            pitch_q=self._pending['pitch'].decoded_code,
            speed_code=self._pending['speed'].decoded_code,
            high_yaw=self._pending['yaw'].high_ticks,
            high_pitch=self._pending['pitch'].high_ticks,
            high_speed=self._pending['speed'].high_ticks,
            period_yaw=self._pending['yaw'].period_ticks,
            period_pitch=self._pending['pitch'].period_ticks,
            period_speed=self._pending['speed'].period_ticks,
            capture_quality_bits=CAPTURE_QUALITY_ALL_VALID,
            phase_code=PHASE_CAPTURED,
            hardware_enable_eligible=False)
        self._history.append(snapshot)
        if len(self._history) > HISTORY_LIMIT:
            del self._history[0]
        self._published = snapshot
        self._published_current = True
        self._published_count += 1
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        return _copy_snapshot(snapshot)

    def latest_published(self):
        '''Detached latest historical snapshot, or None.'''
        return _copy_snapshot(self._published)

    # -- events: stop / reset / faults / enable ---------------------------

    def stop(self, reason='unspecified'):
        '''Latch STOP: revoke pending/eligibility and retire the request.

        The session and control epoch are kept so a later enable plus a new
        apply_request can continue the same session, but the retired request
        can never be re-armed by late capture evidence.
        '''
        if not isinstance(reason, str):
            raise ValidationError('reason must be a string')
        self._stopped = True
        self._enabled = False
        self._request_seq = None
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published_current = False
        self._mark += 1

    def reset(self, reason='unspecified', scope='fixture'):
        '''Abstract reset event (either side); requires a genuinely new session.

        scope is an abstract label (fixture/authority/capture) for the
        software fixture; it models no physical CDC implementation.
        '''
        if not isinstance(reason, str):
            raise ValidationError('reason must be a string')
        if not isinstance(scope, str) or scope not in ALLOWED_RESET_SCOPES:
            raise ValidationError('scope must be one of ' + repr(ALLOWED_RESET_SCOPES)
                                  + ', got ' + repr(scope))
        self._session = None
        self._control_epoch = None
        self._request_seq = None
        self._last_request_seq = None
        self._last_batch_seq = None
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published_current = False
        self._stopped = True
        self._enabled = False
        self._mark += 1

    def set_fault(self, bit):
        '''Latch one candidate fault bit; conservative stop and new handshake.'''
        _require_int('bit', bit, FAULT_BIT_MIN, FAULT_BIT_MAX)
        self._faults |= (1 << bit)
        self._session = None
        self._control_epoch = None
        self._request_seq = None
        self._last_request_seq = None
        self._last_batch_seq = None
        self._pending = None
        self._pending_key = None
        self._pending_poisoned = False
        self._published_current = False
        self._stopped = True
        self._enabled = False
        self._mark += 1

    def clear_fault(self):
        '''Clear latched faults; never enables motion and never changes capture.'''
        if not self._stopped:
            raise StateError('clear_fault is a stopped-state operation')
        self._faults = 0

    def enable(self):
        '''Software-local enable flag only; never hardware_enable_eligible.'''
        if self._faults != 0:
            raise FaultStateError('enable refused while fault bits are latched: '
                                  + str(self._faults))
        if not self._stopped:
            raise StateError('enable is a stopped-state operation (already enabled)')
        self._stopped = False
        self._enabled = True

    # -- atomic reads ------------------------------------------------------

    def begin_frozen_read(self):
        '''Latch one coherent multiword read transaction (candidate-local).'''
        words = snapshot_word_view(self._published)
        key = self._published.batch_key if self._published is not None else None
        latched_current = self._published is not None and self._published_current
        return FrozenRead(self, words, key, self._mark, latched_current)

    def words_consistent(self, words):
        '''True iff the tuple matches one bounded-history snapshot exactly.

        A caller-mutated or torn mix of words from different snapshots fails
        this check; bool elements are rejected like everywhere else.
        '''
        try:
            candidate = tuple(words)
        except TypeError:
            return False
        if len(candidate) != SNAPSHOT_WORD_COUNT:
            return False
        for item in candidate:
            if type(item) is not int:
                return False
            if item < 0 or item > UINT32_MAX:
                return False
        for snapshot in self._history:
            if snapshot_word_view(snapshot) == candidate:
                return True
        return False


HIGH_AT_ZERO = {'yaw': 250000, 'pitch': 250000, 'speed': 50000}
PERM_ORDERS = (
    ('yaw', 'pitch', 'speed'),
    ('yaw', 'speed', 'pitch'),
    ('pitch', 'yaw', 'speed'),
    ('pitch', 'speed', 'yaw'),
    ('speed', 'yaw', 'pitch'),
    ('speed', 'pitch', 'yaw'),
)
_OMIT = object()


def _st(op, expect=None, **kwargs):
    step = {'op': op}
    step.update(kwargs)
    if expect is not None:
        step['expect'] = expect
    return step


def _ok(value=_OMIT):
    expect = {'outcome': 'ok'}
    if value is not _OMIT:
        expect['value'] = value
    return expect


def _err(name):
    return {'error': name, 'outcome': 'error'}


def _setup(session=100, epoch=1, request_seq=7):
    return [
        _st('begin_session', _ok(), session=session),
        _st('enable', _ok()),
        _st('begin_epoch', _ok(), control_epoch=epoch),
        _st('apply_request', _ok(), request_seq=request_seq),
    ]


def _sub(channel, batch_seq, high_ticks, expect, session=100, control_epoch=1,
         request_seq=7, period_ticks=PWM_PERIOD_TICKS):
    return _st('submit', expect, channel=channel, session=session,
               control_epoch=control_epoch, request_seq=request_seq,
               batch_seq=batch_seq, period_ticks=period_ticks,
               high_ticks=high_ticks)


def _full_batch(batch_seq, expect=_ok('stored'), session=100, request_seq=7):
    return [
        _sub('yaw', batch_seq, HIGH_AT_ZERO['yaw'], expect, session=session, request_seq=request_seq),
        _sub('pitch', batch_seq, HIGH_AT_ZERO['pitch'], expect, session=session, request_seq=request_seq),
        _sub('speed', batch_seq, HIGH_AT_ZERO['speed'], expect, session=session, request_seq=request_seq),
    ]


def _pwm_vector_id(channel, code, delta_ticks, period_delta):
    def part(value):
        sign = 'p' if value >= 0 else 'm'
        return sign + str(abs(value))

    return ('pwm-' + channel + '-code' + str(code) + '-d' + part(delta_ticks)
            + '-period' + part(period_delta))


def _pwm_vector(channel, mode, code, high_ticks, delta_ticks, period_delta):
    period_ticks = PWM_PERIOD_TICKS + period_delta
    within = abs(delta_ticks) <= CAPTURE_TOLERANCE_TICKS
    period_ok = abs(period_delta) <= CAPTURE_TOLERANCE_TICKS
    return {
        'channel': channel,
        'expect': {
            'accepted': within and period_ok,
            'candidate_only': True,
            'channel': channel,
            'decoded_code': code,
            'delta_ticks': delta_ticks,
            'expected_high_ticks': high_ticks - delta_ticks,
            'hardware_enable_eligible': False,
            'mode': mode,
            'period_ticks': period_ticks,
            'period_valid': period_ok,
            'within_candidate_tolerance': within,
        },
        'high_ticks': high_ticks,
        'id': _pwm_vector_id(channel, code, delta_ticks, period_delta),
        'period_ticks': period_ticks,
    }


def build_pwm_vectors():
    '''Candidate PWM boundary vectors: +/-2 accepted, +/-3 rejected (candidate).'''
    vectors = []
    deltas = (-3, -2, 0, 2, 3)
    for q in (-15000, -14999, -1, 0, 1, 14999, 15000):
        base = ANGLE_HIGH_BASE + ANGLE_HIGH_STEP * (q - ANGLE_Q_MIN)
        for delta in deltas:
            vectors.append(_pwm_vector('yaw', 'angle', q, base + delta, delta, 0))
    zero_base = ANGLE_HIGH_BASE + ANGLE_HIGH_STEP * (0 - ANGLE_Q_MIN)
    vectors.append(_pwm_vector('yaw', 'angle', 0, zero_base + 8, 8, 0))
    for code in (0, 1, 19, 20):
        base = SPEED_HIGH_BASE + SPEED_HIGH_STEP * (code - SPEED_CODE_MIN)
        for delta in deltas:
            vectors.append(_pwm_vector('speed', 'speed', code, base + delta, delta, 0))
    for period_delta in deltas:
        vectors.append(_pwm_vector('pitch', 'angle', 0, zero_base, 0, period_delta))
    return vectors


def _scenarios():
    scenarios = []

    def add(identifier, description, steps, negative=False):
        scenarios.append({'description': description, 'id': identifier,
                          'negative': negative, 'steps': steps})

    add('happy-path-atomic-publish',
        'Three channels of one batch publish atomically and become eligible.',
        _setup() + [
            _sub('yaw', 1, 250002, _ok('stored')),
            _sub('pitch', 1, 249998, _ok('stored')),
            _sub('speed', 1, 51000, _ok('stored')),
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('latest_published', _ok([100, 1, 7, 1])),
        ])

    for number, order in enumerate(PERM_ORDERS, 1):
        steps = _setup()
        for channel in order:
            steps.append(_sub(channel, 1, HIGH_AT_ZERO[channel], _ok('stored')))
        steps.append(_st('publish', _ok([100, 1, 7, 1])))
        steps.append(_st('eligibility', _ok(True)))
        add('perm-' + str(number) + '-' + '-'.join(order),
            'Channel arrival permutation ' + '-'.join(order) + ' still publishes one batch.',
            steps)

    add('missing-channel-no-publish',
        'Missing channel evidence cannot publish and stays ineligible.',
        _setup() + [
            _sub('yaw', 1, 250000, _ok('stored')),
            _sub('pitch', 1, 250000, _ok('stored')),
            _st('publish', _err('PublishNotReadyError')),
            _st('eligibility', _ok(False)),
            _st('pending_channels', _ok(['pitch', 'yaw'])),
        ], negative=True)

    add('mixed-batch-no-merge',
        'A newer batch_seq starts fresh pending state; old pitch is never merged with new yaw.',
        _setup() + [
            _sub('yaw', 1, 250000, _ok('stored')),
            _sub('pitch', 1, 250000, _ok('stored')),
            _sub('yaw', 2, 490000, _ok('stored')),
            _st('pending_channels', _ok(['yaw'])),
            _st('publish', _err('PublishNotReadyError')),
            _sub('pitch', 2, 249984, _ok('stored')),
            _sub('speed', 2, 70000, _ok('stored')),
            _st('publish', _ok([100, 1, 7, 2])),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('wrong-session-evidence',
        'Evidence from another session is rejected without state change.',
        _setup() + [
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError'), session=99),
            _st('pending_channels', _ok([])),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('wrong-epoch-evidence',
        'Evidence from another control epoch is rejected without state change.',
        _setup() + [
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError'), control_epoch=2),
            _sub('yaw', 1, 250000, _ok('stored')),
            _st('publish', _err('PublishNotReadyError')),
        ], negative=True)

    add('wrong-request-evidence',
        'Evidence bound to another request_seq is rejected without state change.',
        _setup() + [
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError'), request_seq=8),
            _st('pending_channels', _ok([])),
        ], negative=True)

    add('dup-identical-before-publish',
        'Identical duplicate channel evidence before publication is idempotent.',
        _setup() + [
            _sub('yaw', 1, 250000, _ok('stored')),
            _sub('yaw', 1, 250000, _ok('duplicate_ignored')),
            _sub('pitch', 1, 250000, _ok('stored')),
            _sub('speed', 1, 50000, _ok('stored')),
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
        ])

    add('dup-conflict-before-publish',
        'Conflicting duplicate before publication poisons the batch permanently.',
        _setup() + [
            _sub('yaw', 1, 250000, _ok('stored')),
            _sub('yaw', 1, 250016, _err('BatchConflictError')),
            _sub('pitch', 1, 250000, _ok('stored')),
            _sub('speed', 1, 50000, _ok('stored')),
            _st('publish', _err('PublishNotReadyError')),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('dup-conflict-after-publish',
        'Conflict after publication revokes eligibility; frozen bytes become INVALID; object unchanged.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('frozen_read', _ok({'had_snapshot': True}), label='f1'),
            _sub('yaw', 1, 250016, _err('BatchConflictError')),
            _st('eligibility', _ok(False)),
            _st('latest_published', _ok([100, 1, 7, 1])),
            _st('frozen_coherent', _ok(False), label='f1'),
            _st('frozen_words', _ok([100, 1, 7, 1, 15000, 15000, 0, 15]), label='f1'),
        ], negative=True)

    add('dup-identical-after-publish',
        'Identical duplicate after publication is idempotent and does not restore or revoke eligibility.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _sub('yaw', 1, 250000, _ok('duplicate_ignored')),
            _st('eligibility', _ok(True)),
            _st('publish', _err('PublishNotReadyError')),
        ])

    add('reset-before-snapshot',
        'Reset before any snapshot: eligibility impossible; old session id cannot be reused; old keys rejected.',
        _setup() + [
            _st('reset', _ok(), reason='fixture-reset', scope='fixture'),
            _st('eligibility', _ok(False)),
            _st('pending_channels', _ok([])),
            _sub('yaw', 1, 250000, _err('SessionStateError')),
            _st('begin_session', _err('SequenceViolationError'), session=100),
            _st('begin_session', _ok(), session=101),
            _st('enable', _ok()),
            _st('begin_epoch', _ok(), control_epoch=1),
            _st('apply_request', _ok(), request_seq=8),
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError'), session=100, request_seq=7),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('reset-clears-pending',
        'Reset during a complete pending batch clears it; publication becomes impossible.',
        _setup() + _full_batch(1) + [
            _st('reset', _ok(), reason='mid-batch-reset', scope='capture'),
            _st('publish', _err('SessionStateError')),
            _st('eligibility', _ok(False)),
            _st('pending_channels', _ok([])),
        ], negative=True)

    add('reset-after-publish-reestablish',
        'Published history survives reset as a stale object; a genuinely new session republishes.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('reset', _ok(), reason='after-publish-reset', scope='authority'),
            _st('eligibility', _ok(False)),
            _st('latest_published', _ok([100, 1, 7, 1])),
            _st('begin_session', _ok(), session=101),
            _st('enable', _ok()),
            _st('begin_epoch', _ok(), control_epoch=1),
            _st('apply_request', _ok(), request_seq=8),
        ] + _full_batch(1, session=101, request_seq=8) + [
            _st('publish', _ok([101, 1, 8, 1])),
            _st('eligibility', _ok(True)),
        ])

    add('stop-dominates-apply',
        'STOP revokes eligibility and blocks apply; enable is separate; the same session continues after enable.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('stop', _ok()),
            _st('eligibility', _ok(False)),
            _st('stopped', _ok(True)),
            _st('enabled', _ok(False)),
            _st('apply_request', _err('StopDominanceError'), request_seq=8),
            _st('publish', _err('PublishNotReadyError')),
            _st('clear_fault', _ok()),
            _st('enable', _ok()),
            _st('enabled', _ok(True)),
            _st('apply_request', _ok(), request_seq=8),
        ] + _full_batch(2, request_seq=8) + [
            _st('publish', _ok([100, 1, 8, 2])),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('stop-mid-batch',
        'STOP during a partial batch clears it and retires the active request; stale evidence for the discarded cycle is refused.',
        _setup() + [
            _sub('yaw', 1, 250000, _ok('stored')),
            _st('stop', _ok()),
            _sub('pitch', 1, 250000, _err('ForeignEvidenceError')),
            _st('pending_channels', _ok([])),
            _st('publish', _err('PublishNotReadyError')),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('apply-clears-eligibility-not-relabel',
        'A new apply clears visible eligibility; the old snapshot is never relabeled to the new request.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('apply_request', _ok(), request_seq=8),
            _st('eligibility', _ok(False)),
            _st('latest_published', _ok([100, 1, 7, 1])),
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError'), request_seq=7),
        ] + _full_batch(2, request_seq=8) + [
            _st('publish', _ok([100, 1, 8, 2])),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('fault-stop-recovery',
        'A fault stops conservatively and requires a new session plus enable before apply.',
        _setup() + [
            _st('set_fault', _ok(), bit=2),
            _st('stopped', _ok(True)),
            _st('enabled', _ok(False)),
            _st('eligibility', _ok(False)),
            _st('apply_request', _err('SessionStateError'), request_seq=8),
            _st('clear_fault', _ok()),
            _st('enable', _ok()),
            _st('begin_session', _ok(), session=101),
            _st('enable', _ok()),
            _st('begin_epoch', _ok(), control_epoch=1),
            _st('apply_request', _ok(), request_seq=8),
        ] + _full_batch(1, session=101, request_seq=8) + [
            _st('publish', _ok([101, 1, 8, 1])),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('fault-enable-refusal',
        'clear_fault and enable stay separate: enable refuses while faults latch; clear_fault alone never enables.',
        [
            _st('begin_session', _ok(), session=1),
            _st('enable', _ok()),
            _st('set_fault', _ok(), bit=5),
            _st('enable', _err('FaultStateError')),
            _st('clear_fault', _ok()),
            _st('enable', _ok()),
            _st('clear_fault', _err('StateError')),
            _st('set_fault', _ok(), bit=6),
            _st('clear_fault', _ok()),
            _st('enabled', _ok(False)),
            _st('enable', _ok()),
            _st('enabled', _ok(True)),
        ], negative=True)

    add('apply-before-enable',
        'Apply is blocked before enable and replay of the same request is refused.',
        [
            _st('begin_session', _ok(), session=5),
            _st('apply_request', _err('StopDominanceError'), request_seq=1),
            _st('enable', _ok()),
            _st('apply_request', _ok(), request_seq=1),
            _st('apply_request', _err('SequenceViolationError'), request_seq=1),
        ], negative=True)

    add('boundary-high-accept',
        'Candidate +/-2 boundary evidence is accepted and publishes.',
        _setup() + [
            _sub('yaw', 1, 10002, _ok('stored')),
            _sub('pitch', 1, 249998, _ok('stored')),
            _sub('speed', 1, 50002, _ok('stored')),
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
        ])

    add('boundary-period-minus3',
        'Candidate period +/-3 is stored as invalid and revokes eligibility (candidate-only bound).',
        _setup() + [
            _sub('yaw', 1, 250000, _ok('invalid_stored'), period_ticks=1999997),
            _sub('pitch', 1, 250000, _ok('invalid_stored'), period_ticks=2000003),
            _sub('speed', 1, 50000, _ok('invalid_stored'), period_ticks=1999997),
            _st('publish', _err('PublishNotReadyError')),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('boundary-high-minus3',
        'Candidate high-count +/-3 is invalid; an identical repeat is idempotent; a valid value conflicts.',
        _setup() + [
            _sub('yaw', 1, 249997, _ok('invalid_stored')),
            _sub('pitch', 1, 250003, _ok('invalid_stored')),
            _sub('speed', 1, 50003, _ok('invalid_stored')),
            _sub('yaw', 1, 249997, _ok('duplicate_ignored')),
            _sub('yaw', 1, 250000, _err('BatchConflictError')),
            _st('publish', _err('PublishNotReadyError')),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('typed-rejection',
        'Bools, floats, strings and None cannot bypass validators (bool is never an int).',
        _setup() + [
            _st('submit', _err('ValidationError'), channel='yaw', session=True,
                control_epoch=1, request_seq=7, batch_seq=1, period_ticks=2000000, high_ticks=250000),
            _st('submit', _err('ValidationError'), channel='yaw', session=100,
                control_epoch=True, request_seq=7, batch_seq=1, period_ticks=2000000, high_ticks=250000),
            _st('submit', _err('ValidationError'), channel='yaw', session=100,
                control_epoch=1, request_seq=7.0, batch_seq=1, period_ticks=2000000, high_ticks=250000),
            _st('submit', _err('ValidationError'), channel='yaw', session=100,
                control_epoch=1, request_seq=7, batch_seq='1', period_ticks=2000000, high_ticks=250000),
            _st('submit', _err('ValidationError'), channel='yaw', session=100,
                control_epoch=1, request_seq=7, batch_seq=1, period_ticks=None, high_ticks=250000),
            _st('submit', _err('ValidationError'), channel='yaw', session=100,
                control_epoch=1, request_seq=7, batch_seq=1, period_ticks=2000000, high_ticks=False),
            _st('submit', _err('ValidationError'), channel='yaww', session=100,
                control_epoch=1, request_seq=7, batch_seq=1, period_ticks=2000000, high_ticks=250000),
            _st('begin_session', _err('ValidationError'), session='100'),
            _st('begin_epoch', _err('ValidationError'), control_epoch=1.0),
            _st('apply_request', _err('ValidationError'), request_seq=None),
            _st('reset', _err('ValidationError'), reason='x', scope=5),
            _st('set_fault', _err('ValidationError'), bit=True),
            _st('set_fault', _err('ValidationError'), bit=8),
            _st('shadow_write', _err('ValidationError'), offset=0x08, value=True),
            _st('pending_channels', _ok([])),
            _st('eligibility', _ok(False)),
        ], negative=True)

    add('overflow-replay-regression',
        'Candidate sequences are monotonic and non-wrapping: replay, regression and overflow refused.',
        [
            _st('begin_session', _ok(), session=UINT32_MAX),
            _st('begin_session', _err('SequenceViolationError'), session=UINT32_MAX),
            _st('begin_session', _err('SequenceViolationError'), session=0),
            _st('begin_session', _err('ValidationError'), session=4294967296),
            _st('enable', _ok()),
            _st('begin_epoch', _ok(), control_epoch=1),
            _st('begin_epoch', _err('SequenceViolationError'), control_epoch=1),
            _st('begin_epoch', _err('SequenceViolationError'), control_epoch=0),
            _st('begin_epoch', _err('SequenceViolationError'), control_epoch=3),
            _st('apply_request', _ok(), request_seq=65535),
            _st('apply_request', _err('SequenceViolationError'), request_seq=65535),
            _st('apply_request', _err('SequenceViolationError'), request_seq=10),
            _st('apply_request', _err('ValidationError'), request_seq=65536),
        ] + _full_batch(UINT32_MAX, session=UINT32_MAX, request_seq=65535) + [
            _st('publish', _ok([UINT32_MAX, 1, 65535, UINT32_MAX])),
            _st('eligibility', _ok(True)),
            _sub('yaw', UINT32_MAX, 250000, _ok('duplicate_ignored'),
                 session=UINT32_MAX, request_seq=65535),
            _sub('yaw', 0, 250000, _err('SequenceViolationError'),
                 session=UINT32_MAX, request_seq=65535),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('epoch-rollover-refusal',
        'Epoch wrap and replay are refused; out-of-range epoch is a typed rejection.',
        [
            _st('begin_session', _ok(), session=1),
            _st('enable', _ok()),
            _st('begin_epoch', _ok(), control_epoch=255),
            _st('begin_epoch', _err('SequenceViolationError'), control_epoch=0),
            _st('begin_epoch', _err('ValidationError'), control_epoch=256),
            _st('begin_epoch', _err('SequenceViolationError'), control_epoch=255),
        ], negative=True)

    add('register-inventory-access',
        '29 pinned offsets; 0x2c reserved no_access; unknown values null; partial strobes refused.',
        [
            _st('reg_count', _ok(29)),
            _st('shadow_read', _err('ReservedRegisterAccessError'), offset=0x2c),
            _st('shadow_write', _err('ReservedRegisterAccessError'), offset=0x2c, value=0),
            _st('shadow_read', _ok(None), offset=0x08),
            _st('shadow_write', _ok(), offset=0x08, value=UINT32_MAX),
            _st('shadow_read', _ok(UINT32_MAX), offset=0x08),
            _st('shadow_write', _err('ValidationError'), offset=0x08, value=4294967296),
            _st('shadow_write', _err('ValidationError'), offset=0x100, value=1),
            _st('shadow_read', _err('ValidationError'), offset=0x100),
            _st('shadow_write', _err('ValidationError'), offset=0x08, value=1, write_strobes=1),
        ], negative=True)

    add('stop-late-capture-refused',
        'STOP retires the active request: late capture evidence for it is refused, '
        'enable alone cannot republish, and only a new applied request recovers.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('stop', _ok()),
            _st('eligibility', _ok(False)),
            _st('enable', _ok()),
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError')),
            _sub('pitch', 1, 250000, _err('ForeignEvidenceError')),
            _sub('speed', 1, 50000, _err('ForeignEvidenceError')),
            _st('pending_channels', _ok([])),
            _st('publish', _err('PublishNotReadyError')),
            _st('eligibility', _ok(False)),
            _st('apply_request', _ok(), request_seq=8),
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError'), request_seq=7),
        ] + _full_batch(2, request_seq=8) + [
            _st('publish', _ok([100, 1, 8, 2])),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('epoch-retires-request',
        'A new control epoch retires the active request: old-request evidence is '
        'refused until a new apply, and the old request replay is refused.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('begin_epoch', _ok(), control_epoch=2),
            _st('eligibility', _ok(False)),
            _sub('yaw', 2, 250000, _err('ForeignEvidenceError'), control_epoch=2),
            _st('apply_request', _err('SequenceViolationError'), request_seq=7),
            _st('apply_request', _ok(), request_seq=8),
        ] + [
            _sub('yaw', 2, 250000, _ok('stored'), control_epoch=2, request_seq=8),
            _sub('pitch', 2, 250000, _ok('stored'), control_epoch=2, request_seq=8),
            _sub('speed', 2, 50000, _ok('stored'), control_epoch=2, request_seq=8),
            _st('publish', _ok([100, 2, 8, 2])),
            _st('eligibility', _ok(True)),
        ], negative=True)

    add('frozen-new-cycle-revokes-freshness',
        'A new capture cycle revokes captured eligibility: the latched read keeps its '
        'bytes but is no longer coherent until a fresh latch from the new publication.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('frozen_read', _ok({'had_snapshot': True}), label='f1'),
            _st('frozen_coherent', _ok(True), label='f1'),
        ] + _full_batch(2) + [
            _st('eligibility', _ok(False)),
            _st('frozen_coherent', _ok(False), label='f1'),
            _st('frozen_words', _ok([100, 1, 7, 1, 15000, 15000, 0, 15]), label='f1'),
            _st('publish', _ok([100, 1, 7, 2])),
            _st('eligibility', _ok(True)),
            _st('frozen_read', _ok({'had_snapshot': True}), label='f2'),
            _st('frozen_coherent', _ok(True), label='f2'),
            _st('frozen_coherent', _ok(False), label='f1'),
        ], negative=True)

    add('frozen-atomic-shadow-stop',
        'Frozen reads are atomic; shadow writes cannot mutate them; STOP makes them INVALID with bytes retained and retires the active request.',
        _setup() + _full_batch(1) + [
            _st('publish', _ok([100, 1, 7, 1])),
            _st('eligibility', _ok(True)),
            _st('frozen_read', _ok({'had_snapshot': True}), label='f1'),
            _st('frozen_words', _ok([100, 1, 7, 1, 15000, 15000, 0, 15]), label='f1'),
            _st('frozen_coherent', _ok(True), label='f1'),
            _st('shadow_write', _ok(), offset=0x50, value=12345),
            _st('frozen_words', _ok([100, 1, 7, 1, 15000, 15000, 0, 15]), label='f1'),
            _st('frozen_coherent', _ok(True), label='f1'),
            _st('validate_words', _ok(True), words=[100, 1, 7, 1, 15000, 15000, 0, 15]),
            _st('validate_words', _ok(False), words=[100, 1, 7, 1, 15000, 14999, 0, 15]),
            _st('validate_words', _ok(False), words=[100, 1, 7, 2, 15000, 15000, 0, 15]),
            _st('validate_words', _ok(False), words=[100, 1, 7, 1, 15000, 15000, 0]),
            _st('validate_words', _ok(False), words=[100, 1, 7, 1, 15000, 15000, 0, True]),
            _st('stop', _ok()),
            _st('eligibility', _ok(False)),
            _st('frozen_coherent', _ok(False), label='f1'),
            _st('frozen_words', _ok([100, 1, 7, 1, 15000, 15000, 0, 15]), label='f1'),
            _sub('yaw', 1, 250000, _err('ForeignEvidenceError')),
            _st('eligibility', _ok(False)),
        ], negative=True)

    return scenarios


def build_vectors_document():
    '''Emit the machine-readable PWM vectors and capture scenario vectors.'''
    scenarios = _scenarios()
    return {
        'candidate_only': True,
        'capture_scenarios': scenarios,
        'contract': {
            'contract': CONTRACT_ID,
            'contract_commit': CONTRACT_COMMIT,
            'design_commit': DESIGN_COMMIT,
            'requirements_ids': list(REQUIREMENTS_IDS),
            'requirements_sha256': REQUIREMENTS_SHA256,
            'revision': CONTRACT_REVISION,
        },
        'correction_work_id': CORRECTION_WORK_ID,
        'hardware_enable_eligible': False,
        'input_manifest_sha256': INPUT_MANIFEST_SHA256,
        'negative_scenario_ids': [item['id'] for item in scenarios if item['negative']],
        'notes': [
            'All vectors are candidate-only offline software checks; no board, CDC/RDC, ABI or enable claim.',
            'The +/-2 tick tolerance and +/-3 rejection are proposed candidate bounds, not measured hardware limits.',
            'The capture word view is candidate-local for atomic-read tests only; no public address map or tick word order is claimed.',
            'Correction B-CONTROL-INGRESS-STOP-CORRECTION-20261016-02-v1: derived evidence fields are re-derived and cross-checked at every ingress, STOP and new epochs retire the active request, records are detached from caller aliases, and frozen-read coherence follows captured eligibility.',
        ],
        'pwm_vectors': build_pwm_vectors(),
        'schema': 1,
        'stages': {
            'board': 'not_run',
            'implementation': 'not_run',
            'simulation': 'not_run',
            'synthesis': 'not_run',
            'system': 'not_run',
        },
        'task': TASK_ID,
        'task_version': TASK_VERSION,
        'work_id': WORK_ID,
    }


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return dict((key, _jsonable(item)) for key, item in value.items())
    if isinstance(value, FrozenRead):
        return value.as_dict()
    raise ValidationError('value is not jsonable: ' + repr(value))


def _run_op(model, registers, frozen, step):
    op = step['op']
    if op == 'begin_session':
        model.begin_session(step['session'])
        return None
    if op == 'begin_epoch':
        model.begin_epoch(step['control_epoch'])
        return None
    if op == 'apply_request':
        model.apply_request(step['request_seq'])
        return None
    if op == 'submit':
        evidence = ChannelEvidence.create(
            channel=step['channel'], session=step['session'],
            control_epoch=step['control_epoch'], request_seq=step['request_seq'],
            batch_seq=step['batch_seq'], period_ticks=step['period_ticks'],
            high_ticks=step['high_ticks'])
        return model.submit_evidence(evidence)
    if op == 'publish':
        return list(model.publish_snapshot().batch_key.as_tuple())
    if op == 'eligibility':
        return model.eligibility
    if op == 'latest_published':
        snapshot = model.latest_published()
        return None if snapshot is None else list(snapshot.batch_key.as_tuple())
    if op == 'pending_channels':
        return list(model.pending_channels)
    if op == 'stop':
        model.stop(reason=step.get('reason', 'vector-stop'))
        return None
    if op == 'reset':
        model.reset(reason=step.get('reason', 'vector-reset'), scope=step.get('scope', 'fixture'))
        return None
    if op == 'set_fault':
        model.set_fault(step['bit'])
        return None
    if op == 'clear_fault':
        model.clear_fault()
        return None
    if op == 'enable':
        model.enable()
        return None
    if op == 'frozen_read':
        read = model.begin_frozen_read()
        frozen[step['label']] = read
        return {'had_snapshot': read.words is not None}
    if op == 'frozen_coherent':
        return frozen[step['label']].coherent
    if op == 'frozen_words':
        read = frozen[step['label']]
        return None if read.words is None else list(read.words)
    if op == 'validate_words':
        return model.words_consistent(step['words'])
    if op == 'shadow_write':
        registers.write(step['offset'], step['value'],
                        write_strobes=step.get('write_strobes', 0xF))
        return None
    if op == 'shadow_read':
        return registers.read(step['offset'])
    if op == 'reg_count':
        return len(registers.addresses())
    if op == 'stopped':
        return model.stopped
    if op == 'enabled':
        return model.enabled
    raise ValidationError('unknown vector op: ' + repr(op))


def execute_scenario(scenario):
    '''Execute one vector scenario; returns per-step records with outcomes.'''
    model = CaptureSnapshotModel()
    registers = CandidateRegisterFile()
    frozen = {}
    records = []
    for index, step in enumerate(scenario['steps']):
        op = step['op']
        try:
            value = _jsonable(_run_op(model, registers, frozen, step))
            records.append({'error': None, 'index': index, 'op': op,
                            'outcome': 'ok', 'value': value})
        except ControlCandidateError as exc:
            records.append({'error': type(exc).__name__, 'index': index, 'op': op,
                            'outcome': 'error', 'value': None})
    return records


def compare_records(scenario, records):
    '''Return the list of expectation mismatches with raw expected/actual.'''
    mismatches = []
    for index, step in enumerate(scenario['steps']):
        expect = step.get('expect')
        if expect is None:
            continue
        record = records[index]
        problem = None
        if record['outcome'] != expect['outcome']:
            problem = 'outcome'
        elif expect['outcome'] == 'error' and record['error'] != expect.get('error'):
            problem = 'error'
        elif 'value' in expect and record['value'] != expect['value']:
            problem = 'value'
        if problem is not None:
            mismatches.append({'actual': record, 'expected': expect, 'index': index,
                               'op': step['op'], 'problem': problem,
                               'scenario': scenario['id']})
    return mismatches


def check_documents(inventory_document, vectors_document):
    '''Re-derive and execute every vector; returns all problems found.'''
    problems = []
    if inventory_document != build_inventory_document():
        problems.append({'problem': 'inventory document drift vs module constants'})
    if vectors_document != build_vectors_document():
        problems.append({'problem': 'vectors document drift vs module constants'})
    for vector in vectors_document['pwm_vectors']:
        actual = classify_high_count(vector['channel'], vector['high_ticks'], vector['period_ticks'])
        if actual != vector['expect']:
            problems.append({'actual': actual, 'expected': vector['expect'],
                             'problem': 'pwm', 'vector': vector['id']})
    for scenario in vectors_document['capture_scenarios']:
        records = execute_scenario(scenario)
        problems.extend(compare_records(scenario, records))
    return problems


def _write_json(path, document):
    text = json.dumps(document, indent=1, sort_keys=True, ensure_ascii=True) + '\n'
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    encoded = text.encode('utf-8')
    return len(encoded), hashlib.sha256(encoded).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='capture_snapshot_reference',
        description='Candidate-only control capture/snapshot software reference (B side)')
    subparsers = parser.add_subparsers(dest='command', required=True)
    emit_parser = subparsers.add_parser('emit')
    emit_parser.add_argument('--inventory', required=True)
    emit_parser.add_argument('--vectors', required=True)
    check_parser = subparsers.add_parser('check')
    check_parser.add_argument('--inventory', required=True)
    check_parser.add_argument('--vectors', required=True)
    args = parser.parse_args(argv)
    if args.command == 'emit':
        inventory = build_inventory_document()
        vectors = build_vectors_document()
        inv_bytes, inv_sha = _write_json(args.inventory, inventory)
        vec_bytes, vec_sha = _write_json(args.vectors, vectors)
        print('emitted inventory: ' + args.inventory + ' bytes=' + str(inv_bytes)
              + ' sha256=' + inv_sha)
        print('emitted vectors: ' + args.vectors + ' bytes=' + str(vec_bytes)
              + ' sha256=' + vec_sha)
        print('registers=' + str(len(inventory['registers']))
              + ' pwm_vectors=' + str(len(vectors['pwm_vectors']))
              + ' scenarios=' + str(len(vectors['capture_scenarios']))
              + ' negative_scenarios=' + str(len(vectors['negative_scenario_ids'])))
        print('candidate-only: no board/CDC/ABI/enable claim is made')
        return 0
    with open(args.inventory, encoding='utf-8') as handle:
        inventory = json.load(handle)
    with open(args.vectors, encoding='utf-8') as handle:
        vectors = json.load(handle)
    problems = check_documents(inventory, vectors)
    if problems:
        print('vector check FAILED with ' + str(len(problems)) + ' problem(s)')
        for problem in problems[:40]:
            print(json.dumps(problem, sort_keys=True))
        return 1
    print('vector file: ' + args.vectors)
    print('registers checked: ' + str(len(inventory['registers'])))
    print('pwm vectors checked: ' + str(len(vectors['pwm_vectors'])))
    print('scenarios checked: ' + str(len(vectors['capture_scenarios'])))
    print('vector check passed: inventory crosswalk, candidate PWM decode, scenario semantics')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
