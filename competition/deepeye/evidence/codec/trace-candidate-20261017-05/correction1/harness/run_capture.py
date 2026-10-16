import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

seq = int(sys.argv[1])
label = sys.argv[2]
phase = sys.argv[3]
capture_dir = Path(sys.argv[4])
meta_dir = Path(sys.argv[5])
cwd = sys.argv[6]
argv = sys.argv[7:]

started = datetime.now(timezone.utc)
t0 = time.monotonic()
proc = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE)
duration = time.monotonic() - t0
finished = datetime.now(timezone.utc)

stdout_path = capture_dir / ('%02d_%s.stdout.txt' % (seq, label))
stderr_path = capture_dir / ('%02d_%s.stderr.txt' % (seq, label))
stdout_path.write_bytes(proc.stdout)
stderr_path.write_bytes(proc.stderr)

meta = {
    'seq': seq,
    'label': label,
    'phase': phase,
    'work_id': 'B-TRACE-CANONICAL-SOURCEAGE-CORRECTION-20261017-01-v1',
    'job_id': 'child-c0147fc39c224fbdb10a00068108d119',
    'instance_id': 'deepseek-b-25',
    'argv': argv,
    'cwd': cwd,
    'exit_code': proc.returncode,
    'started_utc': started.isoformat(),
    'finished_utc': finished.isoformat(),
    'duration_s': round(duration, 3),
    'stdout_capture': 'captures/%02d_%s.stdout.txt' % (seq, label),
    'stderr_capture': 'captures/%02d_%s.stderr.txt' % (seq, label),
}
(meta_dir / ('%02d.json' % seq)).write_text(
    json.dumps(meta, indent=1), encoding='utf-8')
print('exit=%d stdout=%d stderr=%d' % (proc.returncode, len(proc.stdout),
      len(proc.stderr)))
