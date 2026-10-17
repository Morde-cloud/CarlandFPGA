<# Update an existing node without rerunning onboarding or replacing secrets. #>
param(
    [Parameter(Mandatory = $true)][ValidateSet('A', 'B', 'C')][string]$Node,
    [Parameter(Mandatory = $true)][string]$Workspace,
    [Parameter(Mandatory = $true)][string]$Package,
    [string]$Config = '',
    [string]$Python = '',
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
$repo = [System.IO.Path]::GetFullPath($Workspace)
$packagePath = [System.IO.Path]::GetFullPath($Package)
$packageRoot = Split-Path -Parent $PSScriptRoot
$updater = Join-Path $packageRoot 'fpga_mesh/update.py'
. (Join-Path $PSScriptRoot 'Preserve-FPGAMeshTask.ps1')
if (-not $Config) { $Config = Join-Path $repo ('.local/deployment/node-{0}/node-{0}.toml' -f $Node.ToLowerInvariant()) }
if (-not $Python) { $Python = Join-Path $repo '.local/venv/Scripts/python.exe' }
$configPath = [System.IO.Path]::GetFullPath($Config)
$pythonPath = [System.IO.Path]::GetFullPath($Python)
foreach ($path in @($packagePath, $updater, $configPath, $pythonPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Required existing file not found: $path" }
}
$updateArgs = @($updater, '--package', $packagePath, '--workspace', $repo, '--config', $configPath, '--node', $Node)
$preflight = @(& $pythonPath @updateArgs)
if ($LASTEXITCODE -ne 0) { throw ('Update preflight blocked; existing files and service preserved. ' + ($preflight -join "`n")) }
$plan = ($preflight -join "`n") | ConvertFrom-Json
Write-Output ($preflight -join "`n")
$control = [string]$plan.control_file
if (-not $control -or -not [IO.Path]::IsPathRooted($control)) { throw 'Preflight did not identify an absolute control file.' }
$snapshot = Get-FPGAMeshTaskSnapshot -Node $Node -Workspace $repo -Config $configPath -Python $pythonPath
Assert-FPGAMeshRouting -Workspace $repo -Python $pythonPath -ControlFile $control
if ($CheckOnly) { return }
$snapshotDirectory = Save-FPGAMeshTaskSnapshot -Snapshot $snapshot -Workspace $repo
$phase = 'before-stop'
$outcome = 'failed'
$failure = $null
try {
    Assert-FPGAMeshRouting -Workspace $repo -Python $pythonPath -ControlFile $control
    Assert-FPGAMeshTaskUnchanged -Snapshot $snapshot -Boundary $phase
    # Keep the existing atomic ledger admission fence and stop callback intact.
    & $pythonPath @updateArgs --stop-idle
    if ($LASTEXITCODE -ne 0) { throw 'Atomic idle/stop guard blocked; do not interrupt work or repeat onboarding.' }
    $phase = 'before-source-write'
    Assert-FPGAMeshRouting -Workspace $repo -Python $pythonPath -ControlFile $control
    Assert-FPGAMeshTaskUnchanged -Snapshot $snapshot -Boundary $phase
    $phase = 'source-apply'
    & $pythonPath @updateArgs --apply
    if ($LASTEXITCODE -ne 0) { throw 'Source update failed; inspect the local backup receipt and any rollback errors before recovery. The task will not be started.' }
    Push-Location $repo
    try {
        $phase = 'before-start'
        Assert-FPGAMeshRouting -Workspace $repo -Python $pythonPath -ControlFile $control
        Assert-FPGAMeshTaskUnchanged -Snapshot $snapshot -Boundary $phase
        $phase = 'start-attempt'
        Start-ScheduledTask -TaskName $snapshot.TaskName -TaskPath $snapshot.TaskPath -ErrorAction Stop
        $phase = 'after-start'
        Assert-FPGAMeshTaskUnchanged -Snapshot $snapshot -Boundary $phase
        $health = $null
        $deadline = (Get-Date).AddSeconds(60)
        do {
            $healthLines = @(& $pythonPath -m fpga_mesh.project_cli --control-file $control health 2>$null)
            if ($LASTEXITCODE -eq 0) {
                $health = ($healthLines -join "`n") | ConvertFrom-Json
                if ($health.started -and ((-not $health.feishu_enabled) -or $health.feishu_connected)) { break }
            }
            Start-Sleep -Seconds 1
        } while ((Get-Date) -lt $deadline)
        if (-not $health -or -not $health.started -or ($health.feishu_enabled -and -not $health.feishu_connected)) {
            throw 'Source updated; resident health/Feishu not ready. Inspect existing service.log; do not repeat onboarding.'
        }
        # Model/role refresh is separate work: it can write native role definitions.
        $phase = 'file-scope-audit'
        $scopeLines = @(& $pythonPath -m fpga_mesh.feishu_permissions --config $configPath)
        if ($LASTEXITCODE -ne 0) { throw 'Resident started; Feishu file-scope audit failed. Inspect the API error; do not recreate apps.' }
        $fileScope = ($scopeLines -join "`n") | ConvertFrom-Json
        if ($fileScope.status -eq 'needs_admin_grant') {
            Write-Warning ('Source update completed. This node Astra app still needs its owner to grant only im:resource: ' + $fileScope.manage_url)
        }
        [ordered]@{
            revision = $plan.revision; node = $Node; sourceUpdated = $true
            residentStarted = $health.started; feishuConnected = $health.feishu_connected
            mainIdentity = $health.identities.main; childIdentity = $health.identities.deepseek
            feishuFileScope = $fileScope
            taskPreservationEvidence = $snapshotDirectory
            nextStep = 'Verify loaded source and the preserved launcher process chain before accepting deployment. This updater did not reinstall routing or refresh roles.'
        } | ConvertTo-Json
        $phase = 'completed'
        $outcome = 'completed'
    } finally { Pop-Location }
} catch {
    # Do not replay failed task work or rerun registration/onboarding blindly.
    $failure = $_.Exception.Message
    throw
} finally {
    [ordered]@{ status = $outcome; phase = $phase; failure = $failure; revision = $plan.revision;
        task = $snapshot.TaskName; taskXmlSha256 = $snapshot.XmlSha256; launcherSha256 = $snapshot.LauncherSha256;
        automaticReplay = $false } | ConvertTo-Json |
        Set-Content -LiteralPath (Join-Path $snapshotDirectory 'update-result.json') -Encoding UTF8
}
