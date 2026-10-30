"""Shared static contract for the NEW98 functional50 source-only builder.

This module has no side effects on import. It defines the exact selected
architecture, source roles, IP identities, pin map and BUILD_ID derivation.
It does not import project runtime, a vendor tool, a simulator or a service.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

TASK_ID = "DEEPEYE-IMPLEMENTATION-20261014"
TASK_VERSION = 1
WORK_ID = "B-DEEPEYE-FUNCTIONAL50-BUILDER-SOURCE-20261030-98"
MAIN_THREAD_ID = "01a18824-4172-74e2-a13f-f3e3d1e3ed99"
CONTRACT_ID = "DEEPEYE-HUMAN-LOCK-20261014"
CONTRACT_REVISION = 1
CONTRACT_PIN = "f5989cd5defce561f9ba98e6b18fc2682945f0a2"
REQUIREMENTS_SHA256 = "c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804"
FROZEN_DESIGN = "1011259415a0916054eb580687612580bc1e5f09"
REQUIREMENT_IDS = tuple(f"H{i:02d}" for i in range(1, 16))

PART = "xc7z020clg400-1"
BOARD_PART = "tul.com.tw:pynq-z2:part0:1.0"
VIVADO_VERSION = "2026.1"
PS7_VERSION = "5.5"
CLOCK_HZ = 50_000_000
CLOCK_PERIOD_NS = 20.0
BAUD = 1_000_000
TRACE_FIFO_BYTES = 4096
TRACE_SOURCE_KIND = 4
TRACE_MAGIC = 0x54353046
TRACE_LAYOUT = 1
G05_MAGIC = 0x47303550
G05_LAYOUT = 2

BD_NAME = "functional50_diag"
TOP_NAME = "functional50_diag_wrapper"
TOP_IMP = "functional50_diag_imp"
G05_INSTANCE = "g05_50_0"
TRACE_INSTANCE = "trace50_0"
G05_VLNV = "carlandfpga.local:diagnostic:deepeye_g05_axi_50:1.0"
TRACE_VLNV = "carlandfpga.local:diagnostic:deepeye_trace50_axi:1.0"
G05_CORE = "deepeye_g05_axi_50"
TRACE_CORE = "deepeye_trace50_axi"
G05_MODULE = "deepeye_g05_axi_50mhz_candidate"
TRACE_MODULE = "deepeye_trace50_axi94"
OLD_G05_VLNV = "carlandfpga.local:diagnostic:deepeye_g05_axi:1.0"

PINS = {
    "yaw_pwm_o": {"package_pin": "W14", "iostandard": "LVCMOS33", "bank": 34, "direction": "O", "g05_port": "g05_50_candidate_yaw_pwm_o"},
    "pitch_pwm_o": {"package_pin": "Y14", "iostandard": "LVCMOS33", "bank": 34, "direction": "O", "g05_port": "g05_50_candidate_pitch_pwm_o"},
    "speed_pwm_o": {"package_pin": "T11", "iostandard": "LVCMOS33", "bank": 34, "direction": "O", "g05_port": "g05_50_candidate_speed_pwm_o"},
    "yaw_capture_i": {"package_pin": "V16", "iostandard": "LVCMOS33", "bank": 34, "direction": "I", "g05_port": "g05_50_candidate_yaw_capture_i"},
    "pitch_capture_i": {"package_pin": "W16", "iostandard": "LVCMOS33", "bank": 34, "direction": "I", "g05_port": "g05_50_candidate_pitch_capture_i"},
    "speed_capture_i": {"package_pin": "V12", "iostandard": "LVCMOS33", "bank": 34, "direction": "I", "g05_port": "g05_50_candidate_speed_capture_i"},
}
CDC_PORTS = ("yaw_capture_i", "pitch_capture_i", "speed_capture_i")
CDC_STAGES = 3
CDC_PERIOD_NS = 20.0
CDC_MODE = "ACTUAL_NETLIST_THREE_FF_V1"


def expected_cdc_policy():
    return {"mode": CDC_MODE, "ports": list(CDC_PORTS), "stages": CDC_STAGES, "period_ns": CDC_PERIOD_NS}


def safe_cdc_name(name):
    return isinstance(name, str) and re.fullmatch(r"(?:[A-Za-z0-9_./-]|\[[0-9]+\])+", name) is not None

# Paths are relative to competition/deepeye.
SOURCE_ENTRIES = (
    {"role": "g05_axi", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_g05_axi_50mhz_candidate.sv", "bytes": 16077, "sha256": "99cdb09399466966458343351d0d941191f34cc9af6f9808c5fb3cc58086ea5a"},
    {"role": "g05_engine", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_g05_capture_engine_50mhz.sv", "bytes": 33796, "sha256": "fcdb04d1e307506328c205154730e1cf8c5bff2efe72727a46a2f3f4b856ed8a"},
    {"role": "g05_mapper", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_g05_command_map_50mhz.sv", "bytes": 2377, "sha256": "8df580388e85a59a43a0eaaae697534123a6e128fdb4675098e7173bda60a6a1"},
    {"role": "g05_profile_package", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_g05_profile_50mhz.sv", "bytes": 1794, "sha256": "8ec9bf0415e2ce5e87d2a793260bf635664f16584e2cb842df1fefba75e64307"},
    {"role": "g05_rom_header", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_g05_curvature_rom_50mhz.svh", "bytes": 1960, "sha256": "d462859e6893cd90fb33ad9ddd481aaa7ee46937ba3d197431f81b602357a83c"},
    {"role": "g05_pwm_capture", "path": "fpga/control3d/deepeye_pwm_coherent_capture.sv", "bytes": 17155, "sha256": "4baddfc31248c49000c00ac74bc2319cef6c9016c7df3f1822030c69cd82f456"},
    {"role": "trace_endpoint94", "path": "fpga/diagnostic/functional50_board94/deepeye_trace50_axi94.sv", "bytes": None, "sha256": None},
    {"role": "trace_fixture74", "path": "fpga/diagnostic/offboard_codec74/deepeye_SYNTHETIC_codec74_fixture.sv", "bytes": 12256, "sha256": "409ee484113fa4006eb27e12554a4db57708df5e7dadf269548f546d03931a6a"},
    {"role": "trace_capture", "path": "fpga/acquisition/deepeye_buffered_scan_capture.sv", "bytes": 3890, "sha256": "c8a540db8122b8f5520582a0f1fa9be0c43cb54a62f03c7c4edc893906f28411"},
    {"role": "trace_sample_capture", "path": "fpga/acquisition/deepeye_sample_scan_capture.sv", "bytes": 17174, "sha256": "fc8064a11ac40b6ee59418994825f0fc550ee867954bd1f1ccd2c9464e52028d"},
    {"role": "trace_raw_queue", "path": "fpga/acquisition/deepeye_raw_scan_queue.sv", "bytes": 6642, "sha256": "630e14803d82b3379517d91626de4ad7e7d3c509ad14363b3164031a5f633ee4"},
    {"role": "trace_lane", "path": "fpga/acquisition/deepeye_scan_lane_stream.sv", "bytes": 1720, "sha256": "b3c9d2024d9325191538cf08fec9a652ff8ff0ae316ec9af96078f85cf5be3cc"},
    {"role": "trace_block_uart", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_uart_50mhz_candidate.sv", "bytes": 11766, "sha256": "41ea63819c892ec67fe92d6e9338a771d5f93f60d0976e895f18bc97966283d2"},
    {"role": "trace_payload_adapter", "path": "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_trace_block_payload_1us_candidate.sv", "bytes": 10545, "sha256": "5ebe65dfe0844aab62365e8664507f153cb75ff47b3c8d4e10f45356e94147a8"},
    {"role": "trace_payload", "path": "fpga/codec/deepeye_trace_payload_candidate.sv", "bytes": 12241, "sha256": "fb64ace453c451838110c81bf6cb4a815a96fb2668e28a306ff699beca5acef6"},
    {"role": "trace_block_encoder", "path": "fpga/codec/deepeye_block_encoder.sv", "bytes": 21517, "sha256": "4cb79428ef89096742e293516c4696caf985048d8185f531fe92eaa485c8d532"},
    {"role": "trace_wire_serializer", "path": "fpga/transport/deepeye_wire_serializer.sv", "bytes": 9705, "sha256": "efc6082f6f5dff215b100f718b12d87d4c6467db7b968a24f846802dc6a19885"},
    {"role": "trace_crc16", "path": "fpga/transport/deepeye_crc16_byte.sv", "bytes": 1875, "sha256": "8594bad79593a5ff5a63761c3b4f5f83adc70ebcfdd5aec178de3aba1f313d6f"},
    {"role": "trace_uart_tx", "path": "fpga/transport/deepeye_uart_tx.sv", "bytes": 6811, "sha256": "5076286e4dd1598aeb2c78281bec83020c85d0711dcee9b985088ac707353c47"},
    {"role": "trace_uart_rx", "path": "fpga/transport/deepeye_uart_rx.sv", "bytes": 11182, "sha256": "935f5d02008535fd5da75b7dc80696d14b03bd54d85f8b52fbf12c1e0504f08f"},
)

TOOLING_ENTRIES = (
    {"role": "builder_tcl", "path": "fpga/diagnostic/functional50_build98/build_functional50.tcl"},
    {"role": "ports_xdc", "path": "fpga/diagnostic/functional50_build98/functional50_ports.xdc"},
    {"role": "cdc_tcl", "path": "fpga/diagnostic/functional50_build98/functional50_cdc.tcl"},
    {"role": "builder_py", "path": "tools/diagnostic/functional50_build98/build_functional50.py"},
    {"role": "contract_py", "path": "tools/diagnostic/functional50_build98/functional50_contract.py"},
    {"role": "closure_verifier", "path": "tools/diagnostic/functional50_build98/verify_functional50_closure.py"},
    {"role": "hwh_verifier", "path": "tools/diagnostic/functional50_build98/verify_functional50_hwh.py"},
)

EXCLUDED_SOURCES = (
    "fpga/diagnostic/g05_capture/additive50_source_candidate/rtl/deepeye_integration_50mhz_candidate.sv",
    "fpga/diagnostic/offboard_aggregate77/deepeye_aggregate12_candidate.sv",
    "fpga/diagnostic/offboard_aggregate77/deepeye_aggregate_uart_candidate.sv",
    "fpga/diagnostic/offboard_control75/tb_offboard_control75.sv",
    "fpga/diagnostic/g05_capture/build/build_g05.tcl",
    "fpga/diagnostic/g05_capture/build/g05_ports.xdc",
    "fpga/diagnostic/g05_capture/build/g05_cdc.tcl",
    "tools/diagnostic/g05_capture/build/build_g05.py",
    "tools/diagnostic/g05_capture/build/hwh_guard.py",
    "tools/diagnostic/g05_capture/build/owned_process.py",
    "tools/diagnostic/g05_capture/collector/pins.py",
)

BUILD_ID_RULE = "first 128 bits (32 lowercase hex characters) of SHA256 over canonical_closure_payload, which excludes build_id/build_id_full_sha256 and the closure file's own hash; full 256-bit digest retained separately"
SNAPSHOT_SCHEMA = "FUNCTIONAL50_BUILD_CLOSURE_V1"
A_SELECTION_OPERATION_ID = "A-GEN4-B50-ONEBUILD-RELEASE-20261031-26"


def require(test, message):
    if not test:
        raise ValueError(message)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def file_record(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return {"path": str(p), "bytes": len(data), "sha256": sha256_bytes(data)}


def canonical_json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json_exclusive(path, value):
    p = Path(path)
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def parse_iso_utc(value):
    require(isinstance(value, str) and value.endswith("Z"), "UTC timestamp ending in Z required")
    parsed = dt.datetime.fromisoformat(value[:-1] + "+00:00")
    require(parsed.tzinfo is not None, "timezone-aware UTC timestamp required")
    return parsed


def source_by_role():
    return {entry["role"]: entry for entry in SOURCE_ENTRIES}


def source_by_path():
    return {entry["path"]: entry for entry in SOURCE_ENTRIES}


def tooling_by_path():
    return {entry["path"]: entry for entry in TOOLING_ENTRIES}


def verify_contract_document(document):
    require(document.get("contract_id") == CONTRACT_ID, "contract identity")
    require(document.get("revision") == CONTRACT_REVISION, "contract revision")
    requirements = document.get("requirements")
    require(isinstance(requirements, list) and len(requirements) == 15, "exactly H01-H15 required")
    require([item.get("id") for item in requirements] == list(REQUIREMENT_IDS), "exact ordered H01-H15 ids")
    digest = sha256_bytes(canonical_json_bytes(requirements))
    require(digest == REQUIREMENTS_SHA256, "canonical H01-H15 requirements hash mismatch")
    require(document.get("requirements_sha256") == REQUIREMENTS_SHA256, "declared requirements hash mismatch")
    return digest


def expected_architecture():
    return {
        "part": PART,
        "board_part": BOARD_PART,
        "vivado_version": VIVADO_VERSION,
        "ps7_version": PS7_VERSION,
        "clock": {"fclk0_hz": CLOCK_HZ, "period_ns": CLOCK_PERIOD_NS, "fclk1_3_disabled": True, "source": "PS7 FCLK0 direct", "pl_clock": False},
        "reset": {"source": "PS7 FCLK_RESET0_N", "proc_sys_reset_version": "5.0", "polarity": "ACTIVE_LOW", "dcm_locked": 1, "ext_reset_high": "inherited_do_not_write"},
        "axi": {"master": "GP0", "interconnect": "xilinx.com:ip:axi_interconnect:2.1", "num_si": 1, "num_mi": 2, "protocol": "AXI4LITE", "data_width": 32, "addr_width": 12,
                "windows": [{"instance": G05_INSTANCE, "range": 4096}, {"instance": TRACE_INSTANCE, "range": 4096}],
                "address_assignment": "Vivado auto; discover exactly two 4KiB HWH windows; no guessed bases"},
        "g05": {"magic": "0x47303550", "layout": 2, "pins": 6, "profile": "unchanged50 AXI/engine/mapper/profile/ROM", "old_100mhz_builders_preserved": True},
        "trace": {"magic": "0x54353046", "layout": 1, "source_kind": TRACE_SOURCE_KIND, "clock_hz": CLOCK_HZ, "baud": BAUD, "fifo_bytes": TRACE_FIFO_BYTES,
                  "external_uart": False, "encoder": "one existing 74 encoder", "build_id_parameter": "BUILD_ID[127:0]"},
        "constraints": {"xdc": "six old pin locations, LVCMOS33 bank34, no UART", "cdc": "20ns exact three-stage external capture; only external->first D false path"},
        "board": {"preset": "TUL PYNQ-Z2 A.0", "ddr": "literal72 checked before/after validate; no hand-modified fallback"},
    }


def expected_ips():
    return [
        {"instance": G05_INSTANCE, "vlnv": G05_VLNV, "core": G05_CORE, "module": G05_MODULE, "range": 4096, "clock_hz": CLOCK_HZ, "reset": "ACTIVE_LOW"},
        {"instance": TRACE_INSTANCE, "vlnv": TRACE_VLNV, "core": TRACE_CORE, "module": TRACE_MODULE, "range": 4096, "clock_hz": CLOCK_HZ, "reset": "ACTIVE_LOW", "parameter": "BUILD_ID[127:0]"},
    ]


def validate_architecture(closure):
    require(closure.get("architecture") == expected_architecture(), "selected architecture differs from the main-selected functional50 contract")
    require(closure.get("ips") == expected_ips(), "exact two private IP identities required")
    require(closure.get("pins") == PINS, "exact six old G05 pin allocations required")


def source_entries_from_closure(closure):
    entries = closure.get("sources")
    require(isinstance(entries, list), "sources list required")
    require(len(entries) == len(SOURCE_ENTRIES), "exact source entry count required")
    by_path = {}
    by_role = {}
    for entry in entries:
        require(isinstance(entry, dict), "source entry object required")
        path = entry.get("path")
        role = entry.get("role")
        require(path in source_by_path(), "unexpected source path: " + str(path))
        require(path not in by_path, "duplicate source path: " + str(path))
        require(role == source_by_path()[path]["role"], "source role mismatch: " + str(path))
        by_path[path] = entry
        by_role[role] = entry
    require(set(by_path) == set(source_by_path()), "missing source path")
    require(set(by_role) == set(source_by_role()), "missing source role")
    return by_path, by_role


def tooling_entries_from_closure(closure):
    entries = closure.get("tooling")
    require(isinstance(entries, list), "tooling list required")
    require(len(entries) == len(TOOLING_ENTRIES), "exact tooling entry count required")
    by_path = {}
    for entry in entries:
        require(isinstance(entry, dict), "tooling entry object required")
        path = entry.get("path")
        require(path in tooling_by_path(), "unexpected tooling path: " + str(path))
        require(path not in by_path, "duplicate tooling path: " + str(path))
        require(entry.get("role") == tooling_by_path()[path]["role"], "tooling role mismatch: " + str(path))
        by_path[path] = entry
    require(set(by_path) == set(tooling_by_path()), "missing tooling path")
    return by_path


def validate_source_bytes(closure, product_root, require_resolved):
    by_path, by_role = source_entries_from_closure(closure)
    root = Path(product_root).resolve()
    for path, expected in source_by_path().items():
        entry = by_path[path]
        if expected["sha256"] is None:
            require(expected["role"] == "trace_endpoint94", "only the selected 94 role may have a deferred source pin")
            if not require_resolved:
                require(entry.get("bytes") is None and entry.get("sha256") is None,
                        "template 94 entry must remain unresolved until the main freezes review95")
                continue
            require(type(entry.get("bytes")) is int and entry["bytes"] > 0,
                    "frozen 94 source requires positive exact byte count")
            require(isinstance(entry.get("sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]),
                    "frozen 94 source requires exact lowercase SHA256")
            actual_path = root / path
            require(actual_path.is_file(), "selected 94 source missing")
            data = actual_path.read_bytes()
            require(len(data) == entry["bytes"] and sha256_bytes(data) == entry["sha256"],
                    "frozen 94 source differs from actual selected source bytes")
            review = closure.get("review_95")
            require(isinstance(review, dict) and review.get("completed") is True, "completed review95 required to resolve 94")
            for key in ("main_review_sha256", "actual_95_result_sha256"):
                require(re.fullmatch(r"[0-9a-f]{64}", str(review.get(key) or "")), "review95 proof required: " + key)
            require(review.get("source94") == {"path": path, "bytes": entry["bytes"], "sha256": entry["sha256"]},
                    "review95/main receipt must bind the exact resolved 94 source")
            continue
        require(entry.get("bytes") == expected["bytes"], "declared source bytes mismatch: " + path)
        require(entry.get("sha256") == expected["sha256"], "declared source hash mismatch: " + path)
        actual_path = root / path
        require(actual_path.is_file(), "source file missing: " + path)
        data = actual_path.read_bytes()
        require(len(data) == expected["bytes"], "actual source bytes mismatch: " + path)
        require(sha256_bytes(data) == expected["sha256"], "actual source hash mismatch: " + path)
    return by_path


def validate_tooling_bytes(closure, product_root, require_resolved):
    by_path = tooling_entries_from_closure(closure)
    root = Path(product_root).resolve()
    for path, entry in by_path.items():
        actual_path = root / path
        require(actual_path.is_file(), "tooling file missing: " + path)
        data = actual_path.read_bytes()
        if entry.get("sha256") is None:
            require(not require_resolved, "unresolved tooling hash blocks frozen closure: " + path)
            require(entry.get("bytes") is None, "unresolved tooling bytes must stay null: " + path)
        else:
            require(re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]), "tooling SHA256 format: " + path)
            require(type(entry.get("bytes")) is int and entry["bytes"] > 0 and entry["bytes"] == len(data), "declared tooling bytes mismatch: " + path)
            require(entry["sha256"] == sha256_bytes(data), "actual tooling hash mismatch: " + path)
    return by_path


def validate_closure(closure, product_root, require_frozen):
    require(closure.get("schema") == SNAPSHOT_SCHEMA, "closure schema")
    require(closure.get("task_id") == TASK_ID and closure.get("task_version") == TASK_VERSION, "closure task identity")
    require(closure.get("work_id") == WORK_ID, "closure work identity")
    require(closure.get("main_thread_id") == MAIN_THREAD_ID, "main identity")
    require(closure.get("contract_id") == CONTRACT_ID and closure.get("contract_revision") == CONTRACT_REVISION, "contract identity")
    require(closure.get("contract_pin") == CONTRACT_PIN, "contract pin")
    require(closure.get("requirements_ids") == list(REQUIREMENT_IDS), "H01-H15 ids")
    require(closure.get("requirements_sha256") == REQUIREMENTS_SHA256, "requirements hash")
    require(closure.get("frozen_design") == FROZEN_DESIGN, "frozen design")
    require(closure.get("build_id_rule") == BUILD_ID_RULE, "BUILD_ID rule")
    validate_architecture(closure)
    require(closure.get("cdc_policy") == expected_cdc_policy(), "exact actual-netlist CDC discovery policy required")
    require(closure.get("cdc_bindings") is None, "prelaunch closure must not invent synthesized CDC names")
    require(set(closure.get("excluded_sources", [])) == set(EXCLUDED_SOURCES), "exact excluded source set")
    source_paths, source_roles = source_entries_from_closure(closure)
    tooling_entries_from_closure(closure)
    validate_source_bytes(closure, product_root, require_frozen)
    validate_tooling_bytes(closure, product_root, require_frozen)
    if require_frozen:
        require(closure.get("status") == "FROZEN_MAIN_REVIEWED" and closure.get("frozen") is True, "frozen main-reviewed closure required")
        require(re.fullmatch(r"[0-9a-f]{40}", str(closure.get("source_commit") or "")), "exact 40-hex source commit required")
        review = closure.get("review_95")
        require(isinstance(review, dict) and review.get("completed") is True, "review95 completion required")
        require(re.fullmatch(r"[0-9a-f]{64}", str(review.get("test_plan_sha256") or "")), "review95 test plan hash")
        require(re.fullmatch(r"[0-9a-f]{64}", str(review.get("main_review_sha256") or "")), "review95 main review hash")
        review_cdc = closure.get("cdc_source_review")
        require(isinstance(review_cdc, dict) and review_cdc.get("reviewed_by") == "main", "main CDC review required")
        require(re.fullmatch(r"[0-9a-f]{64}", str(review_cdc.get("sha256") or "")), "CDC review hash")
        unresolved = [entry for entry in closure["sources"] if entry.get("sha256") is None]
        require(not unresolved, "94 source must be resolved in frozen closure")
        computed = compute_build_id(closure)
        require(closure.get("build_id") == computed["build_id"], "declared BUILD_ID does not match canonical closure")
        require(closure.get("build_id_full_sha256") == computed["full_sha256"], "declared full closure digest mismatch")
    else:
        require(closure.get("frozen") is False, "template must not be frozen")
        require(str(closure.get("status", "")).startswith("UNFROZEN_TEMPLATE"), "template status")
        require(closure.get("source_commit") is None, "template source commit must be null")
        require(closure.get("build_id") is None and closure.get("build_id_full_sha256") is None, "template BUILD_ID must be null")
        unresolved = [entry for entry in closure["sources"] if entry.get("sha256") is None]
        require(len(unresolved) == 1 and unresolved[0]["path"] == source_by_role()["trace_endpoint94"]["path"], "only the selected 94 source may be unresolved")
        require(closure.get("review_95", {}).get("completed") is False, "template review95 must be false")
    return {"sources": source_paths, "tooling": tooling_entries_from_closure(closure)}


def canonical_closure_payload(closure):
    source_paths, _ = source_entries_from_closure(closure)
    tooling = tooling_entries_from_closure(closure)
    sources = {path: source_paths[path]["sha256"] for path in sorted(source_paths)}
    tools = {path: tooling[path]["sha256"] for path in sorted(tooling)}
    require(all(value for value in sources.values()), "all sources must be resolved before BUILD_ID")
    require(all(value for value in tools.values()), "all tooling must be resolved before BUILD_ID")
    architecture = closure["architecture"]
    return {
        "schema": "FUNCTIONAL50_BUILD_CLOSURE_CANONICAL_V1",
        "task_id": TASK_ID,
        "task_version": TASK_VERSION,
        "requirements_sha256": REQUIREMENTS_SHA256,
        "frozen_design": FROZEN_DESIGN,
        "part": architecture["part"],
        "board_part": architecture["board_part"],
        "vivado_version": architecture["vivado_version"],
        "clock": architecture["clock"],
        "reset": architecture["reset"],
        "axi": architecture["axi"],
        "g05": architecture["g05"],
        "trace": architecture["trace"],
        "pins": closure["pins"],
        "cdc": closure["cdc_policy"],
        "ips": closure["ips"],
        "sources": sources,
        "tooling": tools,
    }


def compute_build_id(closure):
    payload = canonical_closure_payload(closure)
    digest = sha256_bytes(canonical_json_bytes(payload))
    return {"build_id": digest[:32], "full_sha256": digest, "canonical_payload": payload}


def tcl_literal(value):
    text = str(value).replace("\\", "/")
    require(not any(ch in text for ch in "{}\n\r\x00"), "unsafe Tcl literal")
    return "{" + text + "}"
