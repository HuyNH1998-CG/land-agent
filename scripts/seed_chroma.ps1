$ErrorActionPreference = "Stop"

Write-Host "Seeding CSV datasets into local Chroma..." -ForegroundColor Cyan
python .\scripts\seed_chroma.py
Write-Host "Chroma seed completed." -ForegroundColor Green
