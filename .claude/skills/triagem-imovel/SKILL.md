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
- `<NOME>` segue o padrão já usado na pasta: nome do cliente em CAIXA ALTA,
  sem acento (ex: `NAGATOMO`, `AREA BANDEIRANTES`).
- Se o cliente for um intermediário com várias áreas (padrão `LUCAS AMBIENTAL`),
  crie como subpasta dele, não na raiz de EM EXECUÇÃO.
- **Nunca reorganize pasta de projeto já existente.** As antigas são planas e
  mexer nelas quebra caminhos de DWG e atalhos. O padrão vale para projeto novo.
- Confirme com o usuário antes de criar se já existir pasta com nome parecido.

Depois salve cada arquivo recebido em `01_DOCUMENTOS/`.

## Passo 2 — Resumo estruturado

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

## Passo 3 — Croqui

Se houver coordenadas utilizáveis (memorial descritivo, KML, shapefile, CAR),
gere um DXF do perímetro em `10_TRIAGEM/`. Se não houver, diga explicitamente
que não houve — não gere croqui a partir de área estimada.

## Regra de ouro

Você lê documento jurídico e aponta o que está escrito e o que não fecha.
Onde a leitura for ambígua (carimbo ilegível, averbação truncada), escreva
"ilegível — conferir no original" em vez de preencher a lacuna por dedução.
Um dado inventado numa triagem vira erro de orçamento e retrabalho em campo.
