"""Main's independent public-port UART RX oracle runner; no author code imported.

Real simulator runs only. Source snapshots/raw pipes/true return codes are
preserved. Synthetic log classifier checks never count as RTL evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def text_lines(raw: bytes) -> list[str]:
    text = raw.decode("utf-8", errors="strict")
    # ModelSim's console transcript prefixes user output with '# '.
    return [line[2:] if line.startswith("# ") else line for line in text.splitlines()]


def classify(raw: bytes, returncode: int, expected: tuple[int, int, int, int], mutant: bool = False) -> dict:
    lines = text_lines(raw)
    begin = f"MAIN_BEGIN clock={expected[0]} baud={expected[1]} stat={expected[2]} brief={expected[3]}"
    rows = [x for x in lines if x.startswith("MAIN_STATS")]
    contradictions = [x for x in lines if re.fullmatch(r"MAIN_MISMATCH cycle=\d+ field=[a-z_]+ got=\d+ expected=\d+ elapsed=\d+", x)]
    numeric = []
    for line in contradictions:
        m = re.search(r"got=(\d+) expected=(\d+)", line)
        if m and m[1] != m[2]:
            numeric.append(line)
    if mutant:
        # A deliberate fatal is expected, but only actual known numeric disagreement
        # qualifies; compile errors/timeouts/malformed rows do not kill a mutant.
        okay = lines.count(begin) == 1 and bool(numeric) and "MAIN_PASS" not in lines
        fatals = [x for x in lines if "** Fatal:" in x]
        okay = okay and fatals == ["** Fatal: main numeric mismatch"]
        okay = okay and not any(re.search(r"\*\*\s*(?:Error|Warning)", x) for x in lines)
        tallies = [re.fullmatch(r"Errors: (\d+), Warnings: (\d+)", x) for x in lines if x.startswith("Errors:")]
        okay = okay and len(tallies) == 1 and tallies[0] is not None and tallies[0].groups() == ("1", "0")
        return {"accepted": okay, "numeric_counterexamples": numeric[:4], "scope": "compiled behavioral mutant"}
    bad = any(re.search(r"(?:\*\*\s*(?:Error|Fatal|Warning)|MAIN_MISMATCH|watchdog|(?:Errors|Warnings):\s*[1-9])", x, re.I) for x in lines)
    bad = bad or any(x.startswith("MAIN_PASS") and x != "MAIN_PASS" for x in lines)
    stats = None
    if len(rows) == 1:
        m = re.fullmatch(r"MAIN_STATS cycles=(\d+) checks=(\d+) frames=(\d+) retired=(\d+) overruns=(\d+) framing=(\d+) falses=(\d+) aborted=(\d+)", rows[0])
        if m:
            stats = dict(zip(("cycles", "checks", "frames", "retired", "overruns", "framing", "falses", "aborted"), map(int, m.groups())))
    minimum = 4 if expected[3] else 256
    okay = returncode == 0 and not bad and lines.count(begin) == 1 and lines.count("MAIN_PASS") == 1 and stats is not None
    if stats:
        okay = okay and stats["frames"] >= minimum and stats["checks"] == stats["cycles"] * 14
        okay = okay and (expected[3] or (stats["overruns"] > 0 and stats["framing"] > 0 and stats["falses"] > 0 and stats["aborted"] > 0))
        okay = okay and lines.index(rows[0]) < lines.index("MAIN_PASS") if "MAIN_PASS" in lines else False
    return {"accepted": bool(okay), "stats": stats, "scope": "RTL public-port waveform"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rtl", type=Path, required=True)
    p.add_argument("--tb", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--tools", type=Path, default=Path("D:/modelsim1/win64"))
    p.add_argument("--mode", choices=("positive", "guard", "mutant"), default="positive")
    p.add_argument("--clock", type=int, default=97)
    p.add_argument("--baud", type=int, default=5)
    p.add_argument("--stat", type=int, default=32)
    p.add_argument("--brief", type=int, choices=(0, 1), default=0)
    p.add_argument("--guard", choices=("CLOCK_HZ", "BAUD", "STAT_W"))
    p.add_argument("--timeout", type=int, default=180)
    a = p.parse_args()
    # No attempt is replayed or overwritten, including failed attempts.
    rtl, tb = a.rtl.resolve(strict=True), a.tb.resolve(strict=True)
    out = a.out.resolve()
    if out.exists() or out in (rtl, tb) or out in rtl.parents or out in tb.parents:
        raise ValueError("output must be fresh and separate from inputs")
    out.mkdir(parents=True)
    (out / "temp").mkdir()
    inputs = {}
    for name, src in (("dut.sv", rtl), ("main_tb.sv", tb)):
        data = src.read_bytes()
        (out / name).write_bytes(data)
        inputs[name] = {"source": str(src), "sha256": digest(data), "bytes": len(data)}
    save(out / "INPUTS.json", inputs)
    env = dict(os.environ, TEMP=str(out / "temp"), TMP=str(out / "temp"), TMPDIR=str(out / "temp"), PYTHONDONTWRITEBYTECODE="1")
    commands = []

    def run(name: str, argv: list[str]) -> tuple[int, bytes]:
        start = time.time()
        timeout = False
        try:
            r = subprocess.run(argv, cwd=out, env=env, capture_output=True, timeout=a.timeout)
            code, stdout, stderr = r.returncode, r.stdout, r.stderr
        except subprocess.TimeoutExpired as e:
            timeout = True
            code, stdout, stderr = None, e.stdout or b"", e.stderr or b""
        (out / (name + ".stdout.bin")).write_bytes(stdout)
        (out / (name + ".stderr.bin")).write_bytes(stderr)
        receipt = {"name": name, "argv": argv, "cwd": str(out), "returncode": code, "timeout": timeout,
                   "started_unix": start, "elapsed_seconds": time.time() - start,
                   "stdout_sha256": digest(stdout), "stderr_sha256": digest(stderr)}
        commands.append(receipt)
        save(out / (name + ".command.json"), receipt)
        if timeout:
            raise RuntimeError("actual simulator timeout; no accepted result")
        return code, stdout + b"\n" + stderr

    result = {"accepted": False, "mode": a.mode, "parameters": [a.clock, a.baud, a.stat, a.brief]}
    try:
        for tool in ("vlog", "vsim"):
            code, _ = run(tool + "_version", [str(a.tools / (tool + ".exe")), "-version"])
            if code != 0:
                raise RuntimeError("version command failed")
        code, _ = run("vlib", [str(a.tools / "vlib.exe"), "work"])
        if code != 0:
            raise RuntimeError("vlib failed")
        code, raw = run("vlog", [str(a.tools / "vlog.exe"), "-sv", "-work", "work", "dut.sv", "main_tb.sv"])
        if code != 0 or re.search(rb"\*\*\s*(?:Error|Warning|Fatal)|(?:Errors|Warnings):\s*[1-9]", raw) or not re.search(rb"Errors: 0, Warnings: 0", raw):
            raise RuntimeError("compile failed or warning/error diagnostics")
        argv = [str(a.tools / "vsim.exe"), "-c", "-onfinish", "stop", "work.main_tb_uart_rx",
                f"-gCLOCK_HZ={a.clock}", f"-gBAUD={a.baud}", f"-gSTAT_W={a.stat}", f"-gBRIEF={a.brief}",
                "-do", "onerror {quit -code 1}; run -all; quit -code 0"]
        code, raw = run("vsim", argv)
        if a.mode == "guard":
            expected = f"deepeye_uart_rx: {a.guard} out of range"
            lines = text_lines(raw)
            own = [x for x in lines if x == "** Fatal: " + expected]
            others = [x for x in lines if re.search(r"\*\*\s*(?:Error|Warning|Fatal)", x) and x not in own]
            tallies = [x for x in lines if x.startswith("Errors:")]
            zero_time = any(re.search(r"Time: 0 (?:ps|ns)\s+Scope: .*\.dut\.", x) for x in lines)
            result.update(accepted=code == 0 and len(own) == 1 and not others and tallies == ["Errors: 1, Warnings: 0"] and zero_time and not any(x.startswith("MAIN_PASS") for x in lines), diagnostic=expected, actual_returncode=code)
        else:
            result.update(classify(raw, code, (a.clock, a.baud, a.stat, a.brief), a.mode == "mutant"))
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
    result["commands"] = commands
    result["inputs"] = inputs
    result["nonclaims"] = "all29/B04/R03/synthesis/implementation/CDC_RDC/board/system not_run"
    save(out / "RESULT.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
