$ErrorActionPreference = 'Stop'
$tag = 'preview-0.2.0-portable.2'
$archiveName = 'Mimisync-0.2.0-preview2-windows-x64-portable.zip'
$report = [ordered]@{
    packagingCommit = $env:GITHUB_SHA
    applicationCommit = 'db86b6f1766182d14d7845acc84e74a98836a9be'
    runId = $env:GITHUB_RUN_ID
    executesApplication = $false
    status = 'not_run'
    distributionAuthorized = $false
    engine = $null
    cloudSettings = $null
    cloudValidation = $null
    files = @()
    detections = @()
    githubDownloadValidation = $null
    error = $null
}
function Scan-Checked([string]$folder) {
    $root = (Resolve-Path $folder).Path
    Start-MpScan -ScanType CustomScan -ScanPath $root
    $found = @(Get-MpThreatDetection | Where-Object { $_.Resources -match [regex]::Escape($root) })
    if ($found.Count -gt 0) {
        $report.detections += @($found | Select-Object ThreatID,ThreatStatusID,Resources)
        throw 'Defender reported a threat. Do not publish.'
    }
}
try {
    $report.cloudValidation = Get-Content scan-report/cloud.json -Raw | ConvertFrom-Json
    Update-MpSignature
    $status = Get-MpComputerStatus
    $report.engine = $status | Select-Object AMServiceEnabled,AntivirusEnabled,RealTimeProtectionEnabled,AMEngineVersion,AntivirusSignatureVersion,DefenderSignaturesOutOfDate
    $report.cloudSettings = Get-MpPreference | Select-Object MAPSReporting,SubmitSamplesConsent,DisableBlockAtFirstSeen,DisableIOAVProtection,DisableScriptScanning
    if (-not $status.RealTimeProtectionEnabled -or -not $status.AntivirusEnabled -or -not $status.AMServiceEnabled -or $status.DefenderSignaturesOutOfDate -or -not $report.cloudValidation.configured -or $report.cloudSettings.MAPSReporting -eq 0 -or $report.cloudSettings.SubmitSamplesConsent -notin @(1,3) -or $report.cloudSettings.DisableBlockAtFirstSeen -or $report.cloudSettings.DisableIOAVProtection -or $report.cloudSettings.DisableScriptScanning) { throw 'Full Defender protection could not be verified.' }
    $archive = Join-Path portable-output $archiveName
    $hash = (Get-FileHash $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    Expand-Archive -LiteralPath $archive -DestinationPath portable-check
    $executable = @(Get-ChildItem portable-check -Recurse -Filter Mimisync.exe)
    if ($executable.Count -ne 1 -or (Get-FileHash $executable[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne '3035f095f9536e472e7725e2aaaeaa50d7e9bc5d2f0299015bcb07aaa2cf8db5') { throw 'Portable executable differs from the reviewed native application.' }
    foreach ($file in @((Get-Item $archive)) + @(Get-ChildItem portable-check -Recurse -File)) {
        $report.files += [ordered]@{ name = $file.FullName.Substring((Get-Location).Path.Length + 1); sha256 = (Get-FileHash $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant(); bytes = $file.Length }
        if ($file.Extension -in @('.exe','.dll','.zip')) { Set-Content -LiteralPath $file.FullName -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3" }
    }
    Scan-Checked portable-output
    Scan-Checked portable-check
    if (-not (Test-Path $archive) -or -not (Test-Path $executable[0].FullName)) { throw 'A sample was removed during scanning.' }
    $report.status = 'scanned_no_detections_pending_delivery_verification'
    $report | ConvertTo-Json -Depth 8 | Set-Content scan-report/portable.json -Encoding utf8
    "$hash  $archiveName" | Set-Content scan-report/portable-SHA256SUMS.txt -Encoding ascii
    @"
    Versao portatil para Windows 11 x64: extraia a pasta inteira e abra Mimisync.exe. Nao requer instalar o aplicativo ou usar CMD.

    O backend ainda usa WSL2, Python, FFmpeg e checkpoints. O assistente prepara esses componentes quando necessario, podendo pedir autorizacao de administrador e reinicializacao para o WSL2. Dados ficam no perfil do Windows, fora da pasta portatil. O WebView2 Runtime normalmente ja esta presente no Windows 11.

    O executavel tem os mesmos bytes do preview 2 nativo verificado. O ZIP e os arquivos extraidos foram analisados com Defender atualizado, protecao em tempo real, de downloads/scripts e em nuvem ativas. O download do GitHub tambem e conferido antes da publicacao. Relatorio e SHA-256 acompanham esta Release.

    ZIP SHA-256: $hash

    Versao experimental, sem assinatura digital. Interface, preparacao e inferencia NVIDIA ainda precisam de testes em hardware real. O ZIP antigo bloqueado permanece retirado, sem conclusao de falso positivo. Se houver deteccao, mantenha o bloqueio, sem exclusoes ou desativacao do antivirus.
    "@ | Set-Content scan-report/portable-notes.md -Encoding utf8
    gh release create $tag $archive scan-report/portable.json scan-report/portable-SHA256SUMS.txt --repo $env:GITHUB_REPOSITORY --target $env:GITHUB_SHA --draft --prerelease --title 'Mimisync — Windows portable preview 2' --notes-file scan-report/portable-notes.md
    if ($LASTEXITCODE -ne 0) { throw 'Could not stage portable release.' }
    gh release download $tag --repo $env:GITHUB_REPOSITORY --pattern $archiveName --dir portable-delivery
    if ($LASTEXITCODE -ne 0) { throw 'Could not validate the staged GitHub download.' }
    $delivered = Join-Path portable-delivery $archiveName
    if ((Get-FileHash $delivered -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hash) { throw 'Delivered ZIP checksum mismatch.' }
    Set-Content -LiteralPath $delivered -Stream Zone.Identifier -Value "[ZoneTransfer]`r`nZoneId=3"
    Expand-Archive -LiteralPath $delivered -DestinationPath portable-delivery/extracted
    Scan-Checked portable-delivery
    if (-not (Test-Path $delivered)) { throw 'Delivered archive was removed.' }
    foreach ($file in $report.files) {
        if (-not (Test-Path $file.name) -or (Get-FileHash $file.name -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256) { throw 'Packaged file changed or was removed.' }
    }
    $report.githubDownloadValidation = [ordered]@{ sha256 = $hash; detections = 0; status = 'delivered_zip_and_extracted_files_scanned' }
    $report.status = 'no_detections_realtime_cloud_and_delivery_verified'
    $report.distributionAuthorized = $true
    $report | ConvertTo-Json -Depth 8 | Set-Content scan-report/portable.json -Encoding utf8
    gh release upload $tag scan-report/portable.json --clobber --repo $env:GITHUB_REPOSITORY
    if ($LASTEXITCODE -ne 0) { throw 'Could not preserve the delivery report.' }
    gh release edit $tag --repo $env:GITHUB_REPOSITORY --draft=false
    if ($LASTEXITCODE -ne 0) { throw 'Could not publish the validated portable release.' }
} catch {
    $report.error = $_.Exception.Message
    if ($report.status -eq 'not_run') { $report.status = 'validation_incomplete' }
    throw
} finally {
    $report | ConvertTo-Json -Depth 8 | Set-Content scan-report/portable.json -Encoding utf8
}
