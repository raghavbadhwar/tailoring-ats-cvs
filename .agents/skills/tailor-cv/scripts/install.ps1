param([switch]$Approved)

$packageRef = "git+https://github.com/raghavbadhwar/tailoring-ats-cvs.git@f666ab5a6a3b074fad6f470f986436814b56a3d3"

if (-not $Approved) {
    Write-Error "Installation requires explicit approval. Re-run: install.ps1 -Approved"
    exit 2
}

if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv tool install $packageRef
    exit $LASTEXITCODE
}
if (Get-Command pipx -ErrorAction SilentlyContinue) {
    & pipx install $packageRef
    exit $LASTEXITCODE
}

Write-Error "No supported installer found. Run: python -m venv .venv; .\.venv\Scripts\python -m pip install '$packageRef'"
exit 1
