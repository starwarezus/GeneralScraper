# PowerShell script to open in GeneralScraper directory and launch Claude Code

# Change to the target directory
Set-Location -Path "E:\Downloads\GeneralScraper"

# Display current directory to confirm
Write-Host "Current directory: $(Get-Location)" -ForegroundColor Green

# Launch Claude Code
Write-Host "Starting Claude Code..." -ForegroundColor Cyan
claude
