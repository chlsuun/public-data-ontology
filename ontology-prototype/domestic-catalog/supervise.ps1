param([switch]$Once)
$ErrorActionPreference = 'Stop'
$taskRoot = 'C:\Users\alsw0\Desktop\project1'
$taskFolder = Join-Path $taskRoot '.local\domestic-catalog'
$taskStatePath = Join-Path $taskFolder 'workers.json'
$taskPolicyPath = Join-Path $taskRoot 'ontology-prototype\domestic-catalog\completion-policy.json'
if (Test-Path -LiteralPath $taskPolicyPath) {
    $taskPolicy = Get-Content -LiteralPath $taskPolicyPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($taskPolicy.bulk_collection_enabled -eq $false) {
        Write-Output 'Bulk collection intentionally stopped after prototype sufficiency assessment; no workers restarted.'
        return
    }
}
if (Test-Path -LiteralPath (Join-Path $taskFolder 'supervisor.stop')) {
    Write-Output 'Supervisor stop marker present; no workers restarted.'
    return
}
$taskPython = (Get-Command python).Source
$taskAllowedScripts = @('collect_definitions.py','collect_kosis.py','collect_seoul.py','collect_seoul_statistics.py','collect_data_go_api.py','collect_data_go_std.py','collect_assembly.py','collect_culture.py','collect_culture_files.py','collect_ecos.py','collect_yeongdeungpo.py','collect_incheon.py','collect_daegu.py','collect_mafra.py','collect_mafra_previews.py','collect_busan.py','collect_chungnam.py','collect_jeonbuk.py','collect_expressway.py','index_progress.py')
do {
    try {
        $taskState = Get-Content -LiteralPath $taskStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $taskProcesses = @(Get-CimInstance Win32_Process -Filter "Name = 'python.exe'")
        $taskChanged = $false
        foreach ($taskWorker in $taskState.workers) {
            $taskScript = [IO.Path]::GetFullPath($taskWorker.script)
            if (-not $taskScript.StartsWith($taskRoot + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Worker script outside this project.' }
            if ([IO.Path]::GetFileName($taskScript) -notin $taskAllowedScripts) { throw 'Unknown worker script.' }
            $taskActive = @($taskProcesses | Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($taskScript,[StringComparison]::OrdinalIgnoreCase) -ge 0 })
            if ($taskActive.Count -gt 0) {
                if ($taskWorker.pid -ne $taskActive[0].ProcessId) { $taskWorker.pid = $taskActive[0].ProcessId; $taskChanged = $true }
                continue
            }
            if ($taskWorker.name -ne 'indexer') {
                $taskReportName = if ($taskWorker.name -eq 'data-go-file') { 'definition-collection-report.json' } else { $taskWorker.name + '-collection-report.json' }
                $taskReportPath = Join-Path (Split-Path -Parent $taskScript) $taskReportName
                if (Test-Path -LiteralPath $taskReportPath) {
                    $taskReport = Get-Content -LiteralPath $taskReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ($taskReport.queue_exhausted -eq $true) { continue }
                }
            }
            if (Test-Path -LiteralPath (Join-Path $taskFolder ($taskWorker.name + '.stop'))) { continue }
            if ($taskWorker.not_before_utc -and [DateTimeOffset]::Parse($taskWorker.not_before_utc) -gt [DateTimeOffset]::UtcNow) { continue }
            $taskStamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmss')
            $taskPrefix = $taskWorker.name + '-supervised-' + $taskStamp
            $taskArgs = @('-X','utf8',('"' + $taskScript + '"')) + @($taskWorker.arguments)
            $taskNew = Start-Process -FilePath $taskPython -ArgumentList $taskArgs -WorkingDirectory $taskRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskFolder ($taskPrefix + '.stdout.log')) -RedirectStandardError (Join-Path $taskFolder ($taskPrefix + '.stderr.log')) -PassThru
            $taskWorker.pid = $taskNew.Id
            $taskWorker.log_prefix = $taskPrefix
            $taskWorker | Add-Member -NotePropertyName not_before_utc -NotePropertyValue ([DateTimeOffset]::UtcNow.AddMinutes(5).ToString('o')) -Force
            $taskChanged = $true
            Write-Output ($taskStamp + ' restarted ' + $taskWorker.name + ' PID=' + $taskNew.Id)
        }
        if ($taskChanged) {
            $taskState.generated_at = [DateTimeOffset]::UtcNow.ToString('o')
            $taskTemporary = $taskStatePath + '.supervisor.tmp'
            [IO.File]::WriteAllText($taskTemporary,($taskState | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
            Move-Item -LiteralPath $taskTemporary -Destination $taskStatePath -Force
        }
    } catch { Write-Output ([DateTimeOffset]::UtcNow.ToString('o') + ' supervisor error: ' + $_.Exception.Message) }
    if ($Once) { break }
    Start-Sleep -Seconds 60
} while (-not (Test-Path -LiteralPath (Join-Path $taskFolder 'supervisor.stop')))
