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

Instalado: **Tesseract 5.4** (build UB-Mannheim) em
`C:\Program Files\Tesseract-OCR`, via `winget install --id
UB-Mannheim.TesseractOCR -e` numa janela **como administrador** — o app do
Claude não consegue elevar.

O modelo de português não vem no instalador padrão. Fica em
`C:\Users\ALCIO\.ajtopogeo\tessdata\por.traineddata`
([tessdata_best](https://github.com/tesseract-ocr/tessdata_best), 7,8 MB),
e o script aponta para lá com `--tessdata-dir`. Assim não depende de escrita
em `Program Files`, que exigiria admin.

O script acha o `tesseract.exe` no PATH ou, se não estiver, no caminho padrão
de instalação — o app do Claude só enxerga PATH novo depois de reiniciado.

Sem Tesseract nada quebra: converte tudo que tem texto e marca os escaneados
como `SEM TEXTO - ler visualmente` no índice.
