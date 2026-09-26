/* Motor de cálculo da Recomendação de Solo (Gestor AJ TopoGeo).
 *
 * Funções puras, sem DOM: recebem o laudo + escolhas e as tabelas
 * (gestor/solo/tabelas.js) e devolvem um objeto com calagem, gessagem,
 * N-P2O5-K2O por época, S, micronutrientes, produtos comerciais e observações.
 * A interface (gestor/solo/solo.js) só lê o formulário, chama
 * SoloMotor.calcular() e desenha o resultado. Os testes (gestor/solo/test/)
 * chamam o mesmo motor pelo Node.
 *
 * Porte fiel do calc() do protótipo recomendacao-solo.html. Unidades internas:
 * cátions em cmolc/dm³ (mmolc ÷ 10; K em mg/dm³ ÷ 391).
 *
 * Entrada de calcular():
 *   metodo ....... "b100" | "mg" | "cerrado"
 *   cultura ...... chave em tabelas.DEF[metodo].crops
 *   laudo ........ { unidade:"m"|"c", unidadeK:"same"|"mg", extratorP:"resina"|"mehlich",
 *                    ph, mo, p, k, ca, mg, al, hal, arg,
 *                    ca2, mg2, k2, al2, hal2, s1, s2, B, Cu, Fe, Mn, Zn }
 *                  (campo vazio = null)
 *   manejo ....... { prodIdx, prod (t/ha, só Cerrado), resp:"alta"|"media"|"baixa",
 *                    correcao:"total"|"gradual", anos, prnt, prof (cm), area (ha) }
 *   fertilizantes  { modo:"simples"|"formula", formula:"04-14-08",
 *                    fonteN:44|20|32, fonteP:"ssp"|"tsp"|"map", fonteK:58|48 }
 */
(function (root, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else root.SoloMotor = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const Y5 = ["Muito baixo", "Baixo", "Médio", "Alto", "Muito alto"];
  const N6 = ["Muito baixo", "Baixo", "Médio", "Adequado", "Alto", "Muito alto"];
  const NK4 = ["Baixo", "Médio", "Adequado", "Alto"];
  const MG5 = ["Muito baixo", "Baixo", "Médio", "Bom", "Muito bom"];
  const MG3 = ["Baixa", "Média", "Boa"];

  const FONTES_P = {
    ssp: { p: 18, n: 0, s: 10, nm: "Superfosfato simples" },
    tsp: { p: 41, n: 0, s: 0, nm: "Superfosfato triplo" },
    map: { p: 48, n: 9, s: 0, nm: "MAP" },
  };
  const FONTES_N = { 44: "Ureia", 20: "Sulfato de amônio", 32: "Nitrato de amônio" };
  const FONTES_K = { 58: "Cloreto de potássio", 48: "Sulfato de potássio" };
  const RESPN = { alta: "Alta", media: "Média e baixa", baixa: "Baixa" };

  // ------------------------------------------------------------ utilitários

  const f1 = (v, d = 1) =>
    v == null || isNaN(v) ? "–" : v.toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
  const f0 = (v) => f1(v, 0);
  const r5 = (v) => Math.round(v / 5) * 5;
  const idxLe = (v, lims) => { for (let i = 0; i < lims.length; i++) if (v <= lims[i]) return i; return lims.length; };
  const idxLt = (v, lt) => { for (let i = 0; i < lt.length; i++) if (v < lt[i]) return i; return lt.length; };
  const nulo = (v) => v == null || v === "" || (typeof v === "number" && isNaN(v));

  /** Converte texto do formulário ("2,5", "", null) em número ou null. */
  function num(v) {
    if (nulo(v)) return null;
    const n = parseFloat(String(v).replace(",", "."));
    return isNaN(n) ? null : n;
  }

  /** Dose da linha na produtividade yi; null = produtividade improvável → faixa anterior. */
  function pick(row, yi) {
    if (row[yi] != null) return { v: row[yi], nulo: false };
    for (let i = yi; i >= 0; i--) if (row[i] != null) return { v: row[i], nulo: true };
    return { v: 0, nulo: true };
  }

  /** Classe de P da 5ª Aproximação pela argila: i5 = 0..4 (MB..MBom), g = 0..2 (Baixa/Média/Boa). */
  function mgPclass(p, arg, MGP) {
    const lims = (MGP.arg.find(([a]) => arg > a) || MGP.arg[3])[1];
    const i5 = idxLe(p, lims);
    return { i5, g: i5 <= 1 ? 0 : i5 === 2 ? 1 : 2, lims };
  }

  /** Gesso da 5ª Aproximação (Quadro 10.1), t/ha para 20 cm, interpolado pela argila (%). */
  function mgNG(arg) {
    const pts = [[0, 0], [15, 0.4], [35, 0.8], [60, 1.2], [100, 1.6]];
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      if (arg <= x1) return y0 + ((arg - x0) * (y1 - y0)) / (x1 - x0);
    }
    return 1.6;
  }

  /** Y do método do Al e Ca+Mg em função da argila (%). */
  const Yarg = (a) => 0.0302 + 0.06532 * a - 0.000257 * a * a;

  /** Classes de resposta a N disponíveis para a cultura (null = não se aplica). */
  function chavesResposta(c, tabelas) {
    const t = c.Ntot || c.Ncob;
    if (t) return Object.keys(t);
    if (c.Nref === "milho") return Object.keys(tabelas.DEF.b100.crops.milho.Ntot);
    return null;
  }
  function rotuloResposta(k, chaves) {
    return k === "media" && chaves.length === 2 ? "Média e baixa" : RESPN[k] || k;
  }

  /** Índices do complexo de troca (tudo em cmolc/dm³). */
  function indices(laudo) {
    const fu = laudo.unidade === "c" ? 1 : 0.1;
    const Kin = (v) => (laudo.unidadeK === "mg" ? v / 391 : v * fu);
    const Ca = num(laudo.ca) * fu, Mg = num(laudo.mg) * fu, Al = (num(laudo.al) || 0) * fu, HAl = num(laudo.hal) * fu;
    const K = Kin(num(laudo.k)), Kmm = K * 10, Kmg = K * 391;
    const SB = Ca + Mg + K, T = SB + HAl, V = (SB / T) * 100, CTCe = SB + Al, m = CTCe > 0 ? (Al / CTCe) * 100 : 0;
    const ca2 = num(laudo.ca2), al2 = num(laudo.al2), hasSub = ca2 != null && al2 != null;
    const Ca2 = hasSub ? ca2 * fu : 0, Mg2 = (num(laudo.mg2) || 0) * fu, Al2 = hasSub ? al2 * fu : 0;
    const K2 = num(laudo.k2) == null ? 0 : Kin(num(laudo.k2));
    const SB2 = Ca2 + Mg2 + K2, m2 = hasSub && SB2 + Al2 > 0 ? (Al2 / (SB2 + Al2)) * 100 : 0;
    const hal2 = num(laudo.hal2), V2sub = hasSub && hal2 != null ? (SB2 / (SB2 + hal2 * fu)) * 100 : null;
    return { fu, Ca, Mg, Al, HAl, K, Kmm, Kmg, SB, T, V, CTCe, m, hasSub, Ca2, Mg2, Al2, K2, SB2, m2, V2sub };
  }

  // ------------------------------------------------------------ cálculo

  function calcular(entrada, tabelas) {
    const metodo = entrada.metodo, laudo = entrada.laudo || {}, man = entrada.manejo || {}, fert = entrada.fertilizantes || {};
    const M = tabelas.DEF[metodo];
    if (!M) return { erro: "Método desconhecido: " + metodo };
    const c = M.crops[entrada.cultura];
    if (!c) return { erro: "Cultura desconhecida: " + entrada.cultura };

    const L = {};
    for (const x of ["ph", "mo", "p", "k", "ca", "mg", "al", "hal", "arg"]) L[x] = num(laudo[x]);
    if (["p", "k", "ca", "mg", "hal", "arg"].some((x) => L[x] == null))
      return { erro: "Preencha P, K, Ca, Mg, H+Al e argila para calcular." };

    const I = indices(laudo);
    const { Ca, Mg, Al, K, Kmm, Kmg, SB, T, V, CTCe, hasSub, Ca2, Al2, m2, V2sub } = I;
    const arg = L.arg;
    const PRNT = num(man.prnt) || 100, fprof = (num(man.prof) || 20) / 20, area = num(man.area) || 1;
    const pext = laudo.extratorP || (metodo === "b100" ? "resina" : "mehlich");
    const W = [], micros = [];
    let NC = 0, NCalt = null, calNota = "", NG = 0, gessoMot = "", gessoForm = "";
    let Pcls = 0, Pnome = "", PclsN = 5, Kcls = 0, Knome = "", KclsN = 5, Pcol = "", Kcol = "";
    let N1 = 0, N2 = 0, Psulco = 0, Plan = 0, Ksulco = 0, Kcob = 0, Klan = 0, Sdose = 0, prodTxt = "";
    const V2 = c.V2, extras = [];
    const yi = metodo !== "cerrado" && c.prod.length > 1 ? Math.min(c.prod.length - 1, Math.max(0, num(man.prodIdx) || 0)) : 0;
    const resp = man.resp || "media";
    const s1 = num(laudo.s1), s2 = num(laudo.s2);

    if (metodo === "b100") {
      if (pext !== "resina") W.push("O Boletim 100 foi calibrado para P em resina. Com Mehlich-1 a classe e a dose de P podem sair erradas.");
      prodTxt = c.prod[yi];
      NC = Math.max(0, ((V2 - V) * T) / PRNT) * fprof;
      if (c.calMin100 && NC > 0 && NC < (c.calMin100 * 100) / PRNT) {
        NC = (c.calMin100 * 100) / PRNT;
        W.push(`O boletim pede no mínimo ${f1(c.calMin100)} t/ha de calcário (PRNT 100%) para esta cultura.`);
      }
      calNota = "NC (t/ha) = CTC × (V2 − V1) ÷ (10 × PRNT), com CTC em mmolc/dm³ (Quaggio, 1983).";
      Pcls = idxLt(L.p, [7, 16, 41, 80.001]); Pnome = Y5[Pcls];
      const Kn = ["Baixo", "Médio", "Alto", "Muito alto"];
      Kcls = idxLt(Kmm, [1.6, 3.05, 6.05]); Knome = Kn[Kcls]; KclsN = 4;
      const pi = idxLt(L.p, c.P.lt), ki = idxLt(Kmm, c.K.lt);
      const colTxt = (lt, i) => {
        const fx = (v) => f1(v, v % 1 ? 1 : 0);
        return i === 0 ? `abaixo de ${fx(lt[0])}`
          : i < lt.length ? `${fx(lt[i - 1])} a ${f1(lt[i] - (lt[i] % 1 ? 0.05 : 1), lt[i] % 1 ? 1 : 0)}`
          : `acima de ${f1(lt[lt.length - 1] - (lt[lt.length - 1] % 1 ? 0.05 : 1), lt[lt.length - 1] % 1 ? 1 : 0)}`;
      };
      Pcol = "coluna " + colTxt(c.P.lt, pi) + " mg/dm³"; Kcol = "coluna " + colTxt(c.K.lt, ki) + " mmolc/dm³";
      const pp = pick(c.P.v[pi], yi), kk = pick(c.K.v[ki], yi);
      Psulco = pp.v; Ksulco = kk.v;
      if (pp.nulo || kk.nulo) W.push("O boletim considera improvável atingir essa produtividade com P tão baixo. Usei a dose da faixa anterior; reveja a meta.");
      N1 = c.Npl[yi] || 0;
      if (c.Ntot) { const t = c.Ntot[resp] ?? c.Ntot.media; N2 = Math.max(0, t[yi] - N1); }
      else if (c.Ncob) N2 = (c.Ncob[resp] ?? c.Ncob.media)[yi];
      else if (c.NcobFix) N2 = c.NcobFix[yi] || 0;
      if (c.NredMO && L.mo != null && L.mo > c.NredMO.acima) {
        N1 = Math.round(N1 * c.NredMO.fator); N2 = Math.round(N2 * c.NredMO.fator);
        W.push("M.O. acima de 20: N reduzido em 30%, como pede o boletim.");
      }
      if (c.Kcob) Kcob = c.Kcob.v[idxLt(Kmm, c.Kcob.lt)][yi] || 0;
      if (c.fosfatagem && L.p <= c.fosfatagem.ate) {
        Plan = c.fosfatagem.dose;
        W.push(`P resina até ${c.fosfatagem.ate} mg/dm³: fosfatagem com ${c.fosfatagem.dose} kg/ha de P₂O₅ incorporado, além da dose de semeadura.`);
      }
      if (c.fosfCana && L.p < 7) {
        Plan = arg <= 25 ? 120 : 150; Psulco = 150;
        W.push(`P abaixo de 7 mg/dm³: fosfatagem com ${Plan} kg/ha de P₂O₅ a lanço (após calagem e gessagem, incorporar a 10–20 cm) e 150 kg/ha no sulco.`);
      }
      if (c.Pzero && L.p > c.Pzero.acima) { Psulco = c.Pzero.dose; W.push(`P acima de ${c.Pzero.acima} mg/dm³: só ${c.Pzero.dose} kg/ha de P₂O₅ como arranque.`); }
      if (c.Kzero && Kmm > c.Kzero) { Ksulco = 0; Kcob = 0; W.push("K acima de 6 mmolc/dm³: adubação potássica dispensada."); }
      if (c.Ksulco && Ksulco > c.Ksulco) {
        Kcob += Ksulco - c.Ksulco; Ksulco = c.Ksulco;
        W.push(`Máximo de ${c.Ksulco} kg/ha de K₂O no sulco; o excedente foi para cobertura.`);
      }
      if (c.NKsulco && N1 + Ksulco > c.NKsulco) {
        const ex = N1 + Ksulco - c.NKsulco, mv = Math.min(ex, Ksulco);
        Ksulco -= mv; Kcob += mv;
        W.push(`N + K₂O no sulco limitado a ${c.NKsulco} kg/ha (até 100 em solo argiloso com espaçamento reduzido); o K excedente foi para a 1ª cobertura.`);
      }
      if (Kcls === 0 && Ksulco + Kcob >= 80) W.push("K baixo e dose ≥ 80 kg/ha: em solo argiloso, prefira transferir o K de cobertura para pré-plantio a lanço.");
      // gesso
      const g = c.gesso || "b97";
      if (g === "cana") {
        gessoForm = "critério da cana (25–50 cm): V < 40% ou m > 30%";
        if (hasSub) {
          if (V2sub == null) W.push("Para a cana, informe também H+Al de 20–40 (25–50) cm: o critério usa V% da subsuperfície.");
          if ((V2sub != null && V2sub < 40) || m2 > 30) { NG = 6 * arg * 10; gessoMot = m2 > 30 ? "m > 30% em subsuperfície" : "V < 40% em subsuperfície"; }
        }
      } else if (g === "pasto") {
        gessoForm = "critério de forrageiras (20–40 cm): V < 25% ou m > 50%";
        if (hasSub && ((V2sub != null && V2sub < 25) || m2 > 50)) { NG = 6 * arg * 10; gessoMot = m2 > 50 ? "m > 50% em 20–40 cm" : "V < 25% em 20–40 cm"; }
      } else {
        gessoForm = "critério geral do B100 1997 (a edição 2022 não traz critério geral para grãos): Ca < 4 mmolc/dm³ ou m > 40% em 20–40 cm";
        if (hasSub && (Ca2 * 10 < 4 || m2 > 40)) { NG = 6 * arg * 10; gessoMot = Ca2 * 10 < 4 ? "Ca < 4 mmolc/dm³ em 20–40 cm" : "m > 40% em 20–40 cm"; }
      }
      if (c.v2040 && V2sub != null && V2sub < c.v2040) W.push(`V% em 20–40 cm (${f0(V2sub)}%) abaixo de ${c.v2040}%: o boletim pede corrigir essa camada para produtividades altas.`);
      if (Mg * 10 < (c.Mgmin || 8)) W.push(`Mg abaixo de ${c.Mgmin || 8} mmolc/dm³: use calcário dolomítico ou magnesiano.`);
      // enxofre
      if (c.S) {
        if (c.S.fix) Sdose = c.S.fix[yi] || 0;
        if (c.S.porT) {
          const t = (c.tmed || [])[yi] || 3;
          if (c.S.se20a40 != null) {
            if (s2 == null) W.push(`Informe S em 20–40 cm: abaixo de ${c.S.se20a40} mg/dm³ aplicar ${c.S.porT} kg/ha de S por tonelada esperada.`);
            else if (s2 < c.S.se20a40) Sdose = c.S.porT * t;
          } else Sdose = c.S.porT * t;
        }
      }
      if (c.Scana && NG === 0 && s2 != null && s2 < 15) extras.push("1 t/ha de gesso como fonte de S (2–3 cortes) ou 50 kg/ha de S");
      // micronutrientes
      const ML = Object.assign({}, tabelas.MICRO.b100.lim, c.microLim || {});
      for (const el of ["B", "Cu", "Fe", "Mn", "Zn"]) {
        const v = num(laudo[el]); if (v == null) continue;
        const i = v < ML[el][0] ? 0 : v <= ML[el][1] ? 1 : 2;
        let dose = 0;
        if (c.micro && c.micro[el]) for (const [t, d] of c.micro[el]) if (v < t) { dose = d; break; }
        micros.push({ el, v, cls: ["Baixo", "Médio", "Alto"][i], i, dose });
      }
    } else if (metodo === "mg") {
      if (pext !== "mehlich") W.push("A 5ª Aproximação interpreta P e K por Mehlich-1.");
      prodTxt = c.prod[yi];
      const Y = Yarg(arg);
      NC = Math.max(0, ((V2 - V) * T) / PRNT) * fprof;
      NCalt = ((Math.max(0, Y * Math.max(0, Al - (c.mt * CTCe) / 100) + Math.max(0, c.X - (Ca + Mg))) * 100) / PRNT) * fprof;
      calNota = `Saturação por bases: NC = T × (Ve − Va) ÷ 100, corrigido pelo PRNT. Al e Ca + Mg: NC = Y × [Al − (mt × t ÷ 100)] + [X − (Ca + Mg)], corrigido pelo PRNT; Y = ${f1(Y, 2)} para ${f0(arg)}% de argila, mt = ${c.mt}%, X = ${c.X} (Quadro 8.1).`;
      if (c.canaMG) {
        const nc3 = ((Math.max(0, 3 - (Ca + Mg)) * 100) / PRNT) * fprof;
        calNota += ` Para cana também vale NC = 3 − (Ca + Mg) = ${f1(nc3, 2)} t/ha, limitado a V de 60%.`;
      }
      if (c.maxCal && Math.max(NC, NCalt) > c.maxCal) W.push(`Não aplicar mais de ${c.maxCal} t/ha de calcário por aplicação nesta cultura.`);
      if (c.mandMG) {
        const tex = arg > 35 ? "argilosa" : arg >= 15 ? "média" : "arenosa";
        const lims = arg > 35 ? [3, 6, 10] : arg >= 15 ? [5, 10, 15] : [7, 15, 20];
        const g = idxLe(L.p, lims);
        Pnome = ["Baixa", "Média", "Boa", "Muito boa"][g]; Pcls = g + 1; PclsN = 5; Pcol = `textura ${tex}: até ${lims.join(" / ")} mg/dm³`;
        const kg = idxLe(Kmg, [20, 40, 60]);
        Knome = ["Baixa", "Média", "Boa", "Muito boa"][kg]; Kcls = kg + 1; KclsN = 5; Kcol = "limites 20 / 40 / 60 mg/dm³";
        Psulco = c.P.v[g][0]; Ksulco = c.K.v[kg][0];
      } else {
        const pc = mgPclass(L.p, arg, tabelas.MGP);
        Pcls = pc.i5; Pnome = `${MG5[pc.i5]} (disponibilidade ${MG3[pc.g].toLowerCase()})`;
        Pcol = `limites para ${f0(arg)}% de argila: ${pc.lims.map((x) => f1(x, 1)).join(" / ")}`;
        const ki5 = idxLe(Kmg, tabelas.MGP.K), kg = ki5 <= 1 ? 0 : ki5 === 2 ? 1 : 2;
        Kcls = ki5; Knome = `${MG5[ki5]} (disponibilidade ${MG3[kg].toLowerCase()})`; Kcol = "limites 15 / 40 / 70 / 120 mg/dm³";
        Psulco = c.P.v[pc.g][yi]; Ksulco = c.K.v[kg][yi];
      }
      N1 = c.Npl[yi] || 0;
      if (c.Ncob) N2 = (c.Ncob[resp] ?? c.Ncob.alta)[yi];
      else if (c.NcobFix) N2 = c.NcobFix[yi] || 0;
      if (c.KzeroMg && Kmg > c.KzeroMg) { Ksulco = 0; W.push(`K acima de ${c.KzeroMg} mg/dm³: não aplicar potássio.`); }
      if (c.KmetadeAcima && Ksulco > c.KmetadeAcima) {
        Kcob = Ksulco / 2; Ksulco /= 2;
        W.push(`Dose de K acima de ${c.KmetadeAcima} kg/ha: metade no plantio e metade com a cobertura de N.`);
      }
      if (c.Ksulco && Ksulco > c.Ksulco) {
        Kcob += Ksulco - c.Ksulco; Ksulco = c.Ksulco;
        W.push(`Máximo de ${c.Ksulco} kg/ha de K₂O no sulco; o excedente foi para cobertura.`);
      }
      if (c.canaMG) {
        gessoForm = "critério da cana: Ca < 0,4 cmolc/dm³ ou m > 40% em 20–40 cm";
        if (hasSub && (Ca2 < 0.4 || m2 > 40)) { NG = mgNG(arg) * 1000; gessoMot = Ca2 < 0.4 ? "Ca < 0,4 cmolc/dm³" : "m > 40%"; }
      } else {
        gessoForm = "critério geral: Ca ≤ 0,4 cmolc/dm³, Al > 0,5 cmolc/dm³ ou m > 30% em 20–40 cm";
        if (hasSub && (Ca2 <= 0.4 || Al2 > 0.5 || m2 > 30)) {
          NG = mgNG(arg) * 1000;
          gessoMot = Ca2 <= 0.4 ? "Ca ≤ 0,4 cmolc/dm³" : Al2 > 0.5 ? "Al > 0,5 cmolc/dm³" : "m > 30%";
        }
      }
      if (NG > 0) gessoForm += ". Dose pelo Quadro 10.1 (camada de 20 cm), interpolada pela argila";
      if (!c.canaMG && Ca / Mg < 3 && ["milho", "sorgo"].includes(entrada.cultura)) W.push("Relação Ca:Mg abaixo de 3:1 prejudica milho e sorgo.");
    } else {
      const D = M, prod = num(man.prod) || c.prod;
      prodTxt = f1(prod) + " t/ha";
      NC = Math.max(0, ((V2 - V) * T) / PRNT) * fprof;
      const Y = Yarg(arg);
      NCalt = ((Math.max(0, Y * Math.max(0, Al - (c.mt * CTCe) / 100) + Math.max(0, c.X - (Ca + Mg))) * 100) / PRNT) * fprof;
      calNota = `Saturação por bases: NC = (V2 − V1) × T ÷ PRNT, com T em cmolc/dm³. Neutralização do Al: NC = Y × [Al − (mt × CTCe ÷ 100)] + [X − (Ca + Mg)], corrigido pelo PRNT; Y = ${f1(Y, 2)} para ${f0(arg)}% de argila, mt = ${c.mt}%, X = ${c.X}.`;
      const band = idxLe(arg, D.bandas);
      let lims, NCp, CTP;
      if (pext === "resina") { lims = D.PresLims; NCp = D.NCres; CTP = D.CTPres[band]; }
      else { const ci = arg <= 15 ? 0 : arg <= 35 ? 1 : arg <= 60 ? 2 : 3; lims = D.PmehLims[ci]; NCp = D.NCmeh[band]; CTP = D.CTPmeh[band]; }
      Pcls = idxLe(L.p, lims); Pnome = N6[Pcls]; PclsN = 6;
      Pcol = `nível crítico ${NCp} mg/dm³, CTP ${CTP} kg P₂O₅ por mg/dm³`;
      const corrP = L.p < NCp ? r5((NCp - L.p) * CTP) : 0;
      const manP = r5((Pcls <= 3 ? c.Pt.ate : Pcls === 4 ? c.Pt.alto : c.Pt.muitoAlto) * prod);
      const baixaCTC = T < 4, Klims = baixaCTC ? [15, 30, 40] : [25, 50, 80];
      Kcls = idxLe(Kmg, Klims); Knome = NK4[Kcls]; KclsN = 4; Kcol = baixaCTC ? "CTC < 4 cmolc/dm³" : "CTC ≥ 4 cmolc/dm³";
      const corrKt = Kcls === 0 ? (baixaCTC ? 50 : 100) : Kcls === 1 ? (baixaCTC ? 25 : 50) : 0;
      const corrKg = Kcls === 0 ? (baixaCTC ? 70 : 80) : Kcls === 1 ? 60 : 0;
      const manK = r5(c.Kt * prod * (Kcls === 3 ? 0.5 : 1));
      if ((man.correcao || "total") === "total") {
        Plan = corrP; Psulco = manP; Klan = corrKt; Ksulco = manK;
        if (corrP > 0) W.push("Fosfatagem: aplicar a lanço e incorporar antes do plantio.");
      } else {
        const n = num(man.anos) || 4;
        Psulco = r5(manP + corrP / n); Ksulco = Math.max(corrKg, manK);
        if (corrP > 0) W.push(`Correção gradual: ${f0(corrP)} kg/ha de P₂O₅ divididos em ${n} safras e somados à manutenção.`);
      }
      if (Pcls === 5) W.push("P muito alto: pode suspender a adubação fosfatada por um ano ou mais, até voltar à classe alta.");
      if (baixaCTC && Ksulco > 40) W.push("CTC abaixo de 4 cmolc/dm³: parcelar doses acima de 40 kg/ha de K₂O ou aplicar a lanço.");
      if (Ksulco > 50) { Kcob = Ksulco - 50; Ksulco = 50; W.push("Máximo de 50 kg/ha de K₂O no sulco; o excedente foi para cobertura (30–40 dias) ou a lanço."); }
      if (c.Nref === "milho") {
        const t = tabelas.DEF.b100.crops.milho, i = idxLt(prod, [6, 8, 10, 12]);
        N1 = t.Npl[i]; N2 = Math.max(0, (t.Ntot[resp] ?? t.Ntot.media)[i] - N1);
        W.push(`N pela tabela de milho do Boletim 100 2022 (${t.prod[i]}); não há tabela de N por análise de solo no Cerrado.`);
      } else { N1 = c.Npl || 0; N2 = c.NcobFix || 0; }
      gessoForm = "critério Embrapa: m > 20% ou Ca < 0,5 cmolc/dm³ em 20–40 cm; NG = 50 × argila (%)";
      if (hasSub && (Ca2 < 0.5 || m2 > 20)) { NG = (c.gesso || 50) * arg; gessoMot = Ca2 < 0.5 ? "Ca < 0,5 cmolc/dm³ em 20–40 cm" : "m > 20% em 20–40 cm"; }
      const mgMin = T < 5 ? 0.5 : 0.9;
      if (Mg < mgMin) W.push(`Mg baixo para a CTC do solo (< ${f1(mgMin)} cmolc/dm³): prefira calcário com pelo menos 12% de MgO.`);
      if (s1 != null && s2 != null) {
        const sm = (s1 + s2) / 2;
        if (sm <= 4) Sdose = prod <= 3 ? 20 : 30; else if (sm < 10) Sdose = 15; else if (s1 <= 4) Sdose = 5;
        if (NG > 0 && Sdose > 0) W.push("O gesso recomendado já supre o enxofre; a dose de S pode ser dispensada.");
      }
      if (c.aviso) W.push(c.aviso);
      const MC = tabelas.MICRO.cerrado;
      for (const el of ["B", "Cu", "Mn", "Zn"]) {
        const v = num(laudo[el]); if (v == null) continue;
        const i = v < MC.lim[el][0] ? 0 : v <= MC.lim[el][1] ? 1 : 2;
        micros.push({ el, v, cls: ["Baixo", "Médio", "Alto"][i], i, dose: i < 2 ? MC.dose[el][i] : 0 });
      }
    }
    if (c.nota) W.push(c.nota);
    if (!hasSub) W.push("Sem análise de 20–40 cm a necessidade de gesso não foi avaliada.");
    if (NG > 0) W.push("O gesso não substitui a calagem; pode ser aplicado junto com o calcário.");

    // ------ fertilizantes → produtos comerciais
    const nF = +(fert.fonteN || 44), kF = +(fert.fonteK || 58), modo = fert.modo || "simples";
    const pSrc = FONTES_P[fert.fonteP || "ssp"];
    const nNm = FONTES_N[nF], kNm = FONTES_K[kF];
    const plantioLbl = c.unica ? "Aplicação (soqueira/pasto)" : "Plantio (sulco)";
    const prods = [];
    const push = (nm, q, kg) => { if (kg > 0.5) prods.push({ nm, q, kg, totalKg: kg * area, sacos: (kg * area) / 50 }); };
    let Sforn = 0;
    if (modo === "formula") {
      const ftxt = fert.formula || "";
      const fp = ftxt.split(/[^0-9.]+/).filter(Boolean).map(Number), a = fp[0] || 0, b = fp[1] || 0, d = fp[2] || 0;
      if (b <= 0 && Psulco > 0) W.push("Informe uma fórmula com P, ex.: 04-14-08.");
      else if (Psulco > 0) {
        const dose = Psulco / (b / 100);
        push(`Formulado ${ftxt}`, plantioLbl, dose);
        const Nd = (dose * a) / 100, Kd = (dose * d) / 100;
        if (Kd > Ksulco + 5) W.push(`O formulado entrega ${f0(Kd)} kg/ha de K₂O, acima dos ${f0(Ksulco)} indicados.`);
        push(kNm, plantioLbl + " – complemento", Math.max(0, Ksulco - Kd) / (kF / 100));
        push(nNm, plantioLbl + " – complemento", Math.max(0, N1 - Nd) / (nF / 100));
      } else { push(kNm, plantioLbl, Ksulco / (kF / 100)); push(nNm, plantioLbl, N1 / (nF / 100)); }
    } else {
      const dP = Psulco / (pSrc.p / 100);
      push(pSrc.nm, plantioLbl, dP); Sforn += (dP * pSrc.s) / 100;
      push(kNm, plantioLbl, Ksulco / (kF / 100));
      const nMap = (dP * pSrc.n) / 100;
      if (nMap > 20 && N1 === 0) W.push(`O MAP entrega ${f0(nMap)} kg/ha de N; em soja evite passar de 20 kg/ha de N no sulco.`);
      const nr = Math.max(0, N1 - nMap) / (nF / 100);
      push(nNm, plantioLbl, nr); if (nF === 20) Sforn += nr * 0.22;
    }
    if (Plan > 0) { const q = Plan / (pSrc.p / 100); push(pSrc.nm + " (fosfatagem)", "A lanço, antes do plantio", q); Sforn += (q * pSrc.s) / 100; }
    if (Klan > 0) push(kNm + " (corretiva)", "A lanço", Klan / (kF / 100));
    const nc = N2 / (nF / 100);
    push(nNm, "Cobertura", nc); if (nF === 20) Sforn += nc * 0.22;
    if (Kcob > 0) push(kNm, "Cobertura", Kcob / (kF / 100));
    if (Sdose > 0 && Sforn > 0) W.push(`As fontes escolhidas já fornecem cerca de ${f0(Sforn)} kg/ha de S.`);

    const tambem = [
      Sdose > 0 ? f0(Sdose) + " kg/ha de S" : null,
      ...micros.filter((x) => x.dose > 0).map((x) => f1(x.dose, 1) + " kg/ha de " + x.el),
      ...extras,
    ].filter(Boolean);

    return {
      metodo, cultura: entrada.cultura, culturaNome: c.nome, metodoNome: M.nome, fonte: c.fonte, prodTxt, extratorP: pext,
      indices: I, V2,
      calagem: { NC, NCalt, nota: calNota, fprof, PRNT, total: Math.max(NC, NCalt || 0) * area },
      gesso: { kgha: NG, tha: NG / 1000, motivo: gessoMot, criterio: gessoForm, total: (NG * area) / 1000 },
      classes: {
        P: { teor: L.p, i: Pcls, nome: Pnome, n: PclsN, col: Pcol },
        K: { i: Kcls, nome: Knome, n: KclsN, col: Kcol },
      },
      micros,
      adubacao: {
        plantioLbl, N1, N2, Plan, Psulco, Klan, Ksulco, Kcob, S: Sdose,
        Ntot: N1 + N2, Ptot: Plan + Psulco, Ktot: Klan + Ksulco + Kcob,
      },
      tambem, produtos: prods, avisos: W, area,
    };
  }

  return { calcular, indices, chavesResposta, rotuloResposta, num, f1, f0, Yarg, mgNG, idxLe, idxLt };
});
