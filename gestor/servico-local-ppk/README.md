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

## Como o atalho encontra o Python

Nesta maquina o Python fica em `%LOCALAPPDATA%\Programs\Python\Python313` e essa
pasta **nao esta no PATH** da sessao do usuario -- so o lancador `py` costuma
estar. Por isso o atalho da Area de Trabalho aponta direto para o
`pythonw.exe` por caminho absoluto, em vez de chamar `pythonw` pelo nome.

O `PPK das Fotos.bat` continua servindo de reserva e procura o interpretador em
cascata: `pyw` no PATH, depois perguntando ao `py` onde ele esta, depois o
caminho padrao da instalacao, e por fim `py` comum.

Rodando por `pythonw` nao ha console, entao uma falha na partida nao apareceria
em lugar nenhum. Quando isso acontece o programa grava `erro_na_partida.txt` na
propria pasta e tenta mostrar uma caixa de mensagem.

## Varios voos na mesma pasta

Um cartao costuma trazer varios voos, cada um na sua pasta com `.MRK`, `.OBS`,
`.NAV` e as fotos. O script processa **todos** contra a mesma base e escreve um
unico arquivo de geotag com as fotos de todos eles -- os nomes nao colidem porque
o DJI carimba o horario.

O relatorio sai por voo, e o veredito geral e o **pior** dos voos: um voo ruim no
meio nao pode ficar escondido atras da media dos outros.

Cuidado que ja custou um processamento inteiro: a busca pela base precisa excluir
**todas** as pastas de voo, nao so a do primeiro. Excluindo so a primeira, o
script elege o segundo voo como se fosse a base -- e ai o RTKLIB nao produz
solucao nenhuma, com uma mensagem que parece problema de horario da base. O
sintoma que denuncia e a linha `antena 0.000 m sobre o marco`: OBS de drone nao
tem registro de altura de antena.

## Defesas contra pasta baguncada

O script nao confia na organizacao da pasta. Antes de processar ele:

1. **Recusa arquivo do drone como base.** Reconhece pelo nome (`DJI_...`) e pela
   ausencia de altura de antena e de nome de marco no cabecalho -- todo receptor
   de base registra os dois, o de drone nao registra nenhum.
2. **Mostra a base escolhida com identidade completa** (versao, receptor, marco,
   periodo gravado) e lista as candidatas descartadas. Escolha errada fica
   visivel na tela em vez de virar erro dez minutos depois.
3. **Confere o horario antes de rodar.** Compara o periodo da base com o de cada
   voo pelo `.MRK` e avisa quantos minutos ficaram descobertos.
4. **Explica quando nao ha solucao.** Em vez de mandar "confira a base", imprime
   o periodo da base, o periodo do voo, e diz se o problema e cobertura de
   horario ou qualidade do dado.

Verificado na pasta que falhou: o `.OBS` do drone e recusado (antena 0.0, sem
marco), a base ComNav e aceita (antena 1,681, marco 03322050), e das duas
candidatas ele fica com a 3.04 e informa que descartou a 2.11.

## As colunas de precisao sao PESO, nao documentacao

O programa de fotogrametria usa os dois ultimos numeros de cada linha para
decidir quanto confiar naquela foto no ajuste do bloco. Declarar precisao
otimista faz o ajuste **conformar o bloco aos geotags** em vez de corrigi-los
pela geometria das imagens.

Medido no levantamento GUSTHAVO -- 3210 fotos, mesmo bloco, mesma maquina, so
trocando o arquivo de geotag:

| | sigma declarado | RMS medido | erro de reprojecao |
|---|---|---|---|
| desvio formal do RTKLIB | 0,0055 m | 0,0225 m (4,1x alem) | **0,2937 px** |
| 0,03/0,06 fixos do DJI Terra | 0,0600 m | 0,0360 m (0,6x dentro) | **0,1519 px** |

Metade do erro de reprojecao, mais 5 milhoes de pontos 2D observados e mais
1.000 correspondencias por imagem -- tudo a favor do arquivo com sigma folgado.

Por isso o padrao passou a ser `--sigma realista`, que escreve conforme a
qualidade da epoca de cada foto:

```
solucao fixa  (Q=1)   0,05 / 0,10 m
float         (Q=2)   0,20 / 0,40 m
demais                0,30 / 0,60 m
```

Isso e melhor que um piso fixo porque diz ao ajuste **quais fotos** merecem
confianca, permitindo que as bem fixadas puxem as mal fixadas. `--sigma formal`
volta a escrever o desvio do RTKLIB, util so para conferencia.

## Fotos com a coordenada ja corrigida

A opcao correspondente grava as copias em **`_ppk/FOTOS CORRIGIDAS/`**, cada
imagem com a coordenada do PPK no lugar da do voo. Ficam dentro de `_ppk` de
proposito: essa pasta ja e excluida da varredura, entao as copias nunca serao
confundidas com fotos originais num reprocessamento. Serve para levar as fotos direto ao
programa de fotogrametria, sem carregar arquivo de geotag a parte.

**Os originais nunca sao tocados** -- o ExifTool escreve em outra pasta com `-o`.

A coordenada e gravada em **tres lugares**, porque a DJI guarda a posicao em
todos e um programa que leia so o XMP pegaria o valor antigo se mexessemos
apenas no EXIF:

```
EXIF     GPSLatitude / GPSLongitude / GPSAltitude (+ Ref)
XMP      drone-dji:GpsLatitude / GpsLongitude
XMP      drone-dji:AbsoluteAltitude
```

A altitude vai como **elipsoidal com referencia "acima do nivel do mar"**, que e
exatamente o que a DJI grava no arquivo original -- trocar a convencao criaria
incoerencia com o que os programas esperam do Matrice.

Custo medido (25 fotos, extrapolado para 3210): **~5 min e ~23 GB**. Confira o
espaco antes: e o tamanho do acervo inteiro duplicado.

O `-m` do ExifTool e obrigatorio: todo arquivo DJI reescrito dispara um aviso de
maker notes, e sem ele a gravacao e recusada.

**O destino e apagado antes de gravar.** O ExifTool com `-o` se recusa a
sobrescrever arquivo existente, e nao falha ao fazer isso: num reprocessamento a
copia antiga ficaria intacta e o programa contaria como gravada, entregando
coordenadas velhas com cara de novas. Verificado: sem o apagamento previo, uma
segunda gravacao com altitude diferente deixava o valor da primeira.

## Erro nao pode usar sys.exit

`achar_arquivos` roda dentro da thread de trabalho da janela. `sys.exit()`
levanta `SystemExit`, que **mata a thread em silencio**: nenhuma mensagem chega
a tela e a barra de progresso gira para sempre. Aconteceu com uma pasta que nao
tinha o arquivo de observacao da base -- o programa detectou corretamente e o
usuario ficou sem saber por que nada avancava.

As validacoes levantam `RuntimeError`, e a janela captura `BaseException` (nao
`Exception`) na thread, para que nem um `sys.exit()` esquecido volte a travar.
`sys.exit` fica so no `main()`, que e a linha de comando.
