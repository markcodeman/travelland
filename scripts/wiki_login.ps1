# PowerShell version of wiki login
# Usage: .\scripts\wiki_login.ps1  (prompts for username/password if not in env)

Param()

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here/..

$WIKI_AUTH_URL = $env:WIKI_AUTH_URL
if (-not $WIKI_AUTH_URL) { $WIKI_AUTH_URL = 'https://auth.enterprise.wikimedia.com/v1/login' }

if (-not $env:WIKI_USER) { $WIKI_USER = Read-Host 'WIKI_USER' } else { $WIKI_USER = $env:WIKI_USER }
$secure = Read-Host 'Password' -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$WIKI_PASS = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)

$tokenFile = '.wiki_token.json'
$cookies = '.wiki_cookies.txt'

# Try JSON token flow
$body = @{ username = $WIKI_USER; password = $WIKI_PASS } | ConvertTo-Json
try {
  $r = Invoke-RestMethod -Uri $WIKI_AUTH_URL -Method Post -Body $body -ContentType 'application/json' -ErrorAction Stop
  if ($r.access_token) {
    $expires = if ($r.expires_in) { [int]$r.expires_in } else { 3600 }
    $expiry = [int](Get-Date -UFormat %s) + $expires - 60
    $obj = @{ access_token = $r.access_token; expires_at = $expiry }
    $obj | ConvertTo-Json | Set-Content $tokenFile
    icacls $tokenFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Write-Host "Saved token to $tokenFile"
    exit 0
  }
} catch {
  # ignore, fallback to cookie method
}

# Cookie-based login (save cookies)
# PowerShell doesn't directly save cookies easily; use curl if available
try {
  & curl -sS -c $cookies -X POST $WIKI_AUTH_URL -H 'Content-Type: application/json' -d $body
  if (Test-Path $cookies) {
    icacls $cookies /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Write-Host "Saved cookies to $cookies"
    exit 0
  }
} catch {
  Write-Error "Login failed: $_"
  exit 1
}

Write-Error "Login failed: no token or cookie captured"
exit 1