# Ferramentas AJ TopoGeo — os programas de serviço local numa janela só

Um executável, um atalho, uma instalação. A janela abre com duas abas:

| Aba | O que faz | Documentação |
|---|---|---|
| **PPK das Fotos** | processa o log do voo contra a base RINEX, interpola a trajetória no instante de cada disparo e escreve o geotag no formato do DJI Terra | [`servico-local-ppk/README.md`](../servico-local-ppk/README.md) |
| **Consulta de Cota** | cota de uma lista de coordenadas, declividade por faixa com mapa em PDF, e curvas de nível em DXF para o CAD | [`consulta-cota/README.md`](../consulta-cota/README.md) |

O **Relatório da Fazenda** foi a terceira aba até 13/09/2026 e saiu: agora é uma
aba do Gestor (`gestor/relatorio-fazenda.js`), gerado no navegador sem instalar
nada. O código Python dele ficou em `relatorio-fazenda/` como referência.

Os programas separados continuam existindo e podem ser construídos como
antes. O que este projeto acrescenta é a casca: `principal.py` monta as telas
dentro de um `Notebook` e o `instalador/build.py` embrulha tudo num pacote só.

## Como roda

```
py principal.py                               # abre a janela
py principal.py --autoteste                   # confere as ferramentas das duas abas
```

Ou pelo atalho `Ferramentas AJ TopoGeo.bat`, que acha o Python sozinho.

## Por que não tem código de tela aqui dentro

`principal.py` não copia nenhuma tela: importa `ppk_janela.Janela` e
`cota_janela.Janela` e monta cada uma no quadro da
sua aba, com `embutido=True`. Esse parâmetro só pula o que pertence à janela —
título, tamanho, ícone — e troca o cabeçalho com logo por uma linha de
descrição, já que o nome está no rótulo da aba.

## As abas carregam separadas, de propósito

Cada aba é importada dentro do seu próprio `try`, e a que falhar mostra o
motivo na própria aba enquanto as outras abrem normalmente. Uma falha no GDAL
não derruba o PPK, que não tem nada com isso.

## O tamanho

| | instalador |
|---|---|
| PPK das Fotos sozinho | 44 MB |
| Consulta de Cota sozinha | 79 MB |
| **Ferramentas AJ TopoGeo** | **~101 MB** |

Não soma 123 MB porque o Python e o tkinter vão uma vez só. O `build.py` exclui
de propósito pandas, IPython, jinja2, scipy, pytest e matplotlib, que entrariam
por import opcional de outras bibliotecas sem serem usados.

## O config.json

Instalado, todos os motores leem **o mesmo** `config.json`, o que fica ao lado
do executável:

```json
{
  "rtklibBin":   "ferramentas/RTKLIB",
  "exiftoolBin": "ferramentas/exiftool",
  "gdalBin":     "ferramentas/gdal",
  "gdalData":    "ferramentas/gdal-data",
  "projData":    "ferramentas/proj"
}
```

Cada motor pega só as chaves que conhece. Rodando do fonte nada muda: cada um
lê o `config.json` da própria pasta.

## Construir o instalador

```
py instalador/build.py
```

Sai em `instalador/dist`:

```
Instalar Ferramentas AJ TopoGeo.exe     instalador de um clique, sem administrador
Ferramentas AJ TopoGeo - portatil.zip   para quem prefere só descompactar
```

O `build.py` daqui não refaz o trabalho dos outros: importa o
`instalador/build.py` do PPK e da Consulta e chama o `copiar_ferramentas` de
lá. O único acréscimo é juntar os `config.json`.

Precisa, **só na máquina que constrói**: Python com `pyproj`, `PyInstaller` e `pefile`; o RTKLIB e o ExifTool onde
o `config.json` do PPK apontar; e o QGIS onde o `config.json` da Consulta
apontar. Na máquina de destino não precisa de nada.
