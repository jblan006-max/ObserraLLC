$u = 'https://api.github.com/repos/usnistgov/800-53-rev5/git/trees/main?recursive=1'
try {
	$r = Invoke-RestMethod -Uri $u -ErrorAction Stop
	$paths = $r.tree | Where-Object { $_.path -match '\.json$' } | Select-Object -ExpandProperty path
	$paths | Out-File -FilePath deploy/onprem/_nist_files.txt -Encoding utf8
	Write-Host 'Wrote file list to deploy/onprem/_nist_files.txt'
} catch {
	Write-Host 'Error:' $_
}
