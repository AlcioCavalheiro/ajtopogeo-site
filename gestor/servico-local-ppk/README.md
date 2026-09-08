# PPK das fotos de drone

Refaz por fora o pos-processamento que o DJI Terra faz nas fotos: processa o log
bruto do rover contra a base RINEX, interpola a trajetoria no instante exato de
cada disparo e escreve o CSV no mesmo formato que o Terra gera
(`arquivo,lat,lon,altitude_elipsoidal,yaw,pitch,roll,precisao_h,precisao_v`).

Validado contra um voo do Matrice 4 RTK ja processado no Terra: 42 fotos,
diferenca media zero e desvio de 5 cm em Norte, 1,5 cm em Leste e 19 cm em
altura, com atitude identica.

## Instalacao em outra maquina

`instalador/dist/Instalar PPK das Fotos.exe` -- um arquivo so, 44 MB. Leva o
Python, o RTKLIB e o ExifTool dentro dele: **na maquina de destino nao precisa
instalar mais nada**, nem Python.

Instala em `%LOCALAPPDATA%\Programs\PPK das Fotos`, por usuario, e **nao pede
senha de administrador** -- de proposito. Instalar em Arquivos de Programas
exigiria elevacao, e o pedido de UAC e o que costuma travar a instalacao em
maquina de cliente ou em rede administrada por TI. Cria atalho na Area de
Trabalho e no menu Iniciar, e aparece em Configuracoes > Aplicativos para
desinstalar.

Quem preferir nao instalar usa `PPK das Fotos - portatil.zip`: descompacta em
qualquer pasta (ou num pendrive) e roda o `PPK das Fotos.exe` de dentro dela.

Para conferir uma instalacao que nao abre, sem console nao ha mensagem de erro:

```
"PPK das Fotos.exe" --autoteste
```

### Gerar o instalador

```
py instalador/build.py
```

Leva uns 3 minutos. Precisa, **so na maquina que constroi**, de Python com
`pyproj` e `pyinstaller`, mais o RTKLIB e o ExifTool nos caminhos do
`config.json` de desenvolvimento. O build so embrulha depois que o pacote passa
no proprio `--autoteste`, entao nao sai instalador quebrado.

Do RTKLIB vao junto apenas o `rnx2rtkp.exe` e o `igs20_*.atx` (a calibracao de
antena); o resto da distribuicao seriam dezenas de MB sem uso aqui dentro.

## Instalacao para desenvolver

Duas ferramentas portateis (nenhuma pede administrador) e os caminhos apontados
no `config.json`:

- **RTKLIB** (motor de pos-processamento) — https://github.com/rtklibexplorer/RTKLIB/releases
- **ExifTool** (le a atitude do gimbal) — https://exiftool.org
  (renomear `exiftool(-k).exe` para `exiftool.exe`)

Do lado do Python: `pyproj`.

No `config.json`, caminho relativo vale a partir da pasta do proprio arquivo --
e o que permite o pacote instalado achar suas ferramentas em qualquer pasta.
Caminho absoluto continua funcionando.

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

O padrao (`--elmask auto`) roda **as duas**, 15 e 10 graus, e entrega a que fixa
mais. As duas rodadas nao sao desperdicio: comparar uma com a outra e a unica
conferencia independente que existe sem ponto de apoio em campo (veja
*As conferencias automaticas*).

## Resolucao de ambiguidade: continuous, nunca fix-and-hold

`pos2-armode = fix-and-hold` trava a ambiguidade e **sustenta um travamento
errado** por minutos de voo -- com selo de "solucao fixa". Medido no voo AQUARELA
(188 fotos, base a menos de 200 m, referencia = PPK do DJI Terra):

| | fotos fixas | fotos a mais de 50 cm da referencia |
|---|---|---|
| fix-and-hold | 88% | 22 |
| **continuous** | **97%** | **6** (exatamente as 6 declaradas float) |

Com `continuous`, **todas** as fotos declaradas fixas cairam dentro de 6 cm no
plano e 4 cm em altura da referencia comercial.

`pos2-gloarmode = off` pelo mesmo motivo, mas por uma razao fisica: o GLONASS e
FDMA, cada satelite transmite numa frequencia diferente, e o atraso de hardware
do receptor varia com a frequencia. Em GPS/Galileo/BeiDou esse atraso cancela na
dupla diferenca; no GLONASS so cancela se base e rover forem do mesmo fabricante.
Base ComNav com rover DJI nunca sao. O GLONASS continua entrando na **posicao**,
so sai da resolucao de ambiguidade.

## Calibracao da antena da base (ANTEX)

A altura de antena que o RINEX declara leva do marco ate o ARP -- a base fisica do
equipamento. O centro de fase, que e onde o sinal realmente e medido, fica alguns
centimetros acima disso, e quanto depende da frequencia. Na CNTT300 da base sao
75 mm em L1 e 63 mm em L2.

Sem declarar a antena, esses centimetros entram inteiros na altura de **todas** as
fotos. Medido no AQUARELA, contra o PPK do DJI Terra:

| | vies mediano em altura | fotos fixas |
|---|---|---|
| sem ANTEX | **-6 cm** | 88% |
| com ANTEX | **+1 cm** | 97% |

O programa le o modelo da antena no cabecalho do RINEX da base e procura no
`igs20_*.atx` que ja vem junto do RTKLIB -- nao precisa baixar nem guardar nada.
O RTKLIB **nao reclama** quando nao encontra a antena, so deixa de corrigir; por
isso o programa confere por conta propria e avisa.

## So a navegacao do drone

O `.NAV` do proprio voo e a unica navegacao usada. Juntar os arquivos de
navegacao da base **arrasa** a solucao: medido no AQUARELA, 96% das fotos em
solucao fixa com o `.NAV` do drone sozinho e **27%** ao acrescentar o `.26N`
(GPS) da base ComNav. Os outros arquivos da base (`.26G`, `.26C`, `.26L`) sao
inofensivos -- o estrago e so do GPS.

O drone grava as efemerides com a data rolada para 2007 (o salto de 1024 semanas
do GPS). O RTKLIB so as reencaixa na semana certa quando elas sao a unica fonte;
com as duas fontes ele alterna entre os dois conjuntos ao longo do voo e a
ambiguidade reinicia toda hora.

## Janela (uso sem linha de comando)

`PPK das Fotos.bat` abre `ppk_janela.py`, que e o jeito normal de usar. Ha um
atalho na Area de Trabalho. O fluxo e: escolher a pasta do voo, informar a base
(digitada em UTM ou lida do relatorio do IBGE-PPP) e clicar em Processar.

Se houver um relatorio do IBGE-PPP dentro da pasta do voo, a janela acha sozinha
e ja preenche a coordenada -- e o caminho preferido, porque erro de digitacao na
base desloca todas as fotos em bloco.

## As conferencias automaticas

O ponto do sistema nao e rodar o RTKLIB, e dizer se o resultado presta.

1. **Duas solucoes independentes, nas mesmas fotos.** O programa processa com
   mascara de 15 e de 10 graus e compara as duas **so nas fotos que ambas
   declararam fixas**. Trocar a mascara troca o conjunto de satelites, entao a
   ambiguidade e resolvida por outro caminho: se as duas caem no mesmo lugar,
   esta firme; se nao caem, esta trocando durante o voo. E o defeito mais
   perigoso, porque nao aparece no desvio que o RTKLIB reporta.

   A restricao **as fotos fixas nas duas** e o que torna o teste util. Sem ela,
   uma foto em float -- que pode estar metros fora em ambas sem que isso diga
   nada sobre a ambiguidade -- domina a estatistica: foi assim que a versao
   anterior acusou 84 cm de divergencia no AQUARELA, um voo em que todas as
   fotos fixas estao dentro de 4 cm em altura. Restrito as fixas, o mesmo teste
   da 0,6 cm de mediana, que e a verdade.

2. **Fotos em solucao fixa.** Com a configuracao atual um voo saudavel passa de
   90%. O que sobra em float costuma estar metros fora -- e por isso ja sai
   declarado com 1,00/2,00 m no geotag.

3. **A coordenada da base, contra o ceu.** Antes de processar, o programa
   posiciona a base sozinha por ponto simples e compara com o que foi digitado.
   Erro na base entra 1:1 em todas as fotos e **nao aparece em nenhuma
   estatistica do PPK**, porque e comum a todas as epocas. Ponto simples acerta
   poucos metros, o suficiente para pegar os dois enganos que acontecem de
   verdade: digitar altitude ortometrica no lugar da elipsoidal (5 a 10 m no
   Brasil) e trocar de marco ou errar digito.

4. **Tempo de gravacao antes da primeira foto.** Sempre entre 53 e 59 s, medido
   em dez voos. **Nao adianta esperar no chao**: o log bruto do Matrice so abre
   quando a missao de mapeamento comeca, ja em altitude de cruzeiro. E firmware.

O que **nao** funciona como conferencia, para nao se tentar de novo:

- **Passagens de ida e volta separadas.** Foi o indicador principal ate aqui e
  nao serve: `forward` e `backward` isolados sao muito piores que o `combined`
  que se entrega (50% e 42% de fixacao contra 97%), e nas epocas das fotos do
  AQUARELA elas **nunca** fixaram as duas ao mesmo tempo -- zero fotos medidas.
  Onde coincidiam era no comeco e no fim, justamente onde uma das passagens
  ainda nao convergiu, e ali discordavam metros. Condenava voo bom.
- **Fracao de epocas em comum** entre duas solucoes: com uma fixando 99% e a
  outra 4%, a intersecao fica em 4% mesmo que concordem perfeitamente.
- **Aceleracao vertical entre epocas**: deixa passar degrau espalhado por
  3 epocas.
- **Diferenca de posicao entre fotos consecutivas**: o drone se move de verdade.
- **Continuidade da trajetoria**: ambiguidade errada de forma constante da
  trajetoria lisa e deslocada.
- **O desvio formal do RTKLIB**: e otimista, nao e acuracia. Prometeu 7 mm em
  altura num voo com 19 cm de discordancia real.

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
solucao fixa  (Q=1)   0,15 / 0,30 m
float         (Q=2)   1,00 / 2,00 m
demais                2,00 / 4,00 m
```

Alem disso, a discordancia medida entre as duas mascaras vira **piso** da
precisao de cada foto: onde as duas solucoes divergem 20 cm, o geotag sai com
20 cm naquela foto. E medicao, nao estimativa.

E **voo que fixa menos de 70% nao tem a solucao fixa levada a serio**: as fotos
que ele declara fixas saem com 0,50/1,00 m. A mesma fragilidade que impediu a
fixacao no resto do voo tambem trava a ambiguidade no inteiro errado onde ela
fixa. Medido na FAZ SAO JORGE contra o PPK do DJI Terra:

| fixacao do voo | fotos fixas erradas por mais de 20 cm |
|---|---|
| 92%, 95% e 100% | **0** de 977 |
| 26% | **45** de 129, uma delas 2,05 m |

O piso das mascaras nao pega esse caso: as duas mascaras erraram juntas, e
concordaram em 0,0 cm. So a taxa de fixacao do voo denuncia.

`--sigma formal` volta a escrever o desvio do RTKLIB, util so para conferencia.

### Por que os numeros sao folgados

O peso entra no ajuste como `exp(-residuo^2 / 2*sigma^2)`. Uma foto declarada com
5 cm e que esteja 1 m fora vale `exp(-200)` -- que em ponto flutuante e zero.
Isso nao degrada devagar, **quebra**: no AQUARELA o Pix4D chegou a 2.170.541
pontos de amarracao, os pesos deram underflow (`GaussNoise: non-positive
weightSum 1.18733e-119`), os pontos cairam para 19.887 -- perda de 99,1% -- e o
passo 1 abortou com `Caught unknown exception during initial processing`. A
precisao declarada era 0,05/0,10 m e o residuo real medido pelo proprio Pix4D
tinha media de 1,14 m e maximo de 28 m.

Declarar mais aperto do que a solucao entrega nao melhora nada: so tira do ajuste
a liberdade de corrigir o geotag pela geometria das imagens, que e justamente o
que ele faz melhor que o GNSS.

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
