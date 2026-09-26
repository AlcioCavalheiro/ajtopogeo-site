/* Leitor de laudo de análise de solo em PDF (Gestor AJ TopoGeo).
 *
 * Duas partes:
 *   interpretar(itens) .. PURA: recebe os pedaços de texto do PDF com posição
 *                         ({p, x, y, w, s} — página, canto esquerdo, linha de base,
 *                         largura, texto) e devolve as amostras encontradas com os
 *                         valores já no formato do laudo do motor. Testada no Node
 *                         com laudos reais (gestor/solo/test/laudos/).
 *   lerPdf(arquivo) ..... navegador: extrai os itens com o pdf.js que o Gestor já
 *                         carrega (window.pdfjsLib) e chama interpretar().
 *
 * Não depende do laboratório: reconhece os dois jeitos de montar a tabela
 *   "linhas"  — uma linha por determinação e uma coluna por amostra, com a unidade
 *               em cada linha (ex.: laboratório de Campo Grande-MS);
 *   "colunas" — uma linha por amostra e uma coluna por determinação, em uma ou mais
 *               tabelas com o cabeçalho acima (ex.: laboratório de SP, Pedido 31).
 * Os nomes das determinações são reconhecidos por ROTULOS abaixo; laboratório novo
 * com nome diferente ("Fósforo Mehlich", "Ca trocável"...) entra ali, com teste.
 *
 * PDF escaneado (imagem) não tem texto: interpretar() devolve erro e o técnico
 * digita os valores.
 */
(function (root, fabrica) {
  if (typeof module === "object" && module.exports) module.exports = fabrica();
  else root.SoloLeitor = fabrica();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ------------------------------------------------------------ rótulos

  // chave → teste do rótulo já normalizado (sem acento, minúsculo, sem espaço/pontuação).
  // Chaves que começam com "_" são reconhecidas só para não roubar valores de outra coluna.
  const ROTULOS = [
    ["ph", /^ph(cacl2?)?$/],
    ["_phagua", /^phh2o$/],
    ["mo", /^(mo|materiaorganica)$/],
    ["pres", /^(presina|pres|fosfororesina)$/],
    ["pmeh", /^(pmehlich1?|pm1|pmeh|fosforomehlich1?)$/],
    ["k", /^k$/],
    ["ca", /^ca$/],
    ["mg", /^mg$/],
    ["al", /^al$/],
    ["hal", /^hal$/],
    ["s", /^(sso4?2?|s|enxofre)$/],
    ["B", /^b$/], ["Cu", /^cu$/], ["Fe", /^fe$/], ["Mn", /^mn$/], ["Zn", /^zn$/],
    ["arg", /^argila$/],
    ["_ign", /^(h|na|co|si|sb|ctc|t|v|m|ce|umidade|silte|areia\w*|prem|nicrip|prfosfrel|ntotal|\w*inorganico|cl|cd|cr|ni|pb|ad|classedead|tiposolo|ras|camg|cak|mgk|\w*ctc|cassificacao|classificacao|textura)$/],
  ];
  const norm = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[₀-₉]/g, (d) => String("₀₁₂₃₄₅₆₇₈₉".indexOf(d)))
    .toLowerCase().replace(/[^a-z0-9]/g, "");
  function chaveRotulo(txt) {
    const n = norm(txt);
    if (!n) return null;
    for (const [k, re] of ROTULOS) if (re.test(n)) return k;
    return null;
  }

  /** "7,8" → 7.8; "1.234,5" → 1234.5; "<0,1" → 0.1; "-", "ns", "" → null. */
  function numero(s) {
    let t = String(s).trim().replace(/^[<>≤≥]\s*/, "");
    if (!/^-?[\d.,]+$/.test(t) || !/\d/.test(t)) return null;
    if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(t)) t = t.replace(/\./g, "");
    const n = parseFloat(t.replace(",", "."));
    return isNaN(n) ? null : n;
  }

  /** Profundidade em cm a partir da descrição ("01 - 0-20", "Talhão 1 - 20-40 CM"). */
  function profundidade(desc) {
    const m = String(desc).match(/(\d{1,3})\s*(?:-|–|a|até)\s*(\d{1,3})\s*(?:cm)?\s*$/i) || String(desc).match(/(\d{1,3})\s*(?:-|–|a)\s*(\d{1,3})\s*cm/i);
    return m ? [+m[1], +m[2]] : null;
  }

  // ------------------------------------------------------------ geometria

  const centro = (it) => it.x + (it.w || 0) / 2;

  /** Agrupa itens em linhas (mesma página, y a até `tol` pontos), de cima para baixo. */
  function linhas(itens, tol = 3) {
    const ord = itens.slice().sort((a, b) => a.p - b.p || b.y - a.y || a.x - b.x);
    const out = [];
    for (const it of ord) {
      const l = out[out.length - 1];
      if (l && l.p === it.p && Math.abs(l.y - it.y) <= tol) l.itens.push(it);
      else out.push({ p: it.p, y: it.y, itens: [it] });
    }
    out.forEach((l) => l.itens.sort((a, b) => a.x - b.x));
    return out;
  }

  const maisPerto = (x, colunas) => {
    let best = null, d = Infinity;
    for (const c of colunas) { const dd = Math.abs(c.cx - x); if (dd < d) { d = dd; best = c; } }
    return { col: best, dist: d };
  };

  /** Texto à direita de um rótulo ("Propriedade:" → "FAZENDA X"), na mesma linha. */
  function campoCabecalho(ls, re) {
    for (const l of ls) {
      const i = l.itens.findIndex((it) => re.test(norm(it.s)));
      if (i < 0) continue;
      const partes = [];
      for (const it of l.itens.slice(i + 1)) { if (/:\s*$/.test(it.s)) break; partes.push(it.s.trim()); }
      return partes.join(" ").trim();
    }
    return "";
  }

  // ------------------------------------------------------------ formato "linhas"
  // Linha de cabeçalho: "Determinação | Unidade | amostra1 | amostra2 ...".

  function lerLinhas(ls) {
    const iCab = ls.findIndex((l) => l.itens.some((it) => /^determina/.test(norm(it.s))) && l.itens.some((it) => norm(it.s) === "unidade"));
    if (iCab < 0) return null;
    const cab = ls[iCab], itUn = cab.itens.find((it) => norm(it.s) === "unidade");
    const colunas = cab.itens.filter((it) => it.x > itUn.x + (itUn.w || 20)).map((it, i) => ({ i, cod: it.s.trim(), cx: centro(it) }));
    if (!colunas.length) return null;
    const xUn = itUn.x - 8, xVal = Math.min(...colunas.map((c) => c.cx)) - 25;
    const dados = colunas.map(() => ({}));
    const unidades = {};
    for (const l of ls.slice(iCab + 1)) {
      if (l.p !== cab.p) break;
      const rot = l.itens.filter((it) => it.x < xUn).map((it) => it.s).join(" ");
      const k = chaveRotulo(rot.replace(/[₀-₉]/g, "")) || chaveRotulo(rot);
      if (!k) continue;
      const un = l.itens.filter((it) => it.x >= xUn && it.x < xVal).map((it) => it.s).join("").trim();
      for (const it of l.itens.filter((it) => it.x >= xVal)) {
        const v = numero(it.s); if (v == null) continue;
        const { col, dist } = maisPerto(centro(it), colunas); if (dist > 30) continue;
        // K vem duas vezes (mmolc e mg): guarda as duas
        const kk = k === "k" ? (/mg/i.test(un) ? "kmg" : "k") : k;
        if (dados[col.i][kk] == null) dados[col.i][kk] = v;
        unidades[kk] = un;
      }
    }
    // descrição das amostras ("Identificação das amostras": código → "01 - 0-20")
    const desc = {};
    const iId = ls.findIndex((l) => l.itens.some((it) => /identificacaodasamostras/.test(norm(it.s))));
    if (iId >= 0) {
      const bloco = ls.slice(iId + 1, iId + 25);
      for (const c of colunas) {
        if (!/\d{3,}/.test(c.cod)) continue;
        const i = bloco.findIndex((l) => l.itens.some((it) => it.s.trim() === c.cod));
        if (i < 0) continue;
        const lin = bloco[i], viz = [lin, bloco[i - 1]].filter((l) => l && Math.abs(l.y - lin.y) <= 3);
        const itCod = lin.itens.find((it) => it.s.trim() === c.cod);
        const txt = viz.flatMap((l) => l.itens).filter((it) => it.x > itCod.x && it.x < itCod.x + 200 && !/^-+$/.test(it.s.replace(/\s/g, "")))
          .sort((a, b) => a.x - b.x).map((it) => it.s.trim()).find((s) => s && s !== c.cod);
        if (txt) desc[c.cod] = txt;
      }
    }
    return colunas.map((c) => ({ id: c.cod, descricao: desc[c.cod] || c.cod, bruto: dados[c.i], unidades }))
      .filter((a) => Object.keys(a.bruto).length >= 3);
  }

  // ------------------------------------------------------------ formato "colunas"
  // Linhas de dados começam com um código numérico e a descrição da amostra; o
  // cabeçalho de cada tabela fica até ~40 pontos acima da primeira linha de dados.

  function lerColunas(ls) {
    const eDado = (l) => l.itens.length >= 4 && /^\d{1,8}$/.test(l.itens[0].s.trim()) && l.itens.slice(2).filter((it) => numero(it.s) != null || norm(it.s) === "ns").length >= 2;
    const amostras = new Map();
    for (let i = 0; i < ls.length; i++) {
      if (!eDado(ls[i]) || (i > 0 && eDado(ls[i - 1]) && ls[i - 1].p === ls[i].p)) continue;
      // bloco = esta linha + as seguintes que também são dados
      const bloco = [ls[i]];
      for (let j = i + 1; j < ls.length && eDado(ls[j]) && ls[j].p === ls[i].p; j++) bloco.push(ls[j]);
      const y0 = ls[i].y, cab = ls.filter((l) => l.p === ls[i].p && l.y > y0 + 4 && l.y <= y0 + 40).flatMap((l) => l.itens);
      const colunas = cab.map((it) => ({ k: chaveRotulo(it.s), cx: centro(it), it })).filter((c) => c.k);
      if (colunas.length < 2) continue;
      const txtCab = cab.map((it) => it.s).join(" ");
      const un = /cmol/i.test(txtCab) ? "cmolc" : /mmol/i.test(txtCab) ? "mmolc" : "";
      const xDesc = bloco[0].itens[1].x;
      for (const l of bloco) {
        const cod = l.itens[0].s.trim();
        const itValores = l.itens.filter((it) => it.x > xDesc && (numero(it.s) != null || norm(it.s) === "ns"));
        const primeiroValor = itValores.length ? itValores[0].x : Infinity;
        const descricao = l.itens.slice(1).filter((it) => it.x < primeiroValor).map((it) => it.s.trim()).join(" ");
        const a = amostras.get(cod) || { id: cod, descricao, bruto: {}, unidades: {} };
        for (const it of itValores) {
          const v = numero(it.s); if (v == null) continue;
          const { col, dist } = maisPerto(centro(it), colunas); if (dist > 22 || col.k[0] === "_") continue;
          if (a.bruto[col.k] == null) a.bruto[col.k] = v;
          if (["k", "ca", "mg", "al", "hal"].includes(col.k) && un) a.unidades[col.k] = un;
          if (col.k === "arg") a.unidades.arg = /g\s*kg/i.test(txtCab) ? "g/kg" : a.unidades.arg;
        }
        amostras.set(cod, a);
      }
      i += bloco.length - 1;
    }
    return [...amostras.values()].filter((a) => Object.keys(a.bruto).length >= 3);
  }

  // ------------------------------------------------------------ montagem

  /** Converte os valores brutos de uma amostra para o formato do laudo do motor. */
  function paraLaudo(a) {
    const b = a.bruto, u = a.unidades || {}, avisos = [];
    const unCat = u.ca || u.k || "";
    const unidade = /cmol|meq/i.test(unCat) ? "c" : "m";
    const laudo = { unidade, unidadeK: "same" };
    for (const k of ["ph", "mo", "ca", "mg", "al", "hal", "B", "Cu", "Fe", "Mn", "Zn"]) if (b[k] != null) laudo[k] = b[k];
    if (b.k != null) laudo.k = b.k;
    else if (b.kmg != null) { laudo.k = b.kmg; laudo.unidadeK = "mg"; }
    if (b.s != null) laudo.s = b.s;
    if (b.arg != null) {
      const gkg = /g\/?kg/i.test(u.arg || "") || b.arg > 100;
      laudo.arg = gkg ? +(b.arg / 10).toFixed(1) : b.arg;
    }
    // M.O. em % (dag/kg) → g/dm³
    if (laudo.mo != null && /%|dag/i.test(u.mo || "")) laudo.mo = +(laudo.mo * 10).toFixed(1);
    laudo.pres = b.pres ?? null; laudo.pmeh = b.pmeh ?? null;
    if (!unCat) avisos.push("Unidade dos cátions não identificada: considerei mmolc/dm³. Confira.");
    return { id: a.id, descricao: a.descricao, prof: profundidade(a.descricao), laudo, avisos };
  }

  /**
   * itens: [{p, x, y, w, s}] de todas as páginas.
   * Retorna { formato, propriedade, proprietario, amostras:[{id, descricao, prof, laudo, avisos}] } ou { erro }.
   */
  function interpretar(itens) {
    const uteis = (itens || []).filter((it) => it && String(it.s).trim());
    if (uteis.length < 20) return { erro: "O PDF não tem texto (parece escaneado ou foto). Digite os valores do laudo." };
    const ls = linhas(uteis);
    let formato = "linhas", brutas = lerLinhas(ls);
    if (!brutas || !brutas.length) { formato = "colunas"; brutas = lerColunas(ls); }
    if (!brutas || !brutas.length) return { erro: "Não reconheci a tabela deste laudo. Digite os valores e, se puder, mande o PDF para ajustarmos o leitor." };
    const amostras = brutas.map(paraLaudo);
    return {
      formato,
      propriedade: campoCabecalho(ls, /^propriedade$/),
      proprietario: campoCabecalho(ls, /^proprietario$/),
      amostras,
    };
  }

  /** Sugere a amostra superficial (0–20) e a subsuperficial (20–40) pelas profundidades. */
  function sugerirPar(amostras) {
    const sup = amostras.find((a) => a.prof && a.prof[0] === 0) || amostras[0] || null;
    const sub = amostras.find((a) => a !== sup && a.prof && a.prof[0] >= 15 && a.prof[0] <= 25) || null;
    return { sup, sub };
  }

  /**
   * Monta os campos do formulário a partir das amostras escolhidas.
   * metodo decide o extrator de P quando o laudo traz os dois (B100 → resina; outros → Mehlich-1).
   */
  function camposFormulario(sup, sub, metodo) {
    const L = sup.laudo, f = { un: L.unidade, kun: L.unidadeK }, avisos = [...sup.avisos];
    for (const k of ["ph", "mo", "k", "ca", "mg", "al", "hal", "arg", "B", "Cu", "Fe", "Mn", "Zn"]) if (L[k] != null) f[k] = L[k];
    const prefRes = metodo === "b100";
    const p = prefRes ? (L.pres ?? L.pmeh) : (L.pmeh ?? L.pres);
    if (p != null) {
      f.p = p; f.pext = p === L.pres && L.pres != null ? "resina" : "mehlich";
      if (prefRes && f.pext === "mehlich") avisos.push("O laudo só traz P Mehlich-1; o Boletim 100 usa P resina.");
      if (!prefRes && f.pext === "resina" && metodo === "mg") avisos.push("O laudo só traz P resina; a 5ª Aproximação usa Mehlich-1.");
    } else avisos.push("Não encontrei o P no laudo.");
    if (L.s != null) f.s1 = L.s;
    if (sub) {
      const S = sub.laudo;
      if (S.unidade !== L.unidade || S.unidadeK !== L.unidadeK) avisos.push("As duas camadas vieram em unidades diferentes; confira a de 20–40 cm.");
      for (const [de, para] of [["ca", "ca2"], ["mg", "mg2"], ["k", "k2"], ["al", "al2"], ["hal", "hal2"], ["s", "s2"]]) if (S[de] != null) f[para] = S[de];
    }
    for (const k of ["k", "ca", "mg", "hal", "arg"]) if (f[k] == null) avisos.push(`Não encontrei ${{ k: "K", ca: "Ca", mg: "Mg", hal: "H+Al", arg: "argila" }[k]} no laudo.`);
    return { campos: f, avisos };
  }

  // ------------------------------------------------------------ navegador

  async function lerPdf(arquivo) {
    const lib = typeof window !== "undefined" && window.pdfjsLib;
    if (!lib) throw new Error("O leitor de PDF não carregou. Verifique a internet e recarregue o Gestor.");
    if (!lib.GlobalWorkerOptions.workerSrc) lib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";
    const doc = await lib.getDocument({ data: new Uint8Array(await arquivo.arrayBuffer()) }).promise;
    const itens = [];
    for (let p = 1; p <= Math.min(doc.numPages, 10); p++) {
      const tc = await (await doc.getPage(p)).getTextContent();
      for (const it of tc.items) if (it.str && it.str.trim()) itens.push({ p, x: it.transform[4], y: it.transform[5], w: it.width, s: it.str });
    }
    return interpretar(itens);
  }

  return { interpretar, sugerirPar, camposFormulario, lerPdf, numero, profundidade, chaveRotulo };
});
