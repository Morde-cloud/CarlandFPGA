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

    def delta(self, command_seq, run_id, yaw_delta_cd, pitch_delta_cd, speed_delta_permille,
              *, move_ms=500, lease_ms=300, flags=1, source_valid_for_ms):
        return self._call('delta', command_seq=command_seq, run_id=run_id,
            yaw_delta_cd=yaw_delta_cd, pitch_delta_cd=pitch_delta_cd,
            speed_delta_permille=speed_delta_permille, move_ms=move_ms,
            lease_ms=lease_ms, flags=flags, source_valid_for_ms=source_valid_for_ms)

    def delta_keepalive(self, command_seq, run_id, *, lease_ms=300):
        return self._call('delta_keepalive',command_seq=command_seq,run_id=run_id,lease_ms=lease_ms)

    def startup_prepare(self, run_id, initial_speed_permille, move_ms=500):
        return self._call('startup_prepare', run_id=run_id,
                          initial_speed_permille=initial_speed_permille, move_ms=move_ms)

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
    def delta(self, command_seq, run_id, yaw_delta_cd, pitch_delta_cd, speed_delta_permille,
              *, move_ms=500, lease_ms=300, flags=1, source_valid_for_ms):
        return self.client.call(dict(op='delta',command_seq=command_seq,run_id=run_id,
            yaw_delta_cd=yaw_delta_cd,pitch_delta_cd=pitch_delta_cd,
            speed_delta_permille=speed_delta_permille,move_ms=move_ms,lease_ms=lease_ms,
            flags=flags,source_valid_for_ms=source_valid_for_ms))
    def delta_keepalive(self, command_seq, run_id, *, lease_ms=300):
        return self.client.call(dict(op='delta_keepalive',command_seq=command_seq,run_id=run_id,lease_ms=lease_ms))
    def startup_prepare(self, run_id, initial_speed_permille, move_ms=500):
        return self.client.call(dict(op='startup_prepare', run_id=run_id,
            initial_speed_permille=initial_speed_permille, move_ms=move_ms))
    def pose(self, *args, **kwargs):return self.client.pose(*args, **kwargs)
    def motor(self, speed_pct):return self.client.motor(speed_pct)
    def keepalive(self):return self.client.call({'op':'keepalive'})
    def stop(self):return self.client.call({'op':'stop'})
