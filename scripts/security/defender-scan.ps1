param(
    [Parameter(Mandatory=$true)][string]$Root,
    [Parameter(Mandatory=$true)][string]$Report
)
$ErrorActionPreference = 'Stop'
$reportData = [ordered]@{
    startedUtc = (Get-Date).ToUniversalTime().ToString('o')
    status = 'not_run'
    executesApplication = $false
    engine = $null
    files = @()
    detections = @()
    threats = @()
    error = $null
}
$exitCode = 1
try {
    $Root = (Resolve-Path $Root).Path
    $status = Get-MpComputerStatus
    $reportData.engine = $status | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AMProductVersion,AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,AntivirusSignatureAge,DefenderSignaturesOutOfDate
    if (-not $status.AntivirusEnabled -or -not $status.AMServiceEnabled) {
        $reportData.status = 'scanner_unavailable'
        throw 'Microsoft Defender is not enabled on this runner. No malware-free result can be claimed.'
    }
    Update-MpSignature
    $status = Get-MpComputerStatus
    $reportData.engine = $status | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AMProductVersion,AMEngineVersion,AntivirusSignatureVersion,AntivirusSignatureLastUpdated,AntivirusSignatureAge,DefenderSignaturesOutOfDate
    if ($status.DefenderSignaturesOutOfDate) { throw 'Defender signatures remain out of date.' }
    $zip = Join-Path $Root 'Mimisync-0.2.0-windows-x64-test.zip'
    if (-not (Test-Path $zip)) { throw 'The reported ZIP is missing. It may have been quarantined before this scan.' }
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash.ToLowerInvariant()
    if ($hash -ne '2cc6338ba6efaf0dffd48c44237d8d7c259dd59bee54c881bf01cbf504a3d861') {
        throw "The ZIP does not match the reported sample: $hash"
    }
    Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $Root 'extracted') -Force
    $files = Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object { $_.Extension -in @('.zip','.exe','.dll','.ps1','.cmd','.bat','.sh') }
    foreach ($file in $files) {
        $signature = if ($file.Extension -in @('.exe','.dll','.ps1')) { (Get-AuthenticodeSignature -LiteralPath $file.FullName).Status.ToString() } else { 'not_applicable' }
        $reportData.files += [ordered]@{
            path = $file.FullName.Substring($Root.Length)
            sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName).Hash.ToLowerInvariant()
            bytes = $file.Length
            authenticode = $signature
        }
    }
    Start-MpScan -ScanType CustomScan -ScanPath $Root
    $detections = @(Get-MpThreatDetection | Where-Object { $_.Resources -match [regex]::Escape($Root) })
    $reportData.detections = @($detections | Select-Object ThreatID,ThreatStatusID,ActionSuccess,InitialDetectionTime,LastThreatStatusChangeTime,Resources)
    if ($detections.Count -gt 0 -or -not (Test-Path $zip)) {
        $reportData.status = 'threat_detected'
        throw 'Defender reported a detection or removed the sample. Downloads must remain suspended.'
    }
    $reportData.status = 'no_detections_reported_by_this_runner'
    $exitCode = 0
} catch {
    $reportData.error = $_.Exception.Message
    if ($reportData.status -eq 'not_run') { $reportData.status = 'scan_incomplete' }
    try {
        $reportData.detections = @(Get-MpThreatDetection | Where-Object { $_.Resources -match [regex]::Escape($Root) } | Select-Object ThreatID,ThreatStatusID,ActionSuccess,InitialDetectionTime,LastThreatStatusChangeTime,Resources)
    } catch { }
    Write-Warning $reportData.error
} finally {
    try {
        $ids = @($reportData.detections | ForEach-Object { $_.ThreatID })
        $reportData.threats = @(Get-MpThreat | Where-Object { $_.ThreatID -in $ids } | Select-Object ThreatID,ThreatName,SeverityID,CategoryID)
    } catch { }
    $reportData.completedUtc = (Get-Date).ToUniversalTime().ToString('o')
    $directory = Split-Path -Parent $Report
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
    $reportData | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Report -Encoding utf8
    Get-Content -LiteralPath $Report
}
exit $exitCode
