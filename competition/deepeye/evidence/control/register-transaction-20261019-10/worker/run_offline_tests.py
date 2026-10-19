'''Capture the portable offline test run as raw binary streams.'''

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import time


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--worktree', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    worktree = pathlib.Path(args.worktree).resolve()
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        '-B',
        '-X',
        'utf8',
        '-m',
        'unittest',
        'discover',
        '-s',
        'competition/deepeye/tests/control',
        '-p',
        'test_register_transaction.py',
        '-v',
    ]
    started_utc = datetime.datetime.now(datetime.timezone.utc)
    started = time.monotonic()
    completed = subprocess.run(
        command,
        cwd=str(worktree),
        capture_output=True,
    )
    duration = time.monotonic() - started
    finished_utc = datetime.datetime.now(datetime.timezone.utc)
    stdout = completed.stdout
    stderr = completed.stderr
    (out / 'stdout.bin').write_bytes(stdout)
    (out / 'stderr.bin').write_bytes(stderr)
    (out / 'returncode.txt').write_text(
        str(completed.returncode) + '\n',
        encoding='ascii',
    )
    metadata = {
        'command': command,
        'cwd': str(worktree),
        'python_executable': sys.executable,
        'python_version': sys.version,
        'started_utc': started_utc.isoformat(),
        'finished_utc': finished_utc.isoformat(),
        'duration_seconds': round(duration, 6),
        'returncode': completed.returncode,
        'stdout_bytes': len(stdout),
        'stderr_bytes': len(stderr),
        'stdout_sha256': _sha256(stdout),
        'stderr_sha256': _sha256(stderr),
        'binary_capture': True,
    }
    text = json.dumps(metadata, indent=2, sort_keys=True) + '\n'
    (out / 'run_metadata.json').write_text(text, encoding='utf-8')
    sys.stdout.write(text)
    return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
