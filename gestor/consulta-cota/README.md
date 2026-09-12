# Consulta de Cota

Devolve a cota de coordenadas sobre um modelo digital (DSM ou DTM). Abre pelo
atalho "Consulta de Cota" na Area de Trabalho.

Fluxo: escolher o `.tif` do modelo, colar a lista de coordenadas, Consultar.
O resultado sai em tabela e pode ser copiado ou salvo em CSV.

## Instalacao em outra maquina

`instalador/dist/Instalar Consulta de Cota.exe` -- um arquivo so, 79 MB. Leva o
Python e o GDAL dentro dele: **na maquina de destino nao precisa de QGIS**, nem
de Python.

Instala em `%LOCALAPPDATA%\Programs\Consulta de Cota`, por usuario, e **nao pede
senha de administrador**. Cria atalho na Area de Trabalho e no menu Iniciar, e
aparece em Configuracoes > Aplicativos para desinstalar. Quem preferir nao
instalar usa `Consulta de Cota - portatil.zip`.

Para conferir uma instalacao que nao abre (sem console nao ha mensagem de erro):

```
"Consulta de Cota.exe" --autoteste
```

### O que vai dentro, e por que so isso

A pasta `bin` do QGIS tem **424 MB** e a `share/proj`, **774 MB**. Nada disso
precisa ir junto:

| o que | tamanho | por que |
|---|---|---|
| 3 executaveis + 51 DLLs | 122 MB | o fecho de dependencia real do `gdalinfo`, `gdallocationinfo` e `gdaldem`, lido da tabela de importacao de cada arquivo |
| `gdal-data` | 3 MB | tabelas de formato e de sistema de coordenadas |
| `proj.db` | 9 MB | o banco de projecoes |

As grades de transformacao entre datums (os 765 MB restantes de `share/proj`)
ficam de fora porque **este programa nao reprojeta nada** -- ele exige que a
coordenada ja esteja no sistema do raster.

Sem o `gdal-data` e o `proj.db` o GDAL ainda abre o raster, mas nao sabe dizer em
que sistema de coordenadas ele esta -- e a conferencia do sistema, que e a defesa
contra consultar com a coordenada errada, deixaria de existir em silencio. Por
isso o programa aponta `GDAL_DATA` e `PROJ_LIB` para as pastas que vieram junto,
e o `--autoteste` confere as duas.

Conferido contra o GDAL do QGIS no mesmo raster, com o QGIS fora do PATH: cota,
analise de vizinhanca e as seis faixas de declividade batem **casa por casa**.

### Gerar o instalador

```
py instalador/build.py
```

Precisa, **so na maquina que constroi**, de Python com `pyinstaller` e `pefile`,
e do QGIS onde o `config.json` de desenvolvimento aponta. O build so embrulha
depois que o pacote passa no proprio `--autoteste`.

O trabalho comum aos dois programas de servico local mora em
`gestor/instalador-comum`: `empacotar.py` (congelar, conferir, compactar,
embrulhar) e `instalar.py` (o instalador em si, que le nome e chave de registro
de um `programa.json` embutido). O `build.py` daqui so diz o nome e como
desmontar o GDAL do QGIS.

## Instalacao para desenvolver

O GDAL sai do QGIS instalado, pelo caminho em `config.json`. Do lado do Python,
so a biblioteca padrao e o `numpy` (usado no ajuste de plano da vizinhanca).

No `config.json`, caminho relativo vale a partir da pasta do proprio arquivo --
e o que permite o pacote instalado achar o GDAL que veio junto. Caminho absoluto
continua funcionando, que e como ele aponta para o QGIS aqui.

## Curvas de nivel

Terceira aba. Gera as curvas do modelo em DXF, com a cota no **Z de cada
vertice** -- o Civil 3D consome direto como superficie, sem precisar ler campo
de atributo. As curvas saem separadas nos layers `CN_SIMPLES` e `CN_MESTRA`.
Tambem grava SHP, GPKG e GeoJSON; nesses tres a cota vai tambem nos campos
`ELEV` e `MESTRA`, que o DXF nao aceita (o esquema dele e fixo).

**Nao entra binario novo no instalador.** A `gdal311.dll` que ja vem no pacote
exporta `GDALContourGenerateEx`; o `curvas.py` fala com ela por `ctypes`. Nao
existe `gdal_contour.exe` no pacote e nao precisa existir.

### Os tres cuidados que separam prancha de espaguete

1. **Reamostragem** para um pixel de trabalho compativel com a equidistancia
   (padrao: metade dela). Contornar pixel bruto de fotogrametria de 3 cm devolve
   linha serrilhada com milhares de vertices por hectare.
2. **Suavizacao** por media movel que ignora vazio -- divide pela contagem de
   pixels validos da janela, nao pelo tamanho dela, senao a borda de um buraco
   puxaria a cota e deformaria a curva justo onde o modelo ja e fraco.
3. **Comprimento minimo**: poca de ruido vira circulinho fechado que nao
   representa relevo. Abaixo do limite, descartada.

Os tres campos ficam no "Ajuste fino" e em branco usam o automatico.

### O que o programa recusa, e por que

- **Modelo em graus.** Equidistancia, pixel e suavizacao sao metricas; num
  raster em grau, pedir pixel de 0,5 reamostraria o voo inteiro para um punhado
  de pixels, e o erro que o GDAL devolve ("too many levels") nao aponta para a
  causa. O programa barra na entrada e manda reprojetar para UTM. **O MDT que
  sai do Agisoft vem assim**; o do Pix4D ja vem em UTM.
- **Desnivel absurdo.** Mais de 2000 niveis nao e relevo, e buraco entrando como
  terreno: o classico e o MDT sem o valor de vazio gravado, com o buraco em
  -9999 ou -10000. Medido: sem essa conferencia o GDAL fica **mais de dez
  minutos** gerando curvas ate a cota -10000, que numa janela se le como
  travamento. Com ela, o programa recusa em **0,8 s** e diz para preencher o
  campo "Vazio do modelo". Informando -10000, o resultado bate exatamente com o
  do mesmo raster que declara o vazio.

### A fase que nao tem barra

O GDAL grava o arquivo no fechamento, e essa parte nao reporta progresso. No DXF
ela e a maior parte do tempo -- medido num modelo de 1918x1818:

| formato | total | contorno + laco | gravacao no fechamento |
|---|---|---|---|
| DXF | 44,5 s | 8,6 s | **35,9 s** |
| GPKG | 11,2 s | 11,1 s | 0,1 s |
| SHP | 1,6 s | 1,6 s | 0,0 s |

Por isso, ao chegar ao fim das feicoes a janela troca o texto para "gravando o
arquivo em disco" e passa a barra para indeterminada. Barra cheia e parada por
36 segundos e o que faz o usuario achar que travou.

### Como foi conferido

Contra o `gdal_contour` do QGIS, no mesmo raster, com
`pixel=0, suavizacao=0, comprimento_minimo=0`: **365.524 feicoes nos dois,
exatamente**. E a paridade que prova que a sequencia de chamadas via ctypes esta
correta. Repetido depois de cada mudanca no modulo.

Tambem conferido com o GDAL **do pacote**, com o QGIS fora do PATH: mesmas 3.201
curvas do QGIS, DXF gravado.

## Marca nas janelas

O icone do executavel e do atalho, e o logo no topo da janela, saem de
`gestor/marca` -- os mesmos do PPK das Fotos. Veja o README de lado para o
detalhe de como sao gerados.

## Formatos de coordenada aceitos

Uma por linha, com ou sem nome do ponto. Separador pode ser espaco, tabulacao,
ponto-e-virgula ou virgula. Decimal pode ser ponto ou virgula:

```
M-01  713000,00  7686800,00
713000;7686800
P3,712800.50,7686600.25
```

**A ordem das colunas e descoberta sozinha.** Em UTM no hemisferio sul o Norte
passa de 1 milhao e o Leste nao, entao da para saber qual e qual sem perguntar
-- uma lista com Norte primeiro funciona igual. Se as duas coordenadas cairem na
mesma ordem de grandeza a deteccao desiste e avisa; ai e so escolher a ordem na
caixa de selecao.

## Cuidados

**Nao ha reprojecao.** As coordenadas precisam estar no mesmo sistema do raster.
A janela mostra o sistema do modelo assim que ele e carregado (por exemplo
`SIRGAS 2000 / UTM zone 21S`) justamente para essa conferencia. Se o modelo
estiver em graus, aparece um aviso em vermelho.

**A cota sai no datum vertical do modelo.** Os modelos gerados a partir do
[../servico-local-ppk](../servico-local-ppk) saem em altitude **elipsoidal**, que
e o padrao usado aqui.

Ponto fora da area do modelo aparece como `fora do modelo`; area sem dado (buraco
no levantamento) aparece como `vazio no modelo`. Nos dois casos a linha continua
na tabela, sem cota, para nao desalinhar a lista.

## Onde ficam os modelos do Pix4D

```
<projeto>/3_dsm_ortho/1_dsm/<nome>_dsm.tif      superficie (DSM)
<projeto>/3_dsm_ortho/extras/dtm/<nome>_dtm.tif terreno (DTM)
```

Para cota de terreno use o DTM; o DSM inclui vegetacao e construcao.

O GDAL vem do QGIS; o caminho esta em `config.json`.

## As colunas de incerteza

O raster do modelo **nao guarda sigma nenhum** -- tem uma banda so, com a altura.
Entao "sigma" aqui e duas coisas distintas, e so uma delas e medida ponto a ponto.

**Sigma local** (medido, diferente para cada ponto). Amostra uma grade 5x5 dentro
do raio escolhido, ajusta um plano por minimos quadrados e devolve o desvio dos
residuos. O ajuste do plano e o que separa **ruido** de **declividade** -- sem
ele, terreno em rampa apareceria como incerteza alta sem motivo.

Nao e a acuracia do levantamento: e a qualidade da superficie naquele ponto.
Medido no voo Portal das Flores:

| ponto | sigma local | declive | leitura |
|---|---|---|---|
| chao limpo | 0,5 a 1,0 cm | 3% | cota confiavel |
| em rampa | 4,8 cm | 24% | aceitavel |
| copa de arvore / quina | 70 a 74 cm | 118 a 211% | **nao confiar** |

E o indicador que pega o ponto caido em cima de vegetacao ou de telhado, onde a
cota do DSM nao representa o solo.

**Sigma do levantamento** (tres campos: E, N e Z), vindo do relatorio de
processamento. Sao iguais para todos os pontos -- descrevem a qualidade do
levantamento, nao do ponto. No Portal das Flores: E 5,9 mm, N 2,1 mm, Z 14,1 mm.

**Sigma Z** e a soma quadratica de tres parcelas:

```
sigma_Z = raiz( levantamento_Z^2  +  rugosidade^2  +  (declive x horizontal)^2 )
```

A terceira parcela existe porque **incerteza horizontal vira vertical em terreno
inclinado**: errar 6 mm no plano, sobre 118% de declive, desloca a cota em 7 mm.
Em terreno plano ela some; em barranco, pesa.

Quem domina o sigma muda conforme o ponto -- em chao limpo manda o levantamento
(1,4 cm), em copa de arvore manda a rugosidade (73 cm):

| ponto | rugosidade | declive | parcela do declive | sigma Z |
|---|---|---|---|---|
| chao limpo | 0,5 cm | 3,5% | 0,02 cm | 1,49 cm |
| em rampa | 4,8 cm | 24% | 0,15 cm | 4,98 cm |
| copa de arvore | 73,7 cm | 118% | 0,74 cm | 73,72 cm |

Nenhum dos dois cobre erro sistematico da base: se a coordenada do marco estiver
errada, todo o modelo desloca junto e nenhuma dessas contas percebe. Para isso so
ponto de apoio medido em campo.

## Leitura automatica do relatorio do Pix4D

Ao escolher o `.tif`, o programa sobe na arvore de pastas procurando
`<projeto>/1_initial/report/report.xml` e, achando, preenche sozinho o campo do
sigma do levantamento com o **RMS vertical do bloco**. Usa o `report.xml`, nao o
PDF: o XML e estruturado e nao quebra quando a Pix4D muda o leiaute do relatorio.

O que o XML traz de util:

```
/results/initial/gsd                          3,32 cm
/results/initial/geolocation/position/sigma   x 0,00587  y 0,00205  z 0,01413
/results/initial/geolocation/position/rms     idem
/results/initial/geolocation/position/mean    ~zero (sem vies)
```

**Cuidado com o que esse numero significa.** Ele mede o quanto o ajuste do bloco
moveu as cameras em relacao ao geotag que entrou. E precisao interna: se as fotos
tivessem entrado todas deslocadas, o ajuste acompanharia o deslocamento e o RMS
continuaria pequeno. Foi exatamente o que aconteceu com o DJI Terra, que
reportava 0,03/0,06 m enquanto errava 1,7 m em altura por nao somar a altura da
antena da base.

Por isso a janela mostra junto a regra pratica: sem ponto de apoio, a expectativa
realista de acuracia vertical fica entre **1,5 e 3 x GSD** -- neste projeto, 5 a
10 cm, e nao os 14 mm do relatorio.

## Aba de declividade

Calcula a declividade em porcentagem com `gdaldem slope -p` e informa quanto de
area cai em cada faixa das classes de capacidade de uso do solo. O raster fica
salvo ao lado do modelo, como `<nome>_declividade.tif`, e pode ser aberto no
QGIS ou no CAD.

**Use o DTM, nao o DSM.** Sobre o DSM a conta sai da copa das arvores e do
telhado, e nao do terreno. A janela avisa se o arquivo escolhido tem "dsm" no
nome, mas nao tem como saber com certeza -- a responsabilidade e de quem escolhe.

Medido no DTM do Portal das Flores (50,7 ha), em 5 segundos:

| declividade | classe | hectares | % |
|---|---|---|---|
| 0 a 3% | plano | 12,06 | 23,7% |
| 3 a 8% | suave ondulado | 22,10 | 43,5% |
| 8 a 13% | ondulado | 8,57 | 16,9% |
| 13 a 20% | forte ondulado | 4,58 | 9,0% |
| 20 a 45% | montanhoso | 3,10 | 6,1% |
| acima de 45% | escarpado | 0,31 | 0,6% |

O rodape destaca a area **ate 13%**, que e o limite usual do terraceamento
mecanizado -- nesse caso 42,73 ha, 84% da area.

As areas saem do histograma do raster. Como ele vem com 256 baldes cobrindo todo
o intervalo, a borda de uma faixa quase nunca coincide com a borda de um balde:
o balde e repartido na proporcao da sobreposicao, em vez de ir inteiro para um
lado. Sem isso o erro chegaria a meio balde por faixa.
