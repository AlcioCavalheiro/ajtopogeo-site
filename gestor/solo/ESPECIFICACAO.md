# Recomendação de calagem e adubação — especificação para implementação

## Objetivo
Aplicativo onde o técnico digita o laudo de análise de solo, escolhe o método (literatura) e a cultura, e recebe:
calagem, gessagem, N-P₂O₅-K₂O por época, S e micronutrientes, conversão para produtos comerciais (kg/ha, total da área, sacos de 50 kg) e observações do boletim.

Usuário: técnico em agrimensura/corretor que atende produtores rurais em Mato Grosso do Sul. Uso em campo, principalmente no celular. Interface em português.

## O que já existe
- `prototipo/recomendacao-solo.html`: protótipo funcional em HTML + JS puro, sem build. É a referência de comportamento e dos cálculos. Toda a lógica está no `<script>` no fim do arquivo.
- `dados/tabelas.json`: tabelas extraídas das publicações, no formato que o protótipo usa (`DEF`, `MGP`, `MICRO`).
- `docs/` (o usuário vai copiar): PDFs originais — Boletim 100 (2022), 5ª Aproximação MG (1999), Cerrado: correção do solo e adubação (escaneado), Recomendações para Goiás (1988, não usado).

## Tarefa sugerida
1. Transformar o protótipo em projeto organizado, separando **dados** (JSON), **motor de cálculo** (funções puras, testáveis) e **interface**.
2. Escrever testes automatizados do motor com os casos da seção "Casos de teste". Os resultados precisam bater.
3. Manter o funcionamento offline e responsivo (uso no campo).
4. Pergunte ao usuário a stack desejada antes de escolher. Sugestão padrão: TypeScript + Vite + React (ou PWA simples), motor em `src/engine/` sem dependência de UI.
5. Não alterar números das tabelas sem conferir no PDF de origem. Toda tabela tem campo `fonte`.

## Unidades e grandezas
- Internamente, cátions em **cmolc/dm³**. Entrada pode ser mmolc/dm³ (÷10) ou cmolc/dm³. K pode vir em mg/dm³ (÷391 → cmolc).
- SB = Ca + Mg + K; T (CTC pH 7) = SB + H+Al; V% = SB/T×100; CTCe = SB + Al; m% = Al/CTCe×100.
- Subsuperfície (20–40 cm): Ca, Mg, K, Al e H+Al → m₂ e V₂.
- Fator de profundidade da calagem = profundidade (cm) / 20.

## Métodos

### 1. Boletim 100 — IAC, edição 2022 (SP) — P em resina
- Calagem: NC (t/ha) = CTC(mmolc) × (V2 − V1) / (10 × PRNT). Equivale a (V2−V)×T(cmolc)/PRNT.
- Cana-planta: mínimo 1,5 t/ha (PRNT 100%) quando houver calagem.
- Classes gerais (anuais): P resina <7 MB, 7–15 B, 16–40 M, 41–80 A, >80 MA. K: <1,6 B, 1,6–3,0 M, 3,1–6,0 A, >6,0 MA.
- Tabelas por cultura: colunas de P e K com limites "menor que" (`lt`), linhas por produtividade esperada (`prod`). Valor `null` = produtividade improvável → usar faixa anterior e avisar.
- N: `Npl` (plantio) + `Ncob`/`NcobFix` ou `Ntot` (total; cobertura = total − plantio). Classes de resposta a N: alta / média-baixa.
- Regras especiais por cultura (ver JSON): `Ksulco` (máx. K₂O no sulco, excedente → cobertura), `NKsulco` (milho/sorgo: N+K₂O ≤ 80 no sulco), `Pzero` (P > 80 → só arranque), `Kzero` (K > 6 mmolc → sem K), `fosfatagem` (soja: P ≤ 6 → 100 kg/ha P₂O₅ a lanço), `fosfCana` (P < 7 → 120 kg/ha se argila ≤ 25%, senão 150, e 150 no sulco), `NredMO` (mandioca: M.O. > 20 → N × 0,7), `Kcob` (mandioca), `S` (fixo por produtividade ou por t esperada; soja só se S 20–40 < 15), `micro` (lista [limite, dose]: aplica a primeira regra em que teor < limite).
- Gesso (dose = 6 × argila em g/kg):
  - cana: V₂ < 40% ou m₂ > 30% (camada 25–50 cm);
  - forrageiras: V₂ < 25% ou m₂ > 50%;
  - grãos: a edição 2022 não traz critério geral → usar o da edição 1997: Ca₂ < 4 mmolc/dm³ ou m₂ > 40%. Informar isso no resultado.
- Micronutrientes (anuais): B <0,20 / 0,20–0,60 / >0,60; Cu <0,3 / 0,3–0,8; Fe <5 / 5–12; Mn <1,5 / 1,5–5,0; Zn <0,6 / 0,6–1,2.

### 2. 5ª Aproximação — CFSEMG 1999 (MG) — P e K em Mehlich-1
- Calagem pelos dois métodos (mostrar ambos; total da área pelo maior):
  - V%: NC = T × (Ve − Va)/100 × 100/PRNT.
  - Al e Ca+Mg: NC = [Y × (Al − mt × CTCe/100) + (X − (Ca+Mg))] × 100/PRNT, termos negativos = 0. Y = 0,0302 + 0,06532·argila − 0,000257·argila². mt, X e Ve por cultura (Quadro 8.1).
  - Cana: também NC = 3 − (Ca+Mg).
  - Respeitar `maxCal` (t/ha por aplicação).
- P por argila (limites ≤ MB/B/M/Bom): 60–100%: 2,7/5,4/8,0/12,0; 35–60%: 4,0/8,0/12,0/18,0; 15–35%: 6,6/12,0/20,0/30,0; 0–15%: 10/20/30/45. K: 15/40/70/120 mg/dm³.
- Disponibilidade das tabelas das culturas: Baixa = MB + B; Média = M; Boa = Bom + Muito bom.
- Mandioca tem classes próprias por textura (argilosa ≤3/6/10; média ≤5/10/15; arenosa ≤7/15/20 mg/dm³; K ≤20/40/60).
- Gesso: Ca₂ ≤ 0,4, Al₂ > 0,5 ou m₂ > 30% (cana: Ca₂ < 0,4 ou m₂ > 40%). Dose interpolada pela argila (Quadro 10.1): 0→0; 15→0,4; 35→0,8; 60→1,2; 100→1,6 t/ha para camada de 20 cm.

### 3. Embrapa Cerrados (Sousa & Lobato 2004; Embrapa Soja 2020)
- Calagem pelos dois métodos (mesma fórmula do Al acima).
- P (6 classes) por Mehlich-1 conforme argila, ou resina: ver `PmehLims`/`PresLims`.
- Fosfatagem corretiva = (nível crítico − P atual) × CTP, com nível crítico e CTP por faixa de argila (`bandas`, `NCmeh`, `CTPmeh`, `NCres`, `CTPres`). Arredondar a 5 kg.
- Manutenção P: kg P₂O₅/t × produtividade (até adequado / alto / muito alto).
- K (Vilela 2004): CTC < 4: ≤15 B, 16–30 M, 31–40 Adeq, >40 A; CTC ≥ 4: ≤25, 26–50, 51–80, >80. Corretiva total: B 50/100, M 25/50; gradual: B 70/80, M 60. Manutenção K₂O/t; classe alta = 50%.
- Modo "total" (lanço + manutenção) ou "gradual" (corretiva de P dividida em N safras no sulco).
- K no sulco ≤ 50 kg/ha; CTC < 4 e > 40 → parcelar.
- Gesso: m₂ > 20% ou Ca₂ < 0,5 → 50 × argila (%) kg/ha.
- S: média 0–40 cm ≤4 → 20 (≤3 t/ha) ou 30; 5–9 → 15; ≥10 → 0.
- Micros Mehlich: B <0,30/0,30–0,50; Cu <0,5/0,5–0,8; Mn <2,0/2,0–5,0; Zn <1,1/1,1–1,6. Doses baixo/médio: B 2/0,5; Cu 2/0,5; Mn 6/1,5; Zn 6/1,5.
- Milho e feijão do Cerrado usam manutenção estimada pela exportação (sem tabela oficial) — manter o aviso.
- Soja em MS: Embrapa indica V2 = 60% (padrão do método é 50%).

## Conversão em produtos
- Fontes: ureia 44% N, sulfato de amônio 20% N (22% S), nitrato de amônio 32%; superfosfato simples 18% P₂O₅ (10% S), triplo 41%, MAP 9-48-00; KCl 58% K₂O, sulfato de K 48% (garantias mínimas MAPA citadas no B100 1997).
- MAP: descontar o N do MAP do N de plantio; avisar se passar de 20 kg/ha em soja.
- Modo formulado NPK: dose pela necessidade de P no sulco; complementar K e N com fontes simples; avisar se o formulado passar o K recomendado.
- Totais para a área informada e sacos de 50 kg.

## Funcionalidades do protótipo a manter
- Laudos salvos por cliente/talhão (hoje em localStorage).
- Editor das tabelas por cultura, com restaurar original.
- Impressão / PDF do resultado.
- Tema claro/escuro, uso no celular.

## Casos de teste (resultados do protótipo)
Laudo A (mmolc/dm³, P resina): P 10, K 1,2, Ca 20, Mg 6, Al 2, H+Al 40, argila 45%, M.O. 25; 20–40 cm: Ca 3, Mg 2, Al 8, H+Al 50; S 20–40 = 10; Zn 0,5. PRNT 85, 0–20 cm.
- B100 milho, 8–10 t/ha, resposta alta → calcário 2,33 t/ha; gesso 2,70 t/ha; plantio 30-120-50; cobertura N 130, K₂O 50; S 40; Zn 4.
- B100 mandioca de mesa, 25–30 t/ha → calcário 1,54; plantio 7-120-60; cobertura N 14, K₂O 70 (N reduzido 30% por M.O. > 20).
- B100 cana-planta, 100–130 t/ha, P = 5 → fosfatagem 150 a lanço; sulco 30-150-80; cobertura N 30, K₂O 60; gesso 2,70 (m₂ > 30%).

Laudo B (cmolc/dm³, K em mg/dm³, Mehlich-1): P 6, K 50, Ca 1,5, Mg 0,5, Al 0,6, H+Al 5, argila 40%; 20–40 cm: Ca 0,3, Mg 0,1, Al 0,7, H+Al 5.
- MG milho 6–8 t/ha, resposta baixa → calcário V% 2,53 / Al 0,50; gesso 0,88 t/ha; plantio 20-100-60; cobertura N 80.
- MG mandioca → P "Média" (textura argilosa), K "Boa"; calcário V% 0,85; plantio 0-40-20; cobertura N 40.
- Cerrado soja 3,6 t/ha, correção total → fosfatagem 105; K corretiva 50; sulco 0-55-50; cobertura K₂O 20; gesso 2,00 t/ha; calcário V% 1,69 / Al 0,14.

## Lacunas conhecidas
- Livro "Cerrado: correção do solo e adubação" é escaneado (sem texto); se precisar de tabelas dele, fazer OCR/leitura das páginas.
- Culturas do B100 2022 ainda não incluídas: café, citros, algodão, amendoim, arroz, eucalipto, hortaliças etc. Seguir o mesmo formato do JSON.
- 5ª Aproximação: pastagens, café e hortaliças ainda não incluídas.
- A recomendação final é responsabilidade de profissional habilitado (manter o aviso na interface).
