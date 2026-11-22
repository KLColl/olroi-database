$ErrorActionPreference = 'Stop'
$pgBin = 'C:\Program Files\PostgreSQL\18\bin'
$backupDirectory = Join-Path $PSScriptRoot 'backups'
$backupPath = Join-Path $backupDirectory 'bookstore_lab4_initial.dump'

New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null

& "$pgBin\pg_dump.exe" -h localhost -p 5432 -U postgres -W `
    --format=custom --file=$backupPath bookstore_lab4
if ($LASTEXITCODE -ne 0) {
    throw 'Не вдалося створити резервну копію.'
}

& "$pgBin\createdb.exe" -h localhost -p 5432 -U postgres -W bookstore_lab5
if ($LASTEXITCODE -ne 0) {
    throw 'Не вдалося створити bookstore_lab5. Відновлення не виконано.'
}

& "$pgBin\pg_restore.exe" -h localhost -p 5432 -U postgres -W `
    --exit-on-error --dbname=bookstore_lab5 $backupPath
if ($LASTEXITCODE -ne 0) {
    throw 'Відновлення перервано. Необхідно перевірити повідомлення pg_restore.'
}

Write-Host 'bookstore_lab5: резервну копію відновлено успішно.'
Get-Item -LiteralPath $backupPath | Select-Object Name, Length
