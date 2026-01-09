# PowerShell скрипт для запуска Docker Compose с выбором режима

param(
    [Parameter(Mandatory=$false)]
    [ValidateSet("http", "https")]
    [string]$Mode = "http"
)

Write-Host "=== Запуск Wells API ===" -ForegroundColor Cyan
Write-Host "Режим: $Mode" -ForegroundColor Yellow

if ($Mode -eq "https") {
    $env:USE_HTTPS = "true"
    Write-Host "Используется HTTPS режим (порт 8443)" -ForegroundColor Green
} else {
    $env:USE_HTTPS = "false"
    Write-Host "Используется HTTP режим (порт 8000)" -ForegroundColor Green
}

Write-Host "`nЗапуск Docker Compose..." -ForegroundColor Cyan
docker-compose up --build


