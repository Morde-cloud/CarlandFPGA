#!/usr/bin/env python3
"""Pure B132 decoder for a latched G05P/layout-2 32-word capture.

This module performs no device I/O, actor authentication, receipt validation,
simulation, or motion authorization.  It decodes caller-supplied capture words
and compares available dimensions with a separately retained original record.
"""

import argparse
import json
import os
import sys
import tempfile


REQUEST_SCHEMA = "B132_G05P_CAPTURE_DECODE_REQUEST_V1"
RECORD_SCHEMA = "B132_ORIGINAL_RECORD_V1"
RESULT_SCHEMA = "B132_G05P_CAPTURE_DECODE_RESULT_V1"

G05P_MAGIC = 0x47303550
G05P_LAYOUT = 2
CLOCK_HZ = 50_000_000
TICK_NS = 20
FRAME_TICKS = 1_000_000
YAW_PITCH_BASE = 125_000
YAW_PITCH_STEP = 8
SPEED_BASE = 25_000
SPEED_STEP = 500
TTL_TICKS_PER_MS = 50_000
NEAR_TOLERANCE_TICKS = 1
Q_MIN = -15_000
Q_MAX = 15_000
SPEED_MAX = 20
TTL_MAX_MS = {1: 3_000, 2: 12_000}
U32_MAX = 0xFFFFFFFF
U64_MAX = 0xFFFFFFFFFFFFFFFF
MAX_REQUEST_BYTES = 262_144
MAX_PRESERVE_RAW_WORDS = 256
MAX_PRESERVED_INPUT_JSON_CHARS = 4_096

STATUS_BOUND = 0x01
STATUS_RETIRED_OR_HALTED = 0x02
STATUS_RUNNING = 0x04
STATUS_PENDING = 0x08
STATUS_LATEST_ELIGIBLE = 0x10
STATUS_LATCH_VALID = 0x20
STATUS_INFLIGHT = 0x40
STATUS_DEFINED_MASK = 0x7F

PROFILE_SPEC = {
    1: {
        "name": "FAST_9600",
        "target_speed_nm_s_per_code": 12_500_000,
        "target_speed_nm_s_per_tick": 25_000,
    },
    2: {
        "name": "STRESS_300",
        "target_speed_nm_s_per_code": 100_000,
        "target_speed_nm_s_per_tick": 200,
    },
}

CURVATURE_ROM = {
    (1, 0): 0,
    (1, 1): 128234,
    (1, 2): 512938,
    (1, 3): 1154111,
    (1, 4): 2051753,
    (1, 5): 3205865,
    (1, 6): 4616446,
    (1, 7): 6283496,
    (1, 8): 8207015,
    (1, 9): 10387004,
    (1, 10): 12823462,
    (1, 11): 15516389,
    (1, 12): 18465785,
    (1, 13): 21671651,
    (1, 14): 25133986,
    (1, 15): 28852790,
    (1, 16): 32828063,
    (1, 17): 37059806,
    (1, 18): 41548017,
    (1, 19): 46292698,
    (1, 20): 51293849,
    (2, 0): 0,
    (2, 1): 8,
    (2, 2): 32,
    (2, 3): 73,
    (2, 4): 131,
    (2, 5): 205,
    (2, 6): 295,
    (2, 7): 402,
    (2, 8): 525,
    (2, 9): 664,
    (2, 10): 820,
    (2, 11): 993,
    (2, 12): 1181,
    (2, 13): 1386,
    (2, 14): 1608,
    (2, 15): 1846,
    (2, 16): 2100,
    (2, 17): 2371,
    (2, 18): 2659,
    (2, 19): 2962,
    (2, 20): 3282,
}

REQUEST_KEYS = {"schema", "layout", "raw_words", "original_record"}
RECORD_REQUIRED_KEYS = {
    "schema",
    "identity_words",
    "status_before",
    "status_after",
    "fault_before",
    "fault_after",
    "command_id",
    "transport_tag",
    "decision",
    "applied_tick",
    "deadline_tick",
    "result_tick",
    "capture_seq",
}
RECORD_OPTIONAL_KEYS = {
    "previous_capture_seq",
    "previous_command_id",
    "operation_id",
}
DECISION_KEYS = {"yaw_q", "pitch_q", "profile", "speed", "ttl_ms"}
DECISION_KEY_ORDER = ("yaw_q", "pitch_q", "profile", "speed", "ttl_ms")


class _Refusal(Exception):
    def __init__(self, status, code, field, message, facts=None, mapped_target=None, association=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.field = field
        self.message = message
        self.facts = facts
        self.mapped_target = mapped_target
        self.association = association


def _is_int(value):
    return type(value) is int


def _is_bounded_text(value, max_length):
    if type(value) is not str or len(value) > max_length:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _u32(value, field):
    if not _is_int(value) or value < 0 or value > U32_MAX:
        raise _Refusal("INPUT_REJECTED", "INVALID_U32", field, "expected an integer in 0..2^32-1")
    return value


def _u64(value, field):
    if not _is_int(value) or value < 0 or value > U64_MAX:
        raise _Refusal("INPUT_REJECTED", "INVALID_U64", field, "expected an integer in 0..2^64-1")
    return value


def _signed16(value):
    return value - 65_536 if value & 0x8000 else value


def _u64_words(words, low_index):
    return words[low_index] | (words[low_index + 1] << 32)


def _ceil_div(value, divisor):
    return -((-value) // divisor)


def _canonical_json_within_budget(value):
    try:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return False
    return len(encoded) <= MAX_PRESERVED_INPUT_JSON_CHARS


def _bounded_int(value):
    return type(value) is int and value.bit_length() <= 128


def _preserve_raw_words(raw_words):
    if type(raw_words) is not list or len(raw_words) > MAX_PRESERVE_RAW_WORDS:
        return None, False
    copied = []
    for value in raw_words:
        if value is None or type(value) is bool or _bounded_int(value):
            copied.append(value)
        elif _is_bounded_text(value, 64):
            copied.append(value)
        else:
            return None, False
    if not _canonical_json_within_budget(copied):
        return None, False
    return copied, True


def _preserve_original_record(record):
    if record is None:
        return None, True
    if type(record) is not dict or len(record) > 32:
        return None, False
    copied = {}
    for key, value in record.items():
        if not _is_bounded_text(key, 64):
            return None, False
        if value is None or type(value) is bool or _bounded_int(value):
            copied[key] = value
        elif _is_bounded_text(value, 128):
            copied[key] = value
        elif type(value) is list and len(value) <= 16:
            if not all(item is None or type(item) is bool or _bounded_int(item) or
                       _is_bounded_text(item, 128) for item in value):
                return None, False
            copied[key] = list(value)
        elif type(value) is dict and len(value) <= 8:
            if not all(_is_bounded_text(k, 64) and
                       (v is None or type(v) is bool or _bounded_int(v) or
                        _is_bounded_text(v, 128)) for k, v in value.items()):
                return None, False
            copied[key] = dict(value)
        else:
            return None, False
    if not _canonical_json_within_budget(copied):
        return None, False
    return copied, True


def _base_result(status, raw_words, raw_preserved, original_record, original_preserved,
                 refusal=None, facts=None, mapped_target=None, association=None):
    return {
        "schema": RESULT_SCHEMA,
        "status": status,
        "refusal": refusal,
        "preserved_input": {
            "raw_words": raw_words,
            "raw_words_preserved": raw_preserved,
            "original_record": original_record,
            "original_record_preserved": original_preserved,
        },
        "facts": facts,
        "mapped_target_reference": mapped_target,
        "association": association,
        "limits": {
            "motion_authority": False,
            "formal_acceptance": False,
            "actor_or_custody_authenticated": False,
            "post_latch_identity_reread": "NOT_MODELED_A_C_OWNS",
            "electrical_loopback": "UNVERIFIED",
            "raw_receipt_transport_validation": "NOT_PERFORMED_C48_OWNS",
            "active_kinematics": "NOT_DERIVED",
            "world_frame_transform": "NOT_PROVIDED",
            "not_evidence_for": [
                "STATE8",
                "BOOT_ACK",
                "UART",
                "TRACE_ADC_AS_PC_AI_COMMAND",
                "PHYSICAL_G05_OPERATION",
                "H01_H15_PRODUCT_ACCEPTANCE",
            ],
        },
    }


def _refusal_result(exc, raw_words, raw_preserved, original_record, original_preserved):
    return _base_result(
        exc.status,
        raw_words,
        raw_preserved,
        original_record,
        original_preserved,
        refusal={"code": exc.code, "field": exc.field, "message": exc.message},
        facts=exc.facts,
        mapped_target=exc.mapped_target,
        association=exc.association,
    )


def _expanded_highs(yaw_q, pitch_q, speed_code):
    return (
        YAW_PITCH_BASE + YAW_PITCH_STEP * yaw_q,
        YAW_PITCH_BASE + YAW_PITCH_STEP * pitch_q,
        SPEED_BASE + SPEED_STEP * speed_code,
    )


def _integer_candidates(observed_high, base, step, low, high):
    candidate_low = _ceil_div(observed_high - NEAR_TOLERANCE_TICKS - base, step)
    candidate_high = (observed_high + NEAR_TOLERANCE_TICKS - base) // step
    candidate_low = max(low, candidate_low)
    candidate_high = min(high, candidate_high)
    if candidate_high < candidate_low:
        return []
    return list(range(candidate_low, candidate_high + 1))


def _validate_identity_words(identity_words):
    if type(identity_words) is not list or len(identity_words) != 13:
        raise _Refusal("REFUSED_ASSOCIATION", "IDENTITY_CARDINALITY", "original_record.identity_words",
                       "exactly 13 identity words are required")
    parsed = []
    for index, value in enumerate(identity_words):
        if not _is_int(value) or value < 0 or value > U32_MAX:
            raise _Refusal("REFUSED_ASSOCIATION", "IDENTITY_TYPE", f"original_record.identity_words[{index}]",
                           "identity words must be uint32")
        parsed.append(value)
    if parsed[12] == 0:
        raise _Refusal("REFUSED_ASSOCIATION", "IDENTITY_SESSION_ZERO", "original_record.identity_words[12]",
                       "session identity word must be nonzero")
    if not any(parsed[0:8]):
        raise _Refusal("REFUSED_ASSOCIATION", "IDENTITY_RUN_ZERO", "original_record.identity_words[0:8]",
                       "run identity group must contain a nonzero word")
    if not any(parsed[8:12]):
        raise _Refusal("REFUSED_ASSOCIATION", "IDENTITY_NONCE_ZERO", "original_record.identity_words[8:12]",
                       "nonce identity group must contain a nonzero word")
    return parsed


def _validate_status(value, field, phase):
    if not _is_int(value) or value < 0 or value > U32_MAX:
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_TYPE", field, "status must be uint32")
    if value & ~STATUS_DEFINED_MASK:
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_RESERVED_BITS", field,
                       "G05P status has only bits 0..6 defined")
    if not (value & STATUS_BOUND):
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_NOT_BOUND", field, "session is not bound")
    if value & STATUS_RETIRED_OR_HALTED:
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_RETIRED", field, "session is retired")
    if not (value & STATUS_RUNNING):
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_NOT_RUNNING", field, "engine is not running")
    if value & STATUS_PENDING:
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_PENDING", field, "a command is pending")
    if value & STATUS_INFLIGHT:
        raise _Refusal("REFUSED_ASSOCIATION", "STATUS_INFLIGHT", field, "a command is inflight")
    if phase == "before":
        if not (value & STATUS_LATEST_ELIGIBLE):
            raise _Refusal("REFUSED_ASSOCIATION", "STATUS_NOT_LATCH_READY", field,
                           "pre-LATCH status does not report a latest eligible result")
        if value & STATUS_LATCH_VALID:
            raise _Refusal("REFUSED_ASSOCIATION", "STATUS_LATCH_ALREADY_VALID", field,
                           "pre-LATCH status already reports a latched capture")
    elif phase == "after":
        if not (value & STATUS_LATCH_VALID):
            raise _Refusal("REFUSED_ASSOCIATION", "STATUS_LATCH_NOT_HELD", field,
                           "post-LATCH status does not report the latched capture")
    else:
        raise ValueError("status phase must be 'before' or 'after'")
    return value


def _validate_decision(decision):
    if type(decision) is not dict or set(decision) != DECISION_KEYS:
        raise _Refusal("REFUSED_ASSOCIATION", "DECISION_SCHEMA", "original_record.decision",
                       "decision must contain exactly yaw_q, pitch_q, profile, speed, ttl_ms")
    values = {}
    for name in DECISION_KEY_ORDER:
        if not _is_int(decision[name]):
            raise _Refusal("REFUSED_ASSOCIATION", "DECISION_TYPE", f"original_record.decision.{name}",
                           "decision values must be integers")
        values[name] = decision[name]
    if values["profile"] not in PROFILE_SPEC:
        raise _Refusal("REFUSED_ASSOCIATION", "DECISION_PROFILE", "original_record.decision.profile",
                       "profile must be 1 or 2")
    if values["yaw_q"] < Q_MIN or values["yaw_q"] > Q_MAX:
        raise _Refusal("REFUSED_ASSOCIATION", "DECISION_YAW_RANGE", "original_record.decision.yaw_q",
                       "yaw_q is outside -15000..15000")
    if values["pitch_q"] < Q_MIN or values["pitch_q"] > Q_MAX:
        raise _Refusal("REFUSED_ASSOCIATION", "DECISION_PITCH_RANGE", "original_record.decision.pitch_q",
                       "pitch_q is outside -15000..15000")
    if values["speed"] < 0 or values["speed"] > SPEED_MAX:
        raise _Refusal("REFUSED_ASSOCIATION", "DECISION_SPEED_RANGE", "original_record.decision.speed",
                       "speed must be in 0..20")
    if values["ttl_ms"] < 1 or values["ttl_ms"] > TTL_MAX_MS[values["profile"]]:
        raise _Refusal("REFUSED_ASSOCIATION", "DECISION_TTL_RANGE", "original_record.decision.ttl_ms",
                       "TTL is outside the selected profile cap")
    return values


def _validate_mapper(yaw_q, pitch_q, speed, profile, ttl_ms, field_prefix):
    if profile not in PROFILE_SPEC:
        raise _Refusal("REFUSED_CAPTURE", "PROFILE_UNSUPPORTED", f"{field_prefix}.profile",
                       "profile is not 1 or 2")
    if yaw_q < Q_MIN or yaw_q > Q_MAX:
        raise _Refusal("REFUSED_CAPTURE", "YAW_RANGE", f"{field_prefix}.yaw_q", "yaw_q is outside mapper range")
    if pitch_q < Q_MIN or pitch_q > Q_MAX:
        raise _Refusal("REFUSED_CAPTURE", "PITCH_RANGE", f"{field_prefix}.pitch_q", "pitch_q is outside mapper range")
    if speed < 0 or speed > SPEED_MAX:
        raise _Refusal("REFUSED_CAPTURE", "SPEED_RANGE", f"{field_prefix}.speed", "speed is outside 0..20")
    if speed == 0 and (yaw_q != 0 or pitch_q != 0):
        raise _Refusal("REFUSED_CAPTURE", "ZERO_SPEED_AXES", field_prefix,
                       "zero target speed requires zero yaw_q and pitch_q")
    if ttl_ms < 1 or ttl_ms > TTL_MAX_MS[profile]:
        raise _Refusal("REFUSED_CAPTURE", "TTL_RANGE", f"{field_prefix}.ttl_ms",
                       "TTL is outside the selected profile cap")
    curvature_sum = yaw_q * yaw_q + pitch_q * pitch_q
    curvature_limit = CURVATURE_ROM[(profile, speed)]
    if curvature_sum > curvature_limit:
        raise _Refusal("REFUSED_CAPTURE", "CURVATURE_ROM", field_prefix,
                       "yaw_q^2 + pitch_q^2 exceeds the selected profile/speed ROM limit")
    return curvature_sum, curvature_limit


def _parse_capture(raw_words, layout):
    words = []
    for index, value in enumerate(raw_words):
        if not _is_int(value) or value < 0 or value > U32_MAX:
            raise _Refusal("INPUT_REJECTED", "RAW_WORD_TYPE", f"raw_words[{index}]",
                           "each capture word must be uint32")
        words.append(value)

    if words[31] != G05P_MAGIC:
        raise _Refusal("REFUSED_CAPTURE", "MAGIC_MISMATCH", "raw_words[31]", "G05P magic is absent")
    if words[30] == 0:
        raise _Refusal("REFUSED_CAPTURE", "SESSION_ZERO", "raw_words[30]", "session word is zero")
    if words[0] == 0:
        raise _Refusal("REFUSED_CAPTURE", "CAPTURE_SEQUENCE", "raw_words[0]",
                       "capture sequence must be nonzero")
    if words[1] == 0:
        raise _Refusal("REFUSED_CAPTURE", "COMMAND_ID_ZERO", "raw_words[1]", "command ID is zero")
    if words[3] >> 16:
        raise _Refusal("REFUSED_CAPTURE", "PROFILE_SPEED_ENCODING", "raw_words[3]",
                       "profile/speed word upper 16 bits must be zero")
    if words[5] >> 16:
        raise _Refusal("REFUSED_CAPTURE", "TTL_ENCODING", "raw_words[5]", "TTL word upper 16 bits must be zero")

    profile = words[3] & 0xFF
    speed = (words[3] >> 8) & 0xFF
    yaw_q = _signed16(words[4] & 0xFFFF)
    pitch_q = _signed16((words[4] >> 16) & 0xFFFF)
    ttl_ms = words[5] & 0xFFFF
    _validate_mapper(yaw_q, pitch_q, speed, profile, ttl_ms, "raw_words.nominal")

    applied_tick = _u64_words(words, 6)
    deadline_tick = _u64_words(words, 8)
    result_tick = _u64_words(words, 10)
    ttl_ticks = ttl_ms * TTL_TICKS_PER_MS
    if applied_tick + ttl_ticks > U64_MAX or deadline_tick != applied_tick + ttl_ticks:
        raise _Refusal("REFUSED_CAPTURE", "TTL_CYCLE_MISMATCH", "raw_words[5..9]",
                       "deadline must equal applied tick plus TTL ticks exactly, without overflow")

    periods = list(words[12:15])
    highs = list(words[15:18])
    starts = [_u64_words(words, 18), _u64_words(words, 20), _u64_words(words, 22)]
    ends = [_u64_words(words, 24), _u64_words(words, 26), _u64_words(words, 28)]

    for index, period in enumerate(periods):
        if abs(period - FRAME_TICKS) > NEAR_TOLERANCE_TICKS:
            raise _Refusal("REFUSED_CAPTURE", "PERIOD_TOLERANCE", f"raw_words[{12 + index}]",
                           "period is outside the selected 50 MHz near tolerance")
    for index, (period, high) in enumerate(zip(periods, highs)):
        if high == 0 or high >= period:
            raise _Refusal("REFUSED_CAPTURE", "HIGH_COUNT_INVALID", f"raw_words[{15 + index}]",
                           "each high count must satisfy 0 < high < period")
    for index in (19, 21, 23, 25, 27, 29):
        if words[index] != 0:
            raise _Refusal("REFUSED_CAPTURE", "WITNESS_UPPER_WORD", f"raw_words[{index}]",
                           "32-bit capture witness is zero-extended; upper word must be zero")
    for index, (start, end, period) in enumerate(zip(starts, ends, periods)):
        if start == 0 or start >= end or end - start != period:
            raise _Refusal("REFUSED_CAPTURE", "WITNESS_PERIOD_MISMATCH", f"raw_words[{18 + 6 * index}..{29}]",
                           "each channel requires start < end and end-start == period without wrap")
    if max(starts) - min(starts) > NEAR_TOLERANCE_TICKS:
        raise _Refusal("REFUSED_CAPTURE", "START_TRIO_SPAN", "raw_words[18..23]",
                       "three channel start witnesses differ by more than one tick")
    if max(ends) - min(ends) > NEAR_TOLERANCE_TICKS:
        raise _Refusal("REFUSED_CAPTURE", "END_TRIO_SPAN", "raw_words[24..29]",
                       "three channel end witnesses differ by more than one tick")

    minimum_post_apply = applied_tick + max(ends)
    if result_tick < minimum_post_apply or result_tick >= deadline_tick:
        raise _Refusal("REFUSED_CAPTURE", "RESULT_CYCLE_BOUNDS", "raw_words[6..11]",
                       "global age must cover every local end witness and precede the original deadline")

    expected_highs = _expanded_highs(yaw_q, pitch_q, speed)
    for index, (observed, expected) in enumerate(zip(highs, expected_highs)):
        if abs(observed - expected) > NEAR_TOLERANCE_TICKS:
            raise _Refusal("REFUSED_CAPTURE", "MEASURED_HIGH_MISMATCH", f"raw_words[{15 + index}]",
                           "measured high is outside the selected mapper near tolerance")

    yaw_candidates = _integer_candidates(highs[0], YAW_PITCH_BASE, YAW_PITCH_STEP, Q_MIN, Q_MAX)
    pitch_candidates = _integer_candidates(highs[1], YAW_PITCH_BASE, YAW_PITCH_STEP, Q_MIN, Q_MAX)
    speed_candidates = _integer_candidates(highs[2], SPEED_BASE, SPEED_STEP, 0, SPEED_MAX)
    if (len(yaw_candidates) != 1 or len(pitch_candidates) != 1 or len(speed_candidates) != 1):
        raise _Refusal("REFUSED_CAPTURE", "MAPPING_AMBIGUOUS_OR_ABSENT", "raw_words[15..17]",
                       "measured highs do not identify one supported integer command")
    measured_yaw, measured_pitch, measured_speed = (
        yaw_candidates[0], pitch_candidates[0], speed_candidates[0])
    curvature_sum, curvature_limit = _validate_mapper(
        measured_yaw, measured_pitch, measured_speed, profile, ttl_ms, "measured_mapping")
    if (measured_yaw, measured_pitch, measured_speed) != (yaw_q, pitch_q, speed):
        raise _Refusal("REFUSED_CAPTURE", "MEASURED_NOMINAL_DISAGREE", "raw_words[3..4,15..17]",
                       "measured mapper candidate does not equal the capture's nominal command fields")

    return {
        "words": words,
        "sequence": words[0],
        "command_id": words[1],
        "transport_tag": words[2],
        "session": words[30],
        "magic": words[31],
        "profile": profile,
        "speed": speed,
        "yaw_q": yaw_q,
        "pitch_q": pitch_q,
        "ttl_ms": ttl_ms,
        "ttl_ticks": ttl_ticks,
        "applied_tick": applied_tick,
        "deadline_tick": deadline_tick,
        "result_tick": result_tick,
        "periods": periods,
        "highs": highs,
        "starts": starts,
        "ends": ends,
        "expected_highs": expected_highs,
        "measured_yaw": measured_yaw,
        "measured_pitch": measured_pitch,
        "measured_speed": measured_speed,
        "curvature_sum": curvature_sum,
        "curvature_limit": curvature_limit,
    }


def _facts_from_capture(capture):
    channels = []
    names = ("yaw", "pitch", "speed")
    for index, name in enumerate(names):
        period = capture["periods"][index]
        high = capture["highs"][index]
        channels.append({
            "index": index,
            "name": name,
            "period_ticks_sampled": period,
            "high_ticks_sampled": high,
            "start_witness_tick_local": capture["starts"][index],
            "end_witness_tick_local": capture["ends"][index],
            "period_ns_center": period * TICK_NS,
            "high_ns_center": high * TICK_NS,
            "start_witness_ns_local": capture["starts"][index] * TICK_NS,
            "end_witness_ns_local": capture["ends"][index] * TICK_NS,
            "end_minus_start_ticks": capture["ends"][index] - capture["starts"][index],
            "period_tick_sampling_bounds": [period - 1, period + 1],
            "high_tick_sampling_bounds": [max(1, high - 1), min(period - 1, high + 1)],
            "duty_ratio_sampled": {"numerator": high, "denominator": period},
            "witness_origin": "local counter reset by the RTL capture rearm; not host QPC or global time",
        })
    return {
        "capture_sequence": capture["sequence"],
        "command_id": capture["command_id"],
        "transport_tag": capture["transport_tag"],
        "session": capture["session"],
        "magic": f"0x{capture['magic']:08x}",
        "nominal_command_fields_from_capture": {
            "yaw_q": capture["yaw_q"],
            "pitch_q": capture["pitch_q"],
            "profile": capture["profile"],
            "speed_code": capture["speed"],
            "ttl_ms": capture["ttl_ms"],
            "note": "Captured metadata only; never used to replace measured period/high/start/end values.",
        },
        "timestamps": {
            "clock_hz": CLOCK_HZ,
            "tick_ns": TICK_NS,
            "applied_tick": capture["applied_tick"],
            "deadline_tick": capture["deadline_tick"],
            "result_tick": capture["result_tick"],
            "ttl_ms": capture["ttl_ms"],
            "ttl_ticks": capture["ttl_ticks"],
            "deadline_equals_applied_plus_ttl": True,
            "minimum_result_tick_from_local_ends": capture["applied_tick"] + max(capture["ends"]),
            "result_covers_witnesses_before_deadline": True,
        },
        "pwm_channels": channels,
        "measured_mapper_candidate": {
            "yaw_q": capture["measured_yaw"],
            "pitch_q": capture["measured_pitch"],
            "speed_code": capture["measured_speed"],
            "curvature_sum": capture["curvature_sum"],
            "curvature_limit": capture["curvature_limit"],
            "within_rom_limit": True,
        },
    }


def _yaw_interval(high, period):
    low_tick = max(1, high - NEAR_TOLERANCE_TICKS)
    high_tick = min(period - 1, high + NEAR_TOLERANCE_TICKS)
    low = (low_tick - YAW_PITCH_BASE) * 125_000
    high_value = (high_tick - YAW_PITCH_BASE) * 125_000
    domain_low = Q_MIN * 1_000_000
    domain_high = Q_MAX * 1_000_000
    clipped = low < domain_low or high_value > domain_high
    return {
        "high_tick_bounds": [low_tick, high_tick],
        "target_rate_interval_ndeg_s": [max(domain_low, low), min(domain_high, high_value)],
        "clip_to_mapper_domain": clipped,
        "unit": "nanodegrees_per_second",
        "mapper_compatibility_tolerance_ticks": NEAR_TOLERANCE_TICKS,
    }


def _speed_interval(high, period, profile):
    low_tick = max(1, high - NEAR_TOLERANCE_TICKS)
    high_tick = min(period - 1, high + NEAR_TOLERANCE_TICKS)
    per_tick = PROFILE_SPEC[profile]["target_speed_nm_s_per_tick"]
    domain_high = SPEED_MAX * PROFILE_SPEC[profile]["target_speed_nm_s_per_code"]
    low = (low_tick - SPEED_BASE) * per_tick
    high_value = (high_tick - SPEED_BASE) * per_tick
    clipped = low < 0 or high_value > domain_high
    return {
        "high_tick_bounds": [low_tick, high_tick],
        "target_speed_interval_nm_s": [max(0, low), min(domain_high, high_value)],
        "clip_to_mapper_domain": clipped,
        "unit": "nanometres_per_second",
        "mapper_compatibility_tolerance_ticks": NEAR_TOLERANCE_TICKS,
    }


def _mapped_target_reference(capture):
    profile = capture["profile"]
    yaw_interval = _yaw_interval(capture["highs"][0], capture["periods"][0])
    pitch_interval = _yaw_interval(capture["highs"][1], capture["periods"][1])
    speed_interval = _speed_interval(capture["highs"][2], capture["periods"][2], profile)
    discrete_speed_nm_s = capture["measured_speed"] * PROFILE_SPEC[profile]["target_speed_nm_s_per_code"]
    return {
        "basis": {
            "clock_hz": CLOCK_HZ,
            "tick_ns": TICK_NS,
            "fixed_mapper_frame_ticks": FRAME_TICKS,
            "period_tolerance_ticks": NEAR_TOLERANCE_TICKS,
            "high_tolerance_ticks": NEAR_TOLERANCE_TICKS,
            "mapper": "deepeye_g05_command_map_50mhz",
            "profile": PROFILE_SPEC[profile]["name"],
            "yaw_pitch_code_unit": "0.001 degree/s per code",
            "speed_code_unit": "profile-specific metres/s per code",
            "rounding": "closed mapper compatibility envelope rounded outward in exact integer nano-units; no floating point",
            "nominal_command_values_used_for_measured_reconstruction": False,
            "target_reference_is_actual_kinematics": False,
        },
        "yaw": {
            "nominal_command_q": capture["yaw_q"],
            "sampled_high_ticks": capture["highs"][0],
            "sampled_high_ns": capture["highs"][0] * TICK_NS,
            "nominal_target_rate_ndeg_s": capture["yaw_q"] * 1_000_000,
            **yaw_interval,
        },
        "pitch": {
            "nominal_command_q": capture["pitch_q"],
            "sampled_high_ticks": capture["highs"][1],
            "sampled_high_ns": capture["highs"][1] * TICK_NS,
            "nominal_target_rate_ndeg_s": capture["pitch_q"] * 1_000_000,
            **pitch_interval,
        },
        "speed": {
            "nominal_speed_code": capture["speed"],
            "sampled_high_ticks": capture["highs"][2],
            "sampled_high_ns": capture["highs"][2] * TICK_NS,
            "nominal_target_speed_nm_s": capture["speed"] * PROFILE_SPEC[profile]["target_speed_nm_s_per_code"],
            **speed_interval,
        },
        "discrete_mapper_candidate": {
            "yaw_q": capture["measured_yaw"],
            "pitch_q": capture["measured_pitch"],
            "speed_code": capture["measured_speed"],
            "target_yaw_rate_ndeg_s": capture["measured_yaw"] * 1_000_000,
            "target_pitch_rate_ndeg_s": capture["measured_pitch"] * 1_000_000,
            "target_speed_nm_s": discrete_speed_nm_s,
            "curvature_sum": capture["curvature_sum"],
            "curvature_limit": capture["curvature_limit"],
            "within_rom_limit": True,
        },
        "engineering_conversion": {
            "reference_kind": "DECODED_TARGET_REFERENCE_NOT_SIMULATOR_POSE",
            "tick_ns": TICK_NS,
            "yaw_pitch_target_rate_ndeg_s_formula": "(sampled_high_ticks - 125000) * 125000",
            "speed_target_nm_s_formula": {
                "FAST_9600": "(sampled_high_ticks - 25000) * 25000",
                "STRESS_300": "(sampled_high_ticks - 25000) * 200",
            },
            "period_ns_formula": "sampled_period_ticks * 20",
            "rounding": "EXACT_INTEGER_NANO_UNITS_NO_ROUNDING",
            "nominal_command_values_used_for_measured_reconstruction": False,
            "simulator_pose_transform": "MISSING_NORMATIVE_SOURCE",
            "simulator_target_application": "NOT_PERFORMED",
            "electrical_loopback": "UNVERIFIED",
        },
        "interpretation": {
            "rate_values": "target reference at the command target speed, not measured instantaneous angular velocity",
            "speed_values": "target reference, not measured actual speed",
            "kappa": "ROM legality is checked exactly; no continuous kappa or world-frame reconstruction is claimed",
            "world_frame_transform": "NOT_PROVIDED",
            "simulator_target_application": "NOT_PERFORMED",
        },
    }


def _association_block(layout, record_present, matched):
    return {
        "mode": "CALLER_SUPPLIED_UNAUTHENTICATED" if record_present else "NONE",
        "status": "MECHANICALLY_MATCHED_AVAILABLE_FIELDS" if matched else "UNPROVEN",
        "layout": "MATCHED" if layout == G05P_LAYOUT else "UNPROVEN" if layout is None else "MISMATCHED",
        "available_dimensions_checked": matched,
        "matching_dimensions": [
            "session32",
            "command_id32",
            "transport_tag32",
            "profile8",
            "speed8",
            "yaw16",
            "pitch16",
            "ttl16",
            "applied64",
            "deadline64",
            "result64",
            "capture_sequence32",
        ] if matched else [],
        "capture_embedded_identity_dimensions": ["session32", "command_id32", "transport_tag32"],
        "external_only_identity_dimensions": ["run_id256", "nonce128"],
        "full_identity_bound_to_capture": False,
        "authenticated": False,
        "custody": "NOT_ASSESSED",
        "actor_runtime_validation": "NOT_PERFORMED_C42_C48_OWN",
    }


def _check_original_record(record, capture, facts, mapped_target):
    if type(record) is not dict:
        raise _Refusal("REFUSED_ASSOCIATION", "RECORD_TYPE", "original_record",
                       "original_record must be an object or null", facts=facts, mapped_target=mapped_target)
    required = RECORD_REQUIRED_KEYS
    allowed = required | RECORD_OPTIONAL_KEYS
    missing = sorted(required - set(record))
    unknown = sorted(set(record) - allowed)
    if missing:
        raise _Refusal("REFUSED_ASSOCIATION", "RECORD_MISSING_FIELDS", "original_record",
                       "missing fields: " + ",".join(missing), facts=facts, mapped_target=mapped_target)
    if unknown:
        raise _Refusal("REFUSED_ASSOCIATION", "RECORD_UNKNOWN_FIELDS", "original_record",
                       "unknown fields: " + ",".join(unknown), facts=facts, mapped_target=mapped_target)
    if record.get("schema") != RECORD_SCHEMA:
        raise _Refusal("REFUSED_ASSOCIATION", "RECORD_SCHEMA", "original_record.schema",
                       "unexpected original-record schema", facts=facts, mapped_target=mapped_target)

    identity_words = _validate_identity_words(record["identity_words"])
    _validate_status(record["status_before"], "original_record.status_before", "before")
    _validate_status(record["status_after"], "original_record.status_after", "after")
    for field in ("fault_before", "fault_after"):
        value = record[field]
        if not _is_int(value) or value < 0 or value > 0xFFFF:
            raise _Refusal("REFUSED_ASSOCIATION", "FAULT_TYPE", f"original_record.{field}",
                           "fault must be uint16", facts=facts, mapped_target=mapped_target)
        if value != 0:
            raise _Refusal("REFUSED_ASSOCIATION", "FAULT_NONZERO", f"original_record.{field}",
                           "capture-time fault word must be zero", facts=facts, mapped_target=mapped_target)

    decision = _validate_decision(record["decision"])
    command_id = _u32(record["command_id"], "original_record.command_id")
    transport_tag = _u32(record["transport_tag"], "original_record.transport_tag")
    applied_tick = _u64(record["applied_tick"], "original_record.applied_tick")
    deadline_tick = _u64(record["deadline_tick"], "original_record.deadline_tick")
    result_tick = _u64(record["result_tick"], "original_record.result_tick")
    capture_seq = _u32(record["capture_seq"], "original_record.capture_seq")

    if command_id == 0:
        raise _Refusal("REFUSED_ASSOCIATION", "COMMAND_ID_ZERO", "original_record.command_id",
                       "command ID must be nonzero", facts=facts, mapped_target=mapped_target)
    if capture_seq != capture["sequence"]:
        raise _Refusal("REFUSED_ASSOCIATION", "CAPTURE_SEQUENCE_MISMATCH", "original_record.capture_seq",
                       "original capture sequence differs from the latched words", facts=facts,
                       mapped_target=mapped_target)
    if identity_words[12] != capture["session"]:
        raise _Refusal("REFUSED_ASSOCIATION", "SESSION_MISMATCH", "original_record.identity_words[12]",
                       "session differs from capture word 30", facts=facts, mapped_target=mapped_target)
    if command_id != capture["command_id"]:
        raise _Refusal("REFUSED_ASSOCIATION", "COMMAND_MISMATCH", "original_record.command_id",
                       "command ID differs from capture word 1", facts=facts, mapped_target=mapped_target)
    if transport_tag != capture["transport_tag"]:
        raise _Refusal("REFUSED_ASSOCIATION", "TAG_MISMATCH", "original_record.transport_tag",
                       "transport tag differs from capture word 2", facts=facts, mapped_target=mapped_target)
    if decision["yaw_q"] != capture["yaw_q"] or decision["pitch_q"] != capture["pitch_q"]:
        raise _Refusal("REFUSED_ASSOCIATION", "AXIS_DECISION_MISMATCH", "original_record.decision",
                       "yaw/pitch decision differs from capture word 4", facts=facts,
                       mapped_target=mapped_target)
    if decision["profile"] != capture["profile"] or decision["speed"] != capture["speed"]:
        raise _Refusal("REFUSED_ASSOCIATION", "PROFILE_SPEED_MISMATCH", "original_record.decision",
                       "profile/speed differs from capture word 3", facts=facts,
                       mapped_target=mapped_target)
    if decision["ttl_ms"] != capture["ttl_ms"]:
        raise _Refusal("REFUSED_ASSOCIATION", "TTL_MISMATCH", "original_record.decision.ttl_ms",
                       "TTL differs from capture word 5", facts=facts, mapped_target=mapped_target)
    if applied_tick != capture["applied_tick"] or deadline_tick != capture["deadline_tick"]:
        raise _Refusal("REFUSED_ASSOCIATION", "APPLY_DEADLINE_MISMATCH", "original_record",
                       "applied/deadline tick differs from capture words 6..9", facts=facts,
                       mapped_target=mapped_target)
    if result_tick != capture["result_tick"]:
        raise _Refusal("REFUSED_ASSOCIATION", "RESULT_TICK_MISMATCH", "original_record.result_tick",
                       "result tick differs from capture words 10..11", facts=facts,
                       mapped_target=mapped_target)

    previous_capture_seq = record.get("previous_capture_seq")
    if previous_capture_seq is not None:
        previous_capture_seq = _u32(previous_capture_seq, "original_record.previous_capture_seq")
        if capture["sequence"] <= previous_capture_seq:
            raise _Refusal("REFUSED_ASSOCIATION", "CAPTURE_SEQUENCE_STALE", "original_record.previous_capture_seq",
                           "capture sequence is not strictly increasing and would wrap or repeat",
                           facts=facts, mapped_target=mapped_target)
    previous_command_id = record.get("previous_command_id")
    if previous_command_id is not None:
        previous_command_id = _u32(previous_command_id, "original_record.previous_command_id")
        if command_id <= previous_command_id:
            raise _Refusal("REFUSED_ASSOCIATION", "COMMAND_SEQUENCE_STALE", "original_record.previous_command_id",
                           "command ID is not strictly increasing and would wrap or repeat",
                           facts=facts, mapped_target=mapped_target)

    operation_id = record.get("operation_id")
    if operation_id is not None and (not _is_bounded_text(operation_id, 128) or len(operation_id) < 1):
        raise _Refusal("REFUSED_ASSOCIATION", "OPERATION_ID", "original_record.operation_id",
                       "operation_id must be a bounded nonempty string", facts=facts,
                       mapped_target=mapped_target)

    return {
        "record_operation_id": operation_id,
        "checks": {
            "schema": True,
            "identity_cardinality": True,
            "identity_session": True,
            "status_before_latch_ready": True,
            "status_after_latch_valid": True,
            "fault_zero": True,
            "capture_sequence": True,
            "capture_sequence_strictly_increasing": previous_capture_seq is not None,
            "command_id": True,
            "command_id_strictly_increasing": previous_command_id is not None,
            "transport_tag": True,
            "profile_speed": True,
            "yaw_pitch": True,
            "ttl": True,
            "applied_tick": True,
            "deadline_tick": True,
            "result_tick": True,
        },
    }


def _decode_bank_request(request):
    raw_preserved = None
    raw_preserved_ok = False
    original_preserved = None
    original_preserved_ok = False
    if type(request) is dict:
        raw_preserved, raw_preserved_ok = _preserve_raw_words(request.get("raw_words"))
        original_preserved, original_preserved_ok = _preserve_original_record(request.get("original_record"))

    try:
        if type(request) is not dict:
            raise _Refusal("INPUT_REJECTED", "REQUEST_TYPE", "request", "request must be a JSON object")
        if len(request) != len(REQUEST_KEYS):
            raise _Refusal("INPUT_REJECTED", "REQUEST_FIELDS", "request",
                           "request must contain exactly four fields")
        if any(not _is_bounded_text(key, 64) for key in request):
            raise _Refusal("INPUT_REJECTED", "REQUEST_FIELDS", "request",
                           "request keys must be bounded strings")
        if set(request) != REQUEST_KEYS:
            missing = sorted(REQUEST_KEYS - set(request))
            unknown = sorted(set(request) - REQUEST_KEYS)
            detail = []
            if missing:
                detail.append("missing=" + ",".join(missing))
            if unknown:
                detail.append("unknown=" + ",".join(unknown))
            raise _Refusal("INPUT_REJECTED", "REQUEST_FIELDS", "request", "; ".join(detail))
        if request["schema"] != REQUEST_SCHEMA:
            raise _Refusal("INPUT_REJECTED", "REQUEST_SCHEMA", "schema", "unexpected request schema")
        layout = request["layout"]
        if layout is not None and (not _is_int(layout) or layout < 0 or layout > U32_MAX):
            raise _Refusal("INPUT_REJECTED", "LAYOUT_TYPE", "layout", "layout must be a uint32 or null")
        if layout is not None and layout != G05P_LAYOUT:
            raise _Refusal("REFUSED_LAYOUT_MISMATCH", "LAYOUT_MISMATCH", "layout",
                           "capture bank is not asserted to be G05P/layout 2")
        raw_words = request["raw_words"]
        if type(raw_words) is not list:
            raise _Refusal("INPUT_REJECTED", "RAW_CARDINALITY", "raw_words", "raw_words must be a list")
        if len(raw_words) != 32:
            raise _Refusal("INPUT_REJECTED", "RAW_CARDINALITY", "raw_words",
                           "exactly 32 capture words are required")
        original_record = request["original_record"]
        if original_record is not None and type(original_record) is not dict:
            raise _Refusal("INPUT_REJECTED", "RECORD_TYPE", "original_record",
                           "original_record must be an object or null")
        if not original_preserved_ok:
            raise _Refusal("INPUT_REJECTED", "RECORD_BOUNDS", "original_record",
                           "original_record exceeds the bounded preservation schema")
        original_record = original_preserved

        capture = _parse_capture(raw_words, layout)
        facts = _facts_from_capture(capture)
        mapped_target = _mapped_target_reference(capture)

        if original_record is None:
            association = _association_block(layout, False, False)
            return _base_result(
                "DECODED_FACTS_ONLY",
                raw_preserved,
                raw_preserved_ok,
                original_preserved,
                original_preserved_ok,
                facts=facts,
                mapped_target=mapped_target,
                association=association,
            )

        try:
            record_check = _check_original_record(original_record, capture, facts, mapped_target)
        except _Refusal as exc:
            exc.status = "REFUSED_ASSOCIATION"
            exc.facts = facts
            exc.mapped_target = mapped_target
            raise
        association = _association_block(layout, True, True)
        association["record_check"] = record_check
        status = "DECODED_PARTIAL_ASSOCIATION" if layout == G05P_LAYOUT else "DECODED_FACTS_ONLY"
        return _base_result(
            status,
            raw_preserved,
            raw_preserved_ok,
            original_preserved,
            original_preserved_ok,
            facts=facts,
            mapped_target=mapped_target,
            association=association,
        )
    except _Refusal as exc:
        if exc.association is None:
            exc.association = _association_block(
                request.get("layout") if type(request) is dict else None,
                type(request) is dict and request.get("original_record") is not None,
                False,
            )
        return _refusal_result(
            exc,
            raw_preserved,
            raw_preserved_ok,
            original_preserved,
            original_preserved_ok,
        )


_BRACKET_KEYS = {"identity_words", "magic", "layout", "status", "fault", "command_id",
                 "transport_tag", "applied_tick", "deadline_tick", "held_capture_seq", "cycle_tick"}


def _check_held_observation(snapshot, original, capture):
    if type(snapshot) is not dict or not len(_BRACKET_KEYS) <= len(snapshot) <= len(_BRACKET_KEYS) + 1:
        raise ValueError("snapshot shape")
    if any(not _is_bounded_text(key, 32) for key in snapshot):
        raise ValueError("snapshot keys")
    if not _BRACKET_KEYS <= snapshot.keys() <= _BRACKET_KEYS | {"latest_seq"}:
        raise ValueError("missing or unsupported snapshot fields")
    identity = _validate_identity_words(snapshot["identity_words"])
    _validate_status(snapshot["status"], "snapshot.status", "after")
    expected = {"magic": G05P_MAGIC, "layout": G05P_LAYOUT, "fault": 0,
                "command_id": original["command_id"], "transport_tag": original["transport_tag"],
                "held_capture_seq": capture["capture_sequence"]}
    if identity != original["identity_words"] or any(_u32(snapshot[k], k) != v for k, v in expected.items()):
        raise ValueError("identity, command or latch mismatch")
    for key in ("applied_tick", "deadline_tick"):
        if _u64(snapshot[key], key) != original[key]:
            raise ValueError("command lifetime mismatch")
    if "latest_seq" in snapshot:
        _u32(snapshot["latest_seq"], "latest_seq")
    return _u64(snapshot["cycle_tick"], "cycle_tick")


def decode_request(request):
    """Decode raw capture; optionally compare two reads bracketing the held bank."""
    if type(request) is not dict or "held_observations" not in request:
        return _decode_bank_request(request)
    if len(request) != len(REQUEST_KEYS) + 1 or any(not _is_bounded_text(k, 64) for k in request):
        return _decode_bank_request(request)
    bank = {k: v for k, v in request.items() if k != "held_observations"}
    result = _decode_bank_request(bank)
    bracket = request["held_observations"]
    preserved = {}
    valid_shape = (type(bracket) is dict and len(bracket) <= 2
                   and all(type(k) is str and k in ("before", "after") for k in bracket))
    if valid_shape:
        for phase in bracket:
            saved, bounded = _preserve_original_record(bracket[phase])
            if bounded:
                preserved[phase] = saved
    result["preserved_input"]["held_observations"] = preserved
    result["preserved_input"]["held_observations_preserved"] = len(preserved) == 2
    if result["refusal"] is not None:
        return result
    original = result["preserved_input"]["original_record"]
    try:
        if len(preserved) != 2 or result["status"] != "DECODED_PARTIAL_ASSOCIATION":
            raise ValueError("two held-bank observations and an associated original command are required")
        ticks = [_check_held_observation(preserved[k], original, result["facts"]) for k in ("before", "after")]
        if not original["result_tick"] <= ticks[0] <= ticks[1] < original["deadline_tick"]:
            raise ValueError("held read outside original lifetime or time order")
    except (_Refusal, ValueError) as exc:
        result["status"] = "REFUSED_ASSOCIATION"
        result["refusal"] = {"code": "HELD_BRACKET_MISMATCH", "field": "held_observations",
                             "message": str(exc)}
        result["association"]["status"] = "HELD_BRACKET_REFUSED"
        return result
    result["status"] = "DECODED_BRACKET_CORRELATED"
    result["association"].update(status="ORIGINAL_AND_HELD_READS_MATCHED", full_external_identity_matched=True,
                                 held_read_cycles=ticks)
    return result


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON field")
        obj[key] = value
    return obj


def _no_nonfinite(_):
    raise ValueError("nonfinite JSON number")





def _load_request(path):
    if not os.path.isfile(path):
        raise ValueError("request path is not a regular file")
    size = os.path.getsize(path)
    if size < 1 or size > MAX_REQUEST_BYTES:
        raise ValueError(f"request file size must be 1..{MAX_REQUEST_BYTES} bytes")
    with open(path, "rb") as handle:
        raw = handle.read(MAX_REQUEST_BYTES + 1)
    if len(raw) != size:
        raise ValueError("request file changed while reading")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys, parse_constant=_no_nonfinite)


def _write_result(out_dir, result):
    if not os.path.isabs(out_dir):
        raise ValueError("--out must be an absolute path")
    if os.path.exists(out_dir):
        raise ValueError("--out must name a new path")
    os.makedirs(out_dir, exist_ok=False)
    encoded = (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=out_dir, prefix=".decode-", suffix=".json", delete=False) as handle:
            temp_path = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        final_path = os.path.join(out_dir, "decode_result.json")
        os.replace(temp_path, final_path)
        temp_path = None
        return final_path
    finally:
        if temp_path is not None and os.path.exists(temp_path):
            os.unlink(temp_path)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Decode a caller-supplied G05P/layout-2 capture bank.")
    parser.add_argument("--request", required=True, help="UTF-8 JSON request file")
    parser.add_argument("--out", required=True, help="new absolute output directory")
    args = parser.parse_args(argv)
    try:
        request = _load_request(args.request)
        result = decode_request(request)
        _write_result(args.out, result)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        print(f"B132_INPUT_OR_OUTPUT_ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


__all__ = [
    "REQUEST_SCHEMA",
    "RECORD_SCHEMA",
    "RESULT_SCHEMA",
    "decode_request",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
