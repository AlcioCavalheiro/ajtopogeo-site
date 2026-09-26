/* Testes do leitor de laudo em PDF. Os arquivos em laudos/ são o texto (com posição)
 * de laudos reais extraído pelo pdf.js, com nomes de pessoas e propriedades trocados.
 *
 *   node --test "gestor/solo/test/*.test.js"
 */
const test = require("node:test");
const assert = require("node:assert/strict");
const leitor = require("../leitor-laudo.js");
const motor = require("../motor.js");
const tabelas = require("../tabelas.js");

test.describe("laboratório de Campo Grande-MS (uma coluna por amostra)", () => {
  const r = leitor.interpretar(require("./laudos/lab-campo-grande.json"));

  test("reconhece o formato, a propriedade e a amostra", () => {
    assert.equal(r.erro, undefined);
    assert.equal(r.formato, "linhas");
    assert.equal(r.propriedade, "FAZENDA TESTE");
    assert.equal(r.proprietario, "PRODUTOR TESTE");
    assert.equal(r.amostras.length, 1);
    assert.equal(r.amostras[0].descricao, "01 - 0-20");
    assert.deepEqual(r.amostras[0].prof, [0, 20]);
  });

  test("valores do laudo (mmolc/dm³, P Mehlich, argila g/kg → %)", () => {
    const L = r.amostras[0].laudo;
    assert.deepEqual(
      { un: L.unidade, kun: L.unidadeK, ph: L.ph, mo: L.mo, pmeh: L.pmeh, pres: L.pres, k: L.k, ca: L.ca, mg: L.mg, al: L.al, hal: L.hal, s: L.s, arg: L.arg },
      { un: "m", kun: "same", ph: 4.6, mo: 7.8, pmeh: 3, pres: null, k: 1.3, ca: 8, mg: 4, al: 3, hal: 18, s: 4, arg: 9.8 });
    assert.deepEqual([L.B, L.Cu, L.Fe, L.Mn, L.Zn], [0.17, 0.3, 54.23, 3.29, 0.15]);
  });
});

test.describe("laboratório de SP (uma linha por amostra, três tabelas)", () => {
  const r = leitor.interpretar(require("./laudos/lab-sp-colunas.json"));

  test("reconhece o formato e as três camadas", () => {
    assert.equal(r.erro, undefined);
    assert.equal(r.formato, "colunas");
    assert.equal(r.propriedade, "SÍTIO TESTE");
    assert.deepEqual(r.amostras.map((a) => a.prof), [[0, 20], [20, 40], [40, 60]]);
  });

  test("valores da camada 0–20 cm", () => {
    const L = r.amostras[0].laudo;
    assert.deepEqual(
      { un: L.unidade, ph: L.ph, pres: L.pres, pmeh: L.pmeh, s: L.s, k: L.k, ca: L.ca, mg: L.mg, al: L.al, hal: L.hal, mo: L.mo, arg: L.arg },
      { un: "m", ph: 4.7, pres: 5, pmeh: null, s: 2, k: 3.9, ca: 12, mg: 6, al: 1.8, hal: 20, mo: 24, arg: 21.1 });
    assert.deepEqual([L.B, L.Cu, L.Fe, L.Mn, L.Zn], [0.16, 0.6, 17, 20.6, 0.6]);
  });

  test("0–20 e 20–40 viram superfície e subsuperfície do formulário", () => {
    const { sup, sub } = leitor.sugerirPar(r.amostras);
    assert.equal(sup.id, "182"); assert.equal(sub.id, "183");
    const { campos, avisos } = leitor.camposFormulario(sup, sub, "b100");
    assert.deepEqual(
      { p: campos.p, pext: campos.pext, ca2: campos.ca2, mg2: campos.mg2, k2: campos.k2, al2: campos.al2, hal2: campos.hal2, s1: campos.s1, s2: campos.s2 },
      { p: 5, pext: "resina", ca2: 9, mg2: 5, k2: 1.2, al2: 1.4, hal2: 16, s1: 2, s2: 3 });
    assert.deepEqual(avisos, []);
  });

  test("do PDF direto para a recomendação (B100, milho)", () => {
    const { sup, sub } = leitor.sugerirPar(r.amostras);
    const { campos: f } = leitor.camposFormulario(sup, sub, "b100");
    const laudo = { unidade: f.un, unidadeK: f.kun, extratorP: f.pext, ...f };
    const res = motor.calcular({ metodo: "b100", cultura: "milho", laudo, manejo: { prnt: 85, prodIdx: 2, resp: "alta" }, fertilizantes: {} }, tabelas);
    assert.equal(res.erro, undefined);
    // T = (12 + 6 + 3,9 + 20)/10 = 4,19 cmolc; V = 52,3% → NC = (70 − 52,3) × 4,19 / 85
    assert.equal(+res.calagem.NC.toFixed(2), 0.87);
    assert.ok(res.gesso.kgha === 0, "Ca 9 mmolc e m baixo em 20–40: sem gesso");
  });
});

test.describe("casos gerais", () => {
  test("Campo Grande sem 20–40: sem subsuperfície e P Mehlich avisado no B100", () => {
    const r = leitor.interpretar(require("./laudos/lab-campo-grande.json"));
    const { sup, sub } = leitor.sugerirPar(r.amostras);
    assert.equal(sub, null);
    const { campos, avisos } = leitor.camposFormulario(sup, sub, "b100");
    assert.equal(campos.pext, "mehlich");
    assert.ok(avisos.some((a) => /P Mehlich-1/.test(a)));
    assert.equal(leitor.camposFormulario(sup, sub, "cerrado").avisos.length, 0);
  });

  test("PDF sem texto (escaneado) devolve erro", () => {
    assert.match(leitor.interpretar([]).erro, /escaneado/);
  });

  test("números e profundidades", () => {
    assert.equal(leitor.numero("54,23"), 54.23);
    assert.equal(leitor.numero("1.234,5"), 1234.5);
    assert.equal(leitor.numero("<0,1"), 0.1);
    assert.equal(leitor.numero("ns"), null);
    assert.equal(leitor.numero("-"), null);
    assert.deepEqual(leitor.profundidade("Talhão 1 - 20-40 CM"), [20, 40]);
    assert.deepEqual(leitor.profundidade("01 - 0-20"), [0, 20]);
    assert.equal(leitor.profundidade("Amostra A"), null);
  });
});
