$tokenFile = '.wiki_token.json'
if (Test-Path $tokenFile) {
  $j = Get-Content $tokenFile | ConvertFrom-Json
  $token = $j.access_token
  Write-Host "Using Bearer token (trim):" ($token.Substring(0, [math]::Min(8,$token.Length)) + '...')
  try {
    $r = Invoke-RestMethod -Uri 'https://enterprise.wikimedia.com/' -Headers @{ Authorization = "Bearer $token" } -Method GET -ErrorAction Stop
    Write-Host "Request succeeded. Response preview:"
    $r | Format-List -Force
  } catch {
    Write-Host "Request failed:" $_.Exception.Message
  }
} elseif (Test-Path '.wiki_cookies.txt') {
  Write-Host "Using cookies file to call endpoint via curl"
  bash -lc "curl -sS -b .wiki_cookies.txt 'https://enterprise.wikimedia.com/' | head -c 1000"
} else {
  Write-Host "No auth token or cookies found"
  exit 1
}
