[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$TemporaryStack,
    [switch]$Cleanup,
    [int]$AppPort = 15000,
    [int]$SecondaryAppPort = 15001
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$composeFile = Join-Path $projectRoot "docker\docker-compose.yml"
$envFile = Join-Path $projectRoot ".env"
$composeArgs = @(
    "compose",
    "--env-file", $envFile,
    "-f", $composeFile,
    "--profile", "integration"
)

if (-not (Test-Path -LiteralPath $envFile)) {
    throw "Missing .env. Copy .env.example to .env and replace every placeholder first."
}

if ($Cleanup -and -not $TemporaryStack) {
    throw "-Cleanup is only accepted together with -TemporaryStack to protect persistent project data."
}

if ($TemporaryStack) {
    $env:DB_PASSWORD = [Guid]::NewGuid().ToString("N")
    $env:MYSQL_ROOT_PASSWORD = [Guid]::NewGuid().ToString("N")
    $env:SECRET_KEY = ([Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N"))
    $env:COMPOSE_PROJECT_NAME = "cloudbox-mysql-test-$(Get-Date -Format 'yyMMddHHmmss')"
}
$env:APP_PORT = "$AppPort"
$env:SECONDARY_APP_PORT = "$SecondaryAppPort"

& docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Engine is not running. Start Docker Desktop and run this script again."
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Command)

    & docker @composeArgs @Command
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose failed: $($Command -join ' ')"
    }
}

function Wait-Web {
    param([int]$Port)

    foreach ($attempt in 1..30) {
        try {
            Invoke-WebRequest -Uri "http://localhost:$Port/" -UseBasicParsing -TimeoutSec 3 | Out-Null
            return
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Web container on port $Port did not become ready within 60 seconds."
}

function Invoke-LoginWithRetry {
    param(
        [int]$Port,
        [string]$Body
    )

    $request = @{
        Uri = "http://localhost:$Port/api/v1/auth/login"
        Method = "Post"
        ContentType = "application/json"
        Body = $Body
        TimeoutSec = 3
    }
    foreach ($attempt in 1..30) {
        try {
            return Invoke-RestMethod @request
        }
        catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Login did not recover on port $Port within 60 seconds."
}

try {
    $upArgs = @("up", "-d")
    if (-not $SkipBuild) {
        $upArgs += "--build"
    }
    Invoke-Compose @upArgs
    Wait-Web -Port $AppPort
    Wait-Web -Port $SecondaryAppPort

    $suffix = (Get-Date -Format "yyMMddHHmmss") + (Get-Random -Minimum 100 -Maximum 999)
    $username = "cross#$suffix"
    $password = "ContainerPass!2026"
    $body = @{
        username = $username
        email = "cross$suffix@test.local"
        password = $password
    } | ConvertTo-Json

    $registerRequest = @{
        Uri = "http://localhost:$AppPort/api/v1/auth/register"
        Method = "Post"
        ContentType = "application/json"
        Body = $body
    }
    $registered = Invoke-RestMethod @registerRequest

    $loginRequest = @{
        Uri = "http://localhost:$AppPort/api/v1/auth/login"
        Method = "Post"
        ContentType = "application/json"
        Body = $body
        SessionVariable = "browserSession"
    }
    $null = Invoke-RestMethod @loginRequest
    $meFromSecondContainer = Invoke-RestMethod `
        -Uri "http://localhost:$SecondaryAppPort/api/v1/me" `
        -Method Get `
        -WebSession $browserSession

    if ($registered.data.id -ne $meFromSecondContainer.data.id) {
        throw "The two web containers returned different users."
    }

    Invoke-Compose restart web web-secondary
    Wait-Web -Port $AppPort
    Wait-Web -Port $SecondaryAppPort
    $null = Invoke-LoginWithRetry -Port $SecondaryAppPort -Body $body

    Invoke-Compose restart db
    $null = Invoke-LoginWithRetry -Port $AppPort -Body $body

    Write-Host "PASS: migration completed on MySQL."
    Write-Host "PASS: account $username was created on web and read from web-secondary."
    Write-Host "PASS: the signed session worked across both app containers."
    Write-Host "PASS: login still worked after restarting app containers and MySQL."
}
finally {
    if ($Cleanup) {
        Invoke-Compose down --volumes
        Write-Host "CLEANUP: removed only the temporary test containers and volumes."
    }
}
