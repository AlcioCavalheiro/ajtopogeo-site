---
name: triagem-imovel
description: Triagem inicial de matrícula e documentação de um imóvel novo — lê matrícula/CAR/CCIR/ITR, devolve resumo estruturado (cadeia dominial, ônus, áreas, inconsistências) e monta a pasta padrão no Drive. Use ao entrar projeto novo, ou quando o usuário mandar matrícula/CAR/CCIR para análise.
---

# Rotina 2 — Triagem de matrícula/documentação

Cadência: sob demanda, no início de cada projeto. Objetivo: visão estruturada
do imóvel **antes** de orçar e antes de ir a campo.

## Entrada

O usuário envia matrícula, CAR, CCIR e/ou ITR (PDF ou texto). Se algum estiver
faltando, siga com o que tem e liste o que falta — não trave a triagem.

## Passo 1 — Criar a pasta padrão

Estrutura em `G:\Meu Drive\EMPRESA\AJ TOPOGEO\TOPOGRAFIA\SERVIÇOS\EM EXECUÇÃO\<NOME>\`:

```
01_DOCUMENTOS/        matrícula, CCIR, ITR, CAR, CNH/CPF, procuração
02_CONTRATO/          proposta, contrato, ART/TRT
03_LEVANTAMENTO/      dados brutos de campo
    BASE/             RINEX e log da base, ponto de apoio
    ROVER/            pontos coletados, cadernetas, arquivo bruto do receptor
    DRONE/            imagens do voo, log, GCPs, plano de voo
04_PROCESSAMENTO/     dados pós-processados
    GPS/              pós-processado GNSS, relatório, coordenadas ajustadas
    DRONE/            ortomosaico, nuvem de pontos, MDS/MDT, relatório
05_DESENHO/           dwg, dxf, plotagens
06_ODS/               planilhas ODS do SIGEF (perímetro, vértices, confrontantes)
07_ENTREGAVEIS/
    MAPA/             plantas finais, assinadas e não assinadas
    MEMORIAL/         memorial descritivo, versões e assinado
    INCRA/            pacote de certificação, recibos, certificado
08_REQUERIMENTOS/     anuência, cartório, zoneamento, comprobatória, cancelamento
09_PROTOCOLO/         protocolos, exigências e respostas (INCRA/cartório/prefeitura)
10_TRIAGEM/           este resumo e anexos de análise
```

Regras:
- `<NOME>` segue o padrão já usado na pasta: nome do cliente ou da área em
  CAIXA ALTA, sem acento. Olhe os vizinhos em EM EXECUÇÃO e siga o estilo.
- Alguns clientes são intermediários com várias áreas sob o mesmo nome. Nesses,
  a área nova entra como subpasta dele, não na raiz de EM EXECUÇÃO. Confirme
  com o usuário quando não estiver claro qual é o caso.
- Este repositório é público: não escreva nome de cliente, telefone, valor de
  contrato ou número de matrícula em nenhum arquivo versionado.
- **Nunca reorganize pasta de projeto já existente.** As antigas são planas e
  mexer nelas quebra caminhos de DWG e atalhos. O padrão vale para projeto novo.
- Confirme com o usuário antes de criar se já existir pasta com nome parecido.

Depois salve cada arquivo recebido em `01_DOCUMENTOS/`.

## Passo 2 — Extrair o texto antes de analisar

Com os arquivos já em `01_DOCUMENTOS/`, rode:

```
C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe .claude\skills\triagem-imovel\scripts\extrair_texto.py "<pasta do projeto>"
```

O script converte PDF, DOCX, planilha e e-mail em `.md` dentro de
`10_TRIAGEM/_texto/`, e passa OCR em português nos PDFs escaneados (matrícula
de cartório, quase sempre). No fim escreve `_texto/_INDICE.md` com o status de
cada arquivo.

Analise a partir desses `.md` — é onde os números ficam confiáveis para
conferência. Mas:

- Todo arquivo com status `SEM TEXTO`, `FALHOU` ou `IGNORADO` no índice tem
  que ser lido no original antes de fechar a triagem. Não conclua sem ele.
- Tabela de vértices, coordenadas e confrontantes: use a seção **Tabelas
  reextraídas**, no fim do `.md`. O corpo do texto sai com a tabela achatada
  em células soltas, e ali é fácil colar a coordenada no vértice errado.
- Em documento que passou por OCR (status `OCR` no índice), **rumo, azimute e
  distância da descrição perimétrica nunca valem sem conferência no original.**
  Em matrícula datilografada antiga o Tesseract troca `º` por `9`, `"` por `!`
  e `4` por `h` — `144,00` virou `14h,00`, `S 8º 35' E` virou `S 89 35! E`.
  O erro é plausível o bastante para passar despercebido.
- Vale o mesmo para área, matrícula nº, CPF/CNPJ, data e fração de condomínio.
  O `.md` é ponto de partida, não fonte final.
- O `_texto/` tem dado de cliente. Fica no Drive, nunca no repositório.

## Passo 3 — Resumo estruturado

Sempre nesta ordem, em `10_TRIAGEM/triagem-<NOME>.md`:

**1. Identificação** — matrícula nº, cartório/comarca, denominação, município,
código INCRA/CCIR, NIRF.

**2. Proprietário(s) atual(is)** — nome, CPF/CNPJ, estado civil e regime de bens
(importa para quem assina), fração de cada um se houver condomínio.

**3. Cadeia dominial resumida** — do registro mais antigo legível até o atual,
uma linha por transmissão: `R-x / AV-x — data — natureza — de quem para quem`.
Marque saltos ou lacunas.

**4. Ônus e gravames** — hipoteca, penhora, usufruto, servidão, alienação
fiduciária, indisponibilidade, reserva legal averbada. Cada um com o número do
ato e se está ativo ou baixado. **Ônus ativo é impeditivo de certificação** —
destaque.

**5. Áreas** — tabela comparando: área registrada (matrícula), área CAR, área
CCIR/ITR e área medida (se já houver). Calcule a divergência em ha e %.

**6. Situação ambiental** — status do CAR (ativo/pendente/cancelado), reserva
legal (averbada? proposta? déficit?), APP, PRADA, CANI, autos do IMASUL.

**7. Inconsistências** — o valor da triagem está aqui. Verifique no mínimo:
- datum das coordenadas do memorial antigo (SAD-69 x SIRGAS2000) e se há
  necessidade de transformação;
- divergência de área registrada vs. CAR acima de 5%;
- confrontantes citados na matrícula que não batem com o CAR;
- descrição perimétrica sem azimute/distância (matrícula antiga, "descrição
  tabular") — indica retificação provável;
- sobreposição potencial com parcelas SIGEF vizinhas;
- imóvel com área abaixo da fração mínima de parcelamento, se houver
  desmembramento pretendido.

**8. Impacto no orçamento e no campo** — o que cada pendência acima significa
em serviço extra (retificação de área, georreferenciamento de confrontante,
retificação de CAR, anuência de confrontante) e o que a equipe precisa saber
antes de sair (acesso, cercas, marcos existentes, época de chuva).

**9. O que falta** — documentos ainda não recebidos, listados para o usuário pedir.

## Passo 4 — Croqui

Havendo coordenadas utilizáveis (memorial, KML, shapefile, CAR), gere o DXF do
perímetro em `10_TRIAGEM/`.

**Não havendo, gere assim mesmo, com o que a matrícula descrever.** Matrícula
antiga costuma dar rumo e distância de alguns alinhamentos e resolver o resto
com divisa natural ("segue o córrego", "acompanha a serra"). Monte o spec e
rode:

```
C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe .claude\skills\triagem-imovel\scripts\croqui.py "<pasta>\spec-<NOME>.json"
```

O script desenha em escala o que está descrito e fecha o resto com um arco
dimensionado para a figura encerrar a área registral. Sai também um
`croqui-<NOME>.md` com o percentual arbitrado do perímetro.

Regras:
- **O que foi arbitrado tem que se identificar sozinho.** O script já põe
  camada separada, tracejado vermelho, rótulo repetido ao longo do traço e
  bloco de aviso no DXF. Não remova nada disso, e não entregue o croqui
  convertido em PDF/imagem sem esses elementos.
- Cite sempre o percentual arbitrado no resumo da triagem. Um croqui 78%
  arbitrado e um 5% arbitrado não são o mesmo documento.
- O croqui **não tem georreferência** — é forma e dimensão em coordenada
  local. Nunca o apresente como localização.
- Se nem rumo houver, aí sim não há croqui. Diga isso explicitamente.

## Regra de ouro

Você lê documento jurídico e aponta o que está escrito e o que não fecha.
Onde a leitura for ambígua (carimbo ilegível, averbação truncada), escreva
"ilegível — conferir no original" em vez de preencher a lacuna por dedução.
Um dado inventado numa triagem vira erro de orçamento e retrabalho em campo.
