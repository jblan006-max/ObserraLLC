<#
One-click Windows installer for Obserra On‑Prem package.
Run this from the project root in an elevated PowerShell session:
  .\deploy\onprem\install-windows.ps1

It will: check Docker, create deploy/.env from the template, generate JWT_SECRET,
start Docker Compose, wait for backend health, and bootstrap an admin account.
#>
param(
	[string]$EnvPath = "deploy/.env",
	[int]$WaitSeconds = 120
)

function Ensure-Command {
	param([string]$cmd)
	try {
		& $cmd --version > $null 2>&1
		return $true
	} catch {
		return $false
	}
}

if (-not (Ensure-Command "docker")) {
	Write-Error "Docker is not installed or not in PATH. Install Docker Desktop and retry."
	exit 1
}

if (-not (Ensure-Command "docker")) {
	Write-Error "Docker Compose is required (docker compose)."
	exit 1
}

$template = "deploy/onprem/.env.example"
if (-not (Test-Path $template)) {
	Write-Error "Template $template not found"
	exit 1
}

if (-not (Test-Path $EnvPath)) {
	Copy-Item $template $EnvPath -Force
	Write-Host "Created $EnvPath from template"
}

# Load env file to check JWT_SECRET
[string]$envText = Get-Content $EnvPath -Raw
if ($envText -match "JWT_SECRET=\s*$") {
	# generate 32-byte hex secret
	$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
	$bytes = New-Object byte[] 32
	$rng.GetBytes($bytes)
	$hex = ([System.BitConverter]::ToString($bytes)).Replace('-', '')
	$envText = $envText -replace "JWT_SECRET=\s*$","JWT_SECRET=$hex"
	Set-Content -Path $EnvPath -Value $envText -Encoding ASCII
	Write-Host "Generated JWT_SECRET and wrote to $EnvPath"
}

Push-Location ".\deploy\onprem"
try {
	Write-Host "Starting Docker Compose (this may take a few minutes)..."
	& docker compose -f docker-compose.yml --env-file .env up -d --build
} catch {
	Write-Error "docker compose failed: $_"
	Pop-Location
	exit 1
}

Write-Host "Waiting for backend health endpoint..."
$health = $false
$start = Get-Date
while (((Get-Date) - $start).TotalSeconds -lt $WaitSeconds) {
	try {
		$r = Invoke-RestMethod -Uri "http://localhost:8080/api/health" -Method Get -UseBasicParsing -ErrorAction Stop
		if ($r) { $health = $true; break }
	} catch {
		Start-Sleep -Seconds 2
	}
}

if (-not $health) {
	Write-Error "Backend did not become healthy within $WaitSeconds seconds. Check 'docker compose logs -f backend' for details."
	Pop-Location
	exit 1
}

Write-Host "Backend is healthy. Creating first administrator..."

# Generate a secure password
$pwBytes = New-Object byte[] 16
[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($pwBytes)
$password = [Convert]::ToBase64String($pwBytes).Substring(0, 16) + "A1!"
$email = "admin@localhost"
$name = "Administrator"

try {
	$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
	$body = @{ email = $email; password = $password; name = $name; org_name = "Local Installation"; seed_demo = $true } | ConvertTo-Json
	$r2 = Invoke-RestMethod -Uri "http://localhost:8080/api/auth/bootstrap-admin" -Method Post -Body $body -ContentType "application/json" -WebSession $session -ErrorAction Stop
	Write-Host "Bootstrap admin created: $email"
	Write-Host "Password: $password"

	# Configure the agent runtime webhook to point to the local agent container service on the compose network.
	$agentSecretBytes = New-Object byte[] 18
	[System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($agentSecretBytes)
	$agentSecret = [Convert]::ToBase64String($agentSecretBytes).Substring(0,24)
	$webhookUrl = "http://agent:5000/inbound/INSTALL"
	$whBody = @{ webhook = $webhookUrl; secret = $agentSecret } | ConvertTo-Json
	try {
		Invoke-RestMethod -Uri "http://localhost:8080/api/agents/runtime/webhook" -Method Put -Body $whBody -ContentType "application/json" -WebSession $session -ErrorAction Stop
		Write-Host "Configured runtime webhook to $webhookUrl with a generated secret."
		# Test the webhook end-to-end
		try {
			Invoke-RestMethod -Uri "http://localhost:8080/api/agents/runtime/webhook/test" -Method Post -WebSession $session -ErrorAction Stop | Out-Null
			Write-Host "Runtime webhook test dispatched. Check the agent container logs for inbound event."
		} catch {
			Write-Warning "Runtime webhook test failed to dispatch: $_"
		}
	} catch {
		Write-Warning "Failed to set runtime webhook: $_"
	}
} catch {
	Write-Warning "Could not automatically create admin (may already exist). You can create one at http://localhost:8080 via the UI. Error: $_"
}

Write-Host "Installation complete. Open http://localhost:8080 in your browser."
Pop-Location
