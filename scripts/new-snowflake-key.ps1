# Creates a Snowflake key pair for this computer in %USERPROFILE%\.rex-secrets and prints the one SQL
# statement to run in Snowflake. Use it on a new computer instead of copying the old private key.
#
#   powershell -ExecutionPolicy Bypass -File scripts\new-snowflake-key.ps1
#
# The private key never leaves this computer and is never written inside the repository.
param(
    [string]$SnowflakeUser = "LIUY99629",
    [ValidateSet(1, 2)][int]$Slot = 2,  # Snowflake keeps two public keys per user; slot 2 leaves the old computer working
    [switch]$Force
)
$ErrorActionPreference = "Stop"

$openssl = "C:\Program Files\Git\usr\bin\openssl.exe"
if (-not (Test-Path $openssl)) {
    $cmd = Get-Command openssl -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "openssl not found. Install Git for Windows first: winget install --id Git.Git -e" }
    $openssl = $cmd.Source
}

$dir = Join-Path $env:USERPROFILE ".rex-secrets"
$key = Join-Path $dir "snowflake_rsa_key.p8"
$pub = Join-Path $dir "snowflake_rsa_key.pub"
if ((Test-Path $key) -and -not $Force) {
    throw "$key already exists. Re-run with -Force to replace it (the old key stops working once Snowflake has the new one)."
}
New-Item -ItemType Directory -Force $dir | Out-Null

function Invoke-OpenSsl {
    # openssl prints progress on stderr; Windows PowerShell would treat that as an error under "Stop".
    $ErrorActionPreference = "Continue"
    & $openssl @args 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "openssl $($args[0]) failed (exit $LASTEXITCODE)" }
}

$rsa = Join-Path $dir "tmp_rsa.pem"
try {
    Invoke-OpenSsl genrsa -out $rsa 2048
    Invoke-OpenSsl pkcs8 -topk8 -nocrypt -in $rsa -out $key
    Invoke-OpenSsl rsa -in $key -pubout -out $pub
} finally {
    Remove-Item $rsa -ErrorAction SilentlyContinue
}

$oneline = ((Get-Content $pub) | Where-Object { $_ -notmatch "PUBLIC KEY" }) -join ""
Set-Content -Path (Join-Path $dir "pub_oneline.txt") -Value $oneline -NoNewline -Encoding ascii
$field = if ($Slot -eq 2) { "RSA_PUBLIC_KEY_2" } else { "RSA_PUBLIC_KEY" }
$sql = "ALTER USER $SnowflakeUser SET $field = '$oneline';"
Set-Content -Path (Join-Path $dir "snowflake_setup.sql") -Value $sql -Encoding ascii

# Only the current user may read the folder.
icacls $dir /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" | Out-Null

Write-Host ""
Write-Host "Private key: $key" -ForegroundColor Green
Write-Host "Next: open Snowflake (https://app.snowflake.com) > Projects > Worksheets, paste ONLY this line and click Run:" -ForegroundColor Yellow
Write-Host ""
Write-Host $sql
Write-Host ""
try { Set-Clipboard -Value $sql; Write-Host "(Already copied to the clipboard.)" } catch {}
