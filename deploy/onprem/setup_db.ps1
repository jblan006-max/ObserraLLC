$ErrorActionPreference = 'Stop'

Write-Host "Checking Docker availability..."
try {
	$docker = Get-Command docker -ErrorAction Stop
	Write-Host "Docker found. Checking for existing 'obserra-mongo' container..."
	$existing = docker ps -a --filter "name=obserra-mongo" --format "{{.Names}}:{{.Status}}" 2>$null
	if ($existing) {
		Write-Host "Found existing container: $existing"
		$running = docker ps --filter "name=obserra-mongo" --format "{{.Names}}" 2>$null
		if (-not $running) {
			Write-Host "Starting existing container..."
			docker start obserra-mongo | Write-Host
		} else {
			Write-Host "Container already running."
		}
	} else {
		Write-Host "No existing container. Creating and starting 'obserra-mongo' (mongo:7)"
		docker run -d --name obserra-mongo -p 27017:27017 -v obserra_uac_mongo:/data/db --restart unless-stopped mongo:7 | Write-Host
	}
	Write-Host "MongoDB should be reachable at mongodb://localhost:27017/"
	exit 0
} catch {
	Write-Warning "Docker not available or failed to manage container: $_"
	Write-Host "Options:"
	Write-Host "1) Install Docker Desktop and re-run this script to start a local MongoDB container."
	Write-Host "2) Provide a SaaS MongoDB connection string (MongoDB Atlas) and set MONGO_URL in your .env file."
	Write-Host "Example Atlas URI: mongodb+srv://<user>:<pass>@cluster0.example.mongodb.net/obserra?retryWrites=true&w=majority"
	exit 2
}
