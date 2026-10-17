<# Read-only guards for reloading an existing node task. No task registration or restore. #>
function Test-FPGAMeshSamePath {
    param([string]$Actual, [string]$Expected)
    if (-not $Actual -or -not [IO.Path]::IsPathRooted($Actual)) { return $false }
    return [string]::Equals([IO.Path]::GetFullPath($Actual).TrimEnd('\', '/'),
        [IO.Path]::GetFullPath($Expected).TrimEnd('\', '/'), [StringComparison]::OrdinalIgnoreCase)
}

function Get-FPGAMeshTaskSnapshot {
    param([string]$Node, [string]$Workspace, [string]$Config, [string]$Python)
    $taskName = "FPGA-Mesh-Node-$Node"
    # The unchanged stop helper selects by name. Refuse same-name tasks in other
    # folders as well, so that helper cannot stop an unrelated task.
    $tasks = @(Get-ScheduledTask -TaskName $taskName -ErrorAction Stop)
    if ($tasks.Count -ne 1 -or $tasks[0].TaskName -cne $taskName -or $tasks[0].TaskPath -cne '\') {
        throw "Exactly one existing root task is required: $taskName"
    }
    $taskXml = [string](Export-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop)
    $readerSettings = New-Object System.Xml.XmlReaderSettings
    $readerSettings.DtdProcessing = [Xml.DtdProcessing]::Prohibit
    $readerSettings.XmlResolver = $null
    $reader = [Xml.XmlReader]::Create([IO.StringReader]::new($taskXml), $readerSettings)
    try {
        $definition = New-Object System.Xml.XmlDocument
        $definition.XmlResolver = $null
        $definition.Load($reader)
    } finally { $reader.Dispose() }
    if ($definition.DocumentElement.LocalName -cne 'Task' -or
        $definition.DocumentElement.NamespaceURI -cne 'http://schemas.microsoft.com/windows/2004/02/mit/task') {
        throw 'Unexpected scheduled task XML schema.'
    }
    $description = [string]$definition.Task.RegistrationInfo.Description
    if ($description -cnotlike "FPGA Mesh $Node controller*") { throw "Scheduled task is not owned by node $Node." }
    $principals = @($definition.Task.Principals.Principal)
    if ($principals.Count -ne 1 -or -not $principals[0].UserId -or $principals[0].GroupId) {
        throw 'Existing task requires a single user principal.'
    }
    $userId = [string]$principals[0].UserId
    $sid = if ($userId -match '^S-1-') {
        [Security.Principal.SecurityIdentifier]::new($userId).Value
    } else {
        [Security.Principal.NTAccount]::new($userId).Translate([Security.Principal.SecurityIdentifier]).Value
    }
    if ($sid -cne [Security.Principal.WindowsIdentity]::GetCurrent().User.Value) {
        throw 'Scheduled task principal differs from the updating Windows identity.'
    }
    $actions = @($definition.Task.Actions.ChildNodes | Where-Object { $_.NodeType -eq [Xml.XmlNodeType]::Element })
    if ($actions.Count -ne 1 -or $actions[0].LocalName -cne 'Exec') { throw 'Exactly one existing Exec action is required.' }
    $action = $actions[0]
    if (-not (Test-FPGAMeshSamePath $action.Command $Python) -or
        -not (Test-FPGAMeshSamePath $action.WorkingDirectory $Workspace)) {
        throw 'Existing task Python or working directory mismatch.'
    }
    $arguments = [string]$action.Arguments
    # Task Scheduler runs an executable, not a shell. Accept only unambiguous argv tokens.
    if ($arguments -notmatch '^\s*(?:(?:"[^"]*"|[^\s"]+)(?:\s+|$))*$') { throw 'Unsupported task argument quoting.' }
    $argv = @([regex]::Matches($arguments, '"[^"]*"|[^\s"]+') | ForEach-Object { $_.Value.Trim('"') })
    $launcherPath = $null
    $launcherBytes = $null
    $offset = 0
    if ($argv.Count -ge 2 -and $argv[0] -ceq '-m' -and $argv[1] -ceq 'fpga_mesh.supervisor') {
        $offset = 2
    } elseif ($argv.Count -ge 1) {
        $launcherPath = Join-Path $Workspace ('.local/deployment/node-{0}/launch-node-{0}.py' -f $Node.ToLowerInvariant())
        if (-not (Test-FPGAMeshSamePath $argv[0] $launcherPath)) { throw 'Existing task launcher path mismatch.' }
        $launcherBytes = [IO.File]::ReadAllBytes($launcherPath)
        $offset = 1
    } else { throw 'Missing task arguments.' }
    $nodeDir = Split-Path -Parent $Config
    $expected = @{ '--config' = $Config; '--ready-file' = (Join-Path $nodeDir 'ready.json'); '--log-file' = (Join-Path $nodeDir 'service.log') }
    if ($argv.Count -ne ($offset + 6)) { throw 'Unexpected task argument count.' }
    $seen = @{}
    for ($i = $offset; $i -lt $argv.Count; $i += 2) {
        $key = $argv[$i]
        if ($key -cnotin @('--config', '--ready-file', '--log-file') -or $seen.ContainsKey($key) -or
            -not (Test-FPGAMeshSamePath $argv[$i + 1] $expected[$key])) { throw "Task argument mismatch: $key" }
        $seen[$key] = $true
    }
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $xmlHash = ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($taskXml)))).Replace('-', '').ToLowerInvariant()
        $launcherHash = if ($null -ne $launcherBytes) {
            ([BitConverter]::ToString($sha.ComputeHash($launcherBytes))).Replace('-', '').ToLowerInvariant()
        } else { $null }
    } finally { $sha.Dispose() }
    [pscustomobject]@{
        TaskName = $taskName; TaskPath = '\'; Node = $Node; Workspace = $Workspace; Config = $Config; Python = $Python
        Xml = $taskXml; XmlSha256 = $xmlHash; XmlHashEncoding = 'UTF-8 exported string without BOM'
        XmlDeclarationEncoding = [string]$definition.FirstChild.Encoding
        LauncherPath = $launcherPath; LauncherBytes = $launcherBytes; LauncherSha256 = $launcherHash
        Actions = $definition.Task.Actions.OuterXml; Principal = $definition.Task.Principals.OuterXml
        Triggers = $definition.Task.Triggers.OuterXml; Settings = $definition.Task.Settings.OuterXml; Description = $description
    }
}

function Assert-FPGAMeshTaskUnchanged {
    param($Snapshot, [string]$Boundary)
    $now = Get-FPGAMeshTaskSnapshot -Node $Snapshot.Node -Workspace $Snapshot.Workspace -Config $Snapshot.Config -Python $Snapshot.Python
    if ($now.Xml -cne $Snapshot.Xml -or $now.LauncherSha256 -cne $Snapshot.LauncherSha256) {
        throw "Existing task or launcher changed at $Boundary; preserve current evidence and reconcile. No task definition will be restored."
    }
}

function Save-FPGAMeshTaskSnapshot {
    param($Snapshot, [string]$Workspace)
    $directory = Join-Path $Workspace ('.local/update-preservation/' + [Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $directory -ErrorAction Stop | Out-Null
    $encoding = [Text.UTF8Encoding]::new($false)
    if ($Snapshot.XmlDeclarationEncoding -and $Snapshot.XmlDeclarationEncoding -ine 'UTF-8') {
        $encoding = [Text.Encoding]::GetEncoding($Snapshot.XmlDeclarationEncoding)
    }
    [IO.File]::WriteAllText((Join-Path $directory 'task-before.xml'), $Snapshot.Xml, $encoding)
    if ($null -ne $Snapshot.LauncherBytes) { [IO.File]::WriteAllBytes((Join-Path $directory 'launcher-before.bin'), $Snapshot.LauncherBytes) }
    $Snapshot | Select-Object TaskName, TaskPath, Node, Workspace, Config, Python, XmlSha256, XmlHashEncoding, XmlDeclarationEncoding, LauncherPath, LauncherSha256,
        Actions, Principal, Triggers, Settings, Description | ConvertTo-Json -Depth 10 |
        Set-Content -LiteralPath (Join-Path $directory 'snapshot.json') -Encoding UTF8
    return $directory
}

function Assert-FPGAMeshRouting {
    param([string]$Workspace, [string]$Python, [string]$ControlFile)
    # Validate only. Neither the MCP configuration nor native role files are rewritten.
    $check = @'
import pathlib, sys, tomllib
root, python, control = sys.argv[1:]
def same(actual, expected):
    return isinstance(actual, str) and pathlib.Path(actual).is_absolute() and pathlib.Path(actual).resolve() == pathlib.Path(expected).resolve()
def require(condition, message):
    if not condition:
        raise ValueError(message)
try:
    path = pathlib.Path(root) / '.codex' / 'config.toml'
    bridge = tomllib.loads(path.read_text(encoding='utf-8-sig'))['mcp_servers']['fpga_mesh']
    env = bridge['env']
    require(same(bridge['command'], python), 'Python mismatch')
    require(bridge['args'] == ['-m', 'fpga_mesh.project_mcp'], 'bridge args mismatch')
    require(same(env['PYTHONPATH'], root), 'root mismatch')
    require(same(env['FPGA_MAIN_CONTROL_FILE'], control), 'control file mismatch')
    require(bridge.get('enabled', True) is True, 'bridge disabled')
    require(bridge.get('startup_timeout_sec') == 20 and bridge.get('tool_timeout_sec') == 3600, 'bridge timeouts need review')
except Exception as exc:
    print('Existing routing requires separate review: ' + str(exc), file=sys.stderr)
    sys.exit(1)
'@
    & $Python -c $check $Workspace $Python $ControlFile
    if ($LASTEXITCODE -ne 0) { throw 'Existing routing validation failed; configuration and roles were not rewritten.' }
}
