"""One foreground IO owner; latest sample only, no autonomous source renewal."""
import threading
import time
from .model import FollowError, Target, need, integer


class Follower:
    def __init__(self, client, mapper, *, motor_enabled=False, clock_ns=time.perf_counter_ns):
        need(type(motor_enabled) is bool, 'EXPLICIT_MOTOR_ENABLE')
        self.client,self.mapper,self.motor_enabled,self.clock = client,mapper,motor_enabled,clock_ns
        self.target = None
        self.stopped = False
        self.stop_reply = None
        self.stop_error = None
        self._last_pose = None
        self._last_duty = 0
        self._pose_at = self._keepalive_at = None
        self._now = -1
        self._reply_seq = 0
        self._owner = threading.get_ident()

    def _time(self):
        need(threading.get_ident() == self._owner, 'ONE_IO_OWNER')
        now = integer(self.clock(), self._now)
        self._now = now
        return now

    def stop(self, reason='explicit_stop'):
        need(threading.get_ident() == self._owner, 'ONE_IO_OWNER')
        if self.stopped:
            return None
        # Distinct STOP attempted at most once even if its outcome is unknown.
        self.stopped = True
        try:
            reply = self.client.stop()
            self._confirmed(reply, 'stop', 0)
            self.stop_reply = reply
            return reply
        except BaseException as error:
            self.stop_error = type(error).__name__+': '+str(error)
            raise

    def _confirmed(self, reply, event, expected_duty):
        need(type(reply) is dict and reply.get('event') == event
             and reply.get('declared_source') == self.mapper.source, 'CORRELATED_CLIENT_RECORD_REQUIRED')
        status = reply.get('status')
        need(type(status) is dict and type(status.get('result_code')) is int
             and status['result_code'] == 0, 'CLIENT_REJECTED_OR_UNKNOWN')
        seq = integer(status.get('seq'), self._reply_seq+1, 0xffffffff)
        duty = integer(status.get('requested_duty_permille'), 0, self.mapper.limits.maximum_duty_permille)
        need(duty == expected_duty and type(status.get('armed')) is bool
             and (status['armed'] if duty else True), 'MOTOR_ACK_MISMATCH')
        if event == 'stop':
            need(not status['armed'], 'STOP_NOT_DISARMED')
        else:
            need(type(status.get('last_joho_error')) is int and status['last_joho_error'] == 0
                 and type(status.get('yaw_feedback')) is dict and type(status.get('pitch_feedback')) is dict
                 and status['yaw_feedback'].get('fresh') is True and status['pitch_feedback'].get('fresh') is True,
                 'ACTUAL_FRESH_GIMBAL_FEEDBACK_REQUIRED')
        self._reply_seq = seq

    def push(self, sample):
        need(not self.stopped, 'FOLLOWER_TERMINAL_NO_RESTART')
        try:
            self.target = self.mapper.map(sample, now_ns=self._time())
            if self.target.terminal:
                self.stop(self.target.terminal_reason)
            return self.target
        except BaseException:
            try:self.stop('invalid_source')
            except Exception:pass
            raise

    def _fresh(self):
        need(self.target is not None and self._time() < self.target.valid_until_ns, 'SOURCE_OR_GRANT_EXPIRED')

    def tick(self):
        need(not self.stopped, 'FOLLOWER_TERMINAL_NO_RESTART')
        if self.target is None:
            return []  # Startup never ARM/SET/spins without a source sample.
        events = []
        try:
            self._fresh()
            t,l,now = self.target,self.mapper.limits,self._now
            desired_duty = t.duty_permille if self.motor_enabled else 0
            if desired_duty != self._last_duty:
                reply = self.client.motor(t.speed_pct if self.motor_enabled else 0)
                self._confirmed(reply, 'motor', desired_duty)
                events.append(reply)
                self._last_duty = desired_duty
                self._keepalive_at = self._time()
                self._fresh()
            pose = (t.yaw_cd,t.pitch_cd)
            due = self._pose_at is None or self._now-self._pose_at >= l.pose_period_ns
            if pose != self._last_pose and due:
                reply = self.client.pose(t.yaw_cd/100,t.pitch_cd/100,move_ms=l.move_ms,
                                         source_seq=t.snapshot_seq,observation_seq=t.native_revision)
                self._confirmed(reply, 'pose', self._last_duty)
                events.append(reply)
                self._last_pose,self._pose_at = pose,self._time()
                self._fresh()
            if self._keepalive_at is None or self._now-self._keepalive_at >= l.keepalive_period_ns:
                self._fresh()
                reply = self.client.keepalive()
                self._confirmed(reply, 'keepalive', self._last_duty)
                events.append(reply)
                self._keepalive_at = self._time()
                self._fresh()
            return events
        except BaseException:
            try:self.stop('unknown_io_or_expired_source')
            except Exception:pass
            raise
