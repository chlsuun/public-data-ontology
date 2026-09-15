# Resume this project's public metadata workers without creating another schedule.
$ErrorActionPreference = 'Stop'
$resumeRoot = 'C:\Users\alsw0\Desktop\project1'
$resumeFolder = Join-Path $resumeRoot '.local\domestic-catalog'
$resumeCatalog = Join-Path $resumeRoot 'ontology-prototype\domestic-catalog'
$resumePolicy = Get-Content -LiteralPath (Join-Path $resumeCatalog 'completion-policy.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($resumePolicy.bulk_collection_enabled -eq $false) {
    Write-Output 'Bulk collection is intentionally stopped. Preserve checkpoints; start browse.py separately if only the viewer is needed.'
    return
}
$resumeStatePath = Join-Path $resumeFolder 'workers.json'
$resumePython = (Get-Command python).Source
$resumeSupervisorScript = Join-Path $resumeCatalog 'supervise.ps1'
$resumeBrowserScript = Join-Path $resumeCatalog 'browse.py'
$resumeStamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmss')
$resumeSupervisors = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('pwsh.exe','powershell.exe') -and $_.CommandLine -and
    $_.CommandLine -match ('-File\s+"?' + [regex]::Escape($resumeSupervisorScript) + '"?(?:\s|$)')
})
if ($resumeSupervisors.Count -gt 1) { throw 'Multiple matching supervisors require review.' }
if ((Test-Path -LiteralPath (Join-Path $resumeFolder 'supervisor.stop'))) { throw 'Supervisor stop marker present; preserve it for review.' }
if ($resumeSupervisors.Count -eq 0) { & $resumeSupervisorScript -Once }
$resumeBrowsers = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.CommandLine -and $_.CommandLine.Contains($resumeBrowserScript)
})
if ($resumeBrowsers.Count -gt 1) { throw 'Multiple matching browsers require review.' }
if ($resumeBrowsers.Count -eq 0) {
    if (Get-NetTCPConnection -LocalPort 8766 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8766 belongs to an unverified process.' }
    $resumeBrowser = Start-Process -FilePath $resumePython -ArgumentList @('-X','utf8','-u',('"'+$resumeBrowserScript+'"'),'--port','8766') -WorkingDirectory $resumeRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $resumeFolder ('browser-'+$resumeStamp+'.stdout.log')) -RedirectStandardError (Join-Path $resumeFolder ('browser-'+$resumeStamp+'.stderr.log')) -PassThru
    $resumeBrowserId = $resumeBrowser.Id
} else { $resumeBrowserId = $resumeBrowsers[0].ProcessId }
if ($resumeSupervisors.Count -eq 0) {
    $resumeShell = 'C:\Users\alsw0\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
    $resumeSupervisor = Start-Process -FilePath $resumeShell -ArgumentList @('-NoProfile','-File',('"'+$resumeSupervisorScript+'"')) -WorkingDirectory $resumeRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $resumeFolder ('supervisor-'+$resumeStamp+'.stdout.log')) -RedirectStandardError (Join-Path $resumeFolder ('supervisor-'+$resumeStamp+'.stderr.log')) -PassThru
    $resumeSupervisorId = $resumeSupervisor.Id
} else { $resumeSupervisorId = $resumeSupervisors[0].ProcessId }
$resumeState = Get-Content -LiteralPath $resumeStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
$resumeState.supervisor_pid = $resumeSupervisorId
$resumeState.browser_pid = $resumeBrowserId
$resumeTemporary = Join-Path $resumeFolder ('workers.resume.'+$PID+'.tmp')
[IO.File]::WriteAllText($resumeTemporary,($resumeState | ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
Move-Item -LiteralPath $resumeTemporary -Destination $resumeStatePath -Force
@{ generated_at=[DateTimeOffset]::UtcNow.ToString('o'); supervisor_pid=$resumeSupervisorId; browser_pid=$resumeBrowserId; action='resume_existing_configuration_only' } | ConvertTo-Json
