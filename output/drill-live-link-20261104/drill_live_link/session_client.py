"""Reuse MTR4/CRC/journal unchanged. No port, SSH or process opens on import."""
from pathlib import Path
import sys
import threading

BASELINE = Path(__file__).resolve().parents[1]/'baseline_mtr4'
sys.path.insert(0, str(BASELINE))
from motor_runtime.variable_session import VariableDisplaySession
from fpga_link.session import SequenceJournal


class SessionClient:
    """Transport is already exclusively owned by caller. One IO thread only."""
    def __init__(self, session):
        self.session = session
        self._owner = threading.get_ident()

    def _call(self, op, **fields):
        if threading.get_ident() != self._owner:
            raise RuntimeError('ONE_UART_OWNER')
        s = self.session
        return s.handle(dict(op=op,session=s.session_id,request_id=s.request_id+1,
                             expires_ms=s.clock_ms()+500,**fields))

    def pose(self, yaw_deg, pitch_deg, *, move_ms=500, source_seq=0, observation_seq=0):
        return self._call('pose',yaw_deg=yaw_deg,pitch_deg=pitch_deg,move_ms=move_ms,
                          source_seq=source_seq,observation_seq=observation_seq)

    def motor(self, speed_pct):
        return self._call('motor',speed_pct=speed_pct)

    def keepalive(self):
        return self._call('keepalive')

    def stop(self):
        return self._call('stop')


class SshClientAdapter:
    """A supplies its already opened/owned SshDisplayClient, keepalive=False.

    This module never opens SSH/PYNQ. Its caller must call Follower.tick while
    source fresh; a background keepalive must not outlive actual source validity.
    """
    def __init__(self, client):
        if client.keepalive:
            raise ValueError('Disable independent background lease renewal')
        self.client = client
    def pose(self, *args, **kwargs):return self.client.pose(*args, **kwargs)
    def motor(self, speed_pct):return self.client.motor(speed_pct)
    def keepalive(self):return self.client.call({'op':'keepalive'})
    def stop(self):return self.client.call({'op':'stop'})
