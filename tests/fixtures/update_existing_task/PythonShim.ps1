$ErrorActionPreference = 'Stop'

function Write-ShimLog {
    param([string]$Action, [object]$Data = $null)
    $entry = [ordered]@{
        at = [DateTime]::UtcNow.ToString('o')
        action = $Action
        data = $Data
    }
    $line = $entry | ConvertTo-Json -Compress -Depth 12
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($env:FIXTURE_LOG, $line + "`n", $encoding)
}

function Mutate-Launcher {
    param([string]$Boundary)
    if ($env:FIXTURE_MUTATE_ROUTING_ON -eq $Boundary) {
        [IO.File]::AppendAllText($env:FIXTURE_ROUTING_PATH, "`ninvalid TOML on purpose`n")
        Write-ShimLog 'routing_mutated' $Boundary
    }
    if ($env:FIXTURE_MUTATE_LAUNCHER_ON -ne $Boundary) { return }
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($env:FIXTURE_LAUNCHER_PATH, "`n# fixture launcher mutation at $Boundary`n", $encoding)
    Write-ShimLog 'launcher_mutated' ([ordered]@{ boundary = $Boundary; path = $env:FIXTURE_LAUNCHER_PATH })
}

$all = @($args)
Write-ShimLog 'python_shim' ([ordered]@{ argv = $all })

if ($all -contains '-c') {
    Write-ShimLog 'routing_forward' ([ordered]@{ realPython = $env:FIXTURE_REAL_PYTHON })
    & $env:FIXTURE_REAL_PYTHON @all
    exit $LASTEXITCODE
}

if (($all -contains 'fpga_mesh.install_routing') -or ($all -contains 'models_refresh') -or ($all -contains 'register-autostart')) {
    Write-ShimLog 'forbidden_command' ([ordered]@{ argv = $all })
    [Console]::Error.WriteLine('fixture rejected forbidden command')
    exit 91
}

if ($all -contains '--stop-idle') {
    if ($env:FIXTURE_BUSY -eq '1') {
        Write-ShimLog 'stop_idle' ([ordered]@{ result = 'busy' })
        [Console]::Error.WriteLine('fixture admission busy')
        exit 11
    }
    if ($env:FIXTURE_LOCKED -eq '1') {
        Write-ShimLog 'stop_idle' ([ordered]@{ result = 'locked' })
        [Console]::Error.WriteLine('fixture admission locked')
        exit 12
    }
    Mutate-Launcher 'stop'
    Write-ShimLog 'stop_idle' ([ordered]@{ result = 'ok' })
    exit 0
}

if ($all -contains '--apply') {
    if ($env:FIXTURE_APPLY_FAIL -eq '1') {
        Write-ShimLog 'apply' ([ordered]@{ result = 'failed' })
        [Console]::Error.WriteLine('fixture apply failure')
        exit 21
    }
    Mutate-Launcher 'apply'
    Write-ShimLog 'apply' ([ordered]@{ result = 'ok' })
    exit 0
}

if (($all -contains '-m') -and ($all -contains 'fpga_mesh.project_cli') -and ($all -contains 'health')) {
    Write-ShimLog 'health' ([ordered]@{ result = 'ok' })
    Write-Output '{"started":true,"feishu_enabled":false,"feishu_connected":false,"identities":{"main":"fixture-main","deepseek":"fixture-child"}}'
    exit 0
}

if (($all -contains '-m') -and ($all -contains 'fpga_mesh.feishu_permissions')) {
    Write-ShimLog 'scope_audit' ([ordered]@{ result = 'ok' })
    Write-Output '{"status":"ready","granted_scopes":[]}'
    exit 0
}

if (($all -contains '--package') -and ($all -contains '--workspace') -and ($all -contains '--config') -and ($all -contains '--node')) {
    Write-ShimLog 'preflight' ([ordered]@{ result = 'ok' })
    $plan = [ordered]@{
        revision = 'fixture-revision'
        control_file = $env:FIXTURE_CONTROL_FILE
    } | ConvertTo-Json -Compress -Depth 4
    Write-Output $plan
    exit 0
}

Write-ShimLog 'unknown_command' ([ordered]@{ argv = $all })
[Console]::Error.WriteLine('fixture unknown command')
exit 92
