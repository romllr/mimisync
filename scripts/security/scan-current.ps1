$ErrorActionPreference = 'Stop'
$report = [ordered]@{
    sourceCommit = $env:GITHUB_SHA
    runId = $env:GITHUB_RUN_ID
    startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    status = 'not_run'
    executesApplication = $false
    distributionAuthorized = $false
    engine = $null
    protectionEnableError = $null
    cloudSettings = $null
    files = @()
    detections = @()
    threats = @()
    error = $null
}
$exitCode = 1
try {
    # Enable protection if the hosted machine permits it. Never weaken policies.
    try { Set-MpPreference -DisableRealtimeMonitoring $false } catch {
        $report.protectionEnableError = $_.Exception.Message
    }
    Update-MpSignature
    $status = Get-MpComputerStatus
    $report.engine = $status | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AMProductVersion,AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,DefenderSignaturesOutOfDate
    $report.cloudSettings = Get-MpPreference | Select-Object MAPSReporting,SubmitSamplesConsent,DisableBlockAtFirstSeen,CloudBlockLevel
    if (-not $status.AntivirusEnabled -or -not $status.AMServiceEnabled -or $status.DefenderSignaturesOutOfDate) {
        throw 'Defender is unavailable or signatures are stale.'
    }
    $binary = 'src-tauri/target/release/mimisync.exe'
    $installers = @(Get-ChildItem 'src-tauri/target/release/bundle' -Recurse -Filter '*-setup.exe' -ErrorAction SilentlyContinue)
    if (-not (Test-Path $binary) -or $installers.Count -eq 0) {
        throw 'Native build did not produce both the application and installer. No successful package validation.'
    }
    New-Item -ItemType Directory -Path scan-input -Force | Out-Null
    Copy-Item $binary scan-input/
    $installers | Copy-Item -Destination scan-input/
    $root = (Resolve-Path scan-input).Path
    foreach ($file in Get-ChildItem $root -File) {
        $report.files += [ordered]@{
            name = $file.Name
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
            bytes = $file.Length
            authenticode = (Get-AuthenticodeSignature -LiteralPath $file.FullName).Status.ToString()
        }
        Set-Content -LiteralPath $file.FullName -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3"
    }
    Start-MpScan -ScanType CustomScan -ScanPath $root
    $report.detections = @(Get-MpThreatDetection | Where-Object { $_.Resources -match [regex]::Escape($root) } | Select-Object ThreatID,ThreatStatusID,ActionSuccess,Resources)
    $ids = @($report.detections | ForEach-Object { $_.ThreatID })
    $report.threats = @(Get-MpThreat | Where-Object { $_.ThreatID -in $ids } | Select-Object ThreatID,ThreatName,SeverityID,CategoryID)
    $missing = @($report.files | Where-Object { -not (Test-Path (Join-Path $root $_.name)) })
    if ($report.detections.Count -gt 0 -or $missing.Count -gt 0) {
        $report.status = 'threat_detected_or_sample_removed'
        throw 'Defender detected or removed a sample. Distribution remains suspended.'
    }
    if (-not $status.RealTimeProtectionEnabled) {
        $report.status = 'on_demand_no_detections_realtime_unavailable'
        throw 'On-demand scan reported no detections, but real-time download protection could not be reproduced. This is not clearance for distribution.'
    }
    $report.status = 'no_detections_on_this_runner_requires_review'
    $exitCode = 0
} catch {
    $report.error = $_.Exception.Message
    if ($report.status -eq 'not_run') { $report.status = 'validation_incomplete' }
    Write-Warning $report.error
} finally {
    $report.completedUtc = (Get-Date).ToUniversalTime().ToString('o')
    New-Item -ItemType Directory -Path scan-report -Force | Out-Null
    $report | ConvertTo-Json -Depth 8 | Set-Content scan-report/current.json -Encoding utf8
    Get-Content scan-report/current.json
}
exit $exitCode
