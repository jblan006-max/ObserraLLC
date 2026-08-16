$urls = @("https://raw.githubusercontent.com/usnistgov/800-53-rev5/main/controls.json","https://raw.githubusercontent.com/18F/cybersecurity-controls/master/sp800-53/rev5/sp800_53_r5.json","https://raw.githubusercontent.com/usnistgov/800-53-rev5/main/sp800_53_rev5.json","https://raw.githubusercontent.com/usnistgov/800-53/main/sp800-53-rev5.json")
$out = "deploy/onprem/sp800_53_rev5.json"
foreach ($u in $urls) {
	Write-Host "Trying: $u"
	try {
		$resp = Invoke-WebRequest -Uri $u -UseBasicParsing -ErrorAction Stop
		if ($resp -and $resp.Content) {
			$resp.Content | Out-File -FilePath $out -Encoding utf8
			Write-Host "Saved from $u"
			break
		}
	} catch {
		Write-Host "Failed: $u - $_"
	}
}

Write-Host "If this script fails to fetch canonical NIST files, run the backend endpoint POST /api/nist/auto-import as an admin to attempt additional mirrors and import into MongoDB."
