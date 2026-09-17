# Read-only process/queue checks; writes a dated audit in this catalog only.
$ErrorActionPreference = 'Stop'
$healthRoot = 'C:\Users\alsw0\Desktop\project1'
$healthCatalog = Join-Path $healthRoot 'ontology-prototype\domestic-catalog'
$healthRuntime = Join-Path $healthRoot '.local\domestic-catalog'
$healthState = Get-Content -LiteralPath (Join-Path $healthRuntime 'workers.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$healthPolicy = Get-Content -LiteralPath (Join-Path $healthCatalog 'completion-policy.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$healthStoppedByPolicy = $healthPolicy.bulk_collection_enabled -eq $false -and $healthPolicy.prototype_metadata_sufficient -eq $true
$healthProcesses = @(Get-CimInstance Win32_Process)
$healthWorkers = @()
foreach ($healthWorker in $healthState.workers) {
    $healthScript = [IO.Path]::GetFullPath($healthWorker.script)
    if (-not $healthScript.StartsWith($healthRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Worker path outside this project.' }
    $healthMatches = @($healthProcesses | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Contains($healthScript) })
    $healthReport = $null
    if ($healthWorker.name -ne 'indexer') {
        $healthReportName = if ($healthWorker.name -eq 'data-go-file') { 'definition-collection-report.json' } else { $healthWorker.name+'-collection-report.json' }
        $healthReport = Get-Content -LiteralPath (Join-Path $healthCatalog $healthReportName) -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    $healthExpected = (-not $healthStoppedByPolicy) -and (($healthWorker.name -eq 'indexer') -or (-not $healthReport.queue_exhausted))
    $healthErrorBytes = $null
    if ($healthWorker.log_prefix) {
        $healthErrorPath = Join-Path $healthRuntime ($healthWorker.log_prefix+'.stderr.log')
        if (Test-Path -LiteralPath $healthErrorPath) { $healthErrorBytes = (Get-Item -LiteralPath $healthErrorPath).Length }
    }
    $healthWorkers += @{
        name=$healthWorker.name; queue_exhausted=$healthReport.queue_exhausted; expected_active=$healthExpected
        actual_count=$healthMatches.Count; pids=@($healthMatches | ForEach-Object {$_.ProcessId})
        command_lines=@($healthMatches | ForEach-Object {$_.CommandLine}); current_error_log_bytes=$healthErrorBytes
        progress_generated_at=$healthReport.generated_at; processed=$healthReport.processed; target_count=$healthReport.target_count
        passed=($healthMatches.Count -eq [int]$healthExpected -and (-not $healthExpected -or $healthErrorBytes -eq 0))
    }
}
# The finite FISIS queue has an explicit state file and no recurring supervisor.
$healthFisisStatePath = Join-Path $healthRuntime 'fisis-worker.json'
if (Test-Path -LiteralPath $healthFisisStatePath) {
    $healthFisisState = Get-Content -LiteralPath $healthFisisStatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $healthFisisScript = [IO.Path]::GetFullPath((Join-Path $healthCatalog 'collect_fisis.py'))
    if ([IO.Path]::GetFullPath($healthFisisState.script) -ne $healthFisisScript) { throw 'Unexpected finite FISIS worker path.' }
    $healthFisisMatches = @($healthProcesses | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Contains($healthFisisScript) })
    $healthFisisReport = Get-Content -LiteralPath (Join-Path $healthCatalog 'fisis-collection-report.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $healthFisisExpected = (-not $healthStoppedByPolicy) -and (-not $healthFisisReport.queue_exhausted)
    $healthFisisErrorPath = Join-Path $healthRuntime ($healthFisisState.log_prefix+'.stderr.log')
    $healthFisisErrorBytes = if (Test-Path -LiteralPath $healthFisisErrorPath) { (Get-Item -LiteralPath $healthFisisErrorPath).Length } else { $null }
    $healthWorkers += @{
        name='fisis'; supervised=$false; queue_exhausted=$healthFisisReport.queue_exhausted; expected_active=$healthFisisExpected
        actual_count=$healthFisisMatches.Count; pids=@($healthFisisMatches | ForEach-Object {$_.ProcessId})
        command_lines=@($healthFisisMatches | ForEach-Object {$_.CommandLine}); current_error_log_bytes=$healthFisisErrorBytes
        progress_generated_at=$healthFisisReport.generated_at; processed=$healthFisisReport.processed; target_count=$healthFisisReport.target_count
        passed=($healthFisisMatches.Count -eq [int]$healthFisisExpected -and (-not $healthFisisExpected -or $healthFisisErrorBytes -eq 0))
    }
}
$healthSupervisorPath = Join-Path $healthCatalog 'supervise.ps1'
$healthSupervisors = @($healthProcesses | Where-Object { $_.Name -in @('pwsh.exe','powershell.exe') -and $_.CommandLine -match ('-File\s+"?'+[regex]::Escape($healthSupervisorPath)+'"?(?:\s|$)') })
$healthBrowserPath = Join-Path $healthCatalog 'browse.py'
$healthBrowsers = @($healthProcesses | Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -and $_.CommandLine.Contains($healthBrowserPath) })
$healthStopFiles = @(Get-ChildItem -LiteralPath $healthRuntime -Filter '*.stop' -File | ForEach-Object {$_.Name})
$healthExpectedStopFiles = if ($healthStoppedByPolicy) { @($healthState.workers | ForEach-Object {$_.name+'.stop'}) + @('supervisor.stop') } else { @() }
$healthStopsMatch = @($healthStopFiles | Where-Object {$_ -notin $healthExpectedStopFiles}).Count -eq 0 -and @($healthExpectedStopFiles | Where-Object {$_ -notin $healthStopFiles}).Count -eq 0
$healthCoverage = Invoke-RestMethod -Uri 'http://127.0.0.1:8766/api/coverage' -TimeoutSec 20
$healthReport = @{
    generated_at=[DateTimeOffset]::UtcNow.ToString('o'); workers=$healthWorkers
    supervisor_pids=@($healthSupervisors | ForEach-Object {$_.ProcessId}); browser_pids=@($healthBrowsers | ForEach-Object {$_.ProcessId})
    stop_files=$healthStopFiles; http_coverage_generated_at=$healthCoverage.generated_at
    completed_unregistered_finite_queues=@('hrfco','expressway-files')
    intentionally_stopped_for_prototype_sufficiency=$healthStoppedByPolicy
    passed=(@($healthWorkers | Where-Object {-not $_.passed}).Count -eq 0 -and $healthSupervisors.Count -eq [int](-not $healthStoppedByPolicy) -and $healthBrowsers.Count -eq 1 -and $healthStopsMatch)
    process_existence_is_not_full_service_health=$true
}
$healthName = 'workers-'+[DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmm')+'-check.json'
[IO.File]::WriteAllText((Join-Path $healthCatalog $healthName),($healthReport | ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false))
@{report=$healthName;passed=$healthReport.passed;active=@($healthWorkers | Where-Object {$_.expected_active} | ForEach-Object {@{name=$_.name;pids=$_.pids}})} | ConvertTo-Json -Depth 5
