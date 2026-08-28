@echo off
rem Abre a janela de consulta de cota. Nao depende do PATH.
setlocal
cd /d "%~dp0"
where pyw >nul 2>&1
if %errorlevel%==0 (
  start "" pyw "cota_janela.py"
  goto :eof
)
for /f "usebackq delims=" %%i in (`py -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul`) do set "PYW=%%i"
if defined PYW if exist "%PYW%" (
  start "" "%PYW%" "cota_janela.py"
  goto :eof
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
  start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "cota_janela.py"
  goto :eof
)
where py >nul 2>&1 && start "" py "cota_janela.py"
