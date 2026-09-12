# Ferramentas AJ TopoGeo — os dois programas numa janela so

Um executavel, um atalho, uma instalacao. A janela abre com duas abas:

| Aba | O que faz | Documentacao |
|---|---|---|
| **PPK das Fotos** | processa o log do voo contra a base RINEX, interpola a trajetoria no instante de cada disparo e escreve o geotag no formato do DJI Terra | [`servico-local-ppk/README.md`](../servico-local-ppk/README.md) |
| **Consulta de Cota** | cota de uma lista de coordenadas, declividade por faixa com mapa em PDF, e curvas de nivel em DXF para o CAD | [`consulta-cota/README.md`](../consulta-cota/README.md) |

Os dois programas separados continuam existindo e podem ser construidos como
antes. O que este projeto acrescenta e a casca: `principal.py` monta as duas
telas dentro de um `Notebook` e o `instalador/build.py` embrulha tudo num
pacote so.

## Como roda

```
py principal.py            # abre a janela
py principal.py --autoteste   # confere as ferramentas das duas abas
```

Ou pelo atalho `Ferramentas AJ TopoGeo.bat`, que acha o Python sozinho.

## Por que nao tem codigo de tela aqui dentro

`principal.py` nao copia nenhuma tela: importa `ppk_janela.Janela` e
`cota_janela.Janela` e monta cada uma no quadro da sua aba, com
`embutido=True`. Esse parametro so pula o que pertence a janela — titulo,
tamanho, icone — e o logo do cabecalho, que na janela unica aparece uma vez
la em cima em vez de uma vez por aba.

Melhoria feita no PPK aparece na aba do PPK sem ninguem ter de lembrar de
repetir. E foi por isso que os dois `Janela` ganharam o parametro em vez de
virarem copia.

## As abas carregam separadas, de proposito

O motivo de quase nao juntar os dois programas era este: uma falha no GDAL
derrubaria tambem o PPK, que nao tem nada com isso. Entao cada aba e importada
dentro do seu proprio `try`, e a que falhar mostra o motivo na propria aba
enquanto a outra abre normal. Um programa com um defeito e melhor do que um
programa que nao abre.

Para ver o que faltou, sem console:

```
"Ferramentas AJ TopoGeo.exe" --autoteste
```

Ele roda o autoteste das duas metades e so devolve zero quando as duas passam —
e e isso que o build e o instalador consultam antes de dar o servico por
concluido.

## O tamanho

|  | solto | junto |
|---|---|---|
| PPK das Fotos | 44 MB | |
| Consulta de Cota | 79 MB | |
| **Ferramentas AJ TopoGeo** | | **~95 MB** |

Nao soma 123 MB porque o Python e o tkinter vao uma vez so. As ferramentas
externas nao se sobrepoem — RTKLIB e ExifTool de um lado, GDAL do outro —,
entao essas somam.

## O config.json

Instalado, os dois motores leem **o mesmo** `config.json`, o que fica ao lado do
executavel; e por isso que ele carrega os cinco caminhos:

```json
{
  "rtklibBin":   "ferramentas/RTKLIB",
  "exiftoolBin": "ferramentas/exiftool",
  "gdalBin":     "ferramentas/gdal",
  "gdalData":    "ferramentas/gdal-data",
  "projData":    "ferramentas/proj"
}
```

Cada motor pega so as chaves que conhece e ignora o resto, entao um arquivo
serve aos dois. Rodando do fonte nada muda: cada um continua lendo o
`config.json` da sua propria pasta, com os caminhos de desenvolvimento.

## Construir o instalador

```
py instalador/build.py
```

Sai em `instalador/dist`:

```
Instalar Ferramentas AJ TopoGeo.exe     instalador de um clique, sem administrador
Ferramentas AJ TopoGeo - portatil.zip   para quem prefere so descompactar
```

O `build.py` daqui nao refaz o trabalho dos outros dois: ele importa o
`instalador/build.py` de cada projeto e chama o `copiar_ferramentas` de la — a
rotina que desmonta o RTKLIB, a que copia o ExifTool e a que segue a tabela de
importacao das DLLs do GDAL continuam morando em um lugar so. O unico acrescimo
e juntar os dois `config.json` num so.

Precisa, **so na maquina que constroi**: Python com `pyproj`, `PyInstaller` e
`pefile`; o RTKLIB e o ExifTool onde o `config.json` do PPK apontar; e o QGIS
onde o `config.json` da Consulta apontar. Na maquina de destino nao precisa de
nada — nem Python, nem QGIS.
