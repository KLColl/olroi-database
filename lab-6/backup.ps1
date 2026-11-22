param(
    [string]$MongoDump = 'mongodump',
    [string]$Uri = 'mongodb://localhost:27017'
)

$ErrorActionPreference = 'Stop'
$backupDir = Join-Path $PSScriptRoot 'backups'
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
$name = 'library-{0}.archive.gz' -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
$archive = Join-Path $backupDir $name

& $MongoDump --uri $Uri --db library "--archive=$archive" --gzip
if ($LASTEXITCODE -ne 0) {
    throw "mongodump failed (exit code $LASTEXITCODE)"
}

Get-Item -LiteralPath $archive | Select-Object Name, Length
