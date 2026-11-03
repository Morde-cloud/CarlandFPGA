"""Stateful command sequencing and honest status projection for the PC bridge."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .codec import (
    Command,
    Reply,
    UINT32_MAX,
    centidegrees_to_degrees,
    decode_reply,
    degrees_to_centidegrees,
    encode_command,
)


class BridgeError(RuntimeError):
    """A protocol-sequencing or bounded-pending rule was violated."""


@dataclass(frozen=True, slots=True)
class PendingCommand:
    command: Command
    seq: int
    sent_at: float
    deadline: float


class WireSession:
    """Assign no-wrap sequences and match each reply to one sent command."""

    def __init__(
        self,
        transport: Any,
        *,
        reply_timeout: float = 1.0,
        max_pending: int = 32,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if reply_timeout <= 0 or reply_timeout > 60:
            raise BridgeError("reply_timeout must be in (0, 60] seconds")
        if max_pending < 1 or max_pending > 256:
            raise BridgeError("max_pending must be in [1, 256]")
        self.transport = transport
        self.reply_timeout = reply_timeout
        self.max_pending = max_pending
        self.clock = clock
        self._next_seq = 1
        self._pending: dict[int, PendingCommand] = {}
        self.last_source = "PC_DIRECT"

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def send(self, command: Command) -> int:
        if not isinstance(command, Command):
            raise BridgeError("send requires a validated Command")
        if command.op != "stop" and len(self._pending) >= self.max_pending:
            raise BridgeError("too many commands awaiting replies")
        if self._next_seq > UINT32_MAX:
            raise BridgeError("command sequence exhausted; no wrap or replay is allowed")

        seq = self._next_seq
        frame = encode_command(command, seq)
        self.transport.write_frame(frame)
        now = self.clock()
        self._pending[seq] = PendingCommand(
            command=command,
            seq=seq,
            sent_at=now,
            deadline=now + self.reply_timeout,
        )
        self._next_seq += 1
        self.last_source = command.source
        return seq

    def poll(self, timeout: float) -> tuple[Command, int, Reply] | None:
        frame = self.transport.read_frame(timeout)
        if frame is None:
            return None
        reply = decode_reply(frame)
        pending = self._pending.pop(reply.seq, None)
        if pending is None:
            raise BridgeError(f"unexpected reply sequence {reply.seq}")
        return pending.command, pending.seq, reply

    def pending_stop_seq(self) -> int | None:
        for seq, pending in reversed(self._pending.items()):
            if pending.command.op == "stop":
                return seq
        return None

    def first_expired(self, now: float | None = None) -> PendingCommand | None:
        current = self.clock() if now is None else now
        for pending in self._pending.values():
            if current >= pending.deadline:
                return pending
        return None

    def pending_summary(self) -> list[dict[str, Any]]:
        return [
            {"seq": pending.seq, "op": pending.command.op}
            for pending in self._pending.values()
        ]


def _feedback_record(feedback: Any) -> dict[str, Any]:
    return {
        "raw_position": feedback.raw_position,
        "age_ms": feedback.age_ms,
        "fresh": feedback.fresh,
    }


def status_record(
    command: Command,
    command_seq: int,
    reply: Reply,
    transport: Any,
) -> dict[str, Any]:
    """Return output that keeps commands, raw feedback, and measurements distinct."""

    record = transport.description()
    record.update(
        {
            "schema": 1,
            "event": "status",
            "protocol": "physical-display-v1",
            "op": command.op,
            "command_seq": command_seq,
            "reply_seq": reply.seq,
            "request": command.request_record(),
            "armed": reply.armed,
            "result": {"code": reply.result_code, "name": reply.result},
            "targets": {
                "semantics": "last accepted command; not measured",
                "yaw_centideg": reply.target_yaw_cd,
                "pitch_centideg": reply.target_pitch_cd,
                "yaw_deg": centidegrees_to_degrees(reply.target_yaw_cd),
                "pitch_deg": centidegrees_to_degrees(reply.target_pitch_cd),
                "duty_permille": reply.requested_duty_permille,
                "direction": "forward" if reply.direction == 0 else "reverse",
            },
            "feedback": {
                "semantics": "last raw bus positions; not converted to angles",
                "yaw": _feedback_record(reply.yaw_feedback),
                "pitch": _feedback_record(reply.pitch_feedback),
            },
            "active_source": reply.active_source,
            "outputs": {
                "motor_compiled_enabled": reply.motor_output_compiled_enabled,
                "gimbal_compiled_enabled": reply.gimbal_output_compiled_enabled,
            },
            "last_joho_error": reply.last_joho_error,
            "servo_error_count": reply.servo_error_count,
            "measured_rpm": None,
            "actuation": "simulated" if transport.simulation else "external_unverified",
        }
    )
    return record


def executed_pose_command(
    yaw_deg: Any,
    pitch_deg: Any,
    provenance: str,
    *,
    duty_permille: int = 0,
    direction: int = 0,
    move_ms: int = 100,
    source_seq: int = 0,
    observation_seq: int = 0,
) -> Command:
    """Adapter seam for an already executed pose supplied by the product owner.

    ``yaw_deg`` and ``pitch_deg`` are pose degrees that the owner has already
    converted to the calibrated-neutral target frame.  CONTROL3D ``yaw_q`` and
    ``pitch_q`` are angular rates and cannot be passed here as angles.  A
    ``model_candidate`` is not executed motion and is rejected as provenance.
    This function creates a command only; it does not transmit or arm anything.
    """

    if provenance not in ("PC_DIRECT", "FPGA_OUTPUT"):
        raise ValueError(
            "provenance must be PC_DIRECT or FPGA_OUTPUT after an actual execution gate"
        )
    return Command(
        op="set",
        source=provenance,
        yaw_cd=degrees_to_centidegrees(yaw_deg, "executed yaw_deg"),
        pitch_cd=degrees_to_centidegrees(pitch_deg, "executed pitch_deg"),
        duty_permille=duty_permille,
        direction=direction,
        move_ms=move_ms,
        source_seq=source_seq,
        observation_seq=observation_seq,
    )


__all__ = [
    "BridgeError",
    "PendingCommand",
    "WireSession",
    "executed_pose_command",
    "status_record",
]
