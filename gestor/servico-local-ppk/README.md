# PPK das fotos de drone

Refaz por fora o pos-processamento que o DJI Terra faz nas fotos: processa o log
bruto do rover contra a base RINEX, interpola a trajetoria no instante exato de
cada disparo e escreve o CSV no mesmo formato que o Terra gera
(`arquivo,lat,lon,altitude_elipsoidal,yaw,pitch,roll,precisao_h,precisao_v`).

Validado contra um voo do Matrice 4 RTK ja processado no Terra: 42 fotos,
diferenca media zero e desvio de 5 cm em Norte, 1,5 cm em Leste e 19 cm em
altura, com atitude identica.

## Instalacao

Precisa de duas ferramentas portateis (nenhuma pede administrador) e dos
caminhos apontados no `config.json`:

- **RTKLIB** (motor de pos-processamento) — https://github.com/rtklibexplorer/RTKLIB/releases
- **ExifTool** (le a atitude do gimbal) — https://exiftool.org
  (renomear `exiftool(-k).exe` para `exiftool.exe`)

Do lado do Python: `pyproj`.

## Uso

```bash
py ppk_fotos.py --projeto "D:\LEV 2026-08-27" --base-e 751382.175 --base-n 7739504.037 --base-z 646.246
```

A pasta do projeto pode ter qualquer estrutura, desde que contenha:

- os arquivos do drone (`*_D.MRK`, `*_D.OBS`, `*_D.NAV`) e as fotos `.JPG` juntos
- os arquivos da base (observacao + navegacao) em outra pasta

Opcoes: `--epsg` (padrao 31981, SIRGAS2000/UTM 21S), `--altura-antena` (por
padrao lida do cabecalho da base) e `--saida`.

## Coordenada da base

`--base-z` e altura **elipsoidal** do marco; a altura da antena entra separada e
por padrao vem do campo `ANTENNA: DELTA H/E/N` do RINEX da base. Um erro aqui
desloca todas as fotos em bloco, na mesma proporcao — foi assim que se descobriu
que a coordenada do `COORDENADAS DA BASE.txt` do voo de referencia estava 2,2 m
no plano e 1,7 m em altura longe da que o Terra usou.

## Exportar a base em RINEX 3.04

Exporte a base **com todas as constelacoes** (GPS, GLONASS, Galileo, BeiDou).
Com a base antiga em RINEX 2.11, que so tinha GPS/GLONASS e gravava L2 em
codigo-P enquanto o drone grava L2C, a ambiguidade nunca fixava e o erro passava
de um metro. Com o RINEX 3.04 multiconstelacao a solucao fixa em 78% das epocas.

## Detalhe do RINEX 3.05

O Matrice 4 exporta o rover em RINEX 3.05, versao que o RTKLIB 2.5.1 rejeita —
sem avisar, devolve posicoes centenas de quilometros fora. O script reetiqueta o
cabecalho para 3.04 ao copiar; os dados nao mudam.

## Sobre as colunas de precisao

As duas ultimas colunas sao o desvio formal do filtro do RTKLIB (o mesmo que o
T2R-Geotagger exporta como *Std Error*). Sao **precisao formal, nao acuracia**:
no voo de referencia o filtro prometia 7 mm em altura enquanto a diferenca real
contra o DJI Terra foi de 19 cm. Servem para pesar as fotos no ajuste do bloco.

Nao comparar esses numeros entre voos diferentes: eles refletem a geometria dos
satelites, o comprimento da linha de base e o tempo de rastreio daquele voo.

## Mascara de elevacao

O padrao e 15 graus, como o material da T2R recomenda. Em voo com boa visada,
`--elmask 10` costuma fixar bem mais epocas -- num voo de 534 fotos passou de
45% para 69% das fotos em solucao fixa, com as duas solucoes concordando em
0,5-1,4 cm de media. Vale conferir a continuidade da trajetoria depois de baixar
a mascara: satelite baixo e mais ruidoso.

O `pos2-elmaskhold` fica fixo em 15 e nao acompanha a `--elmask`: travar a
ambiguidade em satelite baixo derruba a fixacao (medido: 69% -> 49%).

## Janela (uso sem linha de comando)

`PPK das Fotos.bat` abre `ppk_janela.py`, que e o jeito normal de usar. Ha um
atalho na Area de Trabalho. O fluxo e: escolher a pasta do voo, informar a base
(digitada em UTM ou lida do relatorio do IBGE-PPP) e clicar em Processar.

Se houver um relatorio do IBGE-PPP dentro da pasta do voo, a janela acha sozinha
e ja preenche a coordenada -- e o caminho preferido, porque erro de digitacao na
base desloca todas as fotos em bloco.

## As conferencias automaticas

O ponto do sistema nao e rodar o RTKLIB, e dizer se o resultado presta. Sao tres
indicadores, e o segundo e o que importa:

1. **Fotos em solucao fixa.** Util, mas engana sozinho: um voo defeituoso marcou
   86% aqui e mesmo assim estava errado.
2. **Concordancia entre as passagens de ida e volta.** As duas resolvem a
   ambiguidade de forma independente; onde as duas fixam, a ambiguidade e
   confiavel. Foi o unico indicador que separou os dois voos de referencia:
   1% no voo com degrau de 37 cm, 13% no voo limpo. Abaixo de 5% e defeito.
3. **Tempo de gravacao antes da primeira foto.** Nos dois voos medidos havia
   ~55 s, curto demais. E a causa raiz dos dois problemas.

Ficou registrado o que **nao** funciona como conferencia, para nao se tentar de
novo: aceleracao vertical entre epocas (deixa passar degrau espalhado por
3 epocas) e diferenca de posicao entre fotos consecutivas (o drone se move de
verdade entre disparos). Continuidade da trajetoria tambem nao prova nada
sozinha: ambiguidade errada de forma constante da trajetoria lisa e deslocada.
