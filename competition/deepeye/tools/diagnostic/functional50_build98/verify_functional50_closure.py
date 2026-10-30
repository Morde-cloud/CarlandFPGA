"""Static NEW98 functional50 closure verifier.

This module performs read-only filesystem and JSON checks. It never imports
project runtime, invokes Vivado or a simulator, runs Tcl, touches a board or
network service, mutates Git, or creates a build output directory. It is not a
compiler, place-and-route run, HWH verifier or physical test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import functional50_contract as c


def require(test, message):
    if not test:
        raise ValueError(message)


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def record(path):
    p = Path(path).resolve()
    data = p.read_bytes()
    return {"path": str(p), "bytes": len(data), "sha256": sha256_bytes(data)}


def observe_verilog_structure(path):
    """Read-only structural observation; not a compile or review95 result."""
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    lines = [re.sub(r"//.*$", "", line) for line in text.splitlines()]
    modules = [index + 1 for index, line in enumerate(lines) if re.match(r"^\s*module\s+", line)]
    ends = [index + 1 for index, line in enumerate(lines) if re.match(r"^\s*endmodule\s*$", line)]
    top = any(re.match(r"^\s*module\s+deepeye_trace50_axi94", line) for line in lines)
    trailing = []
    for index in range(ends[-1] if ends else 0, len(lines)):
        value = lines[index].strip()
        if value and not value.startswith(("`default_nettype", "`timescale", "`celldefine", "`endcelldefine")):
            trailing.append({"line": index + 1, "text": value[:160]})
    header = chr(10).join(lines[: min(len(lines), 100)])
    required = ("s_axi_aclk", "s_axi_aresetn", "s_axi_awaddr", "s_axi_wdata", "s_axi_araddr",
                "s_axi_rdata", "s_axi_bresp", "s_axi_rresp")
    missing = [name for name in required if name not in header]
    balanced = len(modules) == len(ends) and len(modules) >= 1
    valid = bool(balanced and top and not trailing and not missing)
    return {"path": str(p.resolve()), "bytes": p.stat().st_size, "sha256": sha256_bytes(p.read_bytes()),
            "module_lines": modules, "endmodule_lines": ends, "top_module_present": top,
            "balanced": balanced, "trailing_code_lines": trailing, "required_ports_missing": missing,
            "status": "STRUCTURE_OK" if valid else "STRUCTURE_INCOMPLETE_OR_MALFORMED",
            "authority": "read-only observation; not a compile, lint, review95 result or hash freeze"}


def verify_contract(path):
    document = load_json(path)
    digest = c.verify_contract_document(document)
    require(digest == c.REQUIREMENTS_SHA256, "contract canonical hash mismatch")
    return {"path": str(Path(path).resolve()), "bytes": Path(path).stat().st_size,
            "sha256": record(path)["sha256"], "requirements_sha256": digest,
            "requirements_ids": [item.get("id") for item in document["requirements"]],
            "contract_id": document.get("contract_id"), "revision": document.get("revision")}


def verify(closure_path, product_root, contract_path, mode):
    product_root = Path(product_root).resolve()
    closure_path = Path(closure_path).resolve()
    closure = load_json(closure_path)
    require(isinstance(closure, dict), "closure must be a JSON object")
    frozen = closure.get("frozen") is True
    require(mode in {"auto", "template", "frozen"}, "mode must be auto/template/frozen")
    if mode == "template":
        require(frozen is False, "template mode requires frozen=false")
    if mode == "frozen":
        require(frozen is True, "frozen mode requires frozen=true")
    effective = "frozen" if frozen else "template"
    c.validate_closure(closure, product_root, frozen)
    contract = verify_contract(contract_path)

    sources, _ = c.source_entries_from_closure(closure)
    source_records = {}
    for path, entry in sorted(sources.items()):
        actual = record(product_root / path)
        if entry.get("sha256") is None:
            require(entry.get("bytes") is None, "unresolved source bytes must remain null: " + path)
            status = "UNRESOLVED_NOT_FROZEN"
        else:
            require(entry.get("bytes") == actual["bytes"], "declared source bytes mismatch: " + path)
            require(entry.get("sha256") == actual["sha256"], "actual source hash mismatch: " + path)
            status = "EXACT_RESOLVED"
        source_records[path] = {"declared": {"bytes": entry.get("bytes"), "sha256": entry.get("sha256")},
                                "actual": actual, "status": status}

    tooling = c.tooling_entries_from_closure(closure)
    tooling_records = {}
    for path, entry in sorted(tooling.items()):
        actual = record(product_root / path)
        if entry.get("sha256") is None:
            require(not frozen, "unresolved tooling hash blocks frozen closure: " + path)
            require(entry.get("bytes") is None, "unresolved tooling bytes must remain null: " + path)
            status = "UNRESOLVED_TEMPLATE_ALLOWED"
        else:
            require(entry.get("bytes") == actual["bytes"], "declared tooling bytes mismatch: " + path)
            require(entry.get("sha256") == actual["sha256"], "actual tooling hash mismatch: " + path)
            status = "EXACT_RESOLVED"
        tooling_records[path] = {"declared": {"bytes": entry.get("bytes"), "sha256": entry.get("sha256")},
                                 "actual": actual, "status": status}

    source94_path = product_root / c.source_by_role()["trace_endpoint94"]["path"]
    source94 = observe_verilog_structure(source94_path)
    source94_key = c.source_by_role()["trace_endpoint94"]["path"]
    require(source94["bytes"] == source_records[source94_key]["actual"]["bytes"],
            "94 source changed during observation")

    if frozen:
        computed = c.compute_build_id(closure)
        require(closure.get("build_id") == computed["build_id"], "declared BUILD_ID mismatch")
        require(closure.get("build_id_full_sha256") == computed["full_sha256"],
                "declared full closure digest mismatch")
        build = {"status": "BUILD_ID_DERIVED_AND_MATCHED", "build_id": computed["build_id"],
                 "full_sha256": computed["full_sha256"], "canonical_payload": computed["canonical_payload"]}
    else:
        require(closure.get("build_id") is None and closure.get("build_id_full_sha256") is None,
                "template BUILD_ID must be null")
        build = {"status": "NOT_COMPUTED_UNFROZEN_TEMPLATE", "build_id": None, "full_sha256": None}

    review = closure.get("review_95") or {}
    cdc = closure.get("cdc_policy")
    a_selection = closure.get("a_selection") or {}
    gaps = []
    if not frozen:
        gaps.append("closure is an unfrozen template; build remains disabled")
    if source94["status"] != "STRUCTURE_OK":
        gaps.append("94 source structural observation is not clean: " + source94["status"])
    if source_records[source94_key]["status"] != "EXACT_RESOLVED":
        gaps.append("94 source hash is not accepted/frozen; observation is not review95")
    if review.get("completed") is not True:
        gaps.append("review95 is not complete")
    if cdc != c.expected_cdc_policy():
        gaps.append("main-selected actual-netlist CDC policy is absent or differs")
    gaps.append("actual synthesized/routed CDC graph discovery and validation NOT_RUN by this static verifier")
    if a_selection.get("provided") is not True:
        gaps.append("A selection/approval is absent; the quality main must verify the actual A message")
    gaps.extend([
        "no synthesis, implementation, bitstream, HWH, timing, DRC/RDC/CDC or same-run pair exists",
        "no board, physical UART, electrical, analog ADC, calibration, Root/BOOT, H12 or H01-H15 acceptance exists",
        "internal 1 Mbaud digital TX/RX loopback is not a physical link result",
    ])
    return {"schema": "FUNCTIONAL50_CLOSURE_VERIFY_V1", "ok": True, "mode_requested": mode,
            "mode_effective": effective, "frozen": frozen, "build_ready": False,
            "build_ready_reason": "this static verifier does not inspect or authorize an A selection; the gated builder must do that separately",
            "closure": record(closure_path), "contract": contract,
            "sources": source_records, "tooling": tooling_records,
            "source94_observation": source94, "build_id_verification": build,
            "review_95": review, "cdc_policy": cdc, "cdc_bindings": closure.get("cdc_bindings"), "a_selection": a_selection,
            "gaps": gaps, "no_runtime": True, "no_vendor_call": True,
            "no_tcl_execution": True, "no_git_mutation": True, "no_board_or_network": True,
            "parent_owns_review_acceptance_and_git": True}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--contract-json", type=Path, required=True)
    parser.add_argument("--closure", type=Path)
    parser.add_argument("--mode", choices=("auto", "template", "frozen"), default="auto")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    closure_path = args.closure or (args.product_root / "fpga" / "diagnostic" / "functional50_build98" / "closure_template.json")
    try:
        report = verify(closure_path, args.product_root, args.contract_json, args.mode)
    except BaseException as error:
        print("FUNCTIONAL50_CLOSURE_FAILED: " + type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1
    text = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + chr(10)
    if args.out:
        out = Path(args.out)
        with out.open("x", encoding="utf-8", newline=chr(10)) as stream:
            stream.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
