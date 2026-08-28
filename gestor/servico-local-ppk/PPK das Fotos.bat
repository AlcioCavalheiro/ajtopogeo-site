@echo off
rem Abre a janela do PPK. O pythonw roda sem deixar janela preta atras.
cd /d "%~dp0"
start "" pythonw.exe ppk_janela.py
if errorlevel 1 (
  echo Nao encontrei o Python. Instale do site python.org e tente de novo.
  pause
)
