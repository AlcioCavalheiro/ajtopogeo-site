---
name: analise-analytics-seo
description: Rotina semanal de análise de Google Analytics (GA4) e Search Console — levanta o que mudou na semana (tráfego, buscas, páginas, cliques em WhatsApp/e-mail/formulário), checa a saúde técnica do site (sitemap, status HTTP, canonical), decide e aplica alterações seguras, e entrega um PDF com os dados e o que foi feito. Use quando o usuário pedir "análise semanal de analytics", "o que mudou no Google Analytics/Search Console", "radar de SEO", ou rodar a rotina semanal de dados do site.
---

# Rotina 8 — Analytics + Search Console semanal

Cadência: semanal, sugestão quinta-feira de manhã (os outros dias fixos já
estão ocupados: segunda `/cobranca-os`, terça `/radar-noticias`, quarta e
sexta `/conteudo-instagram`, sexta `/checkpoint-gestor`).

Objetivo: tirar SEO técnico do modo "só mexe quando alguém percebe que caiu"
(foi assim que nasceu [[seo-canonical-cleanurls-fix]]) e dar um retrato semanal
de tráfego + geração de contato pelo site.

**Diferença importante em relação às outras rotinas de conteúdo:** aqui o
usuário pediu para a rotina **aplicar e commitar sozinha** as correções
técnicas que encontrar — não é para perguntar antes. Mas isso vale só para
**correções técnicas** (ver "O que pode ser alterado sozinho" abaixo); a
rotina nunca dá `git push` (deploy é decisão do usuário, mesmo padrão de
[[rotinas-operacionais]]) e nunca escreve conteúdo novo sozinha.

## Pré-requisito: credenciais

Lê de `C:\Users\ALCIO\.ajtopogeo\google_analytics.env` (formato `CHAVE=VALOR`,
exemplo em `google_analytics.env.exemplo` na mesma pasta):

```
GOOGLE_APPLICATION_CREDENTIALS=C:\Users\ALCIO\.ajtopogeo\credentials\google-analytics-sa.json
GA4_PROPERTY_ID=123456789
GSC_SITE_URL=https://ajtopogeo.com.br/
```

Se o arquivo não existir ou a chave apontada não existir, **pare e avise o
usuário** — não dá para inventar número. O passo a passo de como gerar essas
credenciais (service account no Google Cloud + acesso no GA4 + acesso no
Search Console) foi dado na conversa que criou esta skill; se precisar
repetir, é: criar service account, ativar Analytics Data API e Search Console
API, baixar a chave JSON, adicionar o e-mail da service account como
Visualizador no GA4 (Administrador → Acesso à propriedade) e como usuário
Completo no Search Console (Configurações → Usuários e permissões).

## Ambiente

Mesmo venv das outras rotinas:

```
C:\Users\ALCIO\.ajtopogeo\venv\Scripts\python.exe
```

Pacotes usados por esta rotina: `google-analytics-data`,
`google-api-python-client`, `google-auth` (já instalados nele), mais
`reportlab` (já usado por `relatorio_geral_pdf.py`).

## Modo retomável — rodar sob `/loop` sem perder o trabalho no meio

Mesmo padrão descrito em [[modo-retomavel-rotinas]] (piloto: `/radar-noticias`).
Esta rotina mistura chamada de API, decisão e edição de código — pode não
caber inteira numa execução só.

**Arquivo de estado:** `C:\Users\ALCIO\.ajtopogeo\estado\analise-analytics-seo.json`

No começo de toda execução, carregue o estado:
- **Não existe**, ou existe com `concluido: true` → rodada nova (semana nova):
  crie/zere o estado com todos os passos `pendente`.
- **Existe com `concluido: false`** → retome: pule os passos `feito` e
  continue do primeiro `pendente`, reusando o `dossie_path` já gravado.

Grave o estado logo após concluir cada passo, antes de começar o próximo.

| passo | campo | `feito` quando |
| --- | --- | --- |
| 1 Coletar dados | `coletar` | `dossie.json` existe com `gerado_em` de hoje |
| 2 Analisar e decidir | `analisar` | `dossie["analise"]` está preenchido (destaques + oportunidades) |
| 3 Aplicar correções técnicas | `aplicar` | `dossie["decisoes"]` reflete tudo que foi alterado, e cada alteração já tem commit local |
| 4 Gerar PDF | `pdf` | o PDF existe na pasta de saída |
| 5 Registrar histórico | `registrar` | a entrada está em `rotinas/analise-analytics-historico.json` |
| 6 Entregar | `entregar` | o resumo em prosa + PDF foram entregues ao usuário |

Idempotência: o coletor sobrescreve o `dossie.json` sem problema (reexecutar
é seguro); o PDF é sobrescrito também. A única coisa que não é idempotente é
"aplicar correções" — por isso o passo 3 só é `feito` quando cada item de
`decisoes` já tem um commit associado; se cortar no meio de uma edição,
confira `git status` antes de continuar para não duplicar a correção.

Ao terminar o passo 6, grave `concluido: true` e, se estiver sob `/loop`,
encerre o loop.

Esquema do estado:

```json
{
  "rotina": "analise-analytics-seo",
  "atualizado_em": "2026-09-17T08:00:00-04:00",
  "dossie_path": "C:\\...\\scratchpad\\dossie.json",
  "pdf_path": "",
  "passos": {
    "coletar": "pendente", "analisar": "pendente", "aplicar": "pendente",
    "pdf": "pendente", "registrar": "pendente", "entregar": "pendente"
  },
  "concluido": false
}
```

## Passo 1 — Coletar

```
py rotinas/coletar_analytics_gsc.py <caminho>/dossie.json
```

Compara a última semana fechada (segunda a domingo) com a anterior. Também
baixa `sitemap.xml` do site em produção e confere, para cada URL: status HTTP
200 e tag `canonical` apontando para a própria URL limpa (sem `.html`) — é
exatamente a classe de bug que gerou [[seo-canonical-cleanurls-fix]] e a
redireção do `/topografia-servicos` no histórico do repo.

Grave `dossie_path` no estado e marque `coletar: feito`.

## Passo 2 — Analisar e decidir

Leia o `dossie.json`. Você (o agente) é quem decide — o script só levanta
número. Preencha `dossie["analise"]`:

```jsonc
{
  "destaques": ["frase curta com o que mais chama atenção na semana"],
  "oportunidades": [
    {"titulo": "...", "detalhe": "o que foi visto e por que importa"}
  ]
}
```

Sinais para olhar:

- **Queda de tráfego numa página com volume relevante** (>=20 sessões na
  semana anterior e queda >30%): confira primeiro se é sazonalidade/coincidência
  ou se a "Saúde técnica" apontou problema nela (404, canonical errado). Não
  afirme causa que não confirmou.
- **Busca com impressões razoáveis (>=20) e CTR bem abaixo da média do site,
  em posição <=20**: candidata a melhorar título/meta description da página —
  o conteúdo já rankeia, só não converte clique.
- **Consulta nova ganhando impressão** (não aparecia na semana anterior nem
  no histórico) **sem página dedicada no site**: é oportunidade de conteúdo,
  não de correção técnica — registre como oportunidade e sugira ao usuário
  rodar `/radar-noticias` ou criar página nova depois. **Não escreva a página
  sozinho aqui** (ver limite abaixo).
- **Cliques em WhatsApp/e-mail/formulário caindo** enquanto sessões sobem (ou
  vice-versa): vale destacar, é o sinal mais direto de "o site gera contato".
- **Problema em "Saúde técnica do site"**: qualquer 404, canonical ausente ou
  divergente é sempre uma correção técnica válida — vá para o Passo 3.

Marque `analisar: feito`.

## Passo 3 — Aplicar correções técnicas

### O que pode ser alterado sozinho (aplica e commita, sem perguntar)

- Página do sitemap devolvendo 404/redirecionando errado → corrigir link
  quebrado ou adicionar redirect em `vercel.json` (mesmo padrão do commit
  que corrigiu `/topografia-servicos`).
- Tag `canonical` ausente ou apontando para URL errada (com `.html`, sem
  barra final inconsistente, etc.) → corrigir para a URL limpa da própria
  página.
- Título (`<title>`) ou meta description fracos numa página com oportunidade
  clara de CTR (sinal do Passo 2) → reescrever mantendo a palavra-chave que já
  rankeia, sem inventar dado (preço, prazo) que não está confirmado em outro
  lugar do site.
- Entrada faltando ou desatualizada no `sitemap.xml` para página que existe e
  está sendo indexada.

Para cada alteração: edite o arquivo, rode `git add <arquivo>` e
`git commit` com mensagem curta explicando o motivo (mesmo estilo dos commits
recentes do repo — objetivo, sem jargão). **Nunca `git push`.** Registre em
`dossie["decisoes"]`:

```jsonc
{"titulo": "...", "arquivo": "caminho/do/arquivo", "descricao": "o que mudou e por quê"}
```

### O que NÃO é para fazer sozinho

- Escrever página nova de conteúdo (isso é `/radar-noticias` ou pedido
  explícito do usuário — precisa de curadoria editorial, não é correção).
- Mexer em preço, dado de contato, CRECI ou qualquer conteúdo que envolva
  fato do negócio.
- Mexer no Gestor, Supabase ou schema — esta rotina só toca o site público
  (HTML/JS estático da raiz do repo e `vercel.json`).
- Se nada precisar de correção nesta semana, tudo bem: deixe `decisoes: []`
  e siga em frente. Não force alteração para preencher a seção do relatório.

Marque `aplicar: feito` (mesmo se `decisoes` ficou vazio).

## Passo 4 — Gerar o PDF

```
py rotinas/analise_analytics_pdf.py <dossie.json> <saida>/analytics-<data>.pdf
```

Marque `pdf: feito`.

## Passo 5 — Registrar no histórico

Acrescente uma entrada em `rotinas/analise-analytics-historico.json` (versionado,
sem dado de cliente — só métricas agregadas do site):

```jsonc
{
  "data": "2026-09-17",
  "periodo_atual": ["2026-09-07", "2026-09-13"],
  "sessoes": 412, "cliques_busca": 140, "impressoes_busca": 5200,
  "decisoes": ["título da correção 1", "título da correção 2"]
}
```

Isso serve para o Passo 2 de rodadas futuras não repetir sugestão de
oportunidade já tratada. Se editar este arquivo, inclua no mesmo commit das
correções técnicas (ou um commit próprio "registra histórico da rotina").

Marque `registrar: feito`.

## Passo 6 — Entregar

Mande o PDF ao usuário e resuma em texto curto: o número principal da semana
(tráfego/cliques/posição, com seta de variação), o que foi corrigido (se
houve) e, se houver oportunidade de conteúdo identificada, mencione que ficou
registrada para uma próxima rodada de `/radar-noticias` ou decisão do usuário
— não decida sozinho criar a página.

Marque `entregar: feito` e `concluido: true`.
