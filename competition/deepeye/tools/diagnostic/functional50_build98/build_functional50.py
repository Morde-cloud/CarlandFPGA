"""NEW98 gated builder for the selected functional50 diagnostic.

Default modes `inspect` and `prepare` never call a vendor tool, simulator,
board, service or network. `build` is disabled unless an exact frozen closure
and a main-verified actual A selection record are supplied. No old 100 MHz
builder, R20/R21 image or collector pin map is sourced or mutated.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

# Source-only builder: default modes do not call a vendor tool.
#
# Source-only boundaries:
# - inspect and prepare do not launch Vivado or a simulator
# - build requires a frozen closure and a main-verified A selection
# - unresolved 94 source is never guessed or hash-frozen
# - old 100 MHz builders, R20/R21 images and collector pins stay untouched
# - no board, network, service, credential, SQL or queue operation is implied
# - observed 94 structure is reported, not silently repaired
# - all unexecuted checks remain visibly unexecuted
# - parent retains review, acceptance and Git authority

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import functional50_contract as c

BOARD_HASHES = {
    "board.xml": "a565dcb39737d551cbbbb73c0053b973c40bb3dce2274943370d3032c0fea9ae",
    "preset.xml": "18528f84aea4da503cdb3104f7706fabfb3b6ad09b78b25199cc316afa4c8cfe",
    "part0_pins.xml": "3c809473938e135a925b563b5371c8687ee05c4089376e7318c0c56524cc8a0f",
    "pynq_z2.jpg": "54b4bb2da4a38a647d3df030ec13fe63e427235980ce9ae1ca44ce9a91af4546",
}
TOOL_HASHES = {
    "bin/vivado.bat": "a5f91ee867cea61be4355caf9f7a784c6c34351c5c1d1618562ddda299e38a8b",
    "bin/unwrapped/win64.o/vivado.exe": "3a4e9e3f03d20cd1994dc2eff44566af7a10eaaae04429e9d460bffe3b0e86e4",
}
WINDOWS_JOB_SHA = "3c36fe7209e5cca5b9c354a54d089e838b32a4a566551b65957507a4710295e3"
OWNED_PROCESS_SHA = "1b8d34ce5758ec4bc0fbfd3518a27567e991039e52533c3a62652c5c9db10692"
DDR_VENDOR_REL = "data/PS/7series/data/zynqconfig/ddr/ddr_preset.xml"
DDR_VENDOR_SHA = "73566a941b442804a9c6b0eb42385b6c1cb82f12e354c138f8868005b91c52ed"
DDR_SELECTOR = {"param": "pcw_uiparam_ddr_partno", "name": "MT41J256M16 RE-125", "strength": "8"}
DDR_PREFIX = "CONFIG.PCW_UIPARAM_DDR_"
DDR_MODEL_KEYS = frozenset("DRAM_WIDTH DEVICE_CAPACITY SPEED_BIN BANK_ADDR_COUNT ROW_ADDR_COUNT COL_ADDR_COUNT CL CWL T_RCD T_RP T_RC T_RAS_MIN T_FAW".split())
DDR_OVERRIDES = {"T_RC": ("50.625", "48.91"), "T_RCD": ("13.125", "7"), "T_RP": ("13.125", "7")}
G05_ORDER = ("g05_profile_package", "g05_rom_header", "g05_mapper", "g05_pwm_capture", "g05_engine", "g05_axi")
TRACE_ORDER = ("trace_block_encoder", "trace_payload", "trace_wire_serializer", "trace_crc16", "trace_uart_tx", "trace_uart_rx",
               "trace_payload_adapter", "trace_block_uart", "trace_sample_capture", "trace_raw_queue", "trace_capture", "trace_lane",
               "trace_fixture74", "trace_endpoint94")


def require(test, message):
    if not test:
        raise ValueError(message)


def utc():
    import datetime as dt
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return sha256_bytes(Path(path).read_bytes())


def record(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return {"path": str(p), "bytes": len(data), "sha256": sha256_bytes(data)}


def verilog_structure(path):
    """Read-only structural observation; not a compile, review95 result or freeze."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = [re.sub(r"//.*$", "", line) for line in text.splitlines()]
    modules = [(index + 1, line.strip()) for index, line in enumerate(lines)
               if re.match(r"^\s*module\s+", line)]
    ends = [index + 1 for index, line in enumerate(lines) if re.match(r"^\s*endmodule\s*$", line)]
    top = any(re.match(r"^\s*module\s+deepeye_trace50_axi94\b", line) for _, line in modules)
    trailing = []
    for index in range(ends[-1] if ends else 0, len(lines)):
        value = lines[index].strip()
        if value and not value.startswith(("`default_nettype", "`timescale", "`celldefine", "`endcelldefine")):
            trailing.append({"line": index + 1, "text": value[:160]})
    header = "\n".join(lines[:min(len(lines), 100)])
    required = ("s_axi_aclk", "s_axi_aresetn", "s_axi_awaddr", "s_axi_wdata", "s_axi_araddr",
                "s_axi_rdata", "s_axi_bresp", "s_axi_rresp")
    missing = [name for name in required if name not in header]
    balanced = len(modules) == len(ends) and len(modules) >= 1
    valid = bool(balanced and top and not trailing and not missing)
    return {"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": digest(p),
            "module_count": len(modules), "endmodule_count": len(ends), "top_module_present": top,
            "balanced": balanced, "trailing_code_lines": trailing, "required_ports_missing": missing,
            "status": "STRUCTURE_OK" if valid else "STRUCTURE_INCOMPLETE_OR_MALFORMED",
            "authority": "read-only observation; not a compile, review95 result or hash freeze"}


class _Noop:
    def __init__(self):
        self.calls = []


def _resolve_ddr_tables(board_raw, vendor_raw, *, test_fixture):
    parsed_inputs = []
    vendor_declaration = b'<!DOCTYPE presets PUBLIC "presets" "presets.dtd" >'
    for index, raw in enumerate((board_raw, vendor_raw)):
        require(type(raw) is bytes and 0 < len(raw) <= 1048576, "bounded DDR XML bytes required")
        parsed = raw.replace(vendor_declaration, b"", 1) if index == 1 else raw
        require(b"<!DOCTYPE" not in parsed.upper() and b"<!ENTITY" not in parsed.upper(), "DDR XML unexpected DTD/entity forbidden")
        parsed_inputs.append(parsed)
    board = ET.fromstring(parsed_inputs[0])
    require(board.tag == "ip_presets", "board preset root")
    presets = board.findall("./ip_preset[@preset_proc_name='ps7_preset']")
    require(len(presets) == 1, "unique PS7 board preset required")
    ips = presets[0].findall("./ip[@name='processing_system7']")
    require(len(ips) == 1, "unique board PS7 IP required")
    params = {}
    for p in ips[0].findall("./user_parameters/user_parameter"):
        require(set(p.attrib) == {"name", "value"} and p.get("name") not in params, "duplicate/malformed board parameter")
        params[p.attrib["name"]] = p.attrib["value"]
    require(len(params) == 771, "exact771 raw board parameters required")
    raw_ddr = {k: v for k, v in params.items() if k.startswith(DDR_PREFIX)}
    require(len(raw_ddr) == 72, "exact72 literal board DDR parameters required")
    require(raw_ddr.get(DDR_PREFIX + "PARTNO") == DDR_SELECTOR["name"], "board named model mismatch")
    vendor = ET.fromstring(parsed_inputs[1])
    require(vendor.tag == "presets", "vendor DDR preset root")
    matches = [p for p in vendor.findall("./preset") if p.get("name") == DDR_SELECTOR["name"]]
    require(len(matches) == 1 and matches[0].attrib == DDR_SELECTOR, "unique exact named DDR selector/strength required")
    selected = matches[0]
    sets, disabled = {}, []
    for entry in selected:
        require(entry.tag in ("set", "disable"), "unexpected named-model entry")
        expected = {"param", "value"} if entry.tag == "set" else {"param"}
        require(set(entry.attrib) == expected and len(entry) == 0, "malformed named-model entry")
        name = entry.attrib["param"]
        require(name.startswith("pcw_uiparam_ddr_") and name == name.lower(), "model parameter naming")
        key = "CONFIG." + name.upper()
        if entry.tag == "set":
            require(key not in sets, "duplicate model set entry")
            sets[key] = entry.attrib["value"]
        else:
            require(key not in disabled, "duplicate model disable entry")
            disabled.append(key)
    expected_keys = {DDR_PREFIX + k for k in DDR_MODEL_KEYS}
    require(len(sets) == 13 and set(sets) == expected_keys, "exact13 named-model set keys required")
    require(len(disabled) == 13 and set(disabled) == set(sets), "same13 unique set/disable entries required")
    require(set(sets) <= set(raw_ddr), "named model must be board DDR key subset")
    differences = {k: {"board_literal": raw_ddr[k], "named_model": v} for k, v in sets.items() if raw_ddr[k] != v}
    expected_diff = {DDR_PREFIX + k: {"board_literal": old, "named_model": new} for k, (old, new) in DDR_OVERRIDES.items()}
    require(differences == expected_diff, "exact three main-decided DDR differences required; no additional change")
    require(sum(raw_ddr[k] == v for k, v in sets.items()) == 10, "ten unchanged model values required")
    resolved = {**raw_ddr, **sets}
    require(len(resolved) == 72 and all(resolved[k] == raw_ddr[k] for k in raw_ddr if k not in expected_diff), "nonoverride DDR changed")
    return {"schema": 1, "scope": "synthetic_parser_fixture_not_build_authority" if test_fixture else "pinned_named_model_resolution_not_physical_proof",
            "board_sha256": sha256_bytes(board_raw), "vendor_ddr_sha256": sha256_bytes(vendor_raw),
            "selector": dict(DDR_SELECTOR), "selected_entry_xml": ET.tostring(selected, encoding="unicode"),
            "raw_board_parameters": params, "literal_ddr": raw_ddr, "model_set": sets, "model_disable": sorted(disabled),
            "resolved_ddr": resolved, "differences": differences,
            "counts": {"raw_board": 771, "literal_ddr": 72, "resolved_ddr": 72, "model_set": 13, "model_disable": 13, "model_unchanged": 10, "overrides": 3},
            "units": {"T_RC": "ns explicitly named in installed parameter metadata", "T_RP": "clock cycles explicitly described",
                       "T_RCD": "unit unproven; installed node does not explicitly name a unit", "T_RAS_MIN": "metadata name says ns but description also says cycles"},
            "conversion": "none; retain exact raw string values",
            "xml_parse_policy": "remove only exact pinned vendor PUBLIC declaration from parser copy; never load DTD; raw snapshot unchanged",
            "requirements_sha256": c.REQUIREMENTS_SHA256, "frozen_design": c.FROZEN_DESIGN}



def resolve_ddr(board_raw, vendor_raw):
    require(sha256_bytes(board_raw) == BOARD_HASHES["preset.xml"], "TUL board preset hash mismatch")
    require(sha256_bytes(vendor_raw) == DDR_VENDOR_SHA, "installed vendor DDR preset hash mismatch")
    return _resolve_ddr_tables(board_raw, vendor_raw, test_fixture=False)


def ddr_expected_text(resolution):
    return "".join("set " + var + " [dict create " + " ".join(literal(k) + " " + literal(v) for k, v in sorted(resolution[key].items())) + "]\n"
                   for var, key in (("literal_ddr", "literal_ddr"), ("expected_ddr", "resolved_ddr")))


def literal(value):
    text = str(value).replace("\\", "/")
    require(not any(ch in text for ch in "{}\n\r\x00"), "unsafe Tcl literal")
    return "{" + text + "}"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value, *, exclusive=True):
    p = Path(path)
    mode = "x" if exclusive else "w"
    with p.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")


def copy_verified(source, target, expected_sha=None):
    data = Path(source).read_bytes()
    if expected_sha is not None:
        require(sha256_bytes(data) == expected_sha, "input hash mismatch: " + str(source))
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as stream:
        stream.write(data)
    return record(target)


def git(args, cwd, timeout=60):
    process = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=timeout, shell=False)
    require(process.returncode == 0, "git command failed: " + " ".join(args) + " :: " + process.stderr.strip())
    return process.stdout.strip()


def selected_paths(closure):
    return [entry["path"] for entry in closure["sources"]] + [entry["path"] for entry in closure["tooling"]]


def git_state(product_root, closure):
    head = git(["rev-parse", "HEAD"], product_root)
    require(head == closure["source_commit"], "worktree HEAD does not equal the approved source commit")
    paths = selected_paths(closure)
    tracked = git(["ls-files", "--error-unmatch", "--", *paths], product_root)
    require(len(tracked.splitlines()) == len(paths), "every selected source/tooling path must be tracked")
    status = git(["status", "--porcelain=v1", "--untracked-files=all", "--", *paths], product_root)
    require(status == "", "selected source/tooling tree is dirty or untracked")
    return {"head": head, "tracked_files": len(paths), "dirty_selected_paths": 0}


def verify_board_and_tools(args):
    board_dir = Path(args.board_dir).resolve()
    tool_root = Path(args.tool_root).resolve()
    board_records = {}
    for name, expected in BOARD_HASHES.items():
        path = board_dir / name
        require(path.is_file(), "board file missing: " + name)
        require(digest(path) == expected, "board file hash changed: " + name)
        board_records[name] = record(path)
    tool_records = {}
    for name, expected in TOOL_HASHES.items():
        path = tool_root / name
        require(path.is_file(), "installed tool file missing: " + name)
        require(digest(path) == expected, "installed tool hash changed: " + name)
        tool_records[name] = record(path)
    vendor = tool_root / DDR_VENDOR_REL
    require(vendor.is_file(), "installed vendor DDR preset missing")
    require(digest(vendor) == DDR_VENDOR_SHA, "installed vendor DDR preset hash changed")
    owned = Path(args.owned_process).resolve()
    windows = Path(args.windows_job).resolve()
    require(owned.is_file() and digest(owned) == OWNED_PROCESS_SHA, "pinned owned_process.py missing/changed")
    require(windows.is_file() and digest(windows) == WINDOWS_JOB_SHA, "pinned windows_job.py missing/changed")
    identities = {}
    for directory, name, version in (("processing_system7_v5_5", "processing_system7", "5.5"),
                                     ("axi_interconnect_v2_1", "axi_interconnect", "2.1"),
                                     ("proc_sys_reset_v5_0", "proc_sys_reset", "5.0"),
                                     ("xlconstant_v1_1", "xlconstant", "1.1")):
        path = tool_root / "data/ip/xilinx" / directory / "component.xml"
        require(path.is_file(), "installed IP component missing: " + name)
        xml = ET.parse(path).getroot()
        ns = {"s": "http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009"}
        identity = ":".join(xml.findtext("s:" + key, namespaces=ns) or "" for key in ("vendor", "library", "name", "version"))
        require(identity == f"xilinx.com:ip:{name}:{version}", "installed component identity changed: " + name)
        identities[identity] = record(path)
    board = ET.parse(board_dir / "board.xml").getroot()
    require(board.get("vendor") == "tul.com.tw" and board.find("./components/component[@name='part0']").get("part_name") == c.PART, "TUL board identity")
    return {"board": board_records, "tools": tool_records, "vendor_ddr": record(vendor), "owned_process": record(owned),
            "windows_job": record(windows), "ip_components": identities}


def verify_approval(path, closure_path, closure, out, run_id, operation_id, work_id, timeout, drain, terminate):
    approval = load_json(path)
    require(approval.get("schema") == "FUNCTIONAL50_A_SELECTION_V1", "A selection schema required")
    require(approval.get("task_id") == c.TASK_ID and type(approval.get("task_version")) is int and approval["task_version"] == c.TASK_VERSION, "approval task identity")
    for name, value in (("run_id", run_id), ("operation_id", operation_id), ("work_id", work_id)):
        require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,96}", value), "bounded launch identifier required: " + name)
        require(approval.get(name) == value, "approval differs from explicitly selected launch " + name)
    require(work_id != c.WORK_ID, "new build work must differ from source98")
    require(approval.get("selected_by") == "A" and approval.get("board_operator") == "A", "A selection required")
    require(approval.get("b_board_access") is False, "B must not accept board access")
    require(approval.get("source_commit") == closure.get("source_commit"), "approval source commit mismatch")
    require(approval.get("source_closure_sha256") == digest(closure_path), "approval must bind the exact frozen closure bytes")
    computed = c.compute_build_id(closure)
    require(approval.get("build_id") == computed["build_id"], "approval BUILD_ID mismatch")
    require(approval.get("requirements_sha256") == c.REQUIREMENTS_SHA256 and approval.get("frozen_design") == c.FROZEN_DESIGN, "contract/design mismatch")
    require(approval.get("part") == c.PART and approval.get("board_part") == c.BOARD_PART and approval.get("vivado_version") == c.VIVADO_VERSION, "part/board/tool mismatch")
    plan = approval.get("clock_plan")
    require(isinstance(plan, dict), "clock plan required")
    require(plan.get("fclk0_hz") == c.CLOCK_HZ and plan.get("period_ns") == c.CLOCK_PERIOD_NS, "exact 50MHz/20ns clock plan required")
    require(plan.get("fclk1_3_disabled") is True and plan.get("no_pl_clock") is True, "FCLK1-3/no-PL-clock plan required")
    require(plan.get("cdc_rule") == "exact external-to-first-D only; stages 2/3 and internal TX-RX timed", "exact CDC rule required")
    require(type(approval.get("max_threads")) is int and approval["max_threads"] == 2, "exactly two Vivado threads/jobs required")
    require(type(approval.get("timeout_seconds")) is int and approval["timeout_seconds"] == timeout, "approval timeout must bind this run")
    require(approval.get("job_drain_seconds") == drain and approval.get("job_terminate_seconds") == terminate, "approval job bounds must bind this run")
    require(isinstance(approval.get("output_directory"), str) and approval["output_directory"] and
            Path(approval["output_directory"]).resolve() == out.resolve(), "approval must bind one new output directory")
    selection = approval.get("a_selection")
    require(isinstance(selection, dict) and selection.get("selected") is True, "explicit A selection object required")
    received = closure.get("a_selection")
    require(isinstance(received, dict) and received.get("provided") is True and received.get("selected_by") == "A", "frozen closure must retain the received A scope")
    require(selection.get("operation_id") == received.get("operation_id") == c.A_SELECTION_OPERATION_ID,
            "A conditional scope identity differs from received A26 (B launch operation is separate)")
    require(bool(selection.get("a_message_id")), "actual A message id required")
    require(re.fullmatch(r"[0-9a-f]{64}", str(selection.get("a_message_sha256") or "")) is not None, "A message SHA256 required")
    for key in ("a_message_id", "a_message_sha256"):
        require(selection.get(key) == received.get(key), "A message binding differs from frozen closure: " + key)
    attestation = approval.get("main_attestation")
    require(isinstance(attestation, dict), "main attestation required")
    require(attestation.get("main_thread_id") == c.MAIN_THREAD_ID, "quality main identity mismatch")
    require(attestation.get("verified_actual_a_message") is True, "main must verify the actual A message; JSON matching alone is not authorization")
    for key, selection_key in (("a_operation_id", "operation_id"), ("a_message_id", "a_message_id"), ("a_message_sha256", "a_message_sha256")):
        require(attestation.get(key) == selection.get(selection_key), "main attestation must bind received A scope: " + key)
    require(re.fullmatch(r"[0-9a-f]{64}", str(attestation.get("main_review_sha256") or "")) is not None, "main review SHA256 required")
    c.parse_iso_utc(attestation.get("verified_at_utc"))
    c.parse_iso_utc(approval.get("approved_at_utc"))
    require("TEST_FIXTURE" not in approval and approval.get("synthetic") is not True, "synthetic approval forbidden")
    return approval


def ordered_paths(closure, roles):
    by_role = {entry["role"]: entry for entry in closure["sources"]}
    require(set(by_role) == {entry["role"] for entry in c.SOURCE_ENTRIES}, "source role set mismatch")
    return [by_role[role]["path"] for role in roles]


def prepare_inputs(out, closure, args, state):
    product_root = Path(args.product_root).resolve()
    inputs = out / "inputs"
    source_root = inputs / "readonly_sources"
    tooling_root = inputs / "tooling"
    for directory in (inputs, source_root, tooling_root, inputs / "board_repo" / "pynq-z2" / "A.0", inputs / "vendor", out / "reports", out / "artifacts", out / "constraints"):
        directory.mkdir(parents=True, exist_ok=True)
    source_copies = {}
    for entry in closure["sources"]:
        source = product_root / entry["path"]
        target = source_root / entry["path"]
        source_copies[entry["path"]] = copy_verified(source, target, entry["sha256"])
    tooling_copies = {}
    for entry in closure["tooling"]:
        source = product_root / entry["path"]
        target = tooling_root / Path(entry["path"]).name
        tooling_copies[entry["path"]] = copy_verified(source, target, entry["sha256"])
        if Path(entry["path"]).suffix.lower() in {".tcl", ".xdc"}:
            copy_verified(source, inputs / Path(entry["path"]).name, entry["sha256"])
    for name, expected in BOARD_HASHES.items():
        copy_verified(Path(args.board_dir) / name, inputs / "board_repo" / "pynq-z2" / "A.0" / name, expected)
    vendor_source = Path(args.tool_root) / DDR_VENDOR_REL
    copy_verified(vendor_source, inputs / "vendor_ddr_preset.xml", DDR_VENDOR_SHA)
    copy_verified(Path(args.owned_process).resolve(), tooling_root / "owned_process.py", OWNED_PROCESS_SHA)
    copy_verified(Path(args.windows_job).resolve(), tooling_root / "windows_job.py", WINDOWS_JOB_SHA)
    resolution = resolve_ddr((inputs / "board_repo" / "pynq-z2" / "A.0" / "preset.xml").read_bytes(),
                             (inputs / "vendor_ddr_preset.xml").read_bytes())
    write_json(inputs / "ps7_preset_parameters.json", resolution["raw_board_parameters"])
    write_json(inputs / "ddr_literal.json", resolution["literal_ddr"])
    write_json(inputs / "ddr_resolved.json", resolution["resolved_ddr"])
    write_json(inputs / "ddr_resolution.json", resolution)
    (inputs / "ddr_expected.tcl").write_text(ddr_expected_text(resolution), encoding="utf-8", newline="\n")
    g05_paths = [str(source_root / path) for path in ordered_paths(closure, G05_ORDER)]
    trace_paths = [str(source_root / path) for path in ordered_paths(closure, TRACE_ORDER)]
    (inputs / "g05_sources.txt").write_text("\n".join(g05_paths) + "\n", encoding="utf-8", newline="\n")
    (inputs / "trace_sources.txt").write_text("\n".join(trace_paths) + "\n", encoding="utf-8", newline="\n")
    (inputs / "all_sources.txt").write_text("\n".join(g05_paths + trace_paths) + "\n", encoding="utf-8", newline="\n")
    config = [
        "set run_id " + literal(state["run_id"]),
        "set run_root " + literal(str(out)),
        "set build_authorized_for_run " + literal(state["run_id"]),
        "set max_threads 2",
        "set clock_period_ns 20.0",
        "set build_id " + literal(state["build_id"]),
        "set g05_source_list " + literal(str(inputs / "g05_sources.txt")),
        "set trace_source_list " + literal(str(inputs / "trace_sources.txt")),
        "set board_repo " + literal(str(Path(args.board_dir).resolve())),
    ]
    require(closure["cdc_policy"] == c.expected_cdc_policy() and closure["cdc_bindings"] is None,
            "prelaunch CDC must be the fixed discovery policy, never fabricated names")
    config.append("set cdc_policy " + literal(c.CDC_MODE))
    (inputs / "build_config.tcl").write_text("\n".join(config) + "\n", encoding="utf-8", newline="\n")
    launch = {"task_id": c.TASK_ID, "task_version": c.TASK_VERSION, "work_id": state["work_id"], "operation_id": state["operation_id"],
              "run_id": state["run_id"], "at_utc": utc(), "source_commit": state["source_commit"], "build_id": state["build_id"],
              "source_closure_sha256": state["source_closure_sha256"], "requirements_sha256": c.REQUIREMENTS_SHA256,
              "frozen_design": c.FROZEN_DESIGN, "g05_sources": g05_paths, "trace_sources": trace_paths,
              "source_copies": source_copies, "tooling_copies": tooling_copies,
              "board_files": {name: record(inputs / "board_repo" / "pynq-z2" / "A.0" / name) for name in BOARD_HASHES},
              "vendor_ddr": record(inputs / "vendor_ddr_preset.xml"),
              "owned_process": record(tooling_root / "owned_process.py"), "windows_job": record(tooling_root / "windows_job.py"),
              "ddr_resolution_sha256": digest(inputs / "ddr_resolution.json"), "timeout_seconds": state["timeout"],
              "job_drain_seconds": state["drain"], "job_terminate_seconds": state["terminate"],
              "no_network": True, "no_board_access_by_b": True, "board_operator": "A"}
    write_json(inputs / "LAUNCH_INPUTS.json", launch)
    write_json(out / "SOURCE_SNAPSHOT_BEFORE.json", {"files": {entry["path"]: record(source_root / entry["path"]) for entry in closure["sources"]},
                                                    "tooling": {entry["path"]: record(tooling_root / Path(entry["path"]).name) for entry in closure["tooling"]}})
    return {"inputs": inputs, "source_root": source_root, "tooling_root": tooling_root, "launch": launch}


def load_module(path, name):
    p = Path(path).resolve()
    require(p.is_file(), "module file missing: " + str(p))
    spec = importlib.util.spec_from_file_location(name, p)
    require(spec is not None and spec.loader is not None, "module loader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_vivado(out, inputs, args, state):
    owned = load_module(inputs / "tooling" / "owned_process.py", "functional50_owned_process")
    require(digest(inputs / "tooling" / "owned_process.py") == OWNED_PROCESS_SHA, "owned process copy changed")
    (out / "vivado").mkdir()
    vivado = Path(args.tool_root) / "bin" / "vivado.bat"
    require(vivado.is_file(), "installed vivado.bat missing")
    command = [str(vivado), "-mode", "batch", "-notrace", "-source", str(inputs / "build_functional50.tcl"),
               "-tclargs", str(inputs / "build_config.tcl")]
    result = owned.run_owned(command, out / "vivado", state["timeout"], inputs / "tooling" / "windows_job.py",
                             job_drain_seconds=state["drain"], job_terminate_seconds=state["terminate"])
    write_json(out / "VIVADO_PROCESS.json", result)
    require(result.get("exit_code") == 0, "Vivado launcher nonzero exit; preserve all failure evidence")
    require(result.get("termination_confirmed") is True, "owned Job termination not confirmed")
    require(result.get("job_closed") is True, "owned Job not closed after terminal observation")
    require(result.get("timed_out") is False, "Vivado timeout; no automatic replay")
    require(result.get("job_query_failed") is not True, "owned Job accounting failure")
    stdout = (out / "vivado" / "process.stdout.bin").read_bytes().decode("utf-8", "replace")
    marker = "FUNCTIONAL50_COMPLETE|" + state["run_id"] + "|" + state["build_id"]
    require(marker in stdout, "Vivado completion marker missing")
    return result


def verify_unconstrained(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    counts = re.findall(r"^\s*[0-9]+\.\s+checking unconstrained_internal_endpoints\s+\(([0-9]+)\)\s*$", text, re.M)
    require(len(counts) == 2 and counts[0] == counts[1] and int(counts[0]) == 0,
            "missing/ambiguous/nonzero verbose unconstrained endpoint inventory")
    return {"report": record(path), "unconstrained_internal_endpoints": 0}


def verify_actual_cdc(path, state, stage):
    data = load_json(path)
    require(isinstance(data, dict) and set(data) == {"schema", "mode", "run_id", "build_id", "stage", "bindings"}, "exact actual CDC record fields")
    require(data["schema"] == "FUNCTIONAL50_CDC_BINDINGS_V1" and data["mode"] == c.CDC_MODE, "actual CDC schema/policy")
    require(data["run_id"] == state["run_id"] and data["build_id"] == state["build_id"] and data["stage"] == stage,
            "actual CDC evidence belongs to a different run/build/stage")
    bindings = data["bindings"]
    require(isinstance(bindings, dict) and set(bindings) == set(c.CDC_PORTS), "actual CDC exact three-port set")
    all_names = []
    for port in c.CDC_PORTS:
        names = bindings[port]
        require(isinstance(names, list) and len(names) == c.CDC_STAGES and
                all(c.safe_cdc_name(name) and name.endswith("/D") for name in names), "three exact safe FF D pin names required")
        all_names.extend(names)
    require(len(set(all_names)) == 9 and len({name[:-2] for name in all_names}) == 9, "nine distinct actual CDC FF D pins/cells required")
    return data


def verify_false_paths(xdc_path, bindings):
    lines = []
    text = Path(xdc_path).read_text(encoding="utf-8", errors="strict")
    for raw in re.sub(r"\\\r?\n", " ", text).splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if re.search(r"\b(?:set_clock_groups|set_max_delay|set_min_delay|set_multicycle_path|set_disable_timing|reset_path)\b", line):
            raise ValueError("unselected timing exception forbidden: " + line)
        if "set_false_path" in line:
            lines.append(line)
    require(len(lines) == 3, "exactly three false paths required in implemented.xdc")
    literal = r"(\{[^{}\r\n]+\}|[^\s\[\]{};$\"\\]+)"
    pattern = r"^set_false_path\s+-from\s+\[get_ports\s+" + literal + r"\]\s+-to\s+\[get_pins\s+" + literal + r"\]\s*$"
    observed = []
    for line in lines:
        match = re.fullmatch(pattern, line)
        require(match is not None, "only one simple exact -from get_ports literal -to get_pins literal exception allowed")
        names = [name[1:-1] if name.startswith("{") else name for name in match.groups()]
        require(names[0] in c.CDC_PORTS and c.safe_cdc_name(names[1]), "unsafe/wildcard/unselected XDC endpoint")
        observed.append(tuple(names))
    expected = {(port, bindings[port][0]) for port in c.CDC_PORTS}
    require(len(set(observed)) == 3 and set(observed) == expected, "implemented exceptions differ from the actual same-run first D pins")
    return lines


def verify_mapping(mapping, expected_build_id=None):
    require(mapping.get("bd") == c.BD_NAME and mapping.get("top") == c.TOP_NAME, "BD/top mapping identity")
    require(mapping.get("master") == "ps7_0/Data", "PS GP0 master")
    build_id = mapping.get("build_id")
    require(isinstance(build_id, str) and re.fullmatch(r"[0-9a-f]{32}", build_id) is not None,
            "mapping BUILD_ID must be 32 lowercase hex characters")
    require(build_id != "0" * 32, "mapping BUILD_ID must be nonzero")
    if expected_build_id is not None:
        require(build_id == expected_build_id, "mapping BUILD_ID differs from the frozen closure")
    windows = mapping.get("windows")
    require(isinstance(windows, list) and len(windows) == 2, "exactly two windows required")
    require([w.get("instance") for w in windows] == [c.G05_INSTANCE, c.TRACE_INSTANCE], "window instance order/names")
    require([w.get("vlnv") for w in windows] == [c.G05_VLNV, c.TRACE_VLNV], "window VLNV mismatch")
    spans = []
    for window in windows:
        base = int(str(window.get("base")), 0)
        span = int(str(window.get("range")), 0)
        require(span == 4096 and base % 4096 == 0, "exact aligned 4KiB window required")
        require(0 <= base <= base + span - 1 <= 0xffffffff, "uint32 mapped address range required")
        spans.append((base, base + span - 1))
    spans.sort()
    require(spans[0][1] < spans[1][0], "the two windows overlap")
    return {**mapping, "spans": spans}


def verify_outputs(out, closure, state):
    complete = load_json(out / "VIVADO_COMPLETE.json")
    require(complete.get("run_id") == state["run_id"] and complete.get("build_id") == state["build_id"],
            "same-run completion/build identity mismatch")
    require(complete.get("top") == c.TOP_NAME and complete.get("bd") == c.BD_NAME and
            complete.get("part") == c.PART and complete.get("board_part") == c.BOARD_PART and
            complete.get("version") == c.VIVADO_VERSION and complete.get("status") == "bitstream_complete_pending_hwh_timing_review",
            "same-run completion source/top/tool identity mismatch")
    gate = load_json(out / "reports" / "timing_gate.json")
    required = ("wns_ns", "whs_ns", "tns_ns", "ths_ns", "setup_failing_endpoints", "hold_failing_endpoints", "drc_errors", "lutlp1", "has_20ns_clock", "has_10ns_clock")
    for key in required:
        require(key in gate, "timing gate key missing: " + key)
    require(float(gate["wns_ns"]) >= 0.0, "setup WNS negative")
    require(float(gate["whs_ns"]) >= 0.0, "hold WHS negative")
    require(float(gate["tns_ns"]) >= 0.0, "setup TNS negative")
    require(float(gate["ths_ns"]) >= 0.0, "hold THS negative")
    require(int(gate["setup_failing_endpoints"]) == 0, "setup-failing endpoints remain")
    require(int(gate["hold_failing_endpoints"]) == 0, "hold-failing endpoints remain")
    require(int(gate["drc_errors"]) == 0, "DRC errors remain")
    require(int(gate["lutlp1"]) == 0, "LUTLP-1 combinational loop remains")
    require(int(gate["has_20ns_clock"]) == 1, "20ns/50MHz clock missing")
    require(int(gate["has_10ns_clock"]) == 0, "10ns/100MHz clock present in the new BD")
    unconstrained = verify_unconstrained(out / "reports" / "route_check_timing.txt")
    cdc_synth = verify_actual_cdc(out / "CDC_BINDINGS_ACTUAL.json", state, "synth")
    cdc_route = verify_actual_cdc(out / "CDC_BINDINGS_ROUTED.json", state, "routed")
    require(cdc_synth["bindings"] == cdc_route["bindings"], "actual CDC graph names changed after route")
    false_paths = verify_false_paths(out / "constraints" / "implemented.xdc", cdc_synth["bindings"])
    mapping = verify_mapping(load_json(out / "BD_MAPPING.json"), state["build_id"])
    hwh = load_module(out / "inputs" / "tooling" / "verify_functional50_hwh.py", "functional50_hwh_verifier")
    identity = hwh.verify_hwh(out / "artifacts" / "functional50_diag.hwh", mapping, expected_build_id=state["build_id"])
    timing = hwh.verify_timing_gate(out / "reports" / "timing_gate.json", out / "reports" / "route_check_timing.txt")
    for name in ("functional50_diag.bit", "functional50_diag.hwh", "functional50_diag_routed.dcp", "functional50_diag_synth.dcp"):
        artifact = out / "artifacts" / name
        require(artifact.is_file() and artifact.stat().st_size > 0, "empty/missing paired artifact: " + name)
    inventory = (out / "SYNTHESIS_RUNS.tsv").read_text(encoding="utf-8").splitlines()
    require(inventory, "synthesis run inventory empty")
    for line in inventory:
        name, directory, status = line.split("\t")
        require(status == "synth_design Complete!", "incomplete synthesis run: " + name)
        directory = Path(directory).resolve()
        require(directory.is_relative_to(out), "synthesis run escaped current output")
        for filename in ("vivado.jou", "runme.log"):
            require((directory / filename).is_file(), "missing raw child log/journal: " + name + "/" + filename)
    before = load_json(out / "SOURCE_SNAPSHOT_BEFORE.json")
    after = {"files": {entry["path"]: record(out / "inputs" / "readonly_sources" / entry["path"]) for entry in closure["sources"]},
             "tooling": {entry["path"]: record(out / "inputs" / "tooling" / Path(entry["path"]).name) for entry in closure["tooling"]}}
    require(after == before, "source/tooling snapshot changed during the run")
    manifest = {"schema": "FUNCTIONAL50_ARTIFACT_MANIFEST_V1", "status": "completed_build_pending_hwh_timing_main_review",
                "run_id": state["run_id"], "work_id": state["work_id"], "operation_id": state["operation_id"],
                "source_commit": state["source_commit"], "build_id": state["build_id"],
                "source_closure_sha256": state["source_closure_sha256"], "requirements_sha256": c.REQUIREMENTS_SHA256,
                "hwh_identity": identity, "mapping": mapping, "timing_gate": timing, "false_paths": false_paths,
                "actual_cdc_synth": cdc_synth, "actual_cdc_routed": cdc_route,
                "unconstrained": unconstrained, "raw_synthesis_runs": inventory,
                "board": "not_run; A-only", "physical_validation": "not_claimed",
                "source_snapshot_before": before, "source_snapshot_after": after,
                "files": {p.relative_to(out).as_posix(): record(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "ARTIFACT_MANIFEST.json"}}
    write_json(out / "ARTIFACT_MANIFEST.json", manifest)
    return manifest


def path_tracking(product_root, paths):
    tracked = {}
    dirty = {}
    for path in paths:
        process = subprocess.run(["git", "-C", str(product_root), "ls-files", "--error-unmatch", "--", path],
                                 capture_output=True, text=True, timeout=30, shell=False)
        tracked[path] = process.returncode == 0
    status = subprocess.run(["git", "-C", str(product_root), "status", "--porcelain=v1", "--untracked-files=all", "--", *paths],
                            capture_output=True, text=True, timeout=60, shell=False)
    status_lines = [line for line in status.stdout.splitlines() if line.strip()]
    for path in paths:
        dirty[path] = any(line.endswith(path) or path in line for line in status_lines)
    return {"tracked": tracked, "dirty": dirty, "status_lines": status_lines}


def inspect_status(args, product_root, template_path):
    result = {"schema": "FUNCTIONAL50_INSPECT_V1", "status": "inspect_only_no_build", "at_utc": utc(),
              "task_id": c.TASK_ID, "task_version": c.TASK_VERSION, "work_id": c.WORK_ID,
              "requirements_sha256": c.REQUIREMENTS_SHA256, "contract_pin": c.CONTRACT_PIN,
              "frozen_design": c.FROZEN_DESIGN, "no_runtime": True, "build_ready": False,
              "build_ready_reason": "inspect is read-only; a build additionally requires a frozen main-reviewed closure and a main-verified A selection/approval",
              "blockers": []}
    closure = None
    try:
        closure = load_json(template_path)
        frozen = isinstance(closure, dict) and closure.get("frozen") is True
        c.validate_closure(closure, product_root, frozen)
        result["closure_valid"] = True
        result["closure_frozen"] = frozen
        result["closure_mode"] = "FROZEN_MAIN_REVIEWED" if frozen else "UNFROZEN_TEMPLATE"
    except Exception as error:
        result["closure_valid"] = False
        result["closure_frozen"] = None
        result["closure_error"] = f"{type(error).__name__}: {error}"
        result["blockers"].append("closure invalid: " + result["closure_error"])
        closure = None
    if args.contract_json:
        try:
            c.verify_contract_document(load_json(args.contract_json))
            result["contract_hash_verified"] = True
        except Exception as error:
            result["contract_hash_verified"] = False
            result["contract_error"] = f"{type(error).__name__}: {error}"
    else:
        result["contract_hash_verified"] = None
    if result["contract_hash_verified"] is not True:
        result["blockers"].append("contract H01-H15 hash not verified")
    try:
        result["head"] = git(["rev-parse", "HEAD"], product_root)
    except Exception as error:
        result["head_error"] = f"{type(error).__name__}: {error}"
    source94 = product_root / c.source_by_role()["trace_endpoint94"]["path"]
    result["source94_present"] = source94.is_file()
    if source94.is_file():
        result["source94_observed"] = record(source94)
        structure = verilog_structure(source94)
        result["source94_structure"] = structure
        if structure["status"] != "STRUCTURE_OK":
            result["blockers"].append("94 source structural observation is not clean: " + structure["status"])
        if not result.get("closure_frozen"):
            result["blockers"].append("template does not freeze the observed 94 bytes; actual95/main review still required")
    else:
        result["source94_structure"] = None
        result["blockers"].append("94 source absent/unfrozen; review95 and freeze absent")
    if closure is not None:
        tracking = path_tracking(product_root, selected_paths(closure))
        result["tracked_all"] = all(tracking["tracked"].values())
        result["dirty_selected"] = [path for path, value in tracking["dirty"].items() if value]
        result["untracked_selected"] = [path for path, value in tracking["tracked"].items() if not value]
        if result["dirty_selected"] or result["untracked_selected"]:
            result["blockers"].append("selected source/tooling is dirty or untracked")
        if not result.get("closure_frozen"):
            result["blockers"].append("closure is an unfrozen template")
    result["blockers"].append("A selection/approval not inspected by this read-only command")
    result["build_ready"] = False
    return result


def prepare(args, product_root, template_path, out):
    require(not out.exists(), "existing attempt cannot be reused")
    require(args.contract_json is not None, "fixed contract JSON required")
    c.verify_contract_document(load_json(args.contract_json))
    template = load_json(template_path)
    c.validate_closure(template, product_root, False)
    board_tools = verify_board_and_tools(args)
    head = git(["rev-parse", "HEAD"], product_root)
    tracking = path_tracking(product_root, selected_paths(template))
    out.mkdir(parents=True, exist_ok=False)
    args._invocation_created_output = True
    args._invocation_output_directory = out
    write_json(out / "INTENT.json", {"schema": "FUNCTIONAL50_INTENT_V1", "task_id": c.TASK_ID, "task_version": c.TASK_VERSION,
                                     "work_id": c.WORK_ID, "mode": "prepare", "at_utc": utc(), "argv": sys.argv,
                                     "python": sys.executable, "requirements_sha256": c.REQUIREMENTS_SHA256,
                                     "contract_pin": c.CONTRACT_PIN, "no_runtime": True, "no_vendor_call": True})
    candidate = copy.deepcopy(template)
    for tool in candidate["tooling"]:
        rec = record(product_root / tool["path"])
        tool["bytes"] = rec["bytes"]
        tool["sha256"] = rec["sha256"]
        tool["status"] = "OBSERVED_NOT_FROZEN"
    candidate["observed_at_utc"] = utc()
    candidate["observed_source_commit"] = head
    candidate["observed_tracking"] = tracking
    candidate["build_ready"] = False
    candidate["blockers"] = ["94 source not frozen in held template", "review95/final main review not recorded in template",
                             "actual-netlist CDC policy selected; graph discovery/validation NOT_RUN",
                             "A26 scope received by main; one-use B launch approval not supplied", "closure not frozen", "selected files not committed cleanly"]
    write_json(out / "SOURCE_CLOSURE_CANDIDATE.json", candidate)
    source94 = product_root / c.source_by_role()["trace_endpoint94"]["path"]
    readiness = {"schema": "FUNCTIONAL50_BUILD_READINESS_V1", "build_ready": False, "runtime_executed": False,
                 "vivado_launched": False, "at_utc": utc(), "head": head, "source94_present": source94.is_file(),
                 "source94_structure": verilog_structure(source94) if source94.is_file() else None,
                 "review95_completed": False, "cdc_policy": template["cdc_policy"], "cdc_actual_graph": "NOT_RUN", "a_selection_present": False,
                 "dirty_selected": [path for path, value in tracking["dirty"].items() if value],
                 "untracked_selected": [path for path, value in tracking["tracked"].items() if not value],
                 "blockers": candidate["blockers"]}
    write_json(out / "BUILD_READINESS.json", readiness)
    result = {"schema": "FUNCTIONAL50_PREPARE_RESULT_V1", "status": "prepared_only_no_build", "at_utc": utc(),
              "task_id": c.TASK_ID, "task_version": c.TASK_VERSION, "work_id": c.WORK_ID,
              "requirements_sha256": c.REQUIREMENTS_SHA256, "build_ready": False,
              "vendor_tool_launched": False, "board_touched": False, "network_used": False,
              "candidate_closure": "SOURCE_CLOSURE_CANDIDATE.json", "readiness": "BUILD_READINESS.json"}
    write_json(out / "RESULT.json", result)
    print(json.dumps({"status": result["status"], "out": str(out), "build_ready": False}, sort_keys=True))
    return 0


def build_run(args, product_root, closure_path, out):
    require(not out.exists(), "existing attempt cannot be reused; no overwrite/retry/resume")
    require(args.run_id and re.fullmatch(r"[A-Za-z0-9._-]{1,96}", args.run_id), "simple unique run_id required")
    closure = load_json(closure_path)
    c.validate_closure(closure, product_root, True)
    computed = c.compute_build_id(closure)
    require(closure.get("build_id") == computed["build_id"], "frozen closure BUILD_ID mismatch")
    source94 = product_root / c.source_by_role()["trace_endpoint94"]["path"]
    structure94 = verilog_structure(source94)
    require(structure94["status"] == "STRUCTURE_OK", "94 source structural observation blocks build: " + structure94["status"])
    require(out.is_relative_to((product_root / "evidence" / "diagnostic" / "functional50").resolve()),
            "authorized build output must be a new functional50 evidence directory")
    state = {"run_id": args.run_id, "build_id": computed["build_id"], "source_commit": closure["source_commit"],
             "source_closure_sha256": digest(closure_path), "timeout": args.timeout_seconds,
             "drain": args.job_drain_seconds, "terminate": args.job_terminate_seconds}
    approval = verify_approval(args.approval, closure_path, closure, out, args.run_id, args.operation_id, args.work_id,
                               args.timeout_seconds, args.job_drain_seconds, args.job_terminate_seconds)
    state.update({"work_id": approval["work_id"], "operation_id": approval["operation_id"]})
    board_tools = verify_board_and_tools(args)
    git_info = git_state(product_root, closure)
    out.mkdir(parents=True, exist_ok=False)
    args._invocation_created_output = True
    args._invocation_output_directory = out
    write_json(out / "INTENT.json", {"schema": "FUNCTIONAL50_INTENT_V1", "task_id": c.TASK_ID, "task_version": c.TASK_VERSION,
                                     "work_id": state["work_id"], "operation_id": state["operation_id"], "mode": "build",
                                     "run_id": state["run_id"], "at_utc": utc(), "argv": sys.argv, "python": sys.executable,
                                     "requirements_sha256": c.REQUIREMENTS_SHA256, "build_id": state["build_id"],
                                     "source_commit": state["source_commit"], "source_closure_sha256": state["source_closure_sha256"],
                                     "source94_structure": structure94, "git": git_info, "board_tools": board_tools, "single_build": True,
                                     "no_parallel_second_build": True, "no_network": True, "board_operator": "A"})
    inputs = prepare_inputs(out, closure, args, state)
    process = run_vivado(out, inputs["inputs"], args, state)
    manifest = verify_outputs(out, closure, state)
    result = {"schema": "FUNCTIONAL50_BUILD_RESULT_V1", "status": "completed_build_pending_main_review",
              "at_utc": utc(), "task_id": c.TASK_ID, "task_version": c.TASK_VERSION, "work_id": state["work_id"],
              "operation_id": state["operation_id"], "run_id": state["run_id"], "build_id": state["build_id"],
              "source_commit": state["source_commit"], "source_closure_sha256": state["source_closure_sha256"],
              "requirements_sha256": c.REQUIREMENTS_SHA256, "vivado_version": c.VIVADO_VERSION,
              "pair": {"bit": "artifacts/functional50_diag.bit", "hwh": "artifacts/functional50_diag.hwh"},
              "timing_gate": manifest["timing_gate"], "hwh_identity": manifest["hwh_identity"],
              "process_exit": process.get("exit_code"), "job_closed": process.get("job_closed"),
              "board": "not_run; A-only", "physical_validation": "not_claimed", "main_review_required": True}
    write_json(out / "RESULT.json", result)
    print(json.dumps({"status": result["status"], "out": str(out), "build_id": state["build_id"]}, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("inspect", "prepare", "build"), default="inspect")
    parser.add_argument("--product-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--closure-template", type=Path)
    parser.add_argument("--closure", type=Path)
    parser.add_argument("--approval", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--operation-id", help="exact main-selected B launch operation; distinct from A26 scope")
    parser.add_argument("--work-id", help="exact new main-selected B build work")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--contract-json", type=Path)
    parser.add_argument("--board-dir", type=Path, default=Path("D:/pynq/AMD2026/2026.1/Vivado/data/boards/board_files/pynq-z2/A.0"))
    parser.add_argument("--tool-root", type=Path, default=Path("D:/pynq/AMD2026/2026.1/Vivado"))
    parser.add_argument("--owned-process", type=Path)
    parser.add_argument("--windows-job", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--job-drain-seconds", type=float, default=5.0)
    parser.add_argument("--job-terminate-seconds", type=float, default=5.0)
    args = parser.parse_args(argv)
    args._invocation_created_output = False
    args._invocation_output_directory = None
    product_root = args.product_root.resolve()
    if args.closure_template is None:
        args.closure_template = product_root / "fpga" / "diagnostic" / "functional50_build98" / "closure_template.json"
    if args.owned_process is None:
        args.owned_process = product_root / "tools" / "diagnostic" / "g05_capture" / "build" / "owned_process.py"
    if args.windows_job is None:
        args.windows_job = product_root.parents[1] / "fpga_mesh" / "windows_job.py"
    try:
        require(60 <= args.timeout_seconds <= 14400, "finite build timeout 60..14400 seconds")
        require(0 < args.job_drain_seconds <= 30 and 0 < args.job_terminate_seconds <= 30, "finite Job drain/terminate bounds")
        if args.mode == "inspect":
            result = inspect_status(args, product_root, args.closure_template.resolve())
            print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
            return 0
        require(args.out is not None, "--out new directory required")
        require(args.contract_json is not None, "--contract-json fixed H01-H15 document required")
        out = args.out.resolve()
        if args.mode == "prepare":
            return prepare(args, product_root, args.closure_template.resolve(), out)
        require(args.closure is not None and args.approval is not None and args.run_id and args.operation_id and args.work_id,
                "build requires closure, approval, run_id, operation_id and work_id")
        require(args.closure.resolve().is_file() and args.approval.resolve().is_file(), "closure/approval files missing")
        return build_run(args, product_root, args.closure.resolve(), out)
    except BaseException as error:
        out = args.out.resolve() if args.out is not None else None
        if (args._invocation_created_output and out is not None and
                args._invocation_output_directory == out and out.is_dir()):
            try:
                write_json(out / "FAILURE.json", {"at_utc": utc(), "error": f"{type(error).__name__}: {error}",
                                                   "artifacts_accepted": False, "automatic_retry": False})
                write_json(out / "FAILURE_FILE_MANIFEST.json", {"files": {p.relative_to(out).as_posix(): record(p)
                                                                           for p in sorted(out.rglob("*")) if p.is_file()},
                                                                 "accepted": False})
            except Exception:
                pass
        print("FUNCTIONAL50_FAILED: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
