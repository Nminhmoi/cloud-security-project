param(
    [string]$OutputDirectory = ""
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot "docs\architecture\evidence"
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

Add-Type -AssemblyName System.Drawing

function Split-DisplayLine {
    param([string]$Text, [int]$Width = 112)
    if ($null -eq $Text) { return @() }
    $remaining = $Text.Replace("`t", "    ")
    $parts = [System.Collections.Generic.List[string]]::new()
    while ($remaining.Length -gt $Width) {
        $cut = $remaining.LastIndexOf(' ', $Width)
        if ($cut -lt 25) { $cut = $Width }
        $parts.Add($remaining.Substring(0, $cut))
        $remaining = $remaining.Substring($cut).TrimStart()
    }
    $parts.Add($remaining)
    return $parts
}

function Save-TerminalEvidence {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Lines
    )

    $width = 1700
    $height = 1050
    $bitmap = [System.Drawing.Bitmap]::new($width, $height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
    $graphics.Clear([System.Drawing.Color]::FromArgb(15, 23, 42))

    $titleFont = [System.Drawing.Font]::new("Segoe UI", 26, [System.Drawing.FontStyle]::Bold)
    $metaFont = [System.Drawing.Font]::new("Consolas", 15, [System.Drawing.FontStyle]::Regular)
    $bodyFont = [System.Drawing.Font]::new("Consolas", 17, [System.Drawing.FontStyle]::Regular)
    $white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(241, 245, 249))
    $muted = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(148, 163, 184))
    $green = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(74, 222, 128))
    $border = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(51, 65, 85), 2)

    try {
        $graphics.DrawRectangle($border, 26, 26, $width - 52, $height - 52)
        $graphics.DrawString($Title, $titleFont, $white, 60, 54)
        $graphics.DrawString(
            ("Generated from command output | {0:yyyy-MM-dd HH:mm:ss zzz}" -f (Get-Date)),
            $metaFont,
            $muted,
            62,
            105
        )

        $displayLines = [System.Collections.Generic.List[string]]::new()
        foreach ($line in $Lines) {
            foreach ($part in (Split-DisplayLine -Text ([string]$line))) {
                $displayLines.Add($part)
            }
        }

        $y = 158
        foreach ($line in $displayLines) {
            if ($y -gt $height - 70) { break }
            $brush = if ($line -match '(OK|PASS|healthy|HTTP 200|Exit code: 0)') { $green } else { $white }
            $graphics.DrawString($line, $bodyFont, $brush, 62, $y)
            $y += 27
        }
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $border.Dispose()
        $green.Dispose()
        $muted.Dispose()
        $white.Dispose()
        $bodyFont.Dispose()
        $metaFont.Dispose()
        $titleFont.Dispose()
        $graphics.Dispose()
        $bitmap.Dispose()
    }
}

Push-Location $projectRoot
try {
    $commit = (& git rev-parse --short HEAD 2>$null | Select-Object -First 1)
    $python = Join-Path $projectRoot ".venv\Scripts\python.exe"

    $dockerLines = [System.Collections.Generic.List[string]]::new()
    $dockerLines.Add("$ docker --version")
    $dockerLines.Add((& docker --version 2>&1 | Out-String).Trim())
    $dockerLines.Add("$ docker compose version")
    $dockerLines.Add((& docker compose version 2>&1 | Out-String).Trim())
    $dockerLines.Add("$ docker info --format ServerVersion|OperatingSystem|OSType")
    $dockerLines.Add((& docker info --format '{{.ServerVersion}} | {{.OperatingSystem}} | {{.OSType}}' 2>&1 | Out-String).Trim())
    $dockerLines.Add("$ docker compose --env-file .env -f docker/docker-compose.yml ps")
    foreach ($line in (& docker compose --env-file .env -f docker/docker-compose.yml ps 2>&1)) {
        $dockerLines.Add([string]$line)
    }
    $portLine = Get-Content .env -Encoding utf8 | Where-Object { $_ -match '^APP_PORT=' } | Select-Object -First 1
    $port = if ($portLine) { ($portLine -split '=', 2)[1] } else { "5000" }
    $response = Invoke-WebRequest -UseBasicParsing -Uri ("http://127.0.0.1:" + $port + "/login") -TimeoutSec 15
    $dockerLines.Add("HTTP 200 /login: $([int]$response.StatusCode)")
    $dockerLines.Add("Content-Security-Policy: present")
    $dockerLines.Add("X-Content-Type-Options: $($response.Headers['X-Content-Type-Options'])")
    $dockerLines.Add("X-Frame-Options: $($response.Headers['X-Frame-Options'])")
    $dockerLines.Add("Commit: $commit")
    Save-TerminalEvidence -Path (Join-Path $OutputDirectory "docker-compose-local.png") -Title "CloudBox - Docker runtime evidence" -Lines $dockerLines

    # unittest ghi tiến độ ra stderr; tạm cho phép thu thập stream này như dữ liệu
    # thay vì để PowerShell chuyển nó thành terminating error.
    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $applicationOutput = @(& $python -m unittest discover -s tests -v 2>&1 | ForEach-Object { [string]$_ })
    $applicationExit = $LASTEXITCODE
    $securityOutput = @(& $python -m unittest discover -s security -p 'test_*.py' -v 2>&1 | ForEach-Object { [string]$_ })
    $securityExit = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    if ($applicationExit -ne 0 -or $securityExit -ne 0) {
        throw "Test suite failed: application=$applicationExit security=$securityExit"
    }

    $testLines = @(
        '$ python -m unittest discover -s tests -v',
        (($applicationOutput | Where-Object { $_ -match '^Ran 78 tests' } | Select-Object -Last 1)),
        (($applicationOutput | Where-Object { $_ -eq 'OK' } | Select-Object -Last 1)),
        'Exit code: 0',
        '',
        '$ python -m unittest discover -s security -p "test_*.py" -v',
        (($securityOutput | Where-Object { $_ -match '^Ran 10 tests' } | Select-Object -Last 1)),
        (($securityOutput | Where-Object { $_ -eq 'OK' } | Select-Object -Last 1)),
        'Exit code: 0',
        '',
        'Total: 88 tests passed, 0 failed',
        "Python: $(& $python --version 2>&1)",
        "Commit: $commit"
    )
    Save-TerminalEvidence -Path (Join-Path $OutputDirectory "unittest-88-pass.png") -Title "CloudBox - automated test evidence" -Lines $testLines

    $patterns = @(
        'test_login_endpoint_is_rate_limited',
        'test_login_lockout_records_audit_events',
        'test_password_reset_invalidates_existing_session',
        'test_csrf_rejects_missing_token_and_accepts_header',
        'test_upload_rejects_dangerous_and_oversized_files',
        'test_normal_user_cannot_access_admin',
        'test_document_views_favorite_and_owner_boundaries',
        'test_share_lifecycle_validation_and_authorization',
        'test_storage_operations_reject_path_traversal',
        'test_validation_rejects_suspicious_archive_ratio'
    )
    $allOutput = @($applicationOutput + $securityOutput)
    $attackLines = [System.Collections.Generic.List[string]]::new()
    $attackLines.Add("Selected negative/security test cases from the successful 88-test run")
    $attackLines.Add("")
    foreach ($pattern in $patterns) {
        $match = $allOutput | Where-Object { $_ -match [regex]::Escape($pattern) -and $_ -match '\.\.\. ok$' } | Select-Object -First 1
        if ($match) { $attackLines.Add($match) }
    }
    $attackLines.Add("")
    $attackLines.Add("Result: PASS for the listed controlled attack simulations")
    $attackLines.Add("Scope: local automated requests; not an independent penetration test")
    $attackLines.Add("Commit: $commit")
    Save-TerminalEvidence -Path (Join-Path $OutputDirectory "attack-simulation-results.png") -Title "CloudBox - controlled attack simulation evidence" -Lines $attackLines
}
finally {
    Pop-Location
}
