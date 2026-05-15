Set-Location $PSScriptRoot
chcp 65001 | Out-Null
[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python -m uvicorn app.main:app --app-dir $PSScriptRoot --host 127.0.0.1 --port 8000
