"""Foreground display follower. Dry-run by default; no automatic board startup."""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import json
import os
import queue
import sys
import threading
import time

from drill_live_link import FollowMapper, Follower, FollowError, Limits
from drill_live_link.session_client import BASELINE, SequenceJournal, SessionClient, VariableDisplaySession


def strict_json(raw):
    def pairs(xs):
        d = {}
        for k,v in xs:
            if k in d:raise ValueError('DUPLICATE_JSON_KEY')
            d[k] = v
        return d
    def bad(_):raise ValueError('NONFINITE_JSON')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad)


class DryClient:
    """Explicit synthetic ACK sink, no device/measurements/physical execution."""
    def __init__(self, source):self.source,self.seq,self.duty,self.armed = source,0,0,False
    def record(self, event):
        self.seq += 1
        return dict(event=event,declared_source=self.source,simulation=True,measured_rpm=None,
            raw_feedback_is_measurement=False,uart_ack_is_not_arrival=True,
            status=dict(seq=self.seq,result_code=0,requested_duty_permille=self.duty,armed=self.armed,
                        last_joho_error=0,yaw_feedback=dict(fresh=True,synthetic=True),
                        pitch_feedback=dict(fresh=True,synthetic=True)))
    def pose(self,*args,**kwargs):self.armed=True;return self.record('pose')
    def motor(self,speed_pct):
        self.duty = 0 if speed_pct == 0 else int(round(250+5*speed_pct))
        self.armed = bool(self.duty)
        return self.record('motor')
    def keepalive(self):return self.record('keepalive')
    def stop(self):self.duty=0;self.armed=False;return self.record('stop')


class JournalTransport:
    def __init__(self, transport, journal):self.transport,self.journal = transport,journal
    def write_frame(self, frame):
        self.journal(dict(event='UART_WRITE_INTENT',bytes_hex=frame.hex()))
        self.transport.write_frame(frame)  # No retry after any possible write.
    def read_frame(self, timeout):
        raw = self.transport.read_frame(timeout)
        self.journal(dict(event='UART_READ_RETURNED',bytes_hex=None if raw is None else raw.hex()))
        return raw


def hardware_gate(profile, args):
    p = strict_json(Path(profile).read_bytes())
    if not (args.allow_hardware and args.port == 'COM9' and p.get('hardware_confirmed') is True
            and p.get('observer_present') is True and p.get('motion_space_clear') is True
            and p.get('control_owner') == 'PC_COM9_ONLY'
            and p.get('PB6_to_J101_XDS_TX') is True and p.get('PB7_to_J101_XDS_RX') is True
            and p.get('gimbal_power_confirmed') is True and p.get('no_other_serial_or_SWD_executor') is True):
        raise ValueError('CURRENT_OBSERVER_WIRING_AND_EXCLUSIVE_CONTROL_NOT_CONFIRMED')
    if args.enable_motor and p.get('motor_VM_connected_and_observed') is not True:
        raise ValueError('MOTOR_VM_AND_OBSERVER_NOT_CONFIRMED')
    if args.initialize_sequence is None or not args.mcu_observation:
        raise ValueError('ACTUAL_CURRENT_MCU_OBSERVATION_AND_NEW_SEQUENCE_REQUIRED')
    observed = strict_json(Path(args.mcu_observation).read_bytes())
    final = observed.get('final', {})
    if not (observed.get('image_sha256') == '69c5c57e6f896b879bb41a73d4f114180e11a9f16a8894eae6b035893848841f'
            and final.get('signature') == '0x4d545234' and final.get('state') == 3
            and type(final.get('last_seq')) is int and args.initialize_sequence == final['last_seq']+1
            and final.get('armed') in (0,False) and final.get('bus_status') == 0
            and final.get('yaw_feedback_seen') and final.get('pitch_feedback_seen')
            and final.get('motor',{}).get('duty') == 0 and final.get('motor',{}).get('active') == 0
            and p.get('same_boot_since_observation') is True):
        raise ValueError('CURRENT_MTR4_BOOT_SEQUENCE_OFF_STATE_NOT_ESTABLISHED')
    # These attestations are caller prerequisites, not authentication from JSON.
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id',required=True)
    ap.add_argument('--operation',required=True)
    ap.add_argument('--source',choices=['MANUAL','PC_DIRECT','FPGA_OUTPUT'],required=True)
    ap.add_argument('--reference',type=float,nargs=4,required=True,metavar=('X','Y','Z','W'))
    ap.add_argument('--transport',choices=['dry-run','simulator','serial'],default='dry-run')
    ap.add_argument('--enable-motor',action='store_true')
    ap.add_argument('--maximum-duty',type=int,default=750)
    ap.add_argument('--same-host-qpc',action='store_true')
    ap.add_argument('--allow-hardware',action='store_true')
    ap.add_argument('--profile',type=Path)
    ap.add_argument('--port',choices=['COM9'])
    ap.add_argument('--mcu-observation',type=Path)
    ap.add_argument('--sim-exe',type=Path,help='Explicit Windows real-C simulator, used only in simulator mode')
    ap.add_argument('--initialize-sequence',type=int)
    ap.add_argument('--evidence-root',type=Path,default=Path(__file__).parent/'evidence')
    args = ap.parse_args()
    if not args.operation or not all(c.isalnum() or c in '-_' for c in args.operation):ap.error('NEW_OPERATION_ID')
    if not args.same_host_qpc:ap.error('Explicit --same-host-qpc required; raw A/B absolute clocks cannot be mixed')
    mapper = FollowMapper(args.run_id,args.source,args.reference,Limits(maximum_duty_permille=args.maximum_duty))
    out = args.evidence_root/args.operation;out.mkdir(parents=True,exist_ok=False)
    log = (out/'events.jsonl').open('xb',buffering=0)
    def record(v):
        log.write((json.dumps(dict(host_qpc_ns=time.perf_counter_ns(),**v),allow_nan=False)+'\n').encode())
        os.fsync(log.fileno())
    transport = follower = None
    outcome = dict(operation_id=args.operation,run_id=args.run_id,source=args.source,
                   transport=args.transport,physical=args.transport=='serial',measured_rpm=None,
                   firmware_programmed=False,FPGA_operated=False,product_accepted=False,status='prepared')
    try:
        client = DryClient(args.source)
        if args.transport != 'dry-run':
            from pc.transport import SerialTransport, SimulatorTransport
            if args.transport == 'serial':
                if args.profile is None:raise ValueError('VERIFIED_CURRENT_HARDWARE_PROFILE_REQUIRED')
                hardware_gate(args.profile,args)
                transport = SerialTransport(args.port,hardware_confirmed=True)
                initial = args.initialize_sequence
            else:
                path = args.sim_exe
                if path is None:raise ValueError('EXPLICIT_REAL_C_SIMULATOR_PATH_REQUIRED')
                outcome['simulator_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                transport = SimulatorTransport(path);initial=1
            ledger = SequenceJournal(out/'sequence.json',initial)
            transport.open()
            session = VariableDisplaySession(JournalTransport(transport,record),ledger,source=args.source,
                simulation=args.transport=='simulator',allow_motor=args.enable_motor,
                physical_path='synthetic real-C simulator' if args.transport=='simulator' else 'B PC COM9 -> G3507 UART1')
            ready = session.connect();record(dict(event='LINK_READY_STOP_STATUS_ONLY',reply=ready))
            client = SessionClient(session)
        follower = Follower(client,mapper,motor_enabled=args.enable_motor)
        inbox = queue.Queue(maxsize=1);eof=object()
        def publish(item):
            try:inbox.put_nowait(item)
            except queue.Full:
                try:inbox.get_nowait()
                except queue.Empty:pass
                inbox.put_nowait(item)
        def read():
            try:
                while True:
                    raw = sys.stdin.buffer.readline(32769)
                    if not raw:publish(eof);return
                    if len(raw)>32768 or not raw.endswith(b'\n'):raise ValueError('BOUNDED_SOURCE_LINE')
                    publish(strict_json(raw))
            except BaseException as e:publish(e)
        threading.Thread(target=read,name='display-source-reader',daemon=True).start()
        while not follower.stopped:
            try:item=inbox.get(timeout=.02)
            except queue.Empty:item=None
            if item is eof:record(dict(event='SOURCE_EOF_STOP'));break
            if isinstance(item,BaseException):raise item
            if item is not None:
                target = follower.push(item)
                record(dict(event='ACCEPTED_DISPLAY_TARGET',target=dataclasses.asdict(target),
                            clock_scope='sameHostQPC engineering assumption, not clock qualification'))
            if not follower.stopped:
                for ack in follower.tick():record(dict(event='DEVICE_REPLY_NOT_ARRIVAL',reply=ack))
        outcome['status']='foreground_follow_ended'
    except BaseException as e:
        outcome.update(status='failed_no_replay',error_type=type(e).__name__,error=str(e))
    finally:
        if follower is not None:
            try:outcome['stop_reply']=follower.stop('runtime_exit') or follower.stop_reply
            except Exception as e:outcome['stop_unknown']=str(e)
            if follower.stop_error is not None:outcome['stop_unknown']=follower.stop_error
        if transport is not None:transport.close()
        outcome['closed_at_utc']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
        (out/'RESULT.json').write_text(json.dumps(outcome,indent=2)+'\n',encoding='utf8',newline='\n');log.close()
    print(json.dumps(outcome,ensure_ascii=False),flush=True)
    return 0 if outcome['status']=='foreground_follow_ended' and 'stop_unknown' not in outcome else 1


if __name__ == '__main__':raise SystemExit(main())
