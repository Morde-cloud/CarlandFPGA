"""Accepted own-pose -> bounded two-axis display, never a simulation controller.

Run beside the original NativeClient on its QPC host. Never compare another
machine's absolute QPC values without an independently validated clock bridge.
PWM is an open-loop display proxy; no RPM measurement/upper bound is inferred.
"""
from dataclasses import dataclass
import math

CONTRACT_SHA256 = '2afd4515da6f03dad47d453fb3692c5f67fa2fb09084665d425de1340648bf4d'


class FollowError(ValueError):
    pass


def need(ok, why):
    if not ok:
        raise FollowError(why)


def integer(v, lo=0, hi=(1 << 63)-1):
    need(type(v) is int and lo <= v <= hi, 'EXACT_INTEGER_BOUND')
    return v


def number(v, lo, hi):
    need(type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi, 'FINITE_SCALAR_BOUND')
    return float(v)


def decimal_tick(v):
    need(type(v) is str and v.isascii() and v.isdecimal() and str(int(v)) == v, 'CANONICAL_NATIVE_TICK')
    return integer(int(v))


def quaternion(q):
    need(type(q) in (list, tuple) and len(q) == 4, 'QUATERNION4')
    q = tuple(number(x, -1.000001, 1.000001) for x in q)
    length = math.hypot(*q)
    need(abs(length-1.) <= 1e-6, 'UNIT_QUATERNION')
    return tuple(v/length for v in q)


def rotate(q, v):
    x, y, z, w = q
    a, b, c = v
    cross = (y*c-z*b, z*a-x*c, x*b-y*a)
    cross2 = (y*cross[2]-z*cross[1], z*cross[0]-x*cross[2], x*cross[1]-y*cross[0])
    return tuple(v[i]+2*w*cross[i]+2*cross2[i] for i in range(3))


def project(q, reference_xyzw):
    """Relative +Z forward direction; yaw right, pitch up. Roll not reproduced."""
    world = rotate(quaternion(q), (0., 0., 1.))
    r = quaternion(reference_xyzw)
    x, y, z = rotate((-r[0], -r[1], -r[2], r[3]), world)
    need(math.hypot(x, z) > 1e-10, 'VERTICAL_HEADING_UNDEFINED')
    return math.degrees(math.atan2(x, z)), math.degrees(math.atan2(y, math.hypot(x, z)))


@dataclass(frozen=True)
class Limits:
    yaw_min_deg: float = -90.
    yaw_max_deg: float = 90.
    pitch_min_deg: float = -45.
    pitch_max_deg: float = 68.
    speed_reference_m_s: float = .25
    maximum_duty_permille: int = 750
    max_source_age_ns: int = 250_000_000
    pose_period_ns: int = 500_000_000
    keepalive_period_ns: int = 100_000_000
    move_ms: int = 500
    native_rate_error_ppm: int = 1000

    def __post_init__(self):
        number(self.yaw_min_deg, -90., 0.); number(self.yaw_max_deg, 0., 90.)
        number(self.pitch_min_deg, -45., 0.); number(self.pitch_max_deg, 0., 68.)
        number(self.speed_reference_m_s, .000001, .25)
        # MTR4's percent API reserves exact0 for OFF. A positive percent needs
        # a ceiling above250 to remain representable without inventing epsilon.
        integer(self.maximum_duty_permille, 251, 750)
        integer(self.max_source_age_ns, 1, 250_000_000)
        integer(self.pose_period_ns, 100_000_000, 1_000_000_000)
        integer(self.keepalive_period_ns, 1, 100_000_000)
        integer(self.move_ms, 100, 1000)
        integer(self.native_rate_error_ppm, 0, 10000)


@dataclass(frozen=True)
class Target:
    run_id: str
    source: str
    snapshot_seq: int
    native_revision: int
    yaw_cd: int
    pitch_cd: int
    speed_pct: float
    duty_permille: int
    valid_until_ns: int
    acquired_lower_ns: int
    terminal: bool
    terminal_reason: str
    authority: str = 'display_only_no_product_authority'
    measured_rpm: object = None


class FollowMapper:
    """Root authenticates actual source and retains raw readback itself.

    Explicit reference equals the virtual orientation corresponding to physical
    saved centre2088/1961. Constructor never acquires a reference or moves it.
    The run/source binding cannot be silently switched. No input route/geometry.
    """
    def __init__(self, run_id, source, reference_xyzw, limits=Limits()):
        need(type(run_id) is str and 0 < len(run_id) <= 128 and run_id.isascii(), 'RUN_ID')
        need(source in ('MANUAL', 'PC_DIRECT', 'FPGA_OUTPUT'), 'REAL_SOURCE_DECLARATION')
        need(type(limits) is Limits, 'EXACT_LIMITS')
        limits.__post_init__()
        self.run_id, self.source, self.reference, self.limits = run_id, source, quaternion(reference_xyzw), limits
        self._received, self._revision, self._now, self._seq = -1, -1, -1, 0

    def map(self, sample, *, now_ns):
        integer(now_ns, self._now)
        need(type(sample) is dict and set(sample) == {'run_id','source','native','host'}, 'BOUND_NATIVE_CLIENT_SAMPLE')
        need(type(sample['run_id']) is str and sample['run_id'] == self.run_id
             and type(sample['source']) is str and sample['source'] == self.source, 'RUN_OR_SOURCE_CHANGED')
        state, host = sample['native'], sample['host']
        need(type(state) is dict and type(host) is dict, 'PLAIN_SAMPLE_RECORDS')
        sent = integer(host.get('send_qpc_ns'))
        received = integer(host.get('receive_qpc_ns'), max(sent, self._received+1), now_ns)
        interval = host.get('accepted_tick_qpc_interval_ns')
        need(type(interval) in (list, tuple) and len(interval) == 2, 'ACQUISITION_BRACKET')
        lower = integer(interval[0]); upper = integer(interval[1], lower, received)
        need(now_ns-lower < self.limits.max_source_age_ns, 'ORIGINAL_SOURCE_EXPIRED')
        need(state.get('abi') == 'DEEPEYE-CONTINUOUS-NATIVE-794-v1', 'NATIVE_ABI')
        native_tick, read_tick = decimal_tick(state.get('tick_usec')), decimal_tick(state.get('read_now_usec'))
        need(native_tick <= read_tick, 'NATIVE_SAMPLE_NOT_FUTURE')
        revision = decimal_tick(state.get('revision'))
        need(revision >= self._revision, 'NATIVE_REVISION_REVERSED')
        need(type(state.get('fault')) is str and len(state['fault']) <= 256
             and type(state.get('ready')) is bool and type(state.get('running')) is bool, 'EXACT_STATE_STATUS')
        phase = state.get('phase')
        need(phase in ('INITIAL_OUTSIDE','ENTRY_CROSSING','INSIDE','EXIT_CROSSING','ARRIVED'), 'SOURCE_PHASE')
        terminal = bool(state['fault']) or phase == 'ARRIVED' or not state['ready']
        deadline = lower+self.limits.max_source_age_ns
        yaw = pitch = 0.
        speed = duty = 0
        if not terminal:
            yaw, pitch = project(state.get('orientation_xyzw'), self.reference)
            l = self.limits
            need(l.yaw_min_deg-1e-10 <= yaw <= l.yaw_max_deg+1e-10
                 and l.pitch_min_deg-1e-10 <= pitch <= l.pitch_max_deg+1e-10,
                 'DISPLAY_RANGE_STOP_NO_VIRTUAL_TARGET_CHANGE')
            need(math.ceil(l.yaw_min_deg*100) <= round(yaw*100) <= math.floor(l.yaw_max_deg*100)
                 and math.ceil(l.pitch_min_deg*100) <= round(pitch*100) <= math.floor(l.pitch_max_deg*100),
                 'QUANTIZED_DISPLAY_RANGE')
            v = number(state.get('speed_m_s'), 0., .25)  # Actual speed, NEVER target/cap/slider/yaw_q.
            if v > 0:
                need(state['running'], 'POSITIVE_SPEED_WITHOUT_RUNNING_GRANT')
                native_deadline = decimal_tick(state.get('deadline_usec'))
                need(native_deadline > read_tick, 'NATIVE_GRANT_EXPIRED')
                remaining = (native_deadline-read_tick)*1000
                # t_send precedes actual native read. Debit fullRTT, resolution,
                # and explicit engineering rate bound; never equate epochs.
                remaining = remaining*1_000_000//(1_000_000+l.native_rate_error_ppm)-1_000_000
                deadline = min(deadline, sent+remaining)
                need(now_ns < deadline, 'NO_CONSERVATIVE_NATIVE_GRANT')
                maximum_pct = (l.maximum_duty_permille-250)/5
                speed = min(maximum_pct, 100*v/l.speed_reference_m_s)
                duty = int(round(250+5*speed))
                need(250 <= duty <= l.maximum_duty_permille, 'PWM_CEILING')
        self._seq = integer(self._seq+1, 1, 0xffffffff)
        self._now, self._received, self._revision = now_ns, received, revision
        return Target(self.run_id,self.source,self._seq,revision,int(round(yaw*100)),int(round(pitch*100)),
                      speed,duty,deadline,lower,terminal,state['fault'] or phase if terminal else '')
