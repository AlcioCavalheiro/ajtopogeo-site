# Consulta de Cota

Devolve a cota de coordenadas sobre um modelo digital (DSM ou DTM). Abre pelo
atalho "Consulta de Cota" na Area de Trabalho.

Fluxo: escolher o `.tif` do modelo, colar a lista de coordenadas, Consultar.
O resultado sai em tabela e pode ser copiado ou salvo em CSV.

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

**Sigma do levantamento** (opcional, digitado, igual para todos os pontos). Vem
do relatorio de processamento -- no Portal das Flores, o RMS vertical do bloco
foi 14,1 mm. Se preenchido, a coluna **Sigma total** combina os dois por
`raiz(local^2 + levantamento^2)`.

Nenhum dos dois cobre erro sistematico da base: se a coordenada do marco estiver
errada, todo o modelo desloca junto e nenhuma dessas contas percebe. Para isso so
ponto de apoio medido em campo.
