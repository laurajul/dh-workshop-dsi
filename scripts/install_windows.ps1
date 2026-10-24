# DH Workshop — Windows Setup Script
# Run by right-clicking and selecting "Run with PowerShell"
# Or from PowerShell: powershell -ExecutionPolicy Bypass -File install_windows.ps1

$REPO_URL       = "https://github.com/laurajul/DH-Workshop.git"
$PROJECT_DIR    = "$env:USERPROFILE\DH-Workshop"
$PYTHON_VERSION = "3.11"
$KERNEL_NAME    = "dh-workshop"
$KERNEL_DISPLAY = "DH Workshop"

# ─── helpers ──────────────────────────────────────────────────────────────────
function Write-Step  { Write-Host "`n── $args ──────────────────────────────────────────────" }
function Write-OK    { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "! $args" -ForegroundColor Yellow }
function Write-Fail  { Write-Host "✗ $args" -ForegroundColor Red }

Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  DH Workshop — Windows Setup"               -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# ── 1. Git ────────────────────────────────────────────────────────────────────
Write-Step "Checking for Git"
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Fail "Git is not installed."
    Write-Host ""
    Write-Host "Please install Git from: https://git-scm.com/download/win"
    Write-Host "  → Run the installer with default settings"
    Write-Host "  → Then re-run this script"
    Write-Host ""
    Read-Host "Press Enter to open the download page"
    Start-Process "https://git-scm.com/download/win"
    exit 1
}
Write-OK "git: $(git --version)"

# ── 2. uv ─────────────────────────────────────────────────────────────────────
Write-Step "Checking for uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv..."
    try {
        powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    } catch {
        Write-Fail "Failed to install uv: $_"
        exit 1
    }
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Fail "uv still not found after install."
    Write-Host "Please close this window, open a new PowerShell, and re-run the script."
    Read-Host "Press Enter to exit"
    exit 1
}
Write-OK "uv: $(uv --version)"

# ── 3. Clone repository ───────────────────────────────────────────────────────
Write-Step "Getting the workshop repository"
if (Test-Path "$PROJECT_DIR\.git") {
    Write-OK "Repository already exists at $PROJECT_DIR"
    Set-Location $PROJECT_DIR
    try { git pull --ff-only 2>$null } catch { Write-Warn "Could not pull latest — continuing with existing version" }
} else {
    Write-Host "Cloning to $PROJECT_DIR ..."
    git clone $REPO_URL $PROJECT_DIR
    Set-Location $PROJECT_DIR
}

# ── 4. Python environment ─────────────────────────────────────────────────────
Write-Step "Setting up Python $PYTHON_VERSION environment"
uv python install $PYTHON_VERSION
uv venv --python $PYTHON_VERSION
Write-OK "Virtual environment created"

# ── 5. Install packages ───────────────────────────────────────────────────────
Write-Step "Installing Python packages (this may take a few minutes)"
uv pip install -r requirements.txt
Write-OK "Packages installed"

# ── 6. Register Jupyter kernel ────────────────────────────────────────────────
Write-Step "Registering Jupyter kernel"
uv run python -m ipykernel install --user --name=$KERNEL_NAME --display-name=$KERNEL_DISPLAY
Write-OK "Kernel '$KERNEL_DISPLAY' registered"

# ── 7. Done — launch JupyterLab ───────────────────────────────────────────────
Write-Host ""
Write-Host "==============================================" -ForegroundColor Green
Write-Host "  ✓ Setup complete!"                          -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  JupyterLab is opening in your browser."
Write-Host "  When a notebook is open, select the"
Write-Host "  '$KERNEL_DISPLAY' kernel in the top-right corner."
Write-Host ""

uv run jupyter lab
