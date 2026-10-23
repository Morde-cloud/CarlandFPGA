#!/usr/bin/env python3
"""Bounded author fixture for the frozen digital UART link composition."""

from __future__ import annotations

import binascii
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TRANSPORT = ROOT / "competition/deepeye/fpga/transport"
TESTS = ROOT / "competition/deepeye/tests/rtl/transport"
DOC = TRANSPORT / "uart_link_fixture.md"
TB = TESTS / "tb_uart_link_fixture.sv"
AUTHOR = (
    ROOT
    / "competition/deepeye/evidence/transport/uart-link-fixture-20261024-34/author"
)
SCOPE = (
    ROOT.parents[1]
    / "deployment/node-b/evidence/uart-link-fixture-20261024-34/SCOPE.md"
)

MODELSIM = Path("D:/modelsim1/win64")
VLIB = MODELSIM / "vlib.exe"
VLOG = MODELSIM / "vlog.exe"
VSIM = MODELSIM / "vsim.exe"

SOURCE_COMMIT = "bbfb11439b35e0866a6d2486f3857b92ed6cf529"
PUBLISHED_HEAD = "04e3a46eb1169afca0c133815a9b9f3da15d89f5"
CONTRACT_COMMIT = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
CONTRACT_JSON_PATH = "docs/competition/deepeye-2026/immutable_scope.json"
CONTRACT_MD_PATH = "docs/competition/deepeye-2026/immutable_scope.md"
EXPECTED_REQUIREMENTS_SHA = (
    "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
)
EXPECTED_SCOPE_SHA = (
    "4d4c14ce5d83b67e7b1ca0ad86091a11529bff01d483a851988c744135fc2a89"
)
EXPECTED_PRIOR_RUNNER_SHA = (
    "11223f4f42086a5056a9abf65972063735f06ec2e44fb8ae7f7c4262fc809d55"
)
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014/v1"
OPERATION_ID = "B-DEEPEYE-UART-LINK-FIXTURE-20261024-34"
MAIN_THREAD = "01a13b55-095b-7461-8dd5-5476a130bd82"
MAIN_TURN = "01a16933-edc1-7022-8e5f-25b4561a4ea5"

RTL_ORDER = (
    "deepeye_crc16_byte.sv",
    "deepeye_wire_serializer.sv",
    "deepeye_uart_tx.sv",
    "deepeye_uart_frame_tx.sv",
    "deepeye_wire_uart_tx.sv",
    "deepeye_wire_parser.sv",
    "deepeye_uart_rx.sv",
    "deepeye_uart_wire_rx.sv",
)
RTL_HASHES = {
    "deepeye_wire_uart_tx.sv": (
        "4998acb76fed7e53405816c91203bc93df622f05b621da342e1cc8178f51133d"
    ),
    "deepeye_uart_wire_rx.sv": (
        "b6abab4e1be54ee61bd45e4d7adfcfea8db39f7574d3ce2ae7b7030ff74ade2c"
    ),
    "deepeye_wire_serializer.sv": (
        "efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885"
    ),
    "deepeye_wire_parser.sv": (
        "7806c5d08785b96eae3708d9fd6d6002ef82faa4416a1f7244da73bece552649"
    ),
    "deepeye_uart_tx.sv": (
        "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47"
    ),
    "deepeye_uart_rx.sv": (
        "935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f"
    ),
    "deepeye_uart_frame_tx.sv": (
        "83261e4c5a317500e224f5cd0e9ce538f067be24d3957dd98c7116425e706be3"
    ),
    "deepeye_crc16_byte.sv": (
        "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f"
    ),
}

MODE_NORMAL = 0
MODE_BIT_ERROR = 1
MODE_BAD_STOP = 2
MODE_TX_CANCEL = 3
MODE_RX_CANCEL_HEADER = 4
MODE_RX_CANCEL_PAYLOAD = 5
MODE_RX_CANCEL_PENDING = 6
MODE_OVERRUN = 7
MODE_RETIRED_THEN_ERROR = 8
MODE_IMMEDIATE_PAIR = 20

MAX_PAYLOAD = 32
MAX_WIRE = 46
EXPECTED_SIMULATIONS = 5
EXPECTED_COMMANDS = 9

DIAGNOSTIC_PATTERN = re.compile(
    r"\*\*\s+(?:Error|Warning|Fatal)\b", re.IGNORECASE
)
TALLY_PATTERN = re.compile(r"Errors:\s*([0-9]+),\s*Warnings:\s*([0-9]+)")
EVENT_TIME_PATTERN = re.compile(r"^t_ps=([0-9]+) (.*)$")
FIELD_TOKEN_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9_]*)=([^\s=]+)")
PROTOCOL_MARKERS = (
    "LINK_SUITE_BEGIN",
    "LINK_SUITE_TALLY",
    "LINK_SUITE_STATUS",
    "LINK_WATCHDOG_TIMEOUT",
    "CASE_BEGIN",
    "CASE_END",
)
CASE_BEGIN_KEYS = frozenset({"suite", "case", "name", "mode", "records"})
CASE_END_KEYS = frozenset(
    {"suite", "case", "name", "checks", "failures", "result"}
)
SUITE_TALLY_KEYS = frozenset({"suite", "cases", "checks", "failures"})
SUITE_STATUS_KEYS = frozenset({"suite", "result"})
TX_DE_KEYS = frozenset({"value", "tx", "busy"})
TX_PIN_KEYS = frozenset({"tx", "de", "busy"})
RX_OUT_HANDSHAKE_KEYS = frozenset(
    {"type", "epoch", "seq", "tick", "len", "payload"}
)
LINK_COUNTERS_KEYS = frozenset({
    "tx_admitted", "tx_sent", "tx_aborted",
    "uart_frames", "uart_retired", "uart_overruns", "uart_framing",
    "uart_false_starts", "uart_aborted",
    "parser_bytes", "parser_frames", "parser_retired", "parser_version",
    "parser_length", "parser_crc", "parser_aborted",
    "tx_edges", "rx_edges",
})

# Pinned from the complete zero-error observed run. Every suite and case must
# have an entry; missing or changed counts fail closed.
CASE_CHECK_COUNTS: dict[tuple[int, str], int] = {
    (0, "default_zero_maxmeta"): 2,
    (0, "default_one_minmeta"): 2,
    (1, "len_0"): 2,
    (1, "len_1"): 2,
    (1, "len_2"): 2,
    (1, "len_3"): 2,
    (1, "len_4"): 2,
    (1, "len_5"): 2,
    (1, "len_6"): 2,
    (1, "len_7"): 2,
    (1, "len_8"): 2,
    (1, "len_9"): 2,
    (1, "len_10"): 2,
    (1, "len_11"): 2,
    (1, "len_12"): 2,
    (1, "len_13"): 2,
    (1, "len_14"): 2,
    (1, "len_15"): 2,
    (1, "len_16"): 2,
    (1, "len_17"): 2,
    (1, "len_18"): 2,
    (1, "len_19"): 2,
    (1, "len_20"): 2,
    (1, "len_21"): 2,
    (1, "len_22"): 2,
    (1, "len_23"): 2,
    (1, "len_24"): 2,
    (1, "len_25"): 2,
    (1, "len_26"): 2,
    (1, "len_27"): 2,
    (1, "len_28"): 2,
    (1, "len_29"): 2,
    (1, "len_30"): 2,
    (1, "len_31"): 2,
    (1, "len_32"): 2,
    (1, "immediate_pair"): 4,
    (2, "early_zero_extrema"): 2,
    (2, "early_one_minmeta"): 2,
    (2, "early_max_ramp"): 2,
    (2, "early_bubbles"): 2,
    (3, "late_zero_extrema"): 2,
    (3, "late_one_minmeta"): 2,
    (3, "late_max_ramp"): 2,
    (3, "late_bubbles"): 2,
    (4, "bit_error_crc"): 6,
    (4, "bad_stop_discard"): 7,
    (4, "tx_cancel_rx_recover"): 6,
    (4, "rx_cancel_header"): 6,
    (4, "rx_cancel_payload"): 7,
    (4, "rx_cancel_pending"): 7,
    (4, "uart_overrun_discard"): 10,
    (4, "retired_then_error"): 6,
}
SUITE_LEVEL_CHECKS: dict[int, int] = {
    0: 30,
    1: 129,
    2: 36,
    3: 36,
    4: 65,
}


class RunnerFailure(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(data)


def write_json_new(path: Path, value: object) -> None:
    write_new(
        path,
        (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def canonical_requirements_sha(contract: dict) -> str:
    encoded = json.dumps(
        contract["requirements"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(encoded)


def git_show(commit: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{commit}:{path}"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RunnerFailure(
            f"git show failed for {commit}:{path}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout


def git_rev_parse(ref: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", ref],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RunnerFailure(f"git rev-parse failed for {ref}")
    return completed.stdout.decode("ascii").strip()


@dataclass(frozen=True)
class Frame:
    type_value: int
    epoch: int
    seq: int
    tick: int
    payload: bytes

    def __post_init__(self) -> None:
        if not 0 <= self.type_value <= 255:
            raise RunnerFailure("frame type out of range")
        if not 0 <= self.epoch <= 255:
            raise RunnerFailure("frame epoch out of range")
        if not 0 <= self.seq <= 0xFFFF:
            raise RunnerFailure("frame seq out of range")
        if not 0 <= self.tick <= 0xFFFFFFFF:
            raise RunnerFailure("frame tick out of range")
        if not 0 <= len(self.payload) <= MAX_PAYLOAD:
            raise RunnerFailure("frame payload length out of range")


@dataclass(frozen=True)
class Record:
    case_id: int
    record_index: int
    last_in_case: bool
    mode: int
    frame: Frame
    target_byte: int
    target_bit: int
    expect_output: int
    expect_sent: int
    expect_aborted: int
    expect_frames: int
    wire: bytes


@dataclass(frozen=True)
class Case:
    case_id: int
    name: str
    records: tuple[Record, ...]


@dataclass(frozen=True)
class Suite:
    suite_id: int
    name: str
    tx_period_ps: int
    rx_period_ps: int
    rx_phase_ps: int
    tx_clock_hz: int
    tx_baud: int
    tx_pre: int
    tx_post: int
    rx_clock_hz: int
    rx_baud: int
    cases: tuple[Case, ...]
    wall_timeout_s: int

    @property
    def records(self) -> tuple[Record, ...]:
        return tuple(record for case in self.cases for record in case.records)


def build_wire(frame: Frame) -> bytes:
    covered = (
        b"\x03"
        + bytes([frame.type_value, len(frame.payload), frame.epoch])
        + struct.pack("<H", frame.seq)
        + struct.pack("<I", frame.tick)
        + frame.payload
    )
    crc = binascii.crc_hqx(covered, 0xFFFF)
    return b"\xA5\x5A" + covered + struct.pack("<H", crc)


def crc_bitwise_ccitt_false(data: bytes) -> int:
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def make_record(
    case_id: int,
    record_index: int,
    last_in_case: bool,
    mode: int,
    frame: Frame,
    *,
    target_byte: int = 0,
    target_bit: int = 0,
    expect_output: int = 1,
    expect_sent: int = 1,
    expect_aborted: int = 0,
    expect_frames: int = 1,
) -> Record:
    wire = build_wire(frame)
    if frame.payload and crc_bitwise_ccitt_false(wire[2:-2]) != int.from_bytes(
        wire[-2:], "little"
    ):
        raise RunnerFailure("binascii/bitwise CRC disagreement")
    if len(wire) != 14 + len(frame.payload):
        raise RunnerFailure("wire length mismatch")
    return Record(
        case_id=case_id,
        record_index=record_index,
        last_in_case=last_in_case,
        mode=mode,
        frame=frame,
        target_byte=target_byte,
        target_bit=target_bit,
        expect_output=expect_output,
        expect_sent=expect_sent,
        expect_aborted=expect_aborted,
        expect_frames=expect_frames,
        wire=wire,
    )


def add_case(cases: list[Case], name: str, records: list[tuple[int, Frame, dict]]) -> None:
    case_id = len(cases)
    built: list[Record] = []
    for index, (mode, frame, options) in enumerate(records):
        built.append(
            make_record(
                case_id,
                index,
                index == (len(records) - 1),
                mode,
                frame,
                **options,
            )
        )
    cases.append(Case(case_id, name, tuple(built)))


def normal_options() -> dict:
    return {
        "expect_output": 1,
        "expect_sent": 1,
        "expect_aborted": 0,
        "expect_frames": 1,
    }


def error_options() -> dict:
    return {
        "expect_output": 0,
        "expect_sent": 1,
        "expect_aborted": 0,
        "expect_frames": 0,
    }


def make_suites() -> tuple[Suite, ...]:
    suites: list[Suite] = []

    cases: list[Case] = []
    add_case(
        cases,
        "default_zero_maxmeta",
        [(MODE_NORMAL, Frame(0xFF, 0xFF, 0xFFFF, 0xFFFFFFFF, b""), normal_options())],
    )
    add_case(
        cases,
        "default_one_minmeta",
        [(MODE_NORMAL, Frame(0x00, 0x00, 0x0000, 0x00000000, b"\x00"), normal_options())],
    )
    suites.append(
        Suite(0, "default", 10000, 10000, 2500, 100_000_000, 9600, 0, 0,
              100_000_000, 9600, tuple(cases), 600)
    )

    cases = []
    cursor = 0
    for length in range(33):
        payload = bytes(
            (((cursor + index) * 73 + 19) & 0xFF) for index in range(length)
        )
        cursor += length
        if length == 0:
            frame = Frame(0xFF, 0xFF, 0xFFFF, 0xFFFFFFFF, payload)
        elif length == 1:
            frame = Frame(0x00, 0x00, 0x0001, 0x01020304, payload)
        elif length == 2:
            frame = Frame(0x80, 0x7F, 0x0102, 0x04030201, payload)
        elif length == 32:
            frame = Frame(0x5A, 0xA5, 0xABCD, 0xDEADBEEF, payload)
        else:
            frame = Frame(
                (length * 17 + 3) & 0xFF,
                (0xFE - length) & 0xFF,
                (length * 257 + 0x1234) & 0xFFFF,
                (length * 0x01010101 + 0x0F0E0D0C) & 0xFFFFFFFF,
                payload,
            )
        add_case(cases, f"len_{length}",
                 [(MODE_NORMAL, frame, normal_options())])
    add_case(
        cases,
        "immediate_pair",
        [
            (MODE_IMMEDIATE_PAIR,
             Frame(0x31, 0x41, 0xA1B2, 0x10203040, b"\x10\x20\x30"),
             normal_options()),
            (MODE_IMMEDIATE_PAIR,
             Frame(0x32, 0x42, 0xB2C3, 0x50607080, b"\xF0\xE0\xD0\xC0\xB0"),
             normal_options()),
        ],
    )
    suites.append(
        Suite(1, "primary_lengths", 10000, 10000, 2500, 64, 4, 2, 3,
              64, 4, tuple(cases), 300)
    )

    for suite_id, name, phase in ((2, "rx_early_9900", 2500),
                                  (3, "rx_late_10100", 2500)):
        prefix = "early" if suite_id == 2 else "late"
        base = 0x60 if suite_id == 2 else 0x70
        cases = []
        add_case(
            cases,
            f"{prefix}_zero_extrema",
            [(MODE_NORMAL,
              Frame(0xFF ^ base, 0xFF, 0xFFFF, 0xFFFFFFFF, b""),
              normal_options())],
        )
        add_case(
            cases,
            f"{prefix}_one_minmeta",
            [(MODE_NORMAL, Frame(0x00, 0x00, 0x0000, 0x00000000, b"\x00"),
              normal_options())],
        )
        add_case(
            cases,
            f"{prefix}_max_ramp",
            [(MODE_NORMAL,
              Frame(0x81, 0x7E, 0x1357, 0x89ABCDEF, bytes(range(32))),
              normal_options())],
        )
        add_case(
            cases,
            f"{prefix}_bubbles",
            [(MODE_NORMAL,
              Frame(base, 0x3C, 0x2468, 0xA5C35A3C,
                    bytes([0x00, 0xFF, 0x55, 0xAA, 0x01, 0x80, 0xFE])),
              normal_options())],
        )
        suites.append(
            Suite(suite_id, name, 10000, 9900 if suite_id == 2 else 10100,
                  phase, 64, 4, 2, 3, 64, 4, tuple(cases), 300)
        )

    cases = []
    payload32 = bytes(((index * 7 + 3) & 0xFF) for index in range(32))
    add_case(
        cases,
        "bit_error_crc",
        [
            (MODE_BIT_ERROR,
             Frame(0x91, 0x71, 0x1111, 0x11223344, payload32),
             {**error_options(), "target_byte": 14, "target_bit": 5}),
            (MODE_BIT_ERROR, Frame(0x92, 0x72, 0x2222, 0x22334455, b"\x01\x02\x03\x04\x05"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "bad_stop_discard",
        [
            (MODE_BAD_STOP,
             Frame(0x93, 0x73, 0x3333, 0x33445566,
                   bytes((index + 0x40) & 0xFF for index in range(20))),
             {**error_options(), "target_byte": 2}),
            (MODE_BAD_STOP, Frame(0x94, 0x74, 0x4444, 0x44556677, b"\xAA\x55\x0F\xF0"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "tx_cancel_rx_recover",
        [
            (MODE_TX_CANCEL,
             Frame(0x95, 0x75, 0x5555, 0x55667788, payload32),
             {"expect_output": 0, "expect_sent": 0, "expect_aborted": 1,
              "expect_frames": 0}),
            (MODE_TX_CANCEL, Frame(0x96, 0x76, 0x6666, 0x66778899, b"\x11\x22\x33\x44\x55"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "rx_cancel_header",
        [
            (MODE_RX_CANCEL_HEADER,
             Frame(0x97, 0x77, 0x7777, 0x778899AA, payload32),
             error_options()),
            (MODE_RX_CANCEL_HEADER, Frame(0x98, 0x78, 0x8888, 0x8899AABB, b"\x61\x62\x63"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "rx_cancel_payload",
        [
            (MODE_RX_CANCEL_PAYLOAD,
             Frame(0x99, 0x79, 0x9999, 0x99AABBCC, payload32),
             error_options()),
            (MODE_RX_CANCEL_PAYLOAD, Frame(0x9A, 0x7A, 0xAAAA, 0xAABBCCDD,
                                           b"\x71\x72\x73\x74"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "rx_cancel_pending",
        [
            (MODE_RX_CANCEL_PENDING,
             Frame(0x9B, 0x7B, 0xBBBB, 0xBBCCDDEE, b"\x81\x82\x83\x84\x85\x86\x87\x88"),
             {"expect_output": 0, "expect_sent": 1, "expect_aborted": 0,
              "expect_frames": 1}),
            (MODE_RX_CANCEL_PENDING, Frame(0x9C, 0x7C, 0xCCCC, 0xCCDDEEFF,
                                           b"\x91\x92\x93\x94\x95"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "uart_overrun_discard",
        [
            (MODE_OVERRUN,
             Frame(0x9D, 0x7D, 0xDDDD, 0xDDEEFF00, b"\xA1\xA2\xA3\xA4"),
             {"expect_output": 0, "expect_sent": 1, "expect_aborted": 0,
              "expect_frames": 1}),
            (MODE_OVERRUN,
             Frame(0x9E, 0x7E, 0xEEEE, 0xEEFF0011, payload32),
             {"expect_output": 0, "expect_sent": 1, "expect_aborted": 0,
              "expect_frames": 0}),
            (MODE_OVERRUN, Frame(0x9F, 0x7F, 0xFFFF, 0xFF001122,
                                 b"\xB1\xB2\xB3\xB4"),
             normal_options()),
        ],
    )
    add_case(
        cases,
        "retired_then_error",
        [
            (MODE_RETIRED_THEN_ERROR,
             Frame(0xA1, 0x81, 0x0F0F, 0x01020304, b"\xC1\xC2\xC3\xC4"),
             normal_options()),
            (MODE_RETIRED_THEN_ERROR,
             Frame(0xA2, 0x82, 0x1F1F, 0x05060708, payload32),
             {**error_options(), "target_byte": 14, "target_bit": 6}),
            (MODE_RETIRED_THEN_ERROR,
             Frame(0xA3, 0x83, 0x2F2F, 0x090A0B0C,
                   b"\xD1\xD2\xD3\xD4\xD5\xD6"),
             normal_options()),
        ],
    )
    suites.append(
        Suite(4, "directed_faults", 10000, 10000, 2500, 64, 4, 2, 3,
              64, 4, tuple(cases), 300)
    )

    for suite in suites:
        for case in suite.cases:
            if case.case_id != (case.records[0].case_id):
                raise RunnerFailure("case/record id mismatch")
            if case.records[-1].last_in_case is not True:
                raise RunnerFailure("case lacks final record")
            if any(record.mode != case.records[0].mode for record in case.records):
                raise RunnerFailure("mixed modes inside case")
    return tuple(suites)


SUITES = make_suites()


def suite_totals(suite: Suite) -> dict[str, int]:
    records = suite.records
    return {
        "cases": len(suite.cases),
        "records": len(records),
        "payload_bytes": sum(len(record.frame.payload) for record in records),
        "wire_bytes": sum(len(record.wire) for record in records),
        "outputs": sum(record.expect_output for record in records),
        "frames": sum(record.expect_frames for record in records),
        "sent": sum(record.expect_sent for record in records),
        "aborted": sum(record.expect_aborted for record in records),
    }


def create_attempt() -> Path:
    AUTHOR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    base = AUTHOR / f"attempt-{stamp}-p{os.getpid()}"
    for suffix in range(100):
        candidate = base if suffix == 0 else Path(f"{base}-{suffix:02d}")
        try:
            candidate.mkdir()
            for child in ("inputs/rtl", "vectors", "raw", "events", "sim",
                          "temp", "pycache", "logs"):
                (candidate / child).mkdir(parents=True)
            return candidate
        except FileExistsError:
            continue
    raise RunnerFailure("could not allocate a fresh attempt directory")


def command_environment(attempt: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["TEMP"] = str((attempt / "temp").resolve())
    env["TMP"] = str((attempt / "temp").resolve())
    env["TMPDIR"] = str((attempt / "temp").resolve())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str((attempt / "pycache").resolve())
    return env


def run_command(
    attempt: Path,
    index: int,
    label: str,
    argv: list[str],
    expected_exits: tuple[int, ...],
    timeout_s: int,
    kind: str,
) -> dict:
    raw_dir = attempt / "raw" / f"{index:03d}_{label}"
    raw_dir.mkdir()
    started = utc_now()
    mono = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            argv,
            cwd=attempt / "sim",
            env=command_environment(attempt),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            check=False,
        )
        stdout = completed.stdout
        stderr = completed.stderr
        returncode = completed.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        returncode = None
    duration = time.monotonic() - mono
    write_new(raw_dir / "stdout.raw", stdout)
    write_new(raw_dir / "stderr.raw", stderr)
    record = {
        "index": index,
        "label": label,
        "kind": kind,
        "argv": argv,
        "cwd": str((attempt / "sim").resolve()),
        "started_utc": started,
        "duration_s": round(duration, 6),
        "timeout_s": timeout_s,
        "timed_out": timed_out,
        "returncode": returncode,
        "expected_exits": list(expected_exits),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "stdout_size": len(stdout),
        "stderr_size": len(stderr),
        "raw_stdout": str((raw_dir / "stdout.raw").relative_to(attempt)),
        "raw_stderr": str((raw_dir / "stderr.raw").relative_to(attempt)),
    }
    record["accepted_exit"] = (not timed_out and returncode in expected_exits)
    write_json_new(raw_dir / "command.json", record)
    marker = "PASS" if record["accepted_exit"] else "FAIL"
    print(f"COMMAND {index:03d} {marker} {label} exit={returncode} timeout={timed_out}")
    return record


def combine_output(record: dict, attempt: Path) -> bytes:
    stdout = (attempt / record["raw_stdout"]).read_bytes()
    stderr = (attempt / record["raw_stderr"]).read_bytes()
    return stdout + (b"" if stdout.endswith(b"\n") else b"\n") + stderr


def decode_output(data: bytes, label: str) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerFailure(f"{label}: non-UTF-8 output: {exc}") from exc


def normalize_sim_line(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith("#"):
        stripped = stripped[1:]
        if stripped.startswith(" "):
            stripped = stripped[1:]
    return stripped.strip()


def normalized_lines(text: str) -> list[str]:
    return [normalize_sim_line(line) for line in text.splitlines()]


def snapshot_inputs(attempt: Path) -> dict:
    if sha256_file(SCOPE) != EXPECTED_SCOPE_SHA:
        raise RunnerFailure("scope SHA mismatch")
    contract_bytes = git_show(CONTRACT_COMMIT, CONTRACT_JSON_PATH)
    contract = json.loads(contract_bytes.decode("utf-8"))
    requirements = contract.get("requirements")
    if not isinstance(requirements, list) or len(requirements) != 15:
        raise RunnerFailure("contract requirements are not 15 items")
    ids = [str(item.get("id", "")) for item in requirements]
    if ids != [f"H{index:02d}" for index in range(1, 16)]:
        raise RunnerFailure(f"contract id order mismatch: {ids!r}")
    requirements_sha = canonical_requirements_sha(contract)
    if requirements_sha != EXPECTED_REQUIREMENTS_SHA:
        raise RunnerFailure("canonical requirements SHA mismatch")

    head = git_rev_parse("HEAD")
    if head != PUBLISHED_HEAD:
        raise RunnerFailure(f"worktree HEAD {head} != published head {PUBLISHED_HEAD}")
    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor",
         SOURCE_COMMIT, PUBLISHED_HEAD],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if ancestor.returncode != 0:
        raise RunnerFailure("exact source commit is not an ancestor of publication head")

    manifest: list[dict] = []

    def add_snapshot(role: str, name: str, data: bytes, expected: str | None) -> None:
        actual = sha256_bytes(data)
        if expected is not None and actual != expected:
            raise RunnerFailure(f"{role} {name}: {actual} != {expected}")
        path = attempt / "inputs" / role / name
        write_new(path, data)
        manifest.append({
            "role": role,
            "name": name,
            "snapshot": str(path.relative_to(attempt)),
            "sha256": actual,
            "expected_sha256": expected,
            "size": len(data),
        })

    add_snapshot("scope", "SCOPE.md", SCOPE.read_bytes(), EXPECTED_SCOPE_SHA)
    add_snapshot("contract", "immutable_scope.json", contract_bytes, None)
    add_snapshot("contract", "immutable_scope.md",
                 git_show(CONTRACT_COMMIT, CONTRACT_MD_PATH), None)
    for name in RTL_ORDER:
        data = git_show(SOURCE_COMMIT, f"competition/deepeye/fpga/transport/{name}")
        add_snapshot("rtl", name, data, RTL_HASHES[name])
        worktree_path = TRANSPORT / name
        if sha256_file(worktree_path) != RTL_HASHES[name]:
            raise RunnerFailure(f"worktree read-only RTL changed: {name}")
    prior_data = git_show(
        SOURCE_COMMIT,
        "competition/deepeye/tools/transport/run_uart_wire_rx.py",
    )
    add_snapshot("pattern", "run_uart_wire_rx.py", prior_data,
                 EXPECTED_PRIOR_RUNNER_SHA)
    add_snapshot("owned", "tb_uart_link_fixture.sv", TB.read_bytes(), None)
    add_snapshot("owned", "run_uart_link_fixture.py",
                 Path(__file__).resolve().read_bytes(), None)
    add_snapshot("owned", "uart_link_fixture.md", DOC.read_bytes(), None)

    binding = {
        "task_id": TASK_ID,
        "operation_id": OPERATION_ID,
        "main_thread": MAIN_THREAD,
        "main_turn": MAIN_TURN,
        "executor": "DeepSeek V4.1 Flash child",
        "contract": "DEEPEYE-HUMAN-LOCK-20261014/revision1",
        "contract_commit": CONTRACT_COMMIT,
        "contract_ids": ids,
        "requirements_sha256": requirements_sha,
        "frozen_design": FROZEN_DESIGN,
        "exact_source_commit": SOURCE_COMMIT,
        "published_pr_head": PUBLISHED_HEAD,
        "worktree_head": head,
        "rtl_hashes": RTL_HASHES,
        "rtl_order": list(RTL_ORDER),
        "scope_sha256": EXPECTED_SCOPE_SHA,
        "prior_runner_sha256": EXPECTED_PRIOR_RUNNER_SHA,
        "owned_inputs": manifest,
        "requirements": requirements,
    }
    write_json_new(attempt / "SOURCE_BINDING.json", binding)
    return binding


def write_vectors(suite: Suite, attempt: Path) -> dict:
    path = attempt / "vectors" / f"suite_{suite.suite_id}.txt"
    lines: list[str] = [f"{suite.suite_id} {len(suite.records)}"]
    for case in suite.cases:
        for record in case.records:
            frame = record.frame
            lines.append(
                " ".join(str(value) for value in (
                    record.case_id,
                    record.record_index,
                    int(record.last_in_case),
                    record.mode,
                    len(frame.payload),
                    frame.type_value,
                    frame.epoch,
                    frame.seq,
                    frame.tick,
                    len(record.wire),
                    record.target_byte,
                    record.target_bit,
                    record.expect_output,
                    record.expect_sent,
                    record.expect_aborted,
                    record.expect_frames,
                ))
            )
            lines.extend(
                str(frame.payload[index] if index < len(frame.payload) else 0)
                for index in range(MAX_PAYLOAD)
            )
            lines.extend(
                str(record.wire[index] if index < len(record.wire) else 0)
                for index in range(MAX_WIRE)
            )
    data = ("\n".join(lines) + "\n").encode("ascii")
    write_new(path, data)

    cases_json = []
    for case in suite.cases:
        cases_json.append({
            "case_id": case.case_id,
            "name": case.name,
            "mode": case.records[0].mode,
            "records": [
                {
                    "record_index": record.record_index,
                    "last_in_case": record.last_in_case,
                    "length": len(record.frame.payload),
                    "type": record.frame.type_value,
                    "epoch": record.frame.epoch,
                    "seq": record.frame.seq,
                    "tick": record.frame.tick,
                    "payload_hex": record.frame.payload.hex(),
                    "wire_hex": record.wire.hex(),
                    "target_byte": record.target_byte,
                    "target_bit": record.target_bit,
                    "expect_output": record.expect_output,
                    "expect_sent": record.expect_sent,
                    "expect_aborted": record.expect_aborted,
                    "expect_frames": record.expect_frames,
                }
                for record in case.records
            ],
        })
    manifest = {
        "suite_id": suite.suite_id,
        "suite_name": suite.name,
        "text_path": str(path.relative_to(attempt)),
        "text_sha256": sha256_bytes(data),
        "text_size": len(data),
        "totals": suite_totals(suite),
        "cases": cases_json,
    }
    write_json_new(attempt / "vectors" / f"suite_{suite.suite_id}.json", manifest)
    return manifest


def parse_pairs(message: str) -> dict[str, str]:
    result: dict[str, str] = {}
    tokens = message.split()
    if not tokens:
        raise RunnerFailure("empty field list")
    for token in tokens:
        match = FIELD_TOKEN_PATTERN.fullmatch(token)
        if match is None:
            raise RunnerFailure(f"malformed field token: {token!r}")
        key, value = match.groups()
        if key in result:
            raise RunnerFailure(f"duplicate field key: {key!r}")
        result[key] = value
    return result


def parse_exact_pairs(
    message: str, expected_keys: frozenset[str], label: str
) -> dict[str, str]:
    pairs = parse_pairs(message)
    if set(pairs) != set(expected_keys):
        raise RunnerFailure(f"{label}: field set mismatch")
    return pairs


def classify_protocol_line(line: str) -> tuple[str, str] | None:
    for marker in PROTOCOL_MARKERS:
        if line == marker:
            return marker, ""
        prefix = marker + " "
        if line.startswith(prefix):
            return marker, line[len(prefix):]
    return None


def parse_standard_output(text: str, suite: Suite, attempt: Path,
                          vector_manifest: dict) -> dict:
    lines = normalized_lines(text)
    if any(DIAGNOSTIC_PATTERN.search(line) for line in lines):
        raise RunnerFailure(f"suite {suite.suite_id}: simulator diagnostic present")
    if any("CHECK_FAIL" in line or "CASE_TOTAL_MISMATCH" in line
           for line in lines):
        raise RunnerFailure(f"suite {suite.suite_id}: fixture check failure present")
    tally_candidates = [
        (index, line) for index, line in enumerate(lines)
        if "Errors:" in line or "Warnings:" in line
    ]
    if len(tally_candidates) != 1:
        raise RunnerFailure(f"suite {suite.suite_id}: diagnostic tally count {len(tally_candidates)}")
    tally_index, tally_line = tally_candidates[0]
    if TALLY_PATTERN.fullmatch(tally_line) is None:
        raise RunnerFailure(f"suite {suite.suite_id}: malformed diagnostic tally")
    nonblank = [index for index, line in enumerate(lines) if line]
    if not nonblank or tally_index != nonblank[-1]:
        raise RunnerFailure(f"suite {suite.suite_id}: tally is not final line")
    errors, warnings = map(int, TALLY_PATTERN.fullmatch(tally_line).groups())
    if (errors, warnings) != (0, 0):
        raise RunnerFailure(f"suite {suite.suite_id}: diagnostic tally {errors},{warnings}")

    selected: list[tuple[str, str, str]] = []
    for line in lines:
        if "LINK_" not in line and "CASE_" not in line:
            continue
        classified = classify_protocol_line(line)
        if classified is None:
            raise RunnerFailure(
                f"suite {suite.suite_id}: unknown or decorated protocol marker"
            )
        selected.append((classified[0], classified[1], line))
    if sum(kind == "LINK_SUITE_BEGIN" for kind, _, _ in selected) != 1:
        raise RunnerFailure(f"suite {suite.suite_id}: suite begin marker count")
    if sum(kind == "LINK_SUITE_TALLY" for kind, _, _ in selected) != 1:
        raise RunnerFailure(f"suite {suite.suite_id}: suite tally marker count")
    if sum(kind == "LINK_SUITE_STATUS" for kind, _, _ in selected) != 1:
        raise RunnerFailure(f"suite {suite.suite_id}: suite status marker count")
    if any(kind == "LINK_WATCHDOG_TIMEOUT" for kind, _, _ in selected):
        raise RunnerFailure(f"suite {suite.suite_id}: watchdog marker present")

    begin_index = next(index for index, (kind, _, _) in enumerate(selected)
                       if kind == "LINK_SUITE_BEGIN")
    tally_index2 = next(index for index, (kind, _, _) in enumerate(selected)
                        if kind == "LINK_SUITE_TALLY")
    status_index = next(index for index, (kind, _, _) in enumerate(selected)
                        if kind == "LINK_SUITE_STATUS")
    if not (begin_index == 0 and begin_index < tally_index2 < status_index):
        raise RunnerFailure(f"suite {suite.suite_id}: terminal marker order")
    if status_index != len(selected) - 1:
        raise RunnerFailure(f"suite {suite.suite_id}: status is not final LINK marker")
    begin_pairs = parse_pairs(selected[begin_index][1])
    expected_totals = suite_totals(suite)
    expected_begin = {
        "suite": str(suite.suite_id),
        "cases": str(expected_totals["cases"]),
        "records": str(expected_totals["records"]),
        "tx_clock_hz": str(suite.tx_clock_hz),
        "tx_baud": str(suite.tx_baud),
        "tx_pre": str(suite.tx_pre),
        "tx_post": str(suite.tx_post),
        "rx_clock_hz": str(suite.rx_clock_hz),
        "rx_baud": str(suite.rx_baud),
        "tx_period_ps": str(suite.tx_period_ps),
        "rx_period_ps": str(suite.rx_period_ps),
        "rx_phase_ps": str(suite.rx_phase_ps),
    }
    if begin_pairs != expected_begin:
        raise RunnerFailure(f"suite {suite.suite_id}: begin fields mismatch: {begin_pairs!r}")

    body = selected[1:-2]
    observed: list[dict] = []
    index = 0
    while index < len(body):
        begin_kind, begin_payload, _ = body[index]
        if begin_kind != "CASE_BEGIN":
            raise RunnerFailure(f"suite {suite.suite_id}: expected CASE_BEGIN")
        if (index + 1) >= len(body):
            raise RunnerFailure(f"suite {suite.suite_id}: missing CASE_END")
        end_kind, end_payload, _ = body[index + 1]
        if end_kind != "CASE_END":
            raise RunnerFailure(f"suite {suite.suite_id}: CASE_BEGIN not paired")
        begin_pairs_case = parse_exact_pairs(
            begin_payload, CASE_BEGIN_KEYS,
            f"suite {suite.suite_id}: CASE_BEGIN fields",
        )
        end_pairs_case = parse_exact_pairs(
            end_payload, CASE_END_KEYS,
            f"suite {suite.suite_id}: CASE_END fields",
        )
        if begin_pairs_case.get("name") != end_pairs_case.get("name"):
            raise RunnerFailure(f"suite {suite.suite_id}: case name begin/end mismatch")
        if end_pairs_case.get("result") != "PASS":
            raise RunnerFailure(f"suite {suite.suite_id}: case result is not PASS")
        if end_pairs_case.get("failures") != "0":
            raise RunnerFailure(f"suite {suite.suite_id}: case failure count nonzero")
        observed.append({"begin": begin_pairs_case, "end": end_pairs_case})
        index += 2
    if len(observed) != len(suite.cases):
        raise RunnerFailure(f"suite {suite.suite_id}: case count {len(observed)}")
    total_case_checks = 0
    for case, item in zip(suite.cases, observed):
        if item["begin"].get("suite") != str(suite.suite_id):
            raise RunnerFailure(f"suite {suite.suite_id}: case suite mismatch")
        if item["begin"].get("case") != str(case.case_id):
            raise RunnerFailure(f"suite {suite.suite_id}: case id mismatch")
        if item["begin"].get("name") != case.name:
            raise RunnerFailure(f"suite {suite.suite_id}: case name mismatch")
        if item["begin"].get("mode") != str(case.records[0].mode):
            raise RunnerFailure(f"suite {suite.suite_id}: case mode mismatch")
        if item["begin"].get("records") != str(len(case.records)):
            raise RunnerFailure(f"suite {suite.suite_id}: case record count mismatch")
        checks_value = int(item["end"]["checks"])
        total_case_checks += checks_value
        expected_checks = CASE_CHECK_COUNTS.get((suite.suite_id, case.name))
        if expected_checks is None:
            raise RunnerFailure(
                f"suite {suite.suite_id} case {case.name}: checks are not pinned"
            )
        if checks_value != expected_checks:
            raise RunnerFailure(
                f"suite {suite.suite_id} case {case.name}: checks {checks_value} "
                f"!= {expected_checks}"
            )

    tally_pairs = parse_exact_pairs(
        selected[tally_index2][1], SUITE_TALLY_KEYS,
        f"suite {suite.suite_id}: suite tally fields",
    )
    total_checks = int(tally_pairs["checks"])
    suite_checks_expected = SUITE_LEVEL_CHECKS.get(suite.suite_id)
    if tally_pairs.get("suite") != str(suite.suite_id):
        raise RunnerFailure(f"suite {suite.suite_id}: tally suite mismatch")
    if tally_pairs.get("cases") != str(len(suite.cases)):
        raise RunnerFailure(f"suite {suite.suite_id}: tally case count mismatch")
    if tally_pairs.get("failures") != "0":
        raise RunnerFailure(f"suite {suite.suite_id}: tally failure count nonzero")
    if suite_checks_expected is None:
        raise RunnerFailure(f"suite {suite.suite_id}: suite checks are not pinned")
    expected_total = total_case_checks + suite_checks_expected
    if total_checks != expected_total:
        raise RunnerFailure(
            f"suite {suite.suite_id}: checks {total_checks} != {expected_total}"
        )
    status_pairs = parse_exact_pairs(
        selected[status_index][1], SUITE_STATUS_KEYS,
        f"suite {suite.suite_id}: suite status fields",
    )
    if status_pairs != {"suite": str(suite.suite_id), "result": "PASS"}:
        raise RunnerFailure(f"suite {suite.suite_id}: status marker mismatch")
    return {
        "cases": len(observed),
        "case_checks": total_case_checks,
        "total_checks": total_checks,
        "observed_case_checks": {
            f"{suite.suite_id}:{case.name}": int(item["end"]["checks"])
            for case, item in zip(suite.cases, observed)
        },
    }


def load_event_log(path: Path, suite: Suite) -> tuple[list[tuple[int, str]], int]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerFailure(f"suite {suite.suite_id}: event log is not UTF-8") from exc
    lines = text.splitlines()
    if not lines:
        raise RunnerFailure(f"suite {suite.suite_id}: empty event log")
    end_pattern = re.compile(
        rf"t_ps=([0-9]+) LINK_EVENT_LOG_END suite={suite.suite_id} "
        rf"rows=([0-9]+) status=OK"
    )
    end_match = end_pattern.fullmatch(lines[-1])
    if end_match is None:
        raise RunnerFailure(f"suite {suite.suite_id}: bad event end marker")
    declared_rows = int(end_match.group(2))
    event_lines = lines[:-1]
    if declared_rows != len(event_lines):
        raise RunnerFailure(
            f"suite {suite.suite_id}: event row count {len(event_lines)} != {declared_rows}"
        )
    events: list[tuple[int, str]] = []
    previous = -1
    for line in event_lines:
        match = EVENT_TIME_PATTERN.fullmatch(line)
        if match is None:
            raise RunnerFailure(f"suite {suite.suite_id}: malformed event line: {line!r}")
        stamp = int(match.group(1))
        if stamp < previous:
            raise RunnerFailure(f"suite {suite.suite_id}: event time regressed")
        previous = stamp
        message = match.group(2)
        if "TRUNCATED" in message or message.startswith("CHECK_FAIL"):
            raise RunnerFailure(f"suite {suite.suite_id}: failing event marker {message}")
        events.append((stamp, message))
    return events, declared_rows


def event_messages(events: list[tuple[int, str]], prefix: str) -> list[tuple[int, str]]:
    return [(stamp, message) for stamp, message in events if message.startswith(prefix)]


def validate_clock_profile(events: list[tuple[int, str]], suite: Suite) -> None:
    profiles = event_messages(events, "LINK_CLOCK_PROFILE ")
    if len(profiles) != 1:
        raise RunnerFailure(f"suite {suite.suite_id}: clock profile count")
    pairs = parse_pairs(profiles[0][1].removeprefix("LINK_CLOCK_PROFILE "))
    expected = {
        "suite": str(suite.suite_id),
        "tx_period_ps": str(suite.tx_period_ps),
        "tx_half_ps": str(suite.tx_period_ps // 2),
        "tx_first_rise_ps": str(suite.tx_period_ps // 2),
        "rx_period_ps": str(suite.rx_period_ps),
        "rx_half_ps": str(suite.rx_period_ps // 2),
        "rx_first_rise_ps": str(suite.rx_phase_ps),
        "rx_phase_ps": str(suite.rx_phase_ps),
        "tx_clock_hz": str(suite.tx_clock_hz),
        "tx_baud": str(suite.tx_baud),
        "tx_pre": str(suite.tx_pre),
        "tx_post": str(suite.tx_post),
        "rx_clock_hz": str(suite.rx_clock_hz),
        "rx_baud": str(suite.rx_baud),
    }
    if pairs != expected:
        raise RunnerFailure(f"suite {suite.suite_id}: clock profile mismatch")


def validate_frame_wire(
    pin_events: list[tuple[int, int, int]],
    rise: int,
    fall: int,
    wire: bytes,
    suite: Suite,
) -> None:
    cursor = rise
    local = [(stamp, value) for stamp, value, de in pin_events
             if rise <= stamp <= fall and de == 1]
    for byte_index, expected_byte in enumerate(wire):
        starts = [(stamp, value) for stamp, value in local
                  if stamp >= cursor and stamp < fall and value == 0]
        if not starts:
            raise RunnerFailure(
                f"suite {suite.suite_id}: missing start byte {byte_index} "
                f"in DE interval {rise}..{fall}"
            )
        start = starts[0][0]
        boundaries = [
            start + ((k * suite.tx_clock_hz + suite.tx_baud - 1) // suite.tx_baud)
            * suite.tx_period_ps
            for k in range(1, 10)
        ]
        expected_transitions = [(start, 0)]
        previous_value = 0
        for bit_index in range(8):
            bit_value = (expected_byte >> bit_index) & 1
            if bit_value != previous_value:
                expected_transitions.append((boundaries[bit_index], bit_value))
                previous_value = bit_value
        if previous_value != 1:
            expected_transitions.append((boundaries[8], 1))
            previous_value = 1
        observed = [(stamp, value) for stamp, value in local
                    if start <= stamp <= boundaries[8]]
        if observed != expected_transitions:
            raise RunnerFailure(
                f"suite {suite.suite_id}: TX wire mismatch byte {byte_index}: "
                f"observed={observed!r} expected={expected_transitions!r}"
            )
        cursor = boundaries[8] + 1
    trailing = [(stamp, value) for stamp, value in local
                if cursor <= stamp < fall]
    if trailing:
        raise RunnerFailure(
            f"suite {suite.suite_id}: trailing TX edge after final byte: {trailing!r}"
        )


def validate_output_descriptor(record: Record, pairs: dict[str, str],
                               suite: Suite) -> None:
    expected = {
        "type": f"{record.frame.type_value:02x}",
        "epoch": f"{record.frame.epoch:02x}",
        "seq": f"{record.frame.seq:04x}",
        "tick": f"{record.frame.tick:08x}",
        "len": str(len(record.frame.payload)),
        "payload": record.frame.payload.ljust(32, b"\x00")[::-1].hex(),
    }
    if pairs != expected:
        raise RunnerFailure(
            f"suite {suite.suite_id}: output descriptor mismatch: "
            f"{pairs!r} != {expected!r}"
        )


def validate_events(events: list[tuple[int, str]], suite: Suite) -> dict:
    validate_clock_profile(events, suite)
    records = suite.records
    de_events = []
    for stamp, message in event_messages(events, "TX_DE "):
        pairs = parse_exact_pairs(
            message.removeprefix("TX_DE "), TX_DE_KEYS,
            f"suite {suite.suite_id}: TX_DE fields",
        )
        de_events.append((stamp, int(pairs["value"])))
    intervals: list[tuple[int, int]] = []
    open_rise: int | None = None
    seen_rise = False
    for stamp, value in de_events:
        if value == 1:
            if open_rise is not None:
                raise RunnerFailure(f"suite {suite.suite_id}: overlapping DE rise")
            open_rise = stamp
            seen_rise = True
        elif value == 0:
            if open_rise is None:
                if not seen_rise:
                    continue
                raise RunnerFailure(f"suite {suite.suite_id}: DE fall without rise")
            intervals.append((open_rise, stamp))
            open_rise = None
    if open_rise is not None:
        raise RunnerFailure(f"suite {suite.suite_id}: unterminated DE interval")
    if len(intervals) != len(records):
        raise RunnerFailure(
            f"suite {suite.suite_id}: DE intervals {len(intervals)} != records {len(records)}"
        )

    pin_events: list[tuple[int, int, int]] = []
    for stamp, message in event_messages(events, "TX_PIN "):
        pairs = parse_exact_pairs(
            message.removeprefix("TX_PIN "), TX_PIN_KEYS,
            f"suite {suite.suite_id}: TX_PIN fields",
        )
        tx_value = int(pairs["tx"], 2)
        de_value = int(pairs["de"], 2)
        pin_events.append((stamp, tx_value, de_value))
    for record, (rise, fall) in zip(records, intervals):
        if record.expect_sent == 1:
            validate_frame_wire(pin_events, rise, fall, record.wire, suite)
        else:
            interval_edges = [item for item in pin_events if rise <= item[0] < fall]
            if not any(value == 0 for _, value, _ in interval_edges):
                raise RunnerFailure(f"suite {suite.suite_id}: canceled frame has no TX start")
            if fall <= rise:
                raise RunnerFailure(f"suite {suite.suite_id}: invalid canceled interval")

    if len(event_messages(events, "TX_CFG_ACCEPT ")) != len(records):
        raise RunnerFailure(f"suite {suite.suite_id}: TX config accepted count")
    expected_payload = sum(len(record.frame.payload) for record in records)
    if len(event_messages(events, "TX_PAYLOAD_ACCEPT ")) != expected_payload:
        raise RunnerFailure(f"suite {suite.suite_id}: TX payload accepted count")

    handshakes: list[tuple[int, dict[str, str]]] = []
    for stamp, message in event_messages(events, "RX_OUT_HANDSHAKE "):
        handshakes.append((
            stamp,
            parse_exact_pairs(
                message.removeprefix("RX_OUT_HANDSHAKE "),
                RX_OUT_HANDSHAKE_KEYS,
                f"suite {suite.suite_id}: RX_OUT_HANDSHAKE fields",
            ),
        ))
    expected_outputs = [record for record in records if record.expect_output == 1]
    if len(handshakes) != len(expected_outputs):
        raise RunnerFailure(
            f"suite {suite.suite_id}: output handshakes {len(handshakes)} != {len(expected_outputs)}"
        )
    for record, (_, pairs) in zip(expected_outputs, handshakes):
        validate_output_descriptor(record, pairs, suite)

    modes = {record.mode for record in records}
    if MODE_BIT_ERROR in modes:
        expected_bit_faults = 1 + int(MODE_RETIRED_THEN_ERROR in modes)
        if len(event_messages(events, "FAULT_BIT_ERROR ")) != expected_bit_faults:
            raise RunnerFailure(f"suite {suite.suite_id}: bit-error fault count")
        if not any("code=3" in message
                   for _, message in event_messages(events, "RX_PARSER_ERROR ")):
            raise RunnerFailure(f"suite {suite.suite_id}: bit error did not CRC fail")
    if MODE_BAD_STOP in modes:
        if len(event_messages(events, "FAULT_BAD_STOP ")) != 1:
            raise RunnerFailure(f"suite {suite.suite_id}: bad-stop fault count")
        if not any("framing=1" in message
                   for _, message in event_messages(events, "RX_LINE_ERROR ")):
            raise RunnerFailure(f"suite {suite.suite_id}: bad stop did not frame")
    if MODE_TX_CANCEL in modes:
        tx = event_messages(events, "TX_CANCEL_ASSERT reason=mid_frame")
        rx = event_messages(events, "RX_CANCEL_ASSERT reason=tx_cancel_recovery")
        if len(tx) != 1 or len(rx) != 1:
            raise RunnerFailure(f"suite {suite.suite_id}: cancel recovery missing")
        if rx[0][0] < tx[0][0]:
            raise RunnerFailure(f"suite {suite.suite_id}: RX cancel preceded TX cancel")
    if any(mode in modes for mode in (MODE_RX_CANCEL_HEADER,
                                      MODE_RX_CANCEL_PAYLOAD)):
        if len(event_messages(events, "RX_CANCEL value=1")) < 1:
            raise RunnerFailure(f"suite {suite.suite_id}: explicit RX cancel missing")
    if MODE_RX_CANCEL_PENDING in modes:
        if not event_messages(events, "RX_OUT_PENDING_INVALIDATED"):
            raise RunnerFailure(f"suite {suite.suite_id}: pending invalidation missing")
    if MODE_OVERRUN in modes:
        if not event_messages(events, "RX_OVERRUN_OBSERVED"):
            raise RunnerFailure(f"suite {suite.suite_id}: overrun marker missing")
        if not event_messages(events, "RX_OUT_PENDING_INVALIDATED"):
            raise RunnerFailure(f"suite {suite.suite_id}: overrun pending invalidation missing")
        if not any("overrun=1" in message
                   for _, message in event_messages(events, "RX_LINE_ERROR ")):
            raise RunnerFailure(f"suite {suite.suite_id}: overrun line bit missing")
    if MODE_RETIRED_THEN_ERROR in modes:
        retired = event_messages(events, "RETIRED_BEFORE_LATER_ERROR ")
        parser_error = event_messages(events, "RX_PARSER_ERROR ")
        if len(retired) != 1:
            raise RunnerFailure(f"suite {suite.suite_id}: retired marker count")
        later_crc_errors = [
            item for item in parser_error
            if "code=3" in item[1] and item[0] > retired[0][0]
        ]
        if len(later_crc_errors) != 1:
            raise RunnerFailure(f"suite {suite.suite_id}: retirement/error time order")

    counters = event_messages(events, "LINK_COUNTERS ")
    if len(counters) != 1:
        raise RunnerFailure(f"suite {suite.suite_id}: LINK_COUNTERS count")
    counter_pairs = parse_exact_pairs(
        counters[0][1].removeprefix("LINK_COUNTERS "), LINK_COUNTERS_KEYS,
        f"suite {suite.suite_id}: LINK_COUNTERS fields",
    )
    totals = suite_totals(suite)
    expected_counters = {
        "tx_admitted": str(totals["records"]),
        "tx_sent": str(totals["sent"]),
        "tx_aborted": str(totals["aborted"]),
        "parser_frames": str(totals["frames"]),
        "parser_retired": str(totals["outputs"]),
    }
    for key, value in expected_counters.items():
        if counter_pairs.get(key) != value:
            raise RunnerFailure(
                f"suite {suite.suite_id}: counter {key}={counter_pairs.get(key)} != {value}"
            )
    if suite.suite_id <= 3:
        for key in ("uart_frames", "uart_retired", "parser_bytes"):
            if counter_pairs.get(key) != str(totals["wire_bytes"]):
                raise RunnerFailure(
                    f"suite {suite.suite_id}: {key} != wire bytes"
                )
        for key in ("uart_overruns", "uart_framing", "uart_false_starts",
                    "uart_aborted", "parser_version", "parser_length",
                    "parser_crc", "parser_aborted"):
            if counter_pairs.get(key) != "0":
                raise RunnerFailure(f"suite {suite.suite_id}: {key} nonzero")

    return {
        "event_rows": len(events),
        "de_intervals": len(intervals),
        "tx_pin_events": len(pin_events),
        "output_handshakes": len(handshakes),
        "fault_mux_enables": len(event_messages(events, "RX_MUX_CONTROL enable=1")),
        "rx_cancel_asserts": len(event_messages(events, "RX_CANCEL value=1")),
        "tx_cancel_asserts": len(event_messages(events, "TX_CANCEL value=1")),
        "line_errors": len(event_messages(events, "RX_LINE_ERROR ")),
        "parser_errors": len(event_messages(events, "RX_PARSER_ERROR ")),
    }


def run_negative_controls(
    suite: Suite,
    events: list[tuple[int, str]],
    event_path: Path,
    stdout_text: str,
    attempt: Path,
    vector_manifest: dict,
) -> list[dict]:
    results: list[dict] = []

    def record(name: str, action, expected_fragment: str) -> None:
        try:
            action()
        except RunnerFailure as exc:
            observed = f"REJECT: {exc}"
            passed = expected_fragment in str(exc)
            results.append({
                "name": name,
                "expected": f"REJECT containing {expected_fragment}",
                "observed": observed,
                "passed": passed,
            })
        else:
            results.append({
                "name": name,
                "expected": f"REJECT containing {expected_fragment}",
                "observed": "ACCEPT",
                "passed": False,
            })

    def wrong_wire() -> None:
        records = [record for record in suite.records if record.expect_sent == 1]
        target = records[0]
        de_events = [
            (stamp, parse_pairs(message.removeprefix("TX_DE ")))
            for stamp, message in event_messages(events, "TX_DE ")
        ]
        rise_index = next(index for index, (_, pairs) in enumerate(de_events)
                          if pairs.get("value") == "1")
        rise = de_events[rise_index][0]
        fall = next(stamp for stamp, pairs in de_events[rise_index + 1:]
                    if pairs.get("value") == "0")
        pin_events = []
        for stamp, message in event_messages(events, "TX_PIN "):
            p = parse_pairs(message.removeprefix("TX_PIN "))
            pin_events.append((stamp, int(p["tx"], 2), int(p["de"], 2)))
        bad_wire = bytearray(target.wire)
        bad_wire[0] ^= 0x01
        validate_frame_wire(pin_events, rise, fall, bytes(bad_wire), suite)

    def wrong_descriptor() -> None:
        expected_outputs = [record for record in suite.records if record.expect_output == 1]
        if not expected_outputs:
            raise RunnerFailure("negative-control setup: no output record")
        target = expected_outputs[0]
        observed = parse_pairs(
            event_messages(events, "RX_OUT_HANDSHAKE ")[0][1]
            .removeprefix("RX_OUT_HANDSHAKE ")
        )
        mutated = dict(observed)
        payload_hex = mutated["payload"]
        mutated["payload"] = (
            payload_hex[:-1] + ("1" if payload_hex[-1] == "0" else "0")
        )
        validate_output_descriptor(target, mutated, suite)

    def truncated_stdout() -> None:
        lines = normalized_lines(stdout_text)
        selected = [line for line in lines if line.startswith("CASE_END ")]
        if not selected:
            raise RunnerFailure("negative-control setup: no CASE_END")
        mutated = "\n".join(line for line in lines if line != selected[0])
        if mutated == "\n".join(lines):
            raise RunnerFailure("negative-control setup: truncation no-op")
        parse_standard_output(mutated, suite, attempt, vector_manifest)

    record("wrong_expected_wire", wrong_wire, "TX wire mismatch")
    record("wrong_output_descriptor", wrong_descriptor,
           "output descriptor mismatch")
    record("missing_case_end", truncated_stdout, "CASE_BEGIN not paired")
    write_json_new(attempt / "negative_controls.json", results)
    for item in results:
        print(
            f"NEGATIVE_CONTROL {'PASS' if item['passed'] else 'FAIL'} "
            f"{item['name']} observed={item['observed']}"
        )
    return results


def verify_readonly_unchanged() -> dict[str, str]:
    observed = {name: sha256_file(TRANSPORT / name) for name in RTL_ORDER}
    for name, digest in observed.items():
        if digest != RTL_HASHES[name]:
            raise RunnerFailure(f"read-only RTL changed during run: {name}")
    return observed


def main() -> int:
    started = utc_now()
    attempt = create_attempt()
    failure_reasons: list[str] = []
    summary: dict = {
        "status": "FAIL",
        "attempt": str(attempt),
        "started_utc": started,
        "task_id": TASK_ID,
        "operation_id": OPERATION_ID,
        "main_thread": MAIN_THREAD,
        "main_turn": MAIN_TURN,
        "limitations": {
            "All29": "not_run",
            "B04": "not_run",
            "R03": "not_run",
            "full_product": "not_run",
            "physical_board": "not_run",
            "system": "not_run",
            "ABI_or_control_grant": "not_run",
            "physical_clock_tolerance": "not_claimed",
            "vivado": "not_invoked",
        },
    }
    commands: list[dict] = []
    suite_results: list[dict] = []
    negative_controls: list[dict] = []
    binding: dict = {}
    vector_manifests: list[dict] = []
    try:
        binding = snapshot_inputs(attempt)
        for suite in SUITES:
            vector_manifests.append(write_vectors(suite, attempt))
        vector_index = {
            str(suite.suite_id): manifest
            for suite, manifest in zip(SUITES, vector_manifests)
        }
        write_json_new(attempt / "VECTOR_MANIFEST.json", {
            "schema": "uart-link-fixture-vectors-v1",
            "primary_payload_values": sorted({
                value
                for record in SUITES[1].records
                for value in record.frame.payload
            }),
            "primary_payload_coverage": len({
                value
                for record in SUITES[1].records
                for value in record.frame.payload
            }),
            "suites": vector_index,
        })
        if len({
            value for record in SUITES[1].records for value in record.frame.payload
        }) != 256:
            raise RunnerFailure("primary suite does not cover all 256 byte values")

        commands.append(run_command(
            attempt, 0, "modelsim_vsim_version", [str(VSIM), "-version"],
            (0,), 60, "version",
        ))
        commands.append(run_command(
            attempt, 1, "modelsim_vlog_version", [str(VLOG), "-version"],
            (0,), 60, "version",
        ))
        commands.append(run_command(
            attempt, 2, "vlib_work", [str(VLIB), "work"],
            (0,), 120, "build",
        ))
        compile_argv = [str(VLOG), "-sv", "-work", "work"]
        compile_argv.extend(
            str((attempt / "inputs" / "rtl" / name).resolve())
            for name in RTL_ORDER
        )
        compile_argv.append(str((attempt / "inputs" / "owned" /
                                 "tb_uart_link_fixture.sv").resolve()))
        compile_record = run_command(
            attempt, 3, "vlog_compile_fixture", compile_argv,
            (0,), 180, "compile",
        )
        commands.append(compile_record)
        compile_text = decode_output(combine_output(compile_record, attempt), "compile")
        if DIAGNOSTIC_PATTERN.search(compile_text):
            raise RunnerFailure("compile emitted error/warning/fatal diagnostic")
        if not compile_record["accepted_exit"]:
            raise RunnerFailure("compile command failed")

        for offset, suite in enumerate(SUITES, start=4):
            vector_path = (attempt / "vectors" / f"suite_{suite.suite_id}.txt").resolve()
            event_path = (attempt / "events" / f"suite_{suite.suite_id}.events.log").resolve()
            argv = [
                str(VSIM), "-c", "tb_uart_link_fixture",
                f"-gSUITE={suite.suite_id}",
                f"-gTX_PERIOD_PS={suite.tx_period_ps}",
                f"-gRX_PERIOD_PS={suite.rx_period_ps}",
                f"-gRX_PHASE_PS={suite.rx_phase_ps}",
                f"-gTX_CLOCK_HZ={suite.tx_clock_hz}",
                f"-gTX_BAUD={suite.tx_baud}",
                f"-gTX_PRE_CYCLES={suite.tx_pre}",
                f"-gTX_POST_CYCLES={suite.tx_post}",
                f"-gRX_CLOCK_HZ={suite.rx_clock_hz}",
                f"-gRX_BAUD={suite.rx_baud}",
                f"+VECTOR_FILE={vector_path}",
                f"+EVENT_LOG={event_path}",
                "-do", "run -all; quit -f",
            ]
            record = run_command(
                attempt, offset, f"vsim_suite_{suite.suite_id}_{suite.name}",
                argv, (0,), suite.wall_timeout_s, "simulation",
            )
            commands.append(record)
            if not record["accepted_exit"]:
                failure_reasons.append(
                    f"suite {suite.suite_id}: simulation exit/timeout"
                )
                continue
            stdout_text = decode_output(
                (attempt / record["raw_stdout"]).read_bytes(),
                f"suite {suite.suite_id} stdout",
            )
            stderr_text = decode_output(
                (attempt / record["raw_stderr"]).read_bytes(),
                f"suite {suite.suite_id} stderr",
            )
            if stderr_text.strip():
                raise RunnerFailure(f"suite {suite.suite_id}: nonempty stderr")
            parse_info = parse_standard_output(
                stdout_text, suite, attempt, vector_manifests[suite.suite_id]
            )
            events, rows = load_event_log(event_path, suite)
            event_info = validate_events(events, suite)
            digest = sha256_file(event_path)
            (attempt / "logs" / f"suite_{suite.suite_id}.stdout.log").write_bytes(
                (attempt / record["raw_stdout"]).read_bytes()
            )
            suite_results.append({
                "suite_id": suite.suite_id,
                "suite_name": suite.name,
                "command_index": record["index"],
                "status": "PASS",
                "cases": parse_info["cases"],
                "case_checks": parse_info["case_checks"],
                "total_checks": parse_info["total_checks"],
                "observed_case_checks": parse_info["observed_case_checks"],
                "vector_sha256": vector_manifests[suite.suite_id]["text_sha256"],
                "event_log": str(event_path.relative_to(attempt)),
                "event_sha256": digest,
                "event_rows": rows,
                **event_info,
            })

        if len(suite_results) == EXPECTED_SIMULATIONS and not failure_reasons:
            primary_suite = SUITES[1]
            primary_result = suite_results[1]
            primary_events, _ = load_event_log(
                attempt / primary_result["event_log"], primary_suite
            )
            primary_stdout = (
                attempt / commands[primary_result["command_index"]]["raw_stdout"]
            ).read_text(encoding="utf-8")
            negative_controls = run_negative_controls(
                primary_suite, primary_events,
                attempt / primary_result["event_log"], primary_stdout, attempt,
                vector_manifests[1],
            )
            if not all(item["passed"] for item in negative_controls):
                failure_reasons.append("one or more negative controls were not rejected")
        else:
            failure_reasons.append("not all simulations passed; negative controls skipped")

        readonly_after = verify_readonly_unchanged()
        summary["readonly_after"] = readonly_after
        if len(commands) != EXPECTED_COMMANDS:
            failure_reasons.append(
                f"command count {len(commands)} != {EXPECTED_COMMANDS}"
            )
        if not CASE_CHECK_COUNTS or not SUITE_LEVEL_CHECKS:
            failure_reasons.append("strict case/check-count constants are absent")
    except Exception as exc:
        failure_reasons.append(f"{type(exc).__name__}: {exc}")

    status = "PASS" if not failure_reasons else "FAIL"
    summary.update({
        "status": status,
        "failure_reasons": failure_reasons,
        "finished_utc": utc_now(),
        "source_binding": binding,
        "vectors": vector_manifests,
        "commands": commands,
        "suites": suite_results,
        "negative_controls": negative_controls,
        "expected_commands": EXPECTED_COMMANDS,
        "expected_simulations": EXPECTED_SIMULATIONS,
        "totals": {
            "cases": sum(len(suite.cases) for suite in SUITES),
            "records": sum(len(suite.records) for suite in SUITES),
            "commands": len(commands),
            "simulations": len(suite_results),
            "negative_controls": len(negative_controls),
        },
    })
    write_json_new(attempt / "summary.json", summary)
    summary_text = (
        f"RUN_STATUS {status}\n"
        f"ATTEMPT {attempt}\n"
        f"COMMANDS {len(commands)}\n"
        f"SIMULATIONS {len(suite_results)}\n"
        f"NEGATIVE_CONTROLS {sum(1 for item in negative_controls if item['passed'])}/{len(negative_controls)}\n"
        f"FAILURE_REASONS {len(failure_reasons)}\n"
        + "".join(f"FAIL {reason}\n" for reason in failure_reasons)
        + (
            f"RESULT thread={MAIN_THREAD} turn={MAIN_TURN} "
            f"operation={OPERATION_ID} source={SOURCE_COMMIT} "
            f"scope_sha256={EXPECTED_SCOPE_SHA} requirements_sha256="
            f"{EXPECTED_REQUIREMENTS_SHA} status={status}\n"
        )
    )
    write_new(attempt / "RUN_SUMMARY.txt", summary_text.encode("utf-8"))
    print(
        f"RESULT {status} cases={summary['totals']['cases']} "
        f"records={summary['totals']['records']} commands={len(commands)} "
        f"simulations={len(suite_results)} failures={len(failure_reasons)}"
    )
    for reason in failure_reasons:
        print(f"FAIL {reason}")
    print(f"SUMMARY {attempt / 'summary.json'}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
