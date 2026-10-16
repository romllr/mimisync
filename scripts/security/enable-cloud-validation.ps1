# Isolated GitHub runner only. Enable the normal Defender cloud protections.
# No user media or credentials are staged as antivirus samples.
$ErrorActionPreference = 'Stop'
$result = [ordered]@{ configured = $false; mapsConnectionExitCode = $null; error = $null }
try {
    Set-MpPreference -DisableRealtimeMonitoring $false
    Set-MpPreference -MAPSReporting Advanced -SubmitSamplesConsent SendSafeSamples -DisableBlockAtFirstSeen $false -DisableIOAVProtection $false -DisableScriptScanning $false
    $preferences = Get-MpPreference
    if ($preferences.MAPSReporting -eq 0 -or $preferences.SubmitSamplesConsent -notin @(1,3) -or $preferences.DisableBlockAtFirstSeen -or $preferences.DisableIOAVProtection -or $preferences.DisableScriptScanning) {
        throw 'Required cloud/download protections did not become active.'
    }
    $platform = Join-Path $env:ProgramData 'Microsoft/Windows Defender/Platform'
    $scanner = Get-ChildItem $platform -Filter MpCmdRun.exe -Recurse | Sort-Object FullName -Descending | Select-Object -First 1
    if (-not $scanner) { throw 'Official Defender command-line scanner was not found.' }
    & $scanner.FullName -ValidateMapsConnection
    $result.mapsConnectionExitCode = $LASTEXITCODE
    if ($LASTEXITCODE -ne 0) { throw 'Defender cloud connection verification failed.' }
    $result.configured = $true
} catch {
    $result.error = $_.Exception.Message
    Write-Warning $result.error
} finally {
    New-Item -ItemType Directory -Path scan-report -Force | Out-Null
    $result | ConvertTo-Json | Set-Content scan-report/cloud.json -Encoding utf8
}
# Keep building/scanning even if cloud verification fails; the final scan reports failure.
