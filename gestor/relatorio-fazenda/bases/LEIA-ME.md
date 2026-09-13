# Bases do Relatório da Fazenda

O programa varre estas pastas sozinho. Cadastro (CAR e SIGEF) é consultado **ao
vivo** e só cai para arquivo em disco se o serviço não responder; as tabelas de
valor e de módulo fiscal são sempre lidas daqui.

| Pasta | O que tem | Fonte oficial | Versão |
|---|---|---|---|
| `VTN/` | `vtn_2026.csv` — Valor da Terra Nua por município e aptidão, 3.078 municípios | Receita Federal, *Valores de Terra Nua 2026* ([página](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/vtn)), arquivo `tabela-vtn-2026-para-publicacao-5.pdf` | 5ª versão publicada, baixada em 13/09/2026 |
| `MERCADO/` | `mercado_ms_2024.csv` — preços referenciais (VTI e VTN mínimo/mediano/máximo) dos 15 mercados regionais de MS; `mercado_municipios_ms_2024.csv` — em qual mercado está cada um dos 79 municípios | INCRA/SR-16, *Relatório de Análise de Mercado de Terras de MS 2024* ([página](https://www.gov.br/incra/pt-br/assuntos/governanca-fundiaria/relatorio-de-analise-de-mercados-de-terras/mato-grosso-do-sul)), tabelas 2 e 6 a 20 | RAMT 2024, baixado em 13/09/2026 |
| `MODULO_FISCAL/` | `modulo_fiscal_2013.csv` — módulo fiscal por código IBGE, 5.462 municípios | INCRA, *Tabela de Índices Básicos do SNCR 2013* ([PDF](https://www.gov.br/incra/pt-br/acesso-a-informacao/indices_basicos_2013_por_municipio.pdf)) | reserva: o relatório usa o módulo que o próprio CAR declara |
| `CAR/` | vazio — opcional | consultapublica.car.gov.br › Base de Downloads › AREA_IMOVEL | só se o WFS do SICAR cair |
| `SIGEF/` | vazio — opcional | acervofundiario.incra.gov.br › parcelas certificadas por UF | só se o WFS do INCRA cair |

## Como os CSV foram extraídos

Os três vieram de PDF e foram convertidos por leitura de texto, conferindo
contagem e casos conhecidos:

- **VTN 2026.** Nenhuma linha do PDF ficou sem virar registro. 319 municípios
  têm alguma aptidão como *s/informação* no original: a célula fica vazia no
  CSV e o relatório imprime "sem informação" — não zero. Um valor veio digitado
  com ponto decimal na fonte (`7.046.16`, Paracatu/MG) e foi lido como
  7.046,16. A coluna `fonte` segue a nota da Receita: 1 = informado pelo
  município, 2 = por órgão estadual.
- **RAMT MS 2024.** 76 preços, 19 tipologias. O próprio INCRA publicou 4 linhas
  incoerentes, marcadas na coluna `inconsistencia_na_fonte` e sinalizadas no
  relatório em vez de corrigidas por conta própria:
  - MRT-03 Campo Grande, *Pecuária: Pastagem Formada* — VTN mediano
    (R$ 48.650) maior que o VTI mediano (R$ 36.896);
  - MRT-09 Corumbá, *Pastagem Formada de Média Capacidade* e *Formada/Nativa –
    Pantanal* — VTN mínimo maior que o mediano;
  - MRT-11 Nova Andradina, *Pastagem Formada de Baixa Capacidade em Taquarussu e
    Batayporã* — VTN máximo menor que o mediano.
- **Módulo fiscal 2013.** Campo Grande 15 ha, Sidrolândia 30 ha, Dourados
  30 ha, conferidos. É tabela de reserva: municípios criados depois de 2013
  (Paraíso das Águas, por exemplo) não estão nela, e o módulo que o CAR declara
  é o que o SICAR usa hoje.

## Para outros estados

- **VTN** já é nacional.
- **Mercado de terras**: baixe o RAMT do estado na página do INCRA e gere os dois
  CSV no mesmo formato — `mercado_<uf>_<ano>.csv` (colunas `uf;mrt;mercado;
  nivel;uso;vti_min;vti_mediano;vti_max;vtn_min;vtn_mediano;vtn_max;
  inconsistencia_na_fonte`) e `mercado_municipios_<uf>_<ano>.csv` (colunas
  `uf;municipio;mrt;mercado`). Sem eles, o capítulo de mercado diz que não há
  tabela para o município — não usa média de outro lugar.

## Atualizar

- VTN: todo ano, quando a Receita publica a tabela do exercício (agosto).
- RAMT: quando o INCRA publicar a revisão do estado.

Tabela de outro formato também é lida: o leitor procura as colunas pelo nome e
ignora de propósito as que têm número mas não são valor por hectare — código
IBGE, ano, exercício, área, fonte. Era isso que fazia o gerador original
imprimir o código do município como preço.
