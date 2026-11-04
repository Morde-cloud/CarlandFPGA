"""Same-round op6 commands and non-AI op7 leases on an already-owned UART.

No port/thread/process is created. A supplies each genuine source round's
remaining validity; it is fixed once and is never extended by a heartbeat.
"""
from motor_runtime.variable_session import VariableDisplaySession
from fpga_link.session import LinkError, UINT32_MAX, _integer
from pc.codec import decode_reply
from delta_codec import encode_delta, encode_keepalive, encode_startup_prepare, speed_to_pwm, VALID, PAUSE, STOP


class CompoundDeltaSession(VariableDisplaySession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delta_run_id = self.delta_command_seq = self.delta_speed_norm = 0
        self.delta_source_deadline_ms = None
        self.delta_lease_deadline_ms = None
        self.delta_active = False
        self.delta_reply = None
        self.prepared_run_id = self.prepared_speed_permille = 0
        self.prepared_active = False
        self._last_compound_ack_raw = None

    def stop(self):
        self.delta_active = False
        self.delta_speed_norm = 0
        self.delta_source_deadline_ms = self.delta_lease_deadline_ms = None
        self.delta_reply = None
        # Keep the prepared-run high-water identity after cancellation.
        self.prepared_active = False
        return super().stop()

    def _compound_exchange(self, encoder, deadline, **fields):
        seq = self.journal.reserve()  # Durable before dispatch; never reused.
        if self.clock_ms() >= deadline:
            raise LinkError('expired before compound dispatch; reserved wire sequence skipped')
        frame = encoder(seq=seq, source=self.source, **fields)
        # Conservatively time this frame's lease at its transport write intent,
        # after any initial STATUS/ARM and durable sequence reservation.
        write_started_ms = self.clock_ms()
        self.transport.write_frame(frame)
        raw = self.transport.read_frame(.3)
        if raw is None:
            raise LinkError('compound reply missing; no retry')
        reply = decode_reply(raw)
        if reply.seq != seq or reply.result_code:
            raise LinkError('compound refused or sequence mismatch; no retry')
        self._last_compound_ack_raw = bytes(raw)
        return reply, write_started_ms

    def _startup_prepare(self, request):
        try:
            fields = {'session', 'request_id', 'expires_ms', 'op',
                      'run_id', 'initial_speed_permille', 'move_ms'}
            if type(request) is not dict or set(request)-fields or request.get('session') != self.session_id:
                raise LinkError('unknown field or wrong startup session')
            rid = _integer(request.get('request_id'), 'request_id', 1, UINT32_MAX)
            deadline = _integer(request.get('expires_ms'), 'expires_ms', 0, 2**53)
            if rid <= self.request_id or not 0 < deadline-self.clock_ms() <= 1000:
                raise LinkError('duplicate/stale/expired startup request')
            run = _integer(request.get('run_id'), 'run_id', 1, UINT32_MAX)
            speed = _integer(request.get('initial_speed_permille'), 'initial_speed_permille', 0, 1000)
            move = _integer(request.get('move_ms', 500), 'move_ms', 100, 1000)
            # Validate the exact full wire command before reserving or writing.
            encode_startup_prepare(1, self.source, run, speed, move)
            if run <= max(self.delta_run_id, self.prepared_run_id):
                raise LinkError('startup run already prepared or executed; no replay')
            if self.delta_active or self.motor_duty or self.delta_speed_norm or self.prepared_active:
                raise LinkError('startup prepare requires prior OFF and no active preparation')
            self.request_id = rid
            # The MCU checks actual unarmed/OFF and fresh feedback atomically.
            # No convenience home, ARM, motor, keeper or source TTL is issued.
            reply, _ = self._compound_exchange(encode_startup_prepare, deadline,
                run_id=run, initial_speed_permille=speed, move_ms=move)
            self._fresh(reply)
            if (reply.armed or reply.requested_duty_permille or reply.target_yaw_cd
                    or reply.target_pitch_cd or reply.active_source != self.source):
                raise LinkError('startup ACK is not matching zero-target unarmed/OFF')
            if self.clock_ms() >= deadline:
                raise LinkError('startup request expired during exchange; no replay')
            self.prepared_run_id, self.prepared_speed_permille = run, speed
            self.prepared_active = True
            self.delta_speed_norm = self.motor_duty = 0
            self.motor_speed_pct = 0
            self.delta_active = False
            self.delta_source_deadline_ms = self.delta_lease_deadline_ms = None
            self.delta_reply = None
            result = self.record(reply, 'startup_prepare')
            result.update(prepared_run_id=run, prepared_speed_permille=speed,
                prepared_fields_are_accepted_request_targets=True,
                prepared_speed_is_executed_pwm=False, motor_off=True,
                commanded_yaw_cd=0, commanded_pitch_cd=0,
                commanded_speed_permille=0, commanded_pwm_permille=0,
                compound_source_expires_ms=None, home_reference_raw=[2088, 1961],
                uart_ack_hex=self._last_compound_ack_raw.hex(),
                synchronization_wait_owned_by_caller=True)
            return result
        except Exception:
            self.failed = True
            try:self.stop()
            except Exception:pass
            raise

    def _source_live(self, command_seq, run_id):
        now = self.clock_ms()
        if (not self.delta_active or command_seq != self.delta_command_seq
                or run_id != self.delta_run_id or self.delta_source_deadline_ms is None
                or now >= self.delta_source_deadline_ms):
            raise LinkError('original compound source expired, paused, stopped or changed')
        if (self.delta_lease_deadline_ms is None or now >= self.delta_lease_deadline_ms
                or self.delta_reply is None or not self.delta_reply.armed):
            raise LinkError('compound hardware lease lost; heartbeat cannot ARM or restart')

    def _record_compound(self, reply, event, command_seq, run_id):
        result = self.record(reply, event)
        result.update(command_seq=command_seq, run_id=run_id,
            commanded_yaw_cd=reply.target_yaw_cd,
            commanded_pitch_cd=reply.target_pitch_cd,
            commanded_speed_permille=self.delta_speed_norm,
            commanded_pwm_permille=reply.requested_duty_permille,
            compound_source_expires_ms=self.delta_source_deadline_ms,
            heartbeat_is_ai_command=False,
            motor_speed_mapping={'normalized_range':[0,1000], 'zero':'OFF',
                'positive':'250+(500*speed_permille+500)//1000 PWM permille', 'maximum':750})
        return result

    def handle(self, request):
        if self.failed:
            raise LinkError('session fault latched; no replay')
        op = request.get('op') if type(request) is dict else None
        if op == 'startup_prepare':
            return self._startup_prepare(request)
        # The legacy convenience heartbeat must not bypass a compound TTL by
        # renewing old opcode5. A heartbeat always references the real round.
        if op == 'keepalive' and self.delta_command_seq:
            request = dict(request, op='delta_keepalive',
                command_seq=self.delta_command_seq, run_id=self.delta_run_id)
            op = 'delta_keepalive'
        if op not in ('delta', 'delta_keepalive'):
            if (self.delta_command_seq or self.prepared_active) and op in ('pose', 'home', 'motor'):
                return self._reject_mixed_mode()
            return super().handle(request)
        try:
            fields = {'session','request_id','expires_ms','op','command_seq','run_id','lease_ms'}
            if op == 'delta':
                fields |= {'yaw_delta_cd','pitch_delta_cd','speed_delta_permille',
                           'move_ms','flags','source_valid_for_ms'}
            if type(request) is not dict or set(request)-fields or request.get('session') != self.session_id:
                raise LinkError('unknown field or wrong compound session')
            rid = _integer(request.get('request_id'),'request_id',1,UINT32_MAX)
            deadline = _integer(request.get('expires_ms'),'expires_ms',0,2**53)
            if rid <= self.request_id or not 0 < deadline-self.clock_ms() <= 1000:
                raise LinkError('duplicate/stale/expired compound request')
            cmd = _integer(request.get('command_seq'),'command_seq',1,UINT32_MAX)
            run = _integer(request.get('run_id'),'run_id',1,UINT32_MAX)
            if self.prepared_active and run != self.prepared_run_id:
                raise LinkError('first startup control round must match the prepared run')
            lease = _integer(request.get('lease_ms',300),'lease_ms',100,500)
            self.request_id = rid
            started = self.clock_ms()
            if op == 'delta_keepalive':
                self._source_live(cmd,run)
                self._fresh(self.delta_reply)
                if self.delta_speed_norm and not self.allow_motor:
                    raise LinkError('motor permission required')
                reply, write_started_ms = self._compound_exchange(encode_keepalive, min(deadline,self.delta_source_deadline_ms),
                    command_seq=cmd,run_id=run,lease_ms=lease)
                self._fresh(reply)
                if not reply.armed or reply.requested_duty_permille != speed_to_pwm(self.delta_speed_norm):
                    raise LinkError('heartbeat lost accepted output; never restart')
                # Same run/command/source deadline and no delta accumulation.
            else:
                validity = _integer(request.get('source_valid_for_ms'),'source_valid_for_ms',1,2**31-1)
                source_deadline = started+validity
                kwargs = dict(command_seq=cmd,run_id=run,
                    yaw_delta_cd=request.get('yaw_delta_cd'),pitch_delta_cd=request.get('pitch_delta_cd'),
                    speed_delta_permille=request.get('speed_delta_permille'),
                    move_ms=request.get('move_ms',500),lease_ms=lease,flags=request.get('flags',VALID))
                # Validate all wire fields before a STATUS, ARM or delta write.
                encode_delta(seq=1,source=self.source,**kwargs)
                if run < self.delta_run_id or run == self.delta_run_id and cmd <= self.delta_command_seq:
                    raise LinkError('real run/command already applied; never double accumulate')
                flags = kwargs['flags']
                requested_speed = max(0,min(1000,self.delta_speed_norm+kwargs['speed_delta_permille']))
                if flags == VALID and requested_speed and not self.allow_motor:
                    raise LinkError('motor permission required')
                if flags == VALID:
                    new_run = run != self.delta_run_id
                    lease_expired = (self.delta_active and (self.delta_lease_deadline_ms is None
                        or self.clock_ms() >= self.delta_lease_deadline_ms))
                    if new_run and not lease_expired and (self.delta_speed_norm or self.motor_duty or self.delta_active):
                        raise LinkError('new run requires prior OFF and explicit ARM')
                    current = self.delta_reply if self.delta_active else None
                    if current is None or not current.armed or lease_expired:
                        if lease_expired:
                            # Only this already-validated new real round may
                            # recover an actual OFF watchdog status. A keeper
                            # and ordinary status never take this path.
                            current = self._send(4,require_ok=False,_delta_recover_idle_watchdog=True)
                        else:
                            current = self._send(4,require_ok=False)
                        self._fresh(current)
                        if current.requested_duty_permille:
                            raise LinkError('new compound ARM requires actual OFF')
                        # MCU lease expiry clears its normalized speed. Sync
                        # only from the actual OFF reply, never from a cached
                        # armed reply or the host's elapsed-time estimate.
                        self.delta_speed_norm = self.motor_duty = 0
                        self._fresh(self._send(1,deadline_ms=min(deadline,source_deadline)))
                    else:
                        self._fresh(current)
                speed = max(0,min(1000,self.delta_speed_norm+kwargs['speed_delta_permille']))
                if flags == VALID and speed and not self.allow_motor:
                    raise LinkError('motor permission required')
                reply, write_started_ms = self._compound_exchange(encode_delta,min(deadline,source_deadline),**kwargs)
                if flags == VALID:
                    self._fresh(reply)
                    if not reply.armed or reply.requested_duty_permille != speed_to_pwm(speed):
                        raise LinkError('compound accepted output mismatch')
                    self.delta_speed_norm = speed
                    self.delta_source_deadline_ms = source_deadline
                    self.delta_active = True
                    self.prepared_active = False
                else:
                    if reply.armed or reply.requested_duty_permille:
                        raise LinkError('PAUSE/STOP did not remove drive')
                    self.delta_active = False
                    self.delta_speed_norm = 0
                    self.delta_source_deadline_ms = None
                    self.prepared_active = False
                self.delta_run_id,self.delta_command_seq = run,cmd
                if flags & STOP:
                    # The actual compound STOP reply is the terminal device
                    # receipt; the existing SingleStop layer reuses it on EOF.
                    self.terminal = self.stop_attempted = True
                    self.stop_reply = reply
            self.delta_reply = reply
            self.motor_duty = reply.requested_duty_permille
            self.motor_speed_pct = self.delta_speed_norm/10
            self.delta_lease_deadline_ms = write_started_ms+lease if self.delta_active else None
            if self.clock_ms() >= deadline or (self.delta_active and self.clock_ms() >= self.delta_source_deadline_ms):
                raise LinkError('original request/source expired during compound exchange')
            return self._record_compound(reply,op,cmd,run)
        except Exception:
            self.failed = True
            try:self.stop()
            except Exception:pass
            raise

    def _reject_mixed_mode(self):
        self.failed = True
        try:self.stop()
        finally:raise LinkError('legacy motion cannot replace a compound control round')
