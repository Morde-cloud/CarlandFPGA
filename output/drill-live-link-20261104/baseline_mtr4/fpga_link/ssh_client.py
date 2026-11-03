"""PC application adapter over existing SSH; G3507 is not attached to a PC COM port."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import queue
import shlex
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fpga_link.session import DEFAULT_MOVE_MS, LinkError, strict_json


class SshDisplayClient:
    """Caller supplies an explicit SSH argv with an already trusted board host.

    There is no reconnect or command replay. Source in the board command must
    match the real product execution path; this adapter does not grant that path.
    """
    def __init__(self, argv, *, timeout=1.5, keepalive=False):
        self.argv, self.timeout, self.keepalive = list(argv), timeout, keepalive
        self.inbox = queue.Queue(maxsize=64)
        self.lock = threading.Lock()
        self.closed = threading.Event()
        self.rid = 0
        self.failed = False
        self.process = None

    def _read(self):
        try:
            while True:
                line = self.process.stdout.readline(8193)
                if not line:
                    raise LinkError('SSH closed; reconnect is manual, old poses are not replayed')
                if len(line) > 8192:
                    raise LinkError('oversized SSH reply')
                self.inbox.put_nowait(strict_json(line))
        except Exception as exc:
            try:
                self.inbox.put_nowait(exc)
            except queue.Full:
                self.failed = True

    def _receive(self, timeout):
        try:
            result = self.inbox.get(timeout=timeout)
        except queue.Empty as exc:
            raise LinkError('SSH reply timeout; command outcome unknown, never retried') from exc
        if isinstance(result, Exception):
            raise result
        if not isinstance(result,dict):
            raise LinkError('SSH reply object required')
        if result.get('event') == 'error':
            raise LinkError(result.get('error','board refused'))
        return result

    def open(self):
        if self.process is not None:
            raise LinkError('client already opened')
        self.process = subprocess.Popen(self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=None, text=True, encoding='utf8', bufsize=1)
        self.reader = threading.Thread(target=self._read,daemon=True)
        self.reader.start()
        try:
            ready = self._receive(45)
            if ready.get('event') != 'ready' or not isinstance(ready.get('session'),str):
                raise LinkError('board ready handshake required')
            self.session_id = ready['session']
            self.board_ms, self.started = ready['clock_ms'], time.monotonic()
            if self.keepalive:
                self.heartbeat = threading.Thread(target=self._heartbeat,daemon=True)
                self.heartbeat.start()
            return ready
        except Exception:
            self.failed = True
            self.close()
            raise

    def call(self, command):
        with self.lock:
            if self.closed.is_set() or self.failed:
                raise LinkError('SSH client closed/faulted; no retry')
            if not isinstance(command,dict) or set(command) & {'session','request_id','expires_ms'}:
                raise LinkError('pass only command fields, not session metadata')
            self.rid += 1
            packet = dict(command, session=self.session_id, request_id=self.rid,
                          expires_ms=self.board_ms+int((time.monotonic()-self.started)*1000)+500)
            try:
                self.process.stdin.write(json.dumps(packet, allow_nan=False)+'\n')
                self.process.stdin.flush()
                reply = self._receive(self.timeout)
                if reply.get('session') != self.session_id or reply.get('request_id') != self.rid:
                    raise LinkError('SSH session/request mismatch')
                return reply
            except Exception:
                self.failed = True
                # EOF reaches board's finally STOP when SSH remains connected;
                # otherwise MCU 500ms watchdog prevents further commands.
                try:
                    self.process.stdin.close()
                except Exception:
                    pass
                raise

    def _heartbeat(self):
        while not self.closed.wait(0.1):
            try:
                self.call({'op':'keepalive'})  # Renews active motor only; never ARM/pose replay.
            except Exception:
                return

    def pose(self, yaw_deg, pitch_deg, *, move_ms=DEFAULT_MOVE_MS, source_seq=0, observation_seq=0):
        return self.call({'op':'pose','yaw_deg':yaw_deg,'pitch_deg':pitch_deg,
                          'move_ms':move_ms,'source_seq':source_seq,'observation_seq':observation_seq})

    def motor(self, speed_pct):
        """0 stops; positive0..100 maps display PWM25..75%, not measured RPM."""
        return self.call({'op':'motor','speed_pct':speed_pct})

    def close(self):
        if self.closed.is_set():
            return
        if self.process is not None and not self.failed and hasattr(self,'session_id'):
            try:
                self.call({'op':'stop'})
            except Exception:
                pass
        self.closed.set()
        if self.process is not None:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            if hasattr(self,'reader'):
                self.reader.join(timeout=1)
            if not hasattr(self,'reader') or not self.reader.is_alive():
                self.process.stdout.close()

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host', required=True, help='explicit trusted SSH host or existing SSH config alias')
    ap.add_argument('--remote-root', default='/home/xilinx/drill-display')
    ap.add_argument('--python', default='/usr/local/share/pynq-venv/bin/python')
    ap.add_argument('--source', choices=['MANUAL','PC_DIRECT','FPGA_OUTPUT'], default='MANUAL')
    ap.add_argument('--initialize-sequence', type=int)
    ap.add_argument('--load-overlay', action='store_true')
    ap.add_argument('--allow-hardware', action='store_true')
    args = ap.parse_args()
    if not args.allow_hardware:
        ap.error('remote board operation requires --allow-hardware')
    if args.host.startswith('-'):
        ap.error('host must not be an SSH option')
    remote = [args.python,'-u',args.remote_root+'/fpga_link/bridge_stdio.py',
              '--profile',args.remote_root+'/fpga_link/profile.json',
              '--sequence-state',args.remote_root+'/fpga_link/state/mcu-sequence.json',
              '--source',args.source,'--allow-hardware']
    if args.initialize_sequence is not None:
        remote += ['--initialize-sequence',str(args.initialize_sequence)]
    if args.load_overlay:
        remote += ['--load-overlay']
    argv = ['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',args.host,shlex.join(remote)]
    client = SshDisplayClient(argv, keepalive=True)
    try:
        print(json.dumps(client.open(),ensure_ascii=False),flush=True)
        for line in sys.stdin:
            if line.strip():
                print(json.dumps(client.call(strict_json(line)),ensure_ascii=False),flush=True)
        return 0
    except (Exception,KeyboardInterrupt) as exc:
        print(json.dumps({'event':'error','error':str(exc),'retry':False}),flush=True)
        return 1
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
