$ErrorActionPreference = 'Stop'

$worktree = [System.IO.Path]::GetFullPath('D:/pynq/CarlandFPGA/.local/worktrees/deepeye-implementation-20261014')
$author = [System.IO.Path]::GetFullPath((Join-Path $worktree 'competition/deepeye/evidence/control3d/pwm-applied-capture-20261020-15/author'))
$destination = [System.IO.Path]::GetFullPath((Join-Path $author 'stray-root-artifacts-20261020-15-a'))

if ($worktree -ne 'D:\pynq\CarlandFPGA\.local\worktrees\deepeye-implementation-20261014') {
    throw "Unexpected worktree path: $worktree"
}
if (-not $author.StartsWith($worktree + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Author path is outside worktree: $author"
}
if (-not $destination.StartsWith($author + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Destination is outside author evidence: $destination"
}
if (Test-Path -LiteralPath $destination) {
    throw "Destination already exists; refusing to overwrite: $destination"
}

$sources = @(
    (Join-Path $worktree 'lib'),
    (Join-Path $worktree 'transcript')
)

function Get-ArtifactRecord([string]$path) {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        $item = Get-Item -LiteralPath $path -Force
        return [ordered]@{
            path = $path
            kind = 'file'
            bytes = [long]$item.Length
            sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToUpperInvariant()
            last_write_utc = $item.LastWriteTimeUtc.ToString('o')
        }
    }
    if (Test-Path -LiteralPath $path -PathType Container) {
        $files = @(Get-ChildItem -LiteralPath $path -File -Recurse -Force | Sort-Object FullName)
        $entries = @()
        foreach ($file in $files) {
            $relative = $file.FullName.Substring($path.Length).TrimStart('\', '/')
            $entries += [ordered]@{
                relative_path = $relative
                bytes = [long]$file.Length
                sha256 = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToUpperInvariant()
            }
        }
        return [ordered]@{
            path = $path
            kind = 'directory'
            file_count = $entries.Count
            files = $entries
        }
    }
    throw "Artifact does not exist: $path"
}

New-Item -ItemType Directory -Path $destination | Out-Null
$before = @()
foreach ($source in $sources) {
    $before += Get-ArtifactRecord $source
}

$moves = @()
foreach ($source in $sources) {
    $name = Split-Path -Leaf $source
    $target = [System.IO.Path]::GetFullPath((Join-Path $destination $name))
    if (Test-Path -LiteralPath $target) {
        throw "Move target already exists: $target"
    }
    Move-Item -LiteralPath $source -Destination $target
    if (Test-Path -LiteralPath $source) {
        throw "Source still exists after move: $source"
    }
    if (-not (Test-Path -LiteralPath $target)) {
        throw "Target missing after move: $target"
    }
    $moves += [ordered]@{
        source = $source
        target = $target
        operation = 'Move-Item -LiteralPath source -Destination target'
        source_absent_after = -not (Test-Path -LiteralPath $source)
        target_present_after = Test-Path -LiteralPath $target
    }
}

$after = @()
foreach ($move in $moves) {
    $after += Get-ArtifactRecord $move.target
}

$record = [ordered]@{
    task_id = 'DEEPEYE-IMPLEMENTATION-20261014'
    task_version = 1
    work_id = 'B-PWM-APPLIED-CAPTURE-RTL-20261020-15-v1'
    operation_id = 'B-DEEPEYE-PWM-APPLIED-CAPTURE-20261020-15'
    purpose = 'Preserve ModelSim scratch/cache and transcript accidentally created at the worktree root; no source or prior run directory was edited.'
    recorded_utc = [DateTime]::UtcNow.ToString('o')
    powershell_version = $PSVersionTable.PSVersion.ToString()
    worktree = $worktree
    destination = $destination
    before = $before
    moves = $moves
    after = $after
    note = 'The root lib contained only ModelSim _info cache data (142 bytes). The transcript was a failed compile attempt for an earlier run-c compile directory. Both are retained read-only as failure preparation evidence.'
}

$recordPath = Join-Path $destination 'MOVE_RECORD.json'
$record | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $recordPath -Encoding UTF8
[ordered]@{
    result = 'PASS'
    record = $recordPath
    record_sha256 = (Get-FileHash -LiteralPath $recordPath -Algorithm SHA256).Hash.ToUpperInvariant()
    root_lib_absent = -not (Test-Path -LiteralPath (Join-Path $worktree 'lib'))
    root_transcript_absent = -not (Test-Path -LiteralPath (Join-Path $worktree 'transcript'))
    preserved_files = (Get-ChildItem -LiteralPath $destination -File -Recurse -Force).Count
} | ConvertTo-Json -Depth 4
