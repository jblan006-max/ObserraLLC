$files = @(
  "https://csrc.nist.gov/files/pubs/sp/800/53/r5/upd1/final/docs/sp800-53r5-potential-updates.xlsx",
  "https://csrc.nist.gov/files/pubs/sp/800/53/r5/upd1/final/docs/sp800-53r4-to-r5-comparison-workbook.xlsx",
  "https://csrc.nist.gov/files/pubs/sp/800/53/r5/upd1/final/docs/sp800-53r4-appj-to-r5-comparison.xlsx",
  "https://csrc.nist.gov/files/pubs/sp/800/53/r5/upd1/final/docs/csf-pf-to-sp800-53r5-mappings.xlsx",
  "https://csrc.nist.gov/files/pubs/sp/800/53/r5/upd1/final/docs/sp800-53-collaboration-index-template.xlsx"
)

$outdir = "deploy/onprem/nist_docs"
New-Item -ItemType Directory -Path $outdir -Force | Out-Null

foreach ($u in $files) {
	try {
		$name = Split-Path $u -Leaf
		$out = Join-Path $outdir $name
		Write-Host "Downloading: $u -> $out"
		Invoke-WebRequest -Uri $u -OutFile $out -UseBasicParsing -ErrorAction Stop
		Write-Host "Saved $out"
	} catch {
		Write-Host "Failed to download $u - $_"
	}
}

Write-Host "Downloaded NIST supplemental documents to $outdir. Run backend/scripts/convert_spreadsheets_to_json.py to attempt extracting controls into JSON for import."
