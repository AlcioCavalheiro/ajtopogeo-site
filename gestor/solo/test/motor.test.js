/* Testes do motor da Recomendação de Solo — casos da especificação
 * (resultados do protótipo). Rodar na raiz do SITE:
 *
 *   node --test "gestor/solo/test/*.test.js"
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const motor = require("../motor.js");
const tabelas = require("../tabelas.js");

const perto = (real, esperado, casas = 2, rotulo = "") =>
  assert.equal(+real.toFixed(casas), esperado, `${rotulo}: ${real} ≠ ${esperado}`);

const FERT = { modo: "simples", fonteN: 44, fonteP: "ssp", fonteK: 58 };

// Laudo A — mmolc/dm³, P resina
const LAUDO_A = {
  unidade: "m", unidadeK: "same", extratorP: "resina",
  p: 10, k: 1.2, ca: 20, mg: 6, al: 2, hal: 40, arg: 45, mo: 25,
  ca2: 3, mg2: 2, al2: 8, hal2: 50, s2: 10, Zn: 0.5,
};
// Laudo B — cmolc/dm³, K em mg/dm³, Mehlich-1
const LAUDO_B = {
  unidade: "c", unidadeK: "mg", extratorP: "mehlich",
  p: 6, k: 50, ca: 1.5, mg: 0.5, al: 0.6, hal: 5, arg: 40,
  ca2: 0.3, mg2: 0.1, al2: 0.7, hal2: 5,
};

function calc(metodo, cultura, laudo, manejo) {
  const r = motor.calcular({ metodo, cultura, laudo, manejo: { prnt: 85, prof: 20, area: 1, ...manejo }, fertilizantes: FERT }, tabelas);
  assert.equal(r.erro, undefined, r.erro);
  return r;
}
const prodIdx = (metodo, cultura, rotulo) => {
  const i = tabelas.DEF[metodo].crops[cultura].prod.indexOf(rotulo);
  assert.ok(i >= 0, `produtividade "${rotulo}" não existe em ${metodo}/${cultura}`);
  return i;
};
function adubo(r, plantio, cobertura) {
  const a = r.adubacao;
  assert.deepEqual([a.N1, a.Psulco, a.Ksulco], plantio, "plantio N-P₂O₅-K₂O");
  assert.deepEqual([a.N2, a.Kcob], cobertura, "cobertura N, K₂O");
}

test.describe("Laudo A (mmolc/dm³, P resina)", () => {
  test("B100 milho 8–10 t/ha, resposta alta", () => {
    const r = calc("b100", "milho", LAUDO_A, { prodIdx: prodIdx("b100", "milho", "8–10 t/ha"), resp: "alta" });
    perto(r.calagem.NC, 2.33, 2, "calcário");
    perto(r.gesso.tha, 2.7, 2, "gesso");
    adubo(r, [30, 120, 50], [130, 50]);
    assert.equal(r.adubacao.S, 40);
    assert.deepEqual(r.micros.filter((m) => m.dose > 0).map((m) => [m.el, m.dose]), [["Zn", 4]]);
    assert.match(r.gesso.criterio, /1997/, "deve informar que o critério de gesso é da edição 1997");
  });

  test("B100 mandioca de mesa 25–30 t/ha (N −30% por M.O. > 20)", () => {
    const r = calc("b100", "mandMesa", LAUDO_A, { prodIdx: prodIdx("b100", "mandMesa", "25–30 t/ha") });
    perto(r.calagem.NC, 1.54, 2, "calcário");
    adubo(r, [7, 120, 60], [14, 70]);
    assert.ok(r.avisos.some((w) => /N reduzido em 30%/.test(w)));
  });

  test("B100 cana-planta 100–130 t/ha com P = 5", () => {
    const r = calc("b100", "canaPl", { ...LAUDO_A, p: 5 }, { prodIdx: prodIdx("b100", "canaPl", "100–130 t/ha") });
    assert.equal(r.adubacao.Plan, 150, "fosfatagem a lanço");
    adubo(r, [30, 150, 80], [30, 60]);
    perto(r.gesso.tha, 2.7, 2, "gesso");
    assert.match(r.gesso.motivo, /m > 30%/);
  });
});

test.describe("Laudo B (cmolc/dm³, K mg/dm³, Mehlich-1)", () => {
  test("5ª Aproximação milho 6–8 t/ha, resposta baixa", () => {
    const r = calc("mg", "milho", LAUDO_B, { prodIdx: prodIdx("mg", "milho", "6–8 t/ha"), resp: "baixa" });
    perto(r.calagem.NC, 2.53, 2, "calcário V%");
    perto(r.calagem.NCalt, 0.5, 2, "calcário Al");
    perto(r.gesso.tha, 0.88, 2, "gesso");
    adubo(r, [20, 100, 60], [80, 0]);
  });

  test("5ª Aproximação mandioca", () => {
    const r = calc("mg", "mandioca", LAUDO_B, {});
    assert.equal(r.classes.P.nome, "Média");
    assert.match(r.classes.P.col, /argilosa/);
    assert.equal(r.classes.K.nome, "Boa");
    perto(r.calagem.NC, 0.85, 2, "calcário V%");
    adubo(r, [0, 40, 20], [40, 0]);
  });

  test("Embrapa Cerrados soja 3,6 t/ha, correção total", () => {
    const r = calc("cerrado", "soja", LAUDO_B, { prod: 3.6, correcao: "total" });
    assert.equal(r.adubacao.Plan, 105, "fosfatagem");
    assert.equal(r.adubacao.Klan, 50, "K corretiva");
    adubo(r, [0, 55, 50], [0, 20]);
    perto(r.gesso.tha, 2, 2, "gesso");
    perto(r.calagem.NC, 1.69, 2, "calcário V%");
    perto(r.calagem.NCalt, 0.14, 2, "calcário Al");
  });
});

test.describe("regras gerais", () => {
  test("índices: SB, T, V% e m% em cmolc/dm³", () => {
    const i = motor.indices(LAUDO_A);
    perto(i.SB, 2.72, 2, "SB"); perto(i.T, 6.72, 2, "T"); perto(i.V, 40.48, 2, "V%");
    perto(i.CTCe, 2.92, 2, "CTCe"); perto(i.m, 6.85, 2, "m%");
  });

  test("fator de profundidade = prof/20", () => {
    const a = calc("b100", "milho", LAUDO_A, { prodIdx: 2, resp: "alta" });
    const b = calc("b100", "milho", LAUDO_A, { prodIdx: 2, resp: "alta", prof: 40 });
    perto(b.calagem.NC, +(a.calagem.NC * 2).toFixed(4), 4, "0–40 cm");
  });

  test("laudo incompleto devolve erro em vez de números", () => {
    const r = motor.calcular({ metodo: "b100", cultura: "milho", laudo: { ...LAUDO_A, hal: "" }, manejo: {}, fertilizantes: FERT }, tabelas);
    assert.match(r.erro, /Preencha/);
  });

  test("produtos: kg/ha, total da área e sacos de 50 kg", () => {
    const r = calc("b100", "milho", LAUDO_A, { prodIdx: 2, resp: "alta", area: 10 });
    const ureiaCob = r.produtos.find((p) => p.nm === "Ureia" && p.q === "Cobertura");
    perto(ureiaCob.kg, +(130 / 0.44).toFixed(2), 2, "ureia kg/ha");
    perto(ureiaCob.totalKg, +((130 / 0.44) * 10).toFixed(2), 2, "ureia total");
    perto(ureiaCob.sacos, +((130 / 0.44) * 10 / 50).toFixed(2), 2, "sacos");
  });

  test("MAP desconta o N do plantio", () => {
    const r = motor.calcular({ metodo: "b100", cultura: "milho", laudo: LAUDO_A, manejo: { prnt: 85, prodIdx: 2, resp: "alta" },
      fertilizantes: { ...FERT, fonteP: "map" } }, tabelas);
    const map = r.produtos.find((p) => p.nm === "MAP").kg, nMap = map * 0.09;
    const ureia = r.produtos.find((p) => p.nm === "Ureia" && p.q === "Plantio (sulco)");
    perto(ureia.kg, +((30 - nMap) / 0.44).toFixed(2), 2, "ureia no sulco");
  });

  test("todas as culturas de todos os métodos calculam sem erro", () => {
    for (const m of Object.keys(tabelas.DEF))
      for (const c of Object.keys(tabelas.DEF[m].crops)) {
        const r = motor.calcular({ metodo: m, cultura: c, laudo: m === "b100" ? LAUDO_A : LAUDO_B, manejo: { prnt: 85 }, fertilizantes: FERT }, tabelas);
        assert.equal(r.erro, undefined, `${m}/${c}`);
        for (const v of [r.calagem.NC, r.gesso.kgha, r.adubacao.Ntot, r.adubacao.Ptot, r.adubacao.Ktot])
          assert.ok(Number.isFinite(v), `${m}/${c}: valor não numérico`);
      }
  });
});
