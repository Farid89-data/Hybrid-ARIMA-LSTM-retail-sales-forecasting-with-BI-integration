$ErrorActionPreference = "Stop"
Set-Location "F:\_Arden (MSc Data Science)\6- Final Project\Calude Code\Code"
$url = "https://github.com/Farid89-data/Hybrid-ARIMA-LSTM-retail-sales-forecasting-with-BI-integration.git"
if ((git remote get-url origin) -ne $url) { git remote set-url origin $url }

$branch = git branch --show-current
"Branch: $branch"
git fetch origin --prune

$remoteRef = "origin/$branch"
if (git rev-parse --verify --quiet $remoteRef) {
    $base = git merge-base HEAD $remoteRef 2>$null
    if (-not $base) {
        Write-Host "STOP: local history is unrelated to GitHub. Do not pull. Ask Claude Code to reset this folder to origin/$branch." -ForegroundColor Red
        exit 1
    }
    $counts = (git rev-list --left-right --count "HEAD...$remoteRef") -split "\s+"
    $ahead = [int]$counts[0]; $behind = [int]$counts[1]
    "Ahead: $ahead  Behind: $behind"
    if ($ahead -gt 0 -and $behind -gt 0) {
        Write-Host "STOP: local and GitHub have both changed. Do not pull. Ask Claude Code to reconcile." -ForegroundColor Red
        exit 1
    }
    if ($behind -gt 0) { git pull --ff-only origin $branch }
}

git add -A
git status --short
$staged = @(git diff --cached --name-only)
if ($staged.Count -gt 0) {
    $bad = $staged | Where-Object {
        ($_ -like '*.pbix') -or ($_ -like '*.parquet') -or ($_ -like '*.zip') -or
        ($_ -like '*fact_*.csv') -or ($_ -like 'dashboard/data/*.csv')
    }
    $big = $staged | Where-Object { (Test-Path -LiteralPath $_) -and ((Get-Item -LiteralPath $_).Length -gt 50MB) }
    if ($bad -or $big) {
        Write-Host "STOP: data or large files are staged:" -ForegroundColor Red
        $bad; $big
        git reset -q
        exit 1
    }
    $msg = Read-Host "Commit message"
    if (-not $msg) { $msg = "Update project files" }
    git commit -m $msg
}

git push -u origin $branch
git fetch origin
"Local : $(git rev-parse HEAD)"
"GitHub: $(git rev-parse $remoteRef)"
