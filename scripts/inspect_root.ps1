# scripts/inspect_root.ps1
$j = Get-Content .wiki_token.json | ConvertFrom-Json
$token = $j.access_token
try {
  $r = Invoke-WebRequest -Uri 'https://enterprise.wikimedia.com/' -Headers @{ Authorization = "Bearer $token" } -Method GET -ErrorAction Stop
  $body = $r.Content
  if ($body -match 'api.php') { Write-Host 'Found api.php in root content' } else { Write-Host 'No api.php in root content' }
  $preview = if ($body.Length -gt 800) { $body.Substring(0,800) } else { $body }
  Set-Content -Path .wiki_root_preview.html -Value $preview -Encoding UTF8
  Write-Host "Saved root preview to .wiki_root_preview.html"
} catch {
  Write-Host "Request failed:" $_.Exception.Message
  exit 1
}
