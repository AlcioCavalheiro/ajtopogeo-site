@echo off
rem Abre a janela do PPK. Nao depende do PATH: nesta maquina o Python fica em
rem %LOCALAPPDATA%\Programs\Python e so o lancador "py" costuma estar no PATH.
setlocal
cd /d "%~dp0"

rem 1) lancador windowed, se estiver no PATH
where pyw >nul 2>&1
if %errorlevel%==0 (
  start "" pyw "ppk_janela.py"
  goto :eof
)

rem 2) pergunta ao lancador py onde esta o interpretador
for /f "usebackq delims=" %%i in (`py -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" 2^>nul`) do set "PYW=%%i"
if defined PYW if exist "%PYW%" (
  start "" "%PYW%" "ppk_janela.py"
  goto :eof
)

rem 3) caminho padrao da instalacao por usuario
if exist "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" (
  start "" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "ppk_janela.py"
  goto :eof
)

rem 4) ultimo recurso: py comum, que deixa uma janela preta aberta junto
where py >nul 2>&1
if %errorlevel%==0 (
  start "" py "ppk_janela.py"
  goto :eof
)

echo.
echo Nao encontrei o Python nesta maquina.
echo Instale em python.org marcando a opcao "Add Python to PATH".
echo.
pause
