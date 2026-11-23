$ErrorActionPreference = "Stop"
$s = Join-Path $PWD "C:\d\AgriPredict-AI\free\apps\api\.venv\Scripts\Activate.ps1"
if (Test-Path $s) { & $s -Scope CurrentUser }
$python = Join-Path $PWD "C:\d\AgriPredict-AI\free\.venv\Scripts\python.exe"
& $python -c "from app.core.config import get_settings; s=get_settings(); print('ENV='+s.ENVIRONMENT); print('SMS_PROVIDER='+repr(s.SMS_PROVIDER)); print('MANDI_SOURCE='+repr(s.MANDI_SOURCE)); print('POSTGRES_DSN_SET='+str(bool(s.POSTGRES_DSN))); print('POSTGRES='+repr(s.POSTGRES_DSN[:90])+'...')"
