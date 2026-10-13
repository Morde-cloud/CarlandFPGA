"""Planning arithmetic only. No RTL, inference, hardware, or network calls."""
from fractions import Fraction
from pathlib import Path
import json
import re
import sys

root = Path(__file__).resolve().parent
prefix = [2, 1, 1, 1, 2, 2, 4, 1]
overhead = sum(prefix) + 2
payload = {
    "summary": [8, 8],
    "event": [1, 1, 2],
    "command": [2, 2, 1, 1, 2],
    "applied": [2, 2, 1, 1, 2, 2, 2],
}
frames = {k: overhead + sum(v) for k, v in payload.items()}
assert frames == {"summary": 32, "event": 20, "command": 24, "applied": 28}
normal_bytes = sum(frames.values())
retry_bytes = frames["command"] + frames["applied"]
window = Fraction(8)
guard = Fraction(1, 5)
line_baud = 300
bit_per_byte = 10
normal_seconds = Fraction(normal_bytes * bit_per_byte, line_baud) + guard
retry_seconds = Fraction((normal_bytes + retry_bytes) * bit_per_byte, line_baud) + guard
assert normal_seconds / window == Fraction(11, 24)
assert retry_seconds / window == Fraction(27, 40)
assert normal_seconds < retry_seconds < window
raw_bps = 4 * 100 * 16
assert raw_bps == 6400 and raw_bps // 8 == 800 and raw_bps // 8 > line_baud
review = (root / "review.md").read_text(encoding="utf-8")
assert 1000 <= len(review) <= 2000
missing = []
for path in root.glob("*.md"):
    for link in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
        if "://" not in link and not (path.parent / link.split("#")[0]).exists():
            missing.append({"source": path.name, "target": link})
assert not missing, missing
crlf_files = [p.name for p in root.iterdir() if p.is_file() and b"\r\n" in p.read_bytes()]
assert not crlf_files, crlf_files
result = {
    "task_id": "COMP-20261013-DEEPEYE", "task_version": 2,
    "validation_type": "planning_arithmetic_and_document_integrity_only",
    "python_version": sys.version.split()[0], "passed": True,
    "prefix_bytes": sum(prefix), "crc_bytes": 2, "frame_total_bytes": frames,
    "window_seconds": 8, "wire_baud": 300, "wire_bits_per_byte": 10,
    "normal_bytes": normal_bytes, "retry_exchange_bytes": retry_bytes,
    "guard_seconds": float(guard),
    "normal_seconds_with_guard": float(normal_seconds),
    "retry_seconds_with_guard": float(retry_seconds),
    "normal_fraction": str(normal_seconds / window),
    "with_retry_fraction": str(retry_seconds / window),
    "max_frame_block_seconds": float(Fraction(max(frames.values()) * bit_per_byte, line_baud)),
    "raw_bps": raw_bps, "raw_div_8_bps": raw_bps // 8,
    "review_characters_with_lf": len(review),
    "review_cjk_characters": len(re.findall(r"[\u4e00-\u9fff]", review)),
    "relative_links_missing": missing, "crlf_files": crlf_files,
    "runtime_inference": "not_run", "rtl_simulation": "not_run",
    "synthesis": "not_run", "implementation": "not_run", "hardware": "not_run",
}
print(json.dumps(result, ensure_ascii=False, indent=2))
