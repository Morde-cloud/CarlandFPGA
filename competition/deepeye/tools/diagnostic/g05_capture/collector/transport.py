"""Bounded private G05 transport. Dependencies perform at most one native call.

Post-call timing detects a slow return; Python cannot interrupt a hung kernel
MMIO call. No threads, signal timeouts, automatic retries or command replay.
All fake transports are software controls, never board proof.
"""
import math
import time


class TransportError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise TransportError(message)


def word(value):
    require(type(value) is int and 0 <= value < 2**32, 'read32 returned non-u32')
    return value


class Bus:
    def __init__(self, read32, write32, event, clock, *, max_calls=20000, seconds=30):
        require(type(max_calls) is int and 100 <= max_calls <= 20000, 'call bound')
        require(type(seconds) is int and 1 <= seconds <= 180, 'duration bound')
        self.read32, self.write32, self.event, self.clock = read32, write32, event, clock
        self.started = self.last_time = clock()
        self.deadline = self.started + seconds
        self.max_calls, self.calls = max_calls, 0

    def now(self):
        value = self.clock()
        require(value >= self.last_time, 'monotonic clock moved backwards')
        self.last_time = value
        return value

    def call(self, offset, value=None):
        before = self.now()
        require(before < self.deadline and self.calls < self.max_calls, 'total time/call budget exhausted')
        self.calls += 1
        self.event('read32_attempt' if value is None else 'write32_attempt', offset=offset, value=value, call=self.calls)
        result = self.read32(offset) if value is None else self.write32(offset, value)
        after = self.now()
        if value is None:
            result = word(result)
        self.event('read32_returned' if value is None else 'write32_returned', offset=offset, value=result if value is None else value, call=self.calls)
        require(after - before <= 0.25 and after < self.deadline, 'MMIO call returned after budget')
        return result

    def r(self, offset):
        return self.call(offset)

    def w(self, offset, value):
        return self.call(offset, word(value))

    def u64(self, offset):
        hi = self.r(offset + 4)
        lo = self.r(offset)
        require(self.r(offset + 4) == hi, 'split64 register changed')
        return lo | (hi << 32)


def stop_once(read32, write32, state, *, clock=time.monotonic, sleep=time.sleep):
    """Raw STOP is attempted before any fallible journal/output serialization."""
    if state.get('write_attempted',False):
        return state
    state.update(attempted=True, confirmed=False, write_attempted=False, write_returned=False, reads=[],
                 timing_errors=[],bounded_time_verified=False,
                 physical_outputs_observed=False, observation='running/pending/latch status only')
    last=None

    def sample(label):
        nonlocal last
        try:
            value=clock()
            require(type(value) in (int,float) and math.isfinite(value) and value>=0,'nonfinite/invalid clock')
            require(last is None or value>=last,'clock regression')
            last=value
            return value
        except BaseException as error:
            state['timing_errors'].append(label+': '+type(error).__name__+': '+str(error))
            return None

    # GC01: timing instrumentation must never suppress the single raw STOP.
    # Its failure is evidence, not permission to skip the hardware write.
    started=sample('before_STOP')
    try:
        state['write_attempted']=True
        write32(0x0c, 3)  # Never retried, including when this call raises.
        state['write_returned'] = True
        returned=sample('after_STOP')
        if not state['timing_errors']:
            require(returned-started<=0.25,'STOP write returned late')
        for _ in range(64):
            before=sample('before_status')
            if not state['timing_errors']:
                require(before-started<1.0,'STOP status deadline')
            status = word(read32(8))
            fault = word(read32(0x10))
            state['reads'].append({'status': status, 'fault': fault})
            after=sample('after_status')
            require(not state['timing_errors'],'STOP timing unknown; cleanup cannot be confirmed')
            require(after-before<=0.25 and after-started<1.0,'STOP read returned late')
            require(status & ~0x7f == 0, 'STOP unknown status')
            if status & 2 and status & 0x7c == 0:
                state.update(confirmed=True,engine_running_zero=True,bounded_time_verified=True)
                break
            sleep(0.001)
        require(state['confirmed'], 'STOP retirement/output-dead status not confirmed')
    except BaseException as error:
        state['error'] = type(error).__name__ + ': ' + str(error)
    return state


def run_transport(protocol, fixture, read32, write32, event, record_sink, *,
                  clock=time.monotonic, sleep=time.sleep, total_seconds=30,
                  max_polls=4096, max_calls=20000, cleanup=None):
    """One fixed command list, one captured record per command, one final STOP.

    event and record_sink may raise. Cleanup remains mandatory after any such
    failure. Return code0 requires every requested capture AND confirmed STOP.
    """
    cleanup = cleanup if cleanup is not None else {'attempted': False, 'confirmed': False}
    result = {'status': 'failed', 'exit_code': 2, 'movement_authorized': False,
              'captures': [], 'primary_error': None, 'cleanup': cleanup,
              'automatic_replay': False, 'source_freshness_established': False}
    bus = None
    try:
        require(type(max_polls) is int and 1 <= max_polls <= 4096, 'poll bound')
        commands = tuple(protocol.validate_command(c) for c in fixture['commands'])
        require(1 <= len(commands) <= 16, 'capture count bound')
        require(all(a.command_id < b.command_id for a,b in zip(commands,commands[1:])), 'ordered commands required')
        require(len({c.profile for c in commands}) == 1, 'one profile per session')
        identity = protocol.identity_words(fixture['run_id'],fixture['nonce'],fixture['session'])
        bus = Bus(read32,write32,event,clock,max_calls=max_calls,seconds=total_seconds)
        event('mmio_session_entered', movement_authorized=False)
        require(bus.r(0) == protocol.MAGIC and bus.r(4) == 1, 'private magic/revision')
        require(bus.r(8) == 0 and bus.r(0x10) == 0 and bus.r(0x28) == 0, 'not fresh reset; no resume')
        for i,value in enumerate(identity):
            bus.w(0x100 + i*4,value)
        bus.w(0x0c,1)
        require(bus.r(8) == 1 and bus.r(0x10) == 0, 'BEGIN not bound idle')
        require(tuple(bus.r(0x100+i*4) for i in range(13)) == identity, 'BEGIN identity differs')
        polls, previous_seq, previous_applied = 0, 0, 0

        def live():
            nonlocal polls
            require(polls < max_polls, 'bounded poll count exhausted')
            polls += 1
            status, fault = bus.r(8), bus.r(0x10)
            require(status & ~0x7f == 0 and status & 1 and not status & 2, 'session retired/unbound/unknown status')
            require(fault == 0, 'device fault or TTL expiry')
            return status

        def wait(predicate):
            while True:
                status = live()
                if predicate(status):
                    return status
                sleep(0.001)

        for command in commands:
            require(live() & 0x68 == 0, 'cannot stage while pending/inflight/held')
            for i,value in enumerate(protocol.command_words(command)):
                bus.w(0x200+i*4,value)
            bus.w(0x0c,2)
            wait(lambda s: s & 0x4c == 4)
            require(bus.r(0x14) == command.command_id and bus.r(0x18) == command.tag, 'actual applied command/tag differs')
            applied = bus.u64(0x40)
            require(applied > previous_applied, 'actual application did not advance')
            previous_applied = applied
            wait(lambda s: s & 0x7c == 0x14)
            bus.w(0x0c,4)
            before_status, before_fault = bus.r(8), bus.r(0x10)
            before_identity = tuple(bus.r(0x100+i*4) for i in range(13))
            before_command = bus.r(0x14)
            record = tuple(bus.r(0x300+i*4) for i in range(32))
            after_status, after_fault = bus.r(8), bus.r(0x10)
            after_identity = tuple(bus.r(0x100+i*4) for i in range(13))
            after_command, held_sequence = bus.r(0x14), bus.r(0x300)
            decoded = protocol.validate_readback(identity_expected=identity,
                identity_before=before_identity,identity_after=after_identity,
                status_before=before_status,status_after=after_status,
                fault_before=before_fault,fault_after=after_fault,
                command_before=before_command,command_after=after_command,
                record=record,sequence_after=held_sequence,command=command)
            require(decoded['capture_seq'] > previous_seq, 'capture sequence did not strictly increase')
            require(decoded['applied_cycle'] == applied, 'application changed during capture')
            snapshot={'record':record,'decoded':decoded,'identity_before':before_identity,'identity_after':after_identity,
                      'status_before':before_status,'status_after':after_status,'fault_before':before_fault,
                      'fault_after':after_fault,'command_before':before_command,'command_after':after_command,
                      'held_sequence_after':held_sequence,'movement_authorized':False}
            record_sink(len(result['captures'])+1,snapshot)  # Durable before ACK.
            result['captures'].append(snapshot)
            previous_seq = decoded['capture_seq']
            bus.w(0x0c,5)
            wait(lambda s: not s & 0x20)
        event('all_requested_captures_complete', count=len(result['captures']))
    except BaseException as error:
        result['primary_error'] = type(error).__name__ + ': ' + str(error)
    finally:
        stop_once(read32,write32,cleanup,clock=clock,sleep=sleep)
        try:
            event('stop_cleanup', **cleanup)
        except BaseException as error:
            result['cleanup_log_error'] = type(error).__name__ + ': ' + str(error)
        if bus is not None:
            result['transport_calls'] = bus.calls
    if result['primary_error'] is None and cleanup['confirmed'] and 'cleanup_log_error' not in result:
        result.update(status='private_diagnostic_captures_complete',exit_code=0)
    return result
