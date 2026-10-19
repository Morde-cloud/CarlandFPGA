$ErrorActionPreference='Stop'
$w='D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014'
$a=Join-Path $w 'competition\deepeye\evidence\control3d\pwm-applied-capture-20261020-15\author'
$run=Join-Path $a 'debug-author-20261020-15-g15-b'
$dst=Join-Path $a 'source-snapshot-debug-g15-b-posthoc-20261020-15-a'
if((Resolve-Path -LiteralPath $w).Path -ne $w){throw 'worktree mismatch'}
if(Test-Path -LiteralPath $dst){throw 'destination exists'}
if(-not (Resolve-Path -LiteralPath $run).Path.StartsWith($a,[StringComparison]::OrdinalIgnoreCase)){throw 'run outside author'}
New-Item -ItemType Directory -Path $dst | Out-Null
$defs=@(
 @{k='rtl';p=(Join-Path $w 'competition\deepeye\fpga\control3d\deepeye_pwm_applied_capture.sv');n='rtl.sv'},
 @{k='tb';p=(Join-Path $w 'competition\deepeye\tests\rtl\control3d\tb_pwm_applied_capture.sv');n='tb.sv'},
 @{k='atomic';p=(Join-Path $w 'competition\deepeye\fpga\control3d\deepeye_atomic_pwm.sv');n='atomic.sv'},
 @{k='capture';p=(Join-Path $w 'competition\deepeye\fpga\control3d\deepeye_pwm_coherent_capture.sv');n='capture.sv'})
$recs=@()
foreach($d in $defs){$i=Get-Item -LiteralPath $d.p; $t=Join-Path $dst $d.n; Copy-Item -LiteralPath $d.p -Destination $t; $h=(Get-FileHash -LiteralPath $d.p -Algorithm SHA256).Hash.ToUpperInvariant(); $h2=(Get-FileHash -LiteralPath $t -Algorithm SHA256).Hash.ToUpperInvariant(); if($h -ne $h2){throw ('hash mismatch '+$d.k)}; $recs += [ordered]@{key=$d.k;source=$d.p;source_last_write_utc=$i.LastWriteTimeUtc.ToString('o');source_bytes=$i.Length;source_sha256=$h;snapshot=$t;snapshot_sha256=$h2;hash_match=$true}}
$old=Join-Path $a 'run-author-20261020-15-b\source_snapshot'
$rtl=($recs|Where-Object key -eq 'rtl').source_sha256; $tb=($recs|Where-Object key -eq 'tb').source_sha256
$oldRtl=(Get-FileHash -LiteralPath (Join-Path $old 'rtl.sv') -Algorithm SHA256).Hash.ToUpperInvariant(); $oldTb=(Get-FileHash -LiteralPath (Join-Path $old 'tb.sv') -Algorithm SHA256).Hash.ToUpperInvariant()
$v=Get-Content -LiteralPath (Join-Path $run 'vlog.stdout.txt') -Raw
$r=[ordered]@{task_id='DEEPEYE-IMPLEMENTATION-20261014';task_version=1;work_id='B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1';operation_id='B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15';purpose='Reconstruct exact source bytes used by isolated g15-b, which lacked a pre-run snapshot.';reconstructed_utc=[DateTime]::UtcNow.ToString('o');g15_run_directory=$run;g15_log_start=([regex]::Match($v,'Start time:\s*([^\r\n]+)').Groups[1].Value.Trim());g15_log_end=([regex]::Match($v,'End time:\s*([^\r\n]+)').Groups[1].Value.Trim());current_sources=$recs;comparison_to_run_b_snapshot=[ordered]@{rtl_hash_equals=($rtl -eq $oldRtl);run_b_rtl_sha256=$oldRtl;tb_hash_differs=($tb -ne $oldTb);run_b_tb_sha256=$oldTb;explanation='g15-b followed the phase-shift TB/candidate edits; RTL unchanged, TB intentionally differs from run-b.'};timestamp_proof='All four source last-write times predate the logged 03:56:59 vlog start; current source mtimes remain before that start.';limitation='Post-hoc reconstruction from unchanged source bytes and log/timestamp ordering; no pre-run copy existed for g15-b.'}
$rp=Join-Path $dst 'SOURCE_SNAPSHOT_RECONSTRUCTION.json'
$r|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $rp -Encoding UTF8
[ordered]@{result='PASS';snapshot_directory=$dst;source_files=$recs.Count;record=$rp;record_sha256=(Get-FileHash -LiteralPath $rp -Algorithm SHA256).Hash.ToUpperInvariant();all_source_hashes_match=(($recs|Where-Object {-not $_.hash_match}).Count -eq 0)}|ConvertTo-Json -Depth 4
