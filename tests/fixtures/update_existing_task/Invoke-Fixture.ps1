param(
    [Parameter(Mandatory = $true)][string]$Updater,
    [Parameter(Mandatory = $true)][string]$Node,
    [Parameter(Mandatory = $true)][string]$Workspace,
    [Parameter(Mandatory = $true)][string]$Package,
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Python,
    [switch]$CheckOnly
)
$ErrorActionPreference = 'Stop'
Import-Module Microsoft.PowerShell.Utility -ErrorAction Stop
Import-Module Microsoft.PowerShell.Management -ErrorAction Stop
$PSModuleAutoLoadingPreference = 'None'
Remove-Module ScheduledTasks -Force -ErrorAction SilentlyContinue

function Write-FixtureLog {
    param([string]$Action, [object]$Data = $null)
    $entry = [ordered]@{
        at = [DateTime]::UtcNow.ToString('o')
        action = $Action
        data = $Data
    }
    $line = $entry | ConvertTo-Json -Compress -Depth 10
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::AppendAllText($env:FIXTURE_LOG, $line + "`n", $encoding)
}

$script:Node = $Node
$script:Workspace = $Workspace
$script:Config = $Config
$script:Python = $Python
$global:ExportCount = 0

$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
if ($env:FIXTURE_PRINCIPAL_MODE -eq 'wrong') {
    $sid = 'S-1-5-21-1111111111-2222222222-3333333333-4444'
}

$taskName = "FPGA-Mesh-Node-$Node"
if ($env:FIXTURE_TASK_NAME_MODE -eq 'wrong') { $taskName = 'FPGA-Mesh-Node-C' }
$taskPath = '\'
if ($env:FIXTURE_TASK_PATH_MODE -eq 'wrong') { $taskPath = '\Other\' }
$description = "FPGA Mesh $Node controller fixture"
if ($env:FIXTURE_DESCRIPTION_MODE -eq 'wrong') { $description = 'Unrelated fixture task' }

$actionArguments = $env:FIXTURE_ACTION_ARGUMENTS
if ($env:FIXTURE_ACTION_ARGUMENTS_MODE -eq 'empty') { $actionArguments = '' }
if ([string]::IsNullOrEmpty($actionArguments) -and $env:FIXTURE_ACTION_ARGUMENTS_MODE -ne 'empty') {
    $actionArguments = '--config "' + $Config + '"'
}
$actionExecute = $Python
if ($env:FIXTURE_ACTION_EXECUTE_MODE -eq 'wrong') { $actionExecute = Join-Path $Workspace 'wrong-python.exe' }
$actionWorkdir = $Workspace
if ($env:FIXTURE_ACTION_WORKDIR_MODE -eq 'wrong') { $actionWorkdir = Join-Path $Workspace 'wrong-workdir' }
$action1 = [pscustomobject]@{
    Execute = $actionExecute
    Arguments = $actionArguments
    WorkingDirectory = $actionWorkdir
}
$actions = @($action1)
if ($env:FIXTURE_ACTION_COUNT_MODE -eq 'two') {
    $actions += [pscustomobject]@{
        Execute = $actionExecute
        Arguments = $actionArguments + ' --duplicate-action'
        WorkingDirectory = $actionWorkdir
    }
}

$principal = [pscustomobject]@{
    UserId = $sid
    LogonType = 'Interactive'
    RunLevel = 'Limited'
    GroupId = ''
    DisplayName = ''
    Id = 'Author'
}

$trigger1 = [pscustomobject]@{
    Id = 'LogonTrigger'
    Enabled = $true
    StartBoundary = '2026-01-01T00:00:00'
    EndBoundary = ''
}
$trigger2 = [pscustomobject]@{
    Id = 'BootTrigger'
    Enabled = $true
    Delay = 'PT12S'
    RepetitionInterval = 'PT10M'
}
$settings = [pscustomobject]@{
    MultipleInstances = 'IgnoreNew'
    ExecutionTimeLimit = 'PT0S'
    DisallowStartIfOnBatteries = $false
    StopIfGoingOnBatteries = $false
    AllowHardTerminate = $true
    StartWhenAvailable = $true
    RunOnlyIfNetworkAvailable = $false
    IdleSettings = [pscustomobject]@{ StopOnIdleEnd = $false; RestartOnIdle = $false }
    RestartCount = 3
    RestartInterval = 'PT1M'
}
$global:FixtureTask = [pscustomobject]@{
    TaskName = $taskName
    TaskPath = $taskPath
    Description = $description
    Actions = $actions
    Principal = $principal
    Triggers = @($trigger1, $trigger2)
    Settings = $settings
    State = 'Ready'
}

$xmlEscape = [Security.SecurityElement]
$descriptionXml = $xmlEscape::Escape($description)
$sidXml = $xmlEscape::Escape($sid)
$argumentsXml = $xmlEscape::Escape($actionArguments)
$commandXml = $xmlEscape::Escape($actionExecute)
$workdirXml = $xmlEscape::Escape($actionWorkdir)
$taskPathXml = $xmlEscape::Escape($taskPath)
$extraActionXml = ''
if ($env:FIXTURE_ACTION_COUNT_MODE -eq 'two') {
    $extraActionXml = @"
    <Exec>
      <Command>$commandXml</Command>
      <Arguments>$argumentsXml --duplicate-action</Arguments>
      <WorkingDirectory>$workdirXml</WorkingDirectory>
    </Exec>
"@
}
$global:CurrentXml = @"
<?xml version="1.0" encoding="UTF-8"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>$descriptionXml</Description>
    <URI>$taskPathXml$taskName</URI>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$sidXml</UserId>
    </LogonTrigger>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT12S</Delay>
      <Repetition>
        <Interval>PT10M</Interval>
        <Duration>PT1H</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$sidXml</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$commandXml</Command>
      <Arguments>$argumentsXml</Arguments>
      <WorkingDirectory>$workdirXml</WorkingDirectory>
    </Exec>
$extraActionXml
  </Actions>
</Task>
"@
if ($env:FIXTURE_XML_UTF16 -eq '1') {
    $global:CurrentXml = $global:CurrentXml.Replace('encoding="UTF-8"', 'encoding="UTF-16"')
}
[System.IO.File]::WriteAllText($env:FIXTURE_XML_PATH, $global:CurrentXml, (New-Object System.Text.UTF8Encoding($false)))
$script:OriginalXml = $global:CurrentXml

function global:Get-ScheduledTask {
    param(
        [string]$TaskName,
        [string]$TaskPath,
        [Parameter(ValueFromRemainingArguments = $true)]$Rest
    )
    Write-FixtureLog 'Get-ScheduledTask' ([ordered]@{ taskName = $TaskName; taskPath = $TaskPath })
    if ($env:FIXTURE_TASK_MISSING -eq '1') { return $null }
    $inventory = @($global:FixtureTask)
    if ($env:FIXTURE_DUPLICATE_TASK -eq '1') {
        $inventory += [pscustomobject]@{ TaskName = $TaskName; TaskPath = '\Other\'; Description = 'Unrelated same-name task' }
        if ($TaskPath) { $inventory = @($inventory | Where-Object { $_.TaskPath -eq $TaskPath }) }
    }
    return $inventory
}

function global:Export-ScheduledTask {
    param(
        [string]$TaskName,
        [string]$TaskPath,
        [Parameter(ValueFromRemainingArguments = $true)]$Rest
    )
    $global:ExportCount += 1
    Write-FixtureLog 'Export-ScheduledTask' ([ordered]@{ taskName = $TaskName; taskPath = $TaskPath; count = $global:ExportCount })
    if ([string]$global:ExportCount -eq $env:FIXTURE_MUTATE_LAUNCHER_EXPORT_AT) {
        [IO.File]::AppendAllText($env:FIXTURE_LAUNCHER_PATH, "`n# launcher mutation during export`n")
        Write-FixtureLog 'launcher_mutated' ([ordered]@{ exportCount = $global:ExportCount })
    }
    $mutateAt = 0
    [void][int]::TryParse([string]$env:FIXTURE_MUTATE_XML_EXPORT_AT, [ref]$mutateAt)
    if ($mutateAt -gt 0 -and $global:ExportCount -eq $mutateAt) {
        $global:CurrentXml = $global:CurrentXml.Replace('</Task>', "  <!-- fixture-xml-mutation -->`n</Task>")
        if (-not [string]::IsNullOrEmpty($env:FIXTURE_LIVE_XML)) {
            [System.IO.File]::WriteAllText($env:FIXTURE_LIVE_XML, $global:CurrentXml, (New-Object System.Text.UTF8Encoding($false)))
        }
        Write-FixtureLog 'xml_mutated' ([ordered]@{ exportCount = $global:ExportCount })
    }
    Write-Output $global:CurrentXml
}

function global:Start-ScheduledTask {
    param(
        [string]$TaskName,
        [string]$TaskPath,
        [Parameter(ValueFromRemainingArguments = $true)]$Rest
    )
    Write-FixtureLog 'Start-ScheduledTask' ([ordered]@{ taskName = $TaskName; taskPath = $TaskPath })
    if ($env:FIXTURE_START_FAIL -eq '1') { throw 'fixture start failure' }
}

function global:Stop-ScheduledTask {
    param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
    Write-FixtureLog 'Stop-ScheduledTask' $Rest
    throw 'mutating task cmdlet is unreachable in fixture: Stop-ScheduledTask'
}

function global:Set-ScheduledTask {
    param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
    Write-FixtureLog 'Set-ScheduledTask' $Rest
    throw 'mutating task cmdlet is unreachable in fixture: Set-ScheduledTask'
}

function global:Register-ScheduledTask {
    param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
    Write-FixtureLog 'Register-ScheduledTask' $Rest
    throw 'mutating task cmdlet is unreachable in fixture: Register-ScheduledTask'
}

function global:Unregister-ScheduledTask {
    param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
    Write-FixtureLog 'Unregister-ScheduledTask' $Rest
    throw 'mutating task cmdlet is unreachable in fixture: Unregister-ScheduledTask'
}

function global:Enable-ScheduledTask {
    param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
    Write-FixtureLog 'Enable-ScheduledTask' $Rest
    throw 'mutating task cmdlet is unreachable in fixture: Enable-ScheduledTask'
}

function global:Disable-ScheduledTask {
    param([Parameter(ValueFromRemainingArguments = $true)]$Rest)
    Write-FixtureLog 'Disable-ScheduledTask' $Rest
    throw 'mutating task cmdlet is unreachable in fixture: Disable-ScheduledTask'
}

$resolvedGet = Get-Command Get-ScheduledTask -ErrorAction Stop
$resolvedExport = Get-Command Export-ScheduledTask -ErrorAction Stop
$resolvedStart = Get-Command Start-ScheduledTask -ErrorAction Stop
if ($resolvedGet.CommandType -ne 'Function' -or $resolvedExport.CommandType -ne 'Function' -or $resolvedStart.CommandType -ne 'Function') {
    throw 'Fixture task cmdlets are not fully stub-shadowed.'
}
if (Get-Module -Name ScheduledTasks -ErrorAction SilentlyContinue) {
    throw 'ScheduledTasks module must not be loaded in fixture.'
}
Write-FixtureLog 'harness_start' ([ordered]@{
    updater = $Updater
    node = $Node
    workspace = $Workspace
    package = $Package
    config = $Config
    python = $Python
    checkOnly = [bool]$CheckOnly
    principalSid = $sid
    powershellVersion = $PSVersionTable.PSVersion.ToString()
})

try {
    $callArgs = @{
        Node = $Node
        Workspace = $Workspace
        Package = $Package
        Config = $Config
        Python = $Python
    }
    if ($CheckOnly) { $callArgs['CheckOnly'] = $true }
    Write-FixtureLog 'call_args' $callArgs
    & $Updater @callArgs
    $exitCode = if ($LASTEXITCODE -is [int]) { $LASTEXITCODE } else { 0 }
    Write-FixtureLog 'harness_end' ([ordered]@{ exitCode = $exitCode })
    exit $exitCode
}
catch {
    Write-FixtureLog 'harness_exception' ([ordered]@{ message = $_.Exception.Message; position = $_.InvocationInfo.PositionMessage; scriptStack = $_.ScriptStackTrace })
    [Console]::Error.WriteLine($_.Exception.ToString())
    exit 1
}
