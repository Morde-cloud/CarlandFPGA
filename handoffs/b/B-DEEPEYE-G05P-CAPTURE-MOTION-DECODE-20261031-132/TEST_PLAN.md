# B132 focused test plan (prepared only)

Status: **NOT RUN BY THE SOURCE AUTHOR**. These commands are for the registered B
main or its explicitly assigned reviewer after independent source review. The
fixture is synthetic. A pass is decoder-local software evidence only, not a board
result, electrical-loopback result, motion authority, H01-H15/product acceptance,
or a `1%` timing claim.

## Scope

- Only `g05p_capture_decoder132.py`, its synthetic fixture, and
  `test_g05p_capture_decoder132.py` are exercised.
- Do not run old mapper/protocol/PDE/board suites, Vivado, a simulator, a model,
  a network client, or any physical G05 operation.
- Preserve every refusal result. Do not change a fixture merely to turn a failing
  case green; return the actual output and failure to the main.
- Run with bytecode writing disabled (`-B`) so the handoff remains source-only.

## 1. Optional syntax and fixture preflight

From PowerShell, with `$handoff` set to this exact handoff directory:

```powershell
$handoff = '<absolute path to B-DEEPEYE-G05P-CAPTURE-MOTION-DECODE-20261031-132>'
Set-Location -LiteralPath $handoff
python -B -X utf8 -c "import ast,json,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('g05p_capture_decoder132.py','test_g05p_capture_decoder132.py')]; json.load(open('fixtures/valid32_synthetic.json', encoding='utf-8')); print('SYNTAX_AND_FIXTURE_OK')"
```

This parses syntax and JSON only. It must not import the decoder.

## 2. Focused pure unit tests

```powershell
$handoff = '<absolute path to B-DEEPEYE-G05P-CAPTURE-MOTION-DECODE-20261031-132>'
Set-Location -LiteralPath $handoff
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -X utf8 -m unittest -v test_g05p_capture_decoder132
```

Expected source-level scope: 48 new tests, all values synthetic. They cover the
hand-calculated valid 32-word fixture; null versus zero; cardinality; request and
record bounds; magic/session/sequence; nominal-versus-measured separation;
period/high/start/end and zero-extension checks; profile/TTL/curvature-ROM
limits; pre/post-LATCH status flags; identity/session/command/tag and optional
strict sequence checks; association mismatches; mapper interval endpoints; and
absence of float output.

## 3. CLI/first finite pure test

The main must choose a **new absolute output path whose parent already exists**.
The decoder refuses to overwrite an existing path.

```powershell
$handoff = '<absolute path to B-DEEPEYE-G05P-CAPTURE-MOTION-DECODE-20261031-132>'
$parent = '<existing main-owned absolute test parent>'
$out = Join-Path $parent ('b132-valid-' + [guid]::NewGuid().ToString('N'))
Set-Location -LiteralPath $handoff
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -X utf8 .\g05p_capture_decoder132.py --request .\fixtures\valid32_synthetic.json --out $out
$exit = $LASTEXITCODE
$result = Get-Content -LiteralPath (Join-Path $out 'decode_result.json') -Raw | ConvertFrom-Json
[pscustomobject]@{
  ExitCode = $exit
  Status = $result.status
  MotionAuthority = $result.limits.motion_authority
  FullIdentityBound = $result.association.full_identity_bound_to_capture
  RawWordsPreserved = $result.preserved_input.raw_words_preserved
  ResultSchema = $result.schema
} | ConvertTo-Json
```

Expected result for the synthetic fixture: exit code `0`,
`DECODED_PARTIAL_ASSOCIATION`, `motion_authority=false`,
`full_identity_bound_to_capture=false`, 32 raw words preserved, and
`B132_G05P_CAPTURE_DECODE_RESULT_V1`.

Capture the exact command, Python version, exit code, stdout/stderr, output
absolute path, and SHA256 of `decode_result.json` in the main-owned test evidence.
Do not place a board or acceptance claim on this output.

## 4. Review checks after any run

- Confirm no decoder process accessed a board, network, vendor tool, or old suite.
- Confirm `decode_result.json` is the only requested product leaf and that the
  CLI did not overwrite a pre-existing directory.
- Confirm the refusal paths retained raw words and, where within the bounded
  schema, the original record.
- Confirm no Pytest/cache/`__pycache__` artifact was produced in this handoff.
- If implementation changes are requested, return ownership to the main; do not
  silently patch around a test.

## Estimated budget, not measured evidence

One local Python process, under 64 MiB resident memory, under 2 seconds wall time,
48 pure tests, no subprocess, no network, no simulator, no vendor tool, no board.
These are estimates only. The source author executed none of the commands above.
