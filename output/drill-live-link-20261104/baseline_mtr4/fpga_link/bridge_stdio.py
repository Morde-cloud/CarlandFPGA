"""One foreground SSH stdio session to PYNQ PL UART. No background service."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import select
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fpga_link.session import DisplaySession, LinkError, SequenceJournal, strict_json
from motor_runtime.variable_session import VariableDisplaySession
from fpga_link.uartlite import UartLite


def verified_profile(path):
    path = Path(path).resolve()
    p = strict_json(path.read_text(encoding='utf8'))
    if p.get('hardware_confirmed') is not True:
        raise LinkError('profile is an unconfirmed preparation; confirm actual wiring before board use')
    if (p.get('uart_ip'), p.get('base_address'), p.get('address_range'), p.get('baud')) != ('mcu_uart', 0x43C00000, 65536, 115200):
        raise LinkError('unexpected UARTLite identity/address/baud profile')
    if p.get('pins') != {'fpga_tx':'PMODA1/Y18','fpga_rx':'PMODA2/Y19','mcu_tx':'PB6','mcu_rx':'PB7','ground':'PMODA5/GND'}:
        raise LinkError('unexpected physical pin profile')
    artifacts = {}
    for key in ('bit','hwh'):
        record = p[key]
        file = (path.parent/record['path']).resolve()
        if file.suffix != '.' + key or hashlib.sha256(file.read_bytes()).hexdigest() != record['sha256']:
            raise LinkError('missing or changed matched overlay artifact: ' + key)
        artifacts[key] = file
    if artifacts['bit'].with_suffix('.hwh') != artifacts['hwh']:
        raise LinkError('same-name matched BIT/HWH pair required')
    return p, artifacts


def emit(value):
    print(json.dumps(value, ensure_ascii=False, allow_nan=False), flush=True)


def stop_quietly(session):
    try:
        session.stop()
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--profile', type=Path, required=True)
    ap.add_argument('--sequence-state', type=Path, required=True)
    ap.add_argument('--initialize-sequence', type=int)
    ap.add_argument('--source', choices=['MANUAL','PC_DIRECT','FPGA_OUTPUT'], default='MANUAL')
    ap.add_argument('--allow-hardware', action='store_true')
    ap.add_argument('--load-overlay', action='store_true')
    ap.add_argument('--idle-timeout', type=float, default=2.0)
    args = ap.parse_args()
    if not args.allow_hardware:
        ap.error('board MMIO requires --allow-hardware; importing/testing stays offline')
    if not 0.5 <= args.idle_timeout <= 10:
        ap.error('idle-timeout must be 0.5..10 seconds')
    session = None
    try:
        profile, files = verified_profile(args.profile)
        import fcntl  # Board Linux only, imported after explicit hardware gate.
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            from pynq import Overlay
        with contextlib.ExitStack() as stack:
            lock = stack.enter_context((args.profile.resolve().parent/'.mcu-uart.lock').open('a'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            journal = SequenceJournal(args.sequence_state, args.initialize_sequence)
            # Explicit loading replaces the entire PL design, so standalone use
            # and later product-overlay integration have separate acceptance.
            with contextlib.redirect_stdout(sys.stderr):
                overlay = Overlay(str(files['bit']), download=args.load_overlay)
            if not overlay.is_loaded():
                raise LinkError('verified overlay is not currently loaded; no MMIO attempted')
            descriptor = overlay.ip_dict.get('mcu_uart')
            if not descriptor or descriptor.get('type') != 'xilinx.com:ip:axi_uartlite:2.0' or descriptor.get('phys_addr') != profile['base_address'] or descriptor.get('addr_range') != profile['address_range']:
                raise LinkError('actual HWH IP identity or address mismatch; no MMIO attempted')
            uart = UartLite(overlay.mcu_uart.mmio)
            uart.reset_fifos()
            session = VariableDisplaySession(uart, journal, source=args.source,
                                             allow_motor=profile.get('motor_enabled') is True)
            # LIFO cleanup sends STOP while the UART owner lock is still held.
            stack.callback(stop_quietly, session)
            emit(session.connect())  # STOP/STATUS only, never ARM or SET.
            last_input = time.monotonic()
            buffered = bytearray()
            import os
            while True:
                remaining = args.idle_timeout - (time.monotonic()-last_input)
                if remaining <= 0:
                    raise LinkError('SSH input idle; stopping without target replay')
                readable, _, _ = select.select([sys.stdin.buffer], [], [], min(remaining,0.05))
                if not readable:
                    continue
                data = os.read(sys.stdin.fileno(),4096)
                if not data:
                    break
                buffered.extend(data)
                if len(buffered) > 4096:
                    raise LinkError('bounded input exceeded; stop instead of accumulating targets')
                while b'\n' in buffered:
                    line, _, rest = buffered.partition(b'\n')
                    buffered[:] = rest
                    last_input = time.monotonic()
                    if not line.strip():
                        continue
                    request = strict_json(line.decode('utf8'))
                    emit(session.handle(request))
    except (Exception, KeyboardInterrupt) as exc:
        emit({'event':'error','error':str(exc),'retry':False,'motor_output':False})
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
