'''Stream one apply_patch payload from stdin to the local codex helper.'''

import subprocess
import sys


def main():
    data = []
    while True:
        line = sys.stdin.buffer.readline()
        if not line or line.strip() == b'__PATCH_EOF__':
            break
        data.append(line)
    patch = b''.join(data).decode('utf-8').replace('\r\n', '\n').rstrip('\n')
    result = subprocess.run(
        [sys.argv[1], '--codex-run-as-apply-patch', patch],
        capture_output=True,
    )
    sys.stdout.buffer.write(result.stdout)
    sys.stderr.buffer.write(result.stderr)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
