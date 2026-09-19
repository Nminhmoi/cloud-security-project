$ErrorActionPreference = 'Stop'

if (-not (Get-Command xelatex -ErrorAction SilentlyContinue)) {
    throw 'XeLaTeX was not found. Install MiKTeX or TeX Live and add xelatex to PATH.'
}

Push-Location $PSScriptRoot
try {
    New-Item -ItemType Directory -Path 'build' -Force | Out-Null
    # Two passes update the table of contents and references.
    for ($pass = 1; $pass -le 2; $pass++) {
        & xelatex -interaction=nonstopmode -halt-on-error -no-shell-escape -output-directory=build ATTT1.tex
        if ($LASTEXITCODE -ne 0) {
            throw "XeLaTeX pass $pass failed. See docs/reports/build/ATTT1.log."
        }
    }
    Copy-Item -LiteralPath 'build/ATTT1.pdf' -Destination 'ATTT1.pdf' -Force
    Write-Output 'Report updated: docs/reports/ATTT1.pdf'
}
finally {
    Pop-Location
}
