# Relatório da Fazenda

> **Movido para o Gestor em 13/09/2026.** O relatório agora é a aba
> *Ferramentas GEO › Relatório da Fazenda* do Gestor e roda no navegador:
> `gestor/relatorio-fazenda.js`, com as tabelas em `gestor/dados/`. Saiu do
> programa Ferramentas AJ TopoGeo do computador. Este código Python fica como
> referência — foi nele que os serviços e as tabelas foram conferidos contra o
> dado real, e o porte em JavaScript segue as mesmas regras.
>
> **Ampliado em 17/09/2026** com diagnóstico fundiário e ambiental (Terra
> Indígena, Unidade de Conservação federal, assentamento, quilombola e
> embargos do IBAMA), pareamento geométrico SIGEF × CAR, cálculo da Reserva
> Legal mínima pela Lei 12.651/2012, página de diagnóstico executivo com
> semáforo e um capítulo de logística. A tabela abaixo é a versão anterior,
> só com sensoriamento remoto; a lista de capítulos atual está em
> `gestor/relatorio-fazenda.js` (função `montarPdf`).

Relatório técnico de caracterização de imóvel rural em PDF, a partir do
perímetro em KML/KMZ. Rodando do fonte, ainda abre sozinho:

```
py fazenda_janela.py              # janela própria
py fazenda_janela.py --autoteste  # confere GDAL, certificados, bibliotecas e bases
```

## O que o relatório traz

| Capítulo | De onde vem |
|---|---|
| 1. Situação cadastral | CAR e SIGEF **consultados ao vivo** no dia da emissão; município e módulo fiscal tirados do próprio CAR |
| 2. Imagem de satélite | Sentinel-2 L2A, a cena mais recente **sem nuvem sobre o imóvel** |
| 3. NDVI e série temporal | mesma fonte; nuvem e sombra removidas pela banda SCL |
| 4. Relevo e declividade | Copernicus DEM GLO-30, classes do IBGE, APP e uso restrito da Lei 12.651 |
| 5. Chuva | NASA POWER, normal de 20 anos contra os últimos 12 meses |
| 6. Valor da terra | VTN 2026 da Receita e preços referenciais do INCRA (RAMT MS 2024) — `bases/` |
| 7. Ressalvas e fontes | o que cada dado é e o que não é |

A aba tem mais dois modos sobre o mesmo perímetro: **Imagem de uma data**
(RGB, NDVI e modelo de elevação em GeoTIFF, SIRGAS 2000 / UTM) e **Série de
NDVI** (CSV, gráfico e, se pedido, raster por data).

## De onde saiu, e o que foi corrigido

O código chegou pronto num `files.zip` (`relatorio_fazenda.py`,
`imagens_area.py`, `fontes_dados.py`). Foi portado e testado contra os serviços
reais em volta da Faz. São Jorge (Campo Grande/MS) em 13/09/2026.

**Porte.** O original usava rasterio, geopandas e pystac-client. Os dois
primeiros trazem cada um a sua cópia do GDAL, e o programa único já leva uma.
`fazenda_geo.py` faz o mesmo trabalho pela DLL da Consulta de Cota — recorte de
COG remoto, leitura de vetor, interseção e área. Ficaram o matplotlib (mapas e
gráficos) e o reportlab (PDF). Arquivos com prefixo `fazenda_` porque no
executável todos os módulos dividem o mesmo espaço de nomes, e a Consulta de
Cota já tem um `relatorio.py`.

**Defeitos do original, todos reproduzidos antes de corrigir:**

1. **Tabela de valor imprimia código como preço.** Qualquer coluna numérica
   acima de 100 virava linha: numa planilha no formato oficial, o código IBGE
   saiu como R$ 5.000.203,00/ha e o exercício como R$ 2.025,00/ha, e `18.500`
   era lido como 18,5 e sumia.
2. **CAR ao vivo nunca funcionaria.** O servidor recusa o TLS padrão do
   OpenSSL 3 (aceita com `SECLEVEL=1`); as camadas são `sicar_imoveis_<uf>` e o
   código procurava `imovel`; pegaria as três primeiras em ordem alfabética
   (AC, AL, AM); e o bbox ia em lat,lon quando o GeoServer quer lon,lat.
3. **SIGEF ao vivo nunca funcionaria.** O i3geo do INCRA não serve GeoJSON. Em
   GML2, com bbox em lat,lon, funciona — e o OGR precisa de
   `CONSIDER_EPSG_AS_URN=YES`, senão lê latitude como X.
4. **Instalado, não acharia a pasta `bases`**: procurava ao lado do
   `__file__`, que no executável é uma pasta temporária.
5. **EPSG errado no hemisfério norte**: para o fuso 18N dava 31964, que não
   existe — quebraria em Roraima, Amapá e norte do Pará e do Amazonas.

**Ajustes de critério:**

- **Lasca de divisa não é sobreposição.** Os vizinhos do São Jorge apareciam
  "sobrepostos" com 0,00 %: interseções de 21 m², 0,6 m², 0,6 m² e 0 m², de
  divisas desenhadas por levantamentos diferentes. Abaixo de 100 m² sai da
  tabela.
- **Imagem mais recente limpa, não a de menor nuvem da cena.** O original
  escolheu 15/08 tendo 04/09 limpa sobre o imóvel, e o texto do PDF dizia
  "a mais recente". A nuvem da cena (110 × 110 km) não diz nada sobre a
  fazenda: 09/09 tinha 68 % na cena e 17 % no imóvel; 30/08, 43 % na cena e
  100 % no imóvel.
- **Série de NDVI lê a SCL primeiro** e só baixa as bandas das datas que
  passam na cobertura mínima.
- **Buraco no polígono** (área excluída do perímetro) é descontado da área e
  da máscara; o original lia só o anel externo.

**O que foi conferido e está certo no original:** declividade de Horn (exata em
rampas de 2°, 10°, 30° e 50°), classes do IBGE, limites da Lei 12.651, chuva do
NASA POWER, e o NDVI calculado direto do número digital — o catálogo declara
`offset -0.1`, mas os pixels mostram que o offset da baseline 04.00 já foi
removido (mínimo 111 no B08 e 174 no B04 da cena de 04/09/2026). Aplicar o
metadado estragaria o índice.

## Arquivos

| Arquivo | Papel |
|---|---|
| `fazenda_geo.py` | GDAL pela DLL: `Grade`, `recortar`, `gravar_tif`, `Vetor`, `sobreposicao` |
| `fazenda_fontes.py` | CAR, SIGEF, chuva, declividade, VTN, mercado, módulo fiscal |
| `fazenda_imagens.py` | KML, catálogo STAC, escolha de cena, NDVI, série, modelo de elevação, modos da aba |
| `fazenda_relatorio.py` | mapas, gráficos, montagem do PDF e o fluxo completo |
| `fazenda_janela.py` | a aba (ou janela) e o `--autoteste` |
| `bases/` | tabelas oficiais e o [`LEIA-ME`](bases/LEIA-ME.md) de onde cada uma saiu |
| `config.json` | caminho do GDAL de desenvolvimento (o do QGIS) |

Rodando do fonte, o carregador do GDAL vem de `../consulta-cota/curvas.py`.

## Limites que o próprio relatório imprime

Não é avaliação de imóvel (NBR 14653-3 exige vistoria, amostra e ART); VTN é
régua fiscal, não preço de venda; preço de mercado descreve um agrupamento de
municípios; GLO-30 é modelo de superfície de 30 m e APP por declividade é
indicativa; chuva é grade de ~50 km; cadastro tem data; NDVI é vigor, não
produtividade.
