# Recomendação de Solo (calagem e adubação)

Página do Gestor em **Ferramentas → Recomendação de Solo**. O técnico digita o laudo,
escolhe o método (Boletim 100 2022, 5ª Aproximação MG ou Embrapa Cerrados) e a cultura,
e recebe calagem, gessagem, N-P₂O₅-K₂O por época, S, micronutrientes, produtos comerciais
(kg/ha, total da área, sacos de 50 kg) e as observações do boletim.

Regras, fórmulas e casos de teste: [ESPECIFICACAO.md](ESPECIFICACAO.md).

## Arquivos

| Arquivo | O que é |
|---|---|
| `tabelas.js` | Tabelas das publicações (`DEF`, `MGP`, `MICRO`). Corpo em JSON puro; cada cultura tem `fonte`. **Não mudar número sem conferir no PDF.** |
| `motor.js` | Motor de cálculo: funções puras, sem DOM. `SoloMotor.calcular(entrada, tabelas)` devolve um objeto com todos os resultados. |
| `leitor-laudo.js` | Leitor do laudo em PDF: `interpretar()` (puro, testado) transforma o texto do PDF em amostras; `lerPdf()` usa o pdf.js do Gestor. |
| `solo.js` | Interface: formulário, importação do PDF, resultado, laudos salvos, editor das tabelas, impressão. Não faz conta. |
| `test/motor.test.js` | Testes do motor com os casos da especificação. |
| `test/leitor.test.js` + `test/laudos/*.json` | Testes do leitor com laudos reais (só texto e posição, nomes trocados). |

## Importar laudo em PDF

Botão **Importar laudo em PDF** no card do laudo. Lê PDFs com texto (os gerados pelo
sistema do laboratório); PDF escaneado ou foto não tem texto e o leitor avisa. Se o laudo
tiver várias amostras, o técnico escolhe qual é 0–20 e qual é 20–40 (vem sugerido pela
profundidade na descrição). Os campos preenchidos ficam destacados para conferência.

O leitor não é preso a um laboratório: reconhece tabela "uma linha por determinação"
(ex.: laboratório de Campo Grande-MS) e "uma linha por amostra" (ex.: laboratório de SP).
**Laboratório novo que não for lido direito:** gere o JSON do PDF (texto + posição, como os
de `test/laudos/`, trocando nomes de pessoas), crie o teste com os valores esperados e
ajuste os `ROTULOS` ou o formato em `leitor-laudo.js` até passar.

Os três `.js` carregam por `<script>` no `gestor/index.html` (funciona em `file://` e offline)
e por `require()` nos testes. Sem build, sem dependências — mesmo padrão do resto do Gestor.

## Testes

Na raiz do SITE (precisa do Node 22 ou mais novo):

```
node --test "gestor/solo/test/*.test.js"
```

Regra nova ou mudança de tabela → caso novo no teste.

## Dados guardados

No `localStorage` do navegador (como no protótipo):

- `gestor-solo:laudos` — laudos salvos por cliente/talhão (até 100);
- `gestor-solo:cfg` — tabelas de cultura editadas pelo usuário (só as que diferem do original).

## Offline

`gestor/sw.js` pré-carrega os `.js` desta pasta e o pdf.js (importar laudo sem sinal). O service worker serve scripts do cache
primeiro: **ao alterar qualquer arquivo daqui, suba a versão de `CACHE` em `gestor/sw.js`**
(ex.: `gestor-v3` → `gestor-v4`), senão quem já instalou continua com a versão antiga.

## Deploy

`test/` e os `.md` desta pasta estão no `.vercelignore`; os `.js` precisam ir para o site.
