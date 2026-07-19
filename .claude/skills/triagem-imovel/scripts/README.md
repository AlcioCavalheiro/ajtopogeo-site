# Ambiente do extrair_texto.py

O script roda no venv dedicado em `C:\Users\ALCIO\.ajtopogeo\venv`, fora do
Python do sistema e fora deste repositório.

## Recriar o venv

```powershell
py -m venv C:\Users\ALCIO\.ajtopogeo\venv
& C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe -m pip install `
    "markitdown[pdf,docx,xlsx,xls,pptx,outlook]" pymupdf pillow `
    ezdxf fpdf2 matplotlib
```

- `markitdown` — PDF com texto, DOCX, planilha, PPTX, HTML, e-mail (.msg), ZIP.
- `pymupdf` — rasteriza a página do PDF escaneado para mandar ao OCR, e
  reextrai tabela preservando a estrutura de linha.
- `pillow` — neutraliza marca-texto antes do OCR (ver abaixo) e recorta a
  margem em branco da imagem do croqui.
- `ezdxf` — escreve o DXF do croqui (`croqui.py`).
- `fpdf2` — compõe o PDF da triagem (`relatorio.py`).
- `matplotlib` — rasteriza o DXF para embutir o croqui no PDF.

## Os três scripts

| script | entrada | saída |
| --- | --- | --- |
| `extrair_texto.py` | pasta de documentos | `.md` por documento + `_INDICE.md` |
| `croqui.py` | `spec-<NOME>.json` com os rumos | `croqui-<NOME>.dxf` + `.md` |
| `relatorio.py` | `triagem-<NOME>.md` | `triagem-<NOME>.pdf` |

O PDF usa Arial de `C:\Windows\Fonts`. Faltando, cai para Helvetica embutida,
que é latin-1 e perde caractere fora dessa tabela.

## Padrão visual

Cores e métricas extraídas do **RT-627/2026 Rev. 02**, que é o padrão dos
relatórios técnicos da empresa. Mexer aqui é mudar a identidade dos
entregáveis — confira contra um relatório recente antes.

| elemento | cor |
| --- | --- |
| faixa do cabeçalho, título, cabeçalho de tabela | `#0b2e59` |
| filete sob a faixa | `#5ba3e0` |
| títulos de seção | `#1e5fa5` |
| corpo de texto | `#444444` |
| rodapé | `#7a7a7a` |
| linha alternada de tabela | `#eaf1fb` |
| borda de tabela | `#cfdcef` |
| caixa de síntese: fundo / filete / texto | `#fcebeb` / `#a32d2d` / `#5a1414` |

Faixa de 21,9 mm (62 pt) + filete de 1,4 mm (4 pt), margens de 15 mm, corpo em
9,5 pt e tabela em 8 pt — as mesmas do modelo.

No markdown, `> ` vira a caixa de síntese conclusiva.

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

### Marca-texto

Trecho grifado com marca-texto ciano ou verde **sumia inteiro** do OCR — não
saía errado, saía ausente, com a frase ainda parecendo completa. Numa matrícula
de teste, a área do imóvel e a fração mínima de parcelamento, ambas grifadas,
desapareceram. O binarizador do Tesseract come o texto junto com o fundo
colorido escuro.

Antes do OCR a imagem passa por `max(R,G,B)`, que joga qualquer cor saturada
para branco e mantém o traço preto. Com isso os dois campos voltaram.
