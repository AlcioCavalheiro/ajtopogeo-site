# Ambiente do extrair_texto.py

O script roda no venv dedicado em `C:\Users\ALCIO\.ajtopogeo\venv`, fora do
Python do sistema e fora deste repositório.

## Recriar o venv

```powershell
py -m venv C:\Users\ALCIO\.ajtopogeo\venv
& C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe -m pip install `
    "markitdown[pdf,docx,xlsx,xls,pptx,outlook]" pymupdf
```

- `markitdown` — PDF com texto, DOCX, planilha, PPTX, HTML, e-mail (.msg), ZIP.
- `pymupdf` — rasteriza a página do PDF escaneado para mandar ao OCR.

## OCR (PDF escaneado)

Precisa do **Tesseract** no PATH, com o idioma português. Instale numa janela
do PowerShell **como administrador** — o app do Claude não consegue elevar:

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

No instalador, marque *Additional language data* → **Portuguese**. Se pular
essa etapa, o OCR sai em inglês e erra acentuação.

Conferir depois:

```powershell
tesseract --list-langs   # tem que aparecer "por"
```

Sem Tesseract o script continua funcionando: converte tudo que tem texto e
marca os escaneados como `SEM TEXTO - ler visualmente` no índice.
