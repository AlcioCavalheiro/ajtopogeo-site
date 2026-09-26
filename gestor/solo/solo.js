/* Recomendação de Solo — página do Gestor AJ TopoGeo (menu Ferramentas).
 *
 * Só interface: lê o formulário, chama SoloMotor.calcular() (gestor/solo/motor.js)
 * com as tabelas (gestor/solo/tabelas.js) e desenha o resultado. Nenhuma conta
 * mora aqui — regra nova vai no motor, com teste em gestor/solo/test/.
 *
 * Guardado neste navegador (localStorage), como no protótipo:
 *   gestor-solo:laudos ... laudos salvos por cliente/talhão (até 100)
 *   gestor-solo:cfg ...... tabelas de cultura editadas (só as diferentes do original)
 *
 * Entra no Gestor por window.SoloUI.render(el) — ver pageMap.solo no index.html.
 */
(function () {
  "use strict";

  const UI = (window.SoloUI = window.SoloUI || {});
  const KEY = "gestor-solo";
  const clone = (o) => JSON.parse(JSON.stringify(o));
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const $ = (id) => document.getElementById("so-" + id);

  let cfg = null, metodo = "b100", rascunho = null, ultimo = null;

  // ------------------------------------------------------------ tabelas (com edições locais)

  function carregarCfg() {
    cfg = clone(window.SoloTabelas);
    try {
      const o = JSON.parse(localStorage.getItem(KEY + ":cfg") || "null");
      if (o) for (const m in o) for (const c in o[m]) if (cfg.DEF[m] && cfg.DEF[m].crops[c]) cfg.DEF[m].crops[c] = o[m][c];
    } catch (e) {}
  }
  function salvarCfg() {
    const o = {}, D = window.SoloTabelas.DEF;
    for (const m in cfg.DEF) {
      o[m] = {};
      for (const c in cfg.DEF[m].crops)
        if (JSON.stringify(cfg.DEF[m].crops[c]) !== JSON.stringify(D[m].crops[c])) o[m][c] = cfg.DEF[m].crops[c];
    }
    try { localStorage.setItem(KEY + ":cfg", JSON.stringify(o)); } catch (e) {}
  }
  const cropAtual = () => cfg.DEF[metodo].crops[$("cult").value];

  // ------------------------------------------------------------ estilos (escopo #solo)

  const CSS = `
#solo .so-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}
#solo .so-grid .fg{margin-bottom:0}
#solo .card{margin-bottom:1rem}
#solo h3.so-h{font-size:12px;font-weight:700;color:var(--mu);text-transform:uppercase;letter-spacing:.05em;margin:1rem 0 .6rem}
#solo .so-hint{font-size:12px;color:var(--mu);margin-top:6px;line-height:1.45}
#solo .so-warn{background:#FAEEDA;color:#6b3f08;border-left:4px solid #EF9F27;padding:9px 12px;border-radius:6px;margin:6px 0;font-size:13px;line-height:1.45}
#solo .so-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(115px,1fr));gap:8px;margin-bottom:1rem}
#solo .so-dose{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:.5rem 0 .75rem}
#solo .so-dose>div{border-top:4px solid var(--bd);padding-top:6px}
#solo .so-dose>div:nth-child(2){border-color:#EF9F27}#solo .so-dose>div:nth-child(3){border-color:#8a8a80}
#solo .so-big{font-size:26px;font-weight:800;line-height:1.1}
#solo td.n,#solo th.n{text-align:right;white-space:nowrap}
#solo .so-cls{display:inline-block;padding:2px 9px;border-radius:99px;font-size:11px;font-weight:700;white-space:nowrap}
#solo .so-c0{background:#FCEBEB;color:#A32D2D}#solo .so-c1{background:#FAEEDA;color:#854F0B}#solo .so-c2{background:#EAF3DE;color:#3B6D11}
#solo .so-vbar{position:relative;height:26px;border-radius:6px;background:repeating-linear-gradient(90deg,var(--bor) 0 1px,transparent 1px 10%);border:1px solid var(--bor2);margin:22px 0 26px}
#solo .so-vbar .f{position:absolute;left:0;top:0;bottom:0;background:var(--brand);opacity:.85;border-radius:5px 0 0 5px}
#solo .so-vbar .g{position:absolute;top:0;bottom:0;background:repeating-linear-gradient(135deg,#EF9F27 0 6px,transparent 6px 11px);opacity:.75}
#solo .so-vbar .t{position:absolute;font-size:11px;white-space:nowrap;transform:translateX(-50%)}
#solo .so-vbar .t.up{top:-18px}#solo .so-vbar .t.dn{bottom:-19px}
#solo details>summary{cursor:pointer;font-weight:600;font-size:14px}
#solo .so-lista{list-style:none;margin-top:.5rem}
#solo .so-lista li{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:8px 0;border-bottom:1px solid var(--bor)}
#solo .so-refs{padding-left:18px;margin-top:.6rem;font-size:12.5px;line-height:1.5}#solo .so-refs li{margin-bottom:6px}
#solo textarea.so-json{font:12px/1.4 ui-monospace,Menlo,Consolas,monospace;min-height:260px}
#solo .hide{display:none!important}
@media(max-width:600px){#solo .so-dose{grid-template-columns:1fr 1fr}#solo .so-big{font-size:22px}#solo .card{padding:1rem}}
`;

  // ------------------------------------------------------------ formulário

  const campo = (id, rot, extra = "") =>
    `<div class="fg"><label class="fl" for="so-${id}">${rot}</label><input class="fc" id="so-${id}" type="text" inputmode="decimal" autocomplete="off"${extra}></div>`;
  const selecao = (id, rot, opts, extra = "") =>
    `<div class="fg"${extra}><label class="fl" for="so-${id}">${rot}</label><select class="fc" id="so-${id}">${opts.map(([v, t, s]) => `<option value="${v}"${s ? " selected" : ""}>${t}</option>`).join("")}</select></div>`;

  const HINT = {
    b100: "P em resina, cátions em mmolc/dm³. Calagem por saturação por bases e doses por classe de teor e produtividade esperada.",
    mg: "P e K por Mehlich-1, com P interpretado pela argila. Calagem pelos dois métodos (Al e Ca + Mg ou V%) e doses por disponibilidade baixa, média ou boa.",
    cerrado: "P por Mehlich-1 ou resina interpretado pela argila, correção de P pela capacidade tampão, K pela CTC e manutenção pela produtividade.",
  };
  const METODOS = [["b100", "Boletim 100 · 2022"], ["mg", "5ª Aproximação · MG"], ["cerrado", "Embrapa Cerrados"]];

  function htmlPagina() {
    return `<div id="solo" style="max-width:900px">
<div class="card">
  <div class="tabs" id="so-metodo" style="margin-bottom:.6rem">${METODOS.map(([k, t]) => `<div class="tab" data-v="${k}">${t}</div>`).join("")}</div>
  <div class="so-hint" id="so-metHint" style="margin-top:0"></div>
</div>

<div class="card">
  <div class="st"><i class="ti ti-flask"></i> Laudo de solo (0–20 cm)</div>
  <div class="so-grid" style="margin-bottom:10px">
    ${selecao("un", "Unidade de Ca, Mg, Al, H+Al", [["m", "mmolc/dm³"], ["c", "cmolc/dm³"]])}
    ${selecao("kun", "Unidade do K", [["same", "mesma dos cátions"], ["mg", "mg/dm³"]])}
    ${selecao("pext", "Extrator de P", [["resina", "Resina"], ["mehlich", "Mehlich-1"]])}
  </div>
  <div class="so-grid">
    ${campo("ph", "pH (CaCl₂)")}${campo("mo", "M.O. (g/dm³)")}${campo("p", "P (mg/dm³)")}${campo("k", "K")}
    ${campo("ca", "Ca")}${campo("mg", "Mg")}${campo("al", "Al")}${campo("hal", "H+Al")}${campo("arg", "Argila (%)")}
  </div>
  <h3 class="so-h">Subsuperfície 20–40 cm · gessagem e enxofre</h3>
  <div class="so-grid">${campo("ca2", "Ca")}${campo("mg2", "Mg")}${campo("k2", "K")}${campo("al2", "Al")}${campo("hal2", "H+Al")}</div>
  <details style="margin-top:1rem">
    <summary>Enxofre e micronutrientes (opcional)</summary>
    <div class="so-grid" style="margin-top:10px">
      ${campo("s1", "S 0–20 (mg/dm³)")}${campo("s2", "S 20–40 (mg/dm³)")}${campo("B", "B (mg/dm³)")}${campo("Cu", "Cu (mg/dm³)")}
      ${campo("Fe", "Fe (mg/dm³)")}${campo("Mn", "Mn (mg/dm³)")}${campo("Zn", "Zn (mg/dm³)")}
    </div>
    <div class="so-hint" id="so-microHint"></div>
  </details>
</div>

<div class="card">
  <div class="st"><i class="ti ti-plant-2"></i> Cultura e manejo</div>
  <div class="so-grid">
    <div class="fg" style="grid-column:1/-1"><label class="fl" for="so-cult">Cultura</label><select class="fc" id="so-cult"></select></div>
    ${selecao("prodSel", "Produtividade esperada", [], ' id="so-prodSelBox"')}
    <div class="fg" id="so-prodBox"><label class="fl" for="so-prod">Produtividade esperada (t/ha)</label><input class="fc" id="so-prod" type="text" inputmode="decimal"></div>
    ${selecao("resp", "Resposta esperada a N", [["alta", "Alta"], ["media", "Média", 1], ["baixa", "Baixa"]], ' id="so-respBox"')}
    ${selecao("corr", "Correção de P e K", [["total", "Corretiva total (a lanço)"], ["gradual", "Corretiva gradual (no sulco)"]], ' id="so-corrBox"')}
    ${selecao("anos", "Anos da correção gradual de P", [["2", "2"], ["3", "3"], ["4", "4", 1], ["5", "5"]], ' id="so-anosBox"')}
    <div class="fg"><label class="fl" for="so-prnt">PRNT do calcário (%)</label><input class="fc" id="so-prnt" type="text" inputmode="decimal" value="85"></div>
    ${selecao("prof", "Incorporação do calcário", [["20", "0–20 cm"], ["30", "0–30 cm"], ["40", "0–40 cm"]])}
    <div class="fg"><label class="fl" for="so-area">Área (ha)</label><input class="fc" id="so-area" type="text" inputmode="decimal" value="1"></div>
  </div>
  <div class="so-hint" id="so-respHint"></div>
  <h3 class="so-h">Fertilizantes</h3>
  <div class="so-grid">
    ${selecao("modo", "Forma de aplicação", [["simples", "Fontes simples"], ["formula", "Formulado NPK + complemento"]])}
    <div class="fg hide" id="so-fBox"><label class="fl" for="so-formula">Fórmula (N-P-K)</label><input class="fc" id="so-formula" value="04-14-08"></div>
    ${selecao("fn", "Fonte de N", [["44", "Ureia (44% N)"], ["20", "Sulfato de amônio (20% N)"], ["32", "Nitrato de amônio (32% N)"]])}
    ${selecao("fp", "Fonte de P", [["ssp", "Superfosfato simples (18%)"], ["tsp", "Superfosfato triplo (41%)"], ["map", "MAP (9-48-00)"]])}
    ${selecao("fk", "Fonte de K", [["58", "Cloreto de potássio (58%)"], ["48", "Sulfato de potássio (48%)"]])}
  </div>
  <div class="so-hint">Teores das fontes pelas garantias mínimas do MAPA citadas no Boletim 100. Ajuste se o seu produto tiver garantia maior.</div>
  <div class="fx g8" style="margin-top:1rem;flex-wrap:wrap">
    <button class="btn bp2" id="so-calc" type="button"><i class="ti ti-calculator"></i> Calcular recomendação</button>
    <button class="btn" id="so-limpar" type="button"><i class="ti ti-eraser"></i> Limpar laudo</button>
  </div>
</div>

<div id="so-out" aria-live="polite"></div>

<div class="card">
  <details>
    <summary><i class="ti ti-device-floppy"></i> Laudos salvos</summary>
    <div class="fx g8" style="margin-top:.75rem;flex-wrap:wrap;align-items:flex-end">
      <div class="fg" style="flex:1 1 220px;margin:0"><label class="fl" for="so-nome">Nome (cliente / talhão)</label><input class="fc" id="so-nome" placeholder="Ex.: Faz. Boa Vista – T3"></div>
      <button class="btn" id="so-save" type="button"><i class="ti ti-device-floppy"></i> Salvar laudo</button>
    </div>
    <ul class="so-lista" id="so-lista"></ul>
    <div class="so-hint">Fica gravado neste aparelho/navegador.</div>
  </details>
</div>

<div class="card">
  <details>
    <summary><i class="ti ti-table"></i> Tabela da cultura (editável)</summary>
    <div class="so-hint">Os valores abaixo são os usados no cálculo. Se a sua edição do boletim tiver números diferentes, edite e salve. Fica gravado neste navegador.</div>
    <textarea class="fc so-json" id="so-json" rows="14" style="margin-top:.5rem"></textarea>
    <div class="fx g8" style="margin-top:.6rem;flex-wrap:wrap">
      <button class="btn" id="so-saveJson" type="button">Salvar tabela</button>
      <button class="btn" id="so-resetCfg" type="button">Restaurar original</button>
    </div>
    <div class="so-hint" id="so-jsonMsg"></div>
  </details>
</div>

<div class="card">
  <details>
    <summary><i class="ti ti-books"></i> Fontes consultadas</summary>
    <ul class="so-refs">
      <li>CANTARELLA, H.; QUAGGIO, J. A.; MATTOS JR., D.; BOARETTO, R. M.; RAIJ, B. van (Ed.). <i>Boletim 100: Recomendações de adubação e calagem para o estado de São Paulo</i>. Campinas: IAC, 2022.</li>
      <li>RAIJ, B. van et al. (Ed.). <i>Recomendações de adubação e calagem para o Estado de São Paulo</i>. 2. ed. IAC, 1997 (Boletim Técnico 100). Critério geral de gessagem para grãos.</li>
      <li>RIBEIRO, A. C.; GUIMARÃES, P. T. G.; ALVAREZ V., V. H. (Ed.). <i>Recomendações para o uso de corretivos e fertilizantes em Minas Gerais – 5ª aproximação</i>. Viçosa: CFSEMG, 1999.</li>
      <li>SEIXAS, C. D. S. et al. (Ed.). <i>Tecnologias de produção de soja</i>. Embrapa Soja, 2020 (Sistemas de Produção 17), cap. 7.</li>
      <li>SOUSA, D. M. G.; LOBATO, E. (Ed.). <i>Cerrado: correção do solo e adubação</i>. 2. ed. Embrapa Cerrados, 2004; VILELA, L. et al. Adubação potássica, no mesmo livro.</li>
    </ul>
  </details>
</div>
<div class="so-hint" style="margin-bottom:1rem"><i class="ti ti-alert-circle"></i> Ferramenta de apoio ao técnico. A recomendação final e a ART são responsabilidade do profissional habilitado.</div>
</div>`;
  }

  // ------------------------------------------------------------ comportamento do formulário

  function fillCrops() {
    const sel = $("cult"), cur = sel.value;
    sel.innerHTML = Object.entries(cfg.DEF[metodo].crops).map(([k, c]) => `<option value="${k}">${esc(c.nome)}</option>`).join("");
    if (cur && cfg.DEF[metodo].crops[cur]) sel.value = cur;
    onCrop();
  }

  function onCrop() {
    const c = cropAtual(), tab = metodo !== "cerrado";
    const box = (id, esconder) => document.getElementById("so-" + id).classList.toggle("hide", esconder);
    box("prodSelBox", !tab || c.prod.length < 2);
    box("prodBox", tab);
    box("corrBox", tab);
    box("anosBox", tab || $("corr").value !== "gradual");
    const rk = SoloMotor.chavesResposta(c, cfg);
    box("respBox", !rk);
    if (rk) {
      const cur = $("resp").value;
      $("resp").innerHTML = rk.map((k) => `<option value="${k}">${SoloMotor.rotuloResposta(k, rk)}</option>`).join("");
      if (rk.includes(cur)) $("resp").value = cur;
    }
    $("respHint").textContent = rk
      ? c.respNota || "Alta: solo corrigido após gramíneas, primeiros anos de plantio direto ou solo arenoso. Média e baixa: após leguminosas, pousio longo ou adubação orgânica frequente."
      : "";
    if (tab) {
      const ps = $("prodSel"), cur = ps.value;
      ps.innerHTML = c.prod.map((l, i) => `<option value="${i}">${esc(l)}</option>`).join("");
      if (cur && +cur < c.prod.length) ps.value = cur;
    } else if (!$("prod").value) $("prod").value = String(c.prod).replace(".", ",");
    $("json").value = JSON.stringify(c, null, 1);
    $("jsonMsg").textContent = "";
  }

  function setMetodo(m) {
    metodo = m;
    document.querySelectorAll("#so-metodo .tab").forEach((b) => b.classList.toggle("active", b.dataset.v === m));
    $("metHint").textContent = HINT[m];
    $("microHint").textContent = m === "mg"
      ? "Na 5ª Aproximação os micronutrientes seguem notas de cada cultura (veja Observações)."
      : "Interpretação: " + cfg.MICRO[m].fonte + ".";
    $("pext").value = m === "b100" ? "resina" : "mehlich";
    $("prod").value = "";
    fillCrops();
  }

  const CAMPOS = ["un", "kun", "pext", "ph", "mo", "p", "k", "ca", "mg", "al", "hal", "arg", "ca2", "mg2", "k2", "al2", "hal2",
    "s1", "s2", "B", "Cu", "Fe", "Mn", "Zn", "cult", "prodSel", "prod", "resp", "corr", "anos", "prnt", "prof", "area",
    "modo", "formula", "fn", "fp", "fk", "nome"];
  const LAUDO = ["ph", "mo", "p", "k", "ca", "mg", "al", "hal", "arg", "ca2", "mg2", "k2", "al2", "hal2", "s1", "s2", "B", "Cu", "Fe", "Mn", "Zn"];

  function lerCampos() { const v = {}; CAMPOS.forEach((f) => (v[f] = $(f) ? $(f).value : null)); return v; }
  function aplicarCampos(m, v) {
    $("cult").value = v.cult; setMetodo(m);
    if (v.cult && cfg.DEF[m].crops[v.cult]) { $("cult").value = v.cult; onCrop(); }
    CAMPOS.forEach((f) => { if (v[f] != null && $(f)) $(f).value = v[f]; });
    $("fBox").classList.toggle("hide", $("modo").value !== "formula");
    onCrop();
    ["prodSel", "resp"].forEach((f) => { if (v[f] != null) $(f).value = v[f]; });
  }

  function entrada() {
    const v = lerCampos(), laudo = { unidade: v.un, unidadeK: v.kun, extratorP: v.pext };
    LAUDO.forEach((f) => (laudo[f] = v[f]));
    return {
      metodo, cultura: v.cult, laudo,
      manejo: { prodIdx: v.prodSel, prod: v.prod, resp: v.resp, correcao: v.corr, anos: v.anos, prnt: v.prnt, prof: v.prof, area: v.area },
      fertilizantes: { modo: v.modo, formula: v.formula, fonteN: v.fn, fonteP: v.fp, fonteK: v.fk },
    };
  }

  // ------------------------------------------------------------ resultado

  const { f1, f0 } = window.SoloMotor || {};

  function htmlResultado(r, nome) {
    const I = r.indices, a = r.adubacao, V = I.V, V2 = r.V2;
    const vPct = Math.min(100, Math.max(0, V)), v2Pct = Math.min(100, V2);
    const chip = (i, n, of) => { const k = Math.min(2, Math.round((i * 2) / Math.max(1, of - 1))); return `<span class="so-cls so-c${k}">${esc(n)}</span>`; };
    const titulo = `${esc(r.culturaNome)} · ${esc(r.metodoNome)}${nome ? " · " + esc(nome) : ""}`;
    return `
<div class="card">
  <div class="st" style="margin-bottom:.3rem"><i class="ti ti-report-analytics"></i> ${titulo}</div>
  <div class="so-hint" style="margin:0 0 1rem">${r.prodTxt && r.prodTxt !== "—" ? "Produtividade esperada: " + esc(r.prodTxt) + ". " : ""}Fonte: ${esc(r.fonte)}</div>
  <div class="so-kpis">
    <div class="mc"><div class="ml">SB</div><div class="mv">${f1(I.SB, 2)}</div><div class="ms">cmolc/dm³</div></div>
    <div class="mc"><div class="ml">CTC pH 7</div><div class="mv">${f1(I.T, 2)}</div><div class="ms">cmolc/dm³</div></div>
    <div class="mc"><div class="ml">V%</div><div class="mv">${f0(V)}%</div><div class="ms">saturação por bases</div></div>
    <div class="mc"><div class="ml">m%</div><div class="mv">${f0(I.m)}%</div><div class="ms">saturação por Al</div></div>
    <div class="mc"><div class="ml">Ca:Mg</div><div class="mv">${I.Mg > 0 ? f1(I.Ca / I.Mg, 1) : "–"}</div><div class="ms">relação</div></div>
    <div class="mc"><div class="ml">K na CTC</div><div class="mv">${f1((I.K / I.T) * 100, 1)}%</div><div class="ms">&nbsp;</div></div>
  </div>
  <div class="so-vbar" role="img" aria-label="V% atual ${f0(V)}, desejada ${V2}">
    <div class="f" style="width:${vPct}%"></div>
    ${V < V2 ? `<div class="g" style="left:${vPct}%;width:${v2Pct - vPct}%"></div>` : ""}
    <span class="t dn" style="left:${Math.max(6, vPct)}%">atual ${f0(V)}%</span>
    <span class="t up" style="left:${Math.min(90, v2Pct)}%">meta ${V2}%</span>
  </div>
  <div class="tw"><table>
    <tr><th>Nutriente</th><th>Teor</th><th>Classe</th></tr>
    <tr><td>P (${r.extratorP === "resina" ? "resina" : "Mehlich-1"})</td><td>${f1(r.classes.P.teor)} mg/dm³<div class="so-hint" style="margin:2px 0 0">${esc(r.classes.P.col)}</div></td><td>${chip(r.classes.P.i, r.classes.P.nome, r.classes.P.n)}</td></tr>
    <tr><td>K</td><td>${f1(I.Kmm, 1)} mmolc/dm³ · ${f0(I.Kmg)} mg/dm³<div class="so-hint" style="margin:2px 0 0">${esc(r.classes.K.col)}</div></td><td>${chip(r.classes.K.i, r.classes.K.nome, r.classes.K.n)}</td></tr>
    ${I.V2sub != null ? `<tr><td>V% 20–40 cm</td><td>${f0(I.V2sub)}% · m ${f0(I.m2)}%</td><td></td></tr>` : ""}
    ${r.micros.map((x) => `<tr><td>${x.el}</td><td>${f1(x.v, 2)} mg/dm³</td><td>${chip(x.i * 2, x.cls, 5)}</td></tr>`).join("")}
  </table></div>
</div>

<div class="card">
  <div class="st"><i class="ti ti-shovel"></i> Correção do solo</div>
  <div class="so-dose">
    <div><div class="ml">Calcário${r.calagem.NCalt != null ? " (V%)" : ""}</div><div class="so-big">${f1(r.calagem.NC, 2)}</div><div class="ms">t/ha · PRNT ${r.calagem.PRNT}%</div></div>
    ${r.calagem.NCalt != null ? `<div><div class="ml">Calcário (Al e Ca + Mg)</div><div class="so-big">${f1(r.calagem.NCalt, 2)}</div><div class="ms">t/ha</div></div>` : "<div></div>"}
    <div><div class="ml">Gesso agrícola</div><div class="so-big">${f1(r.gesso.tha, 2)}</div><div class="ms">t/ha${r.gesso.motivo ? " · " + esc(r.gesso.motivo) : ""}</div></div>
  </div>
  <div class="so-hint">${esc(r.calagem.nota)}${r.calagem.fprof !== 1 ? ` Fator de profundidade ${f1(r.calagem.fprof, 1)}.` : ""} Gesso: ${esc(r.gesso.criterio)}${r.gesso.kgha > 0 && r.metodo === "b100" ? "; dose = 6 × argila (g/kg)" : ""}.</div>
  <div style="margin-top:.75rem;font-size:13px"><b>Total para ${f1(r.area, 2)} ha:</b> ${f1(r.calagem.total, 1)} t de calcário${r.calagem.NCalt != null ? " (pelo maior dos dois métodos)" : ""}${r.gesso.kgha > 0 ? ` e ${f1(r.gesso.total, 1)} t de gesso` : ""}.</div>
</div>

<div class="card">
  <div class="st"><i class="ti ti-droplet"></i> Adubação (kg/ha)</div>
  <div class="tw"><table>
    <tr><th>Época</th><th class="n">N</th><th class="n">P₂O₅</th><th class="n">K₂O</th></tr>
    ${a.Plan || a.Klan ? `<tr><td>Corretiva a lanço</td><td class="n">–</td><td class="n">${f0(a.Plan)}</td><td class="n">${f0(a.Klan)}</td></tr>` : ""}
    <tr><td>${esc(a.plantioLbl)}</td><td class="n">${f0(a.N1)}</td><td class="n">${f0(a.Psulco)}</td><td class="n">${f0(a.Ksulco)}</td></tr>
    <tr><td>Cobertura</td><td class="n">${f0(a.N2)}</td><td class="n">–</td><td class="n">${f0(a.Kcob)}</td></tr>
    <tr><td><b>Total</b></td><td class="n"><b>${f0(a.Ntot)}</b></td><td class="n"><b>${f0(a.Ptot)}</b></td><td class="n"><b>${f0(a.Ktot)}</b></td></tr>
  </table></div>
  ${r.tambem.length ? `<div style="margin-top:.75rem;font-size:13px"><b>Também aplicar:</b> ${r.tambem.map(esc).join(", ")}.</div>` : ""}
  <h3 class="so-h">Produtos comerciais</h3>
  <div class="tw"><table>
    <tr><th>Produto</th><th>Quando</th><th class="n">kg/ha</th><th class="n">Total área</th></tr>
    ${r.produtos.map((p) => `<tr><td>${esc(p.nm)}</td><td>${esc(p.q)}</td><td class="n">${f0(p.kg)}</td><td class="n">${f0(p.totalKg)} kg<div class="so-hint" style="margin:0">${f1(p.sacos, 1)} sc 50 kg</div></td></tr>`).join("")
      || `<tr><td colspan="4" class="so-hint">Nenhum fertilizante indicado.</td></tr>`}
  </table></div>
</div>

${r.avisos.length ? `<div class="card"><div class="st"><i class="ti ti-info-circle"></i> Observações</div>${r.avisos.map((w) => `<div class="so-warn">${esc(w)}</div>`).join("")}</div>` : ""}

<div class="card so-noprint">
  <div class="fx g8" style="flex-wrap:wrap"><button class="btn" type="button" id="so-print"><i class="ti ti-printer"></i> Imprimir / salvar PDF</button></div>
  <div class="so-hint">Ferramenta de apoio ao técnico. A recomendação final e a ART são responsabilidade do profissional habilitado.</div>
</div>`;
  }

  function calc(rolar = true) {
    const r = SoloMotor.calcular(entrada(), cfg), out = $("out");
    if (r.erro) { ultimo = null; out.innerHTML = `<div class="card"><div class="so-warn">${esc(r.erro)}</div></div>`; return; }
    ultimo = { r, nome: $("nome").value.trim() };
    out.innerHTML = htmlResultado(r, ultimo.nome);
    $("print").onclick = imprimir;
    if (rolar) out.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // Impressão: resultado num iframe com o CSS da página, sem menu e sem formulário.
  function imprimir() {
    if (!ultimo) return;
    const css = Array.from(document.querySelectorAll("style")).map((s) => s.textContent).join("\n");
    const fr = document.createElement("iframe");
    fr.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
    document.body.appendChild(fr);
    const d = fr.contentDocument;
    d.open();
    d.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Recomendação de calagem e adubação</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
<style>${css}
body{background:#fff;padding:12mm}#solo .card{break-inside:avoid;border-color:#ccc}.so-noprint{display:none!important}
@page{margin:10mm}</style></head><body><div id="solo">
<div style="margin-bottom:1rem"><div style="font-size:18px;font-weight:700">Recomendação de calagem e adubação</div>
<div class="so-hint">AJ TopoGeo · ${new Date().toLocaleDateString("pt-BR")}</div></div>
${htmlResultado(ultimo.r, ultimo.nome)}
<div class="so-hint">Ferramenta de apoio ao técnico. A recomendação final e a ART são responsabilidade do profissional habilitado.</div>
</div></body></html>`);
    d.close();
    const go = () => { try { fr.contentWindow.focus(); fr.contentWindow.print(); } finally { setTimeout(() => fr.remove(), 1500); } };
    if (d.readyState === "complete") setTimeout(go, 300); else fr.onload = go;
  }

  // ------------------------------------------------------------ laudos salvos

  const getSaved = () => { try { return JSON.parse(localStorage.getItem(KEY + ":laudos") || "[]"); } catch (e) { return []; } };
  const putSaved = (a) => { try { localStorage.setItem(KEY + ":laudos", JSON.stringify(a)); } catch (e) { if (typeof toast === "function") toast("Não consegui salvar neste navegador.", true); } };

  function renderSaved() {
    const a = getSaved();
    $("lista").innerHTML = a.length
      ? a.map((l, i) => `<li><span>${esc(l.nome || "Sem nome")} <span class="mu sm">· ${esc(cfg.DEF[l.metodo] ? cfg.DEF[l.metodo].nome : l.metodo)}${l.data ? " · " + esc(l.data) : ""}</span></span>
          <span class="fx g8"><button class="btn bxs" data-o="${i}">Abrir</button><button class="btn bxs bdr" data-d="${i}">Excluir</button></span></li>`).join("")
      : `<li class="mu sm">Nenhum laudo salvo. Preencha um laudo e toque em Salvar laudo.</li>`;
    $("lista").querySelectorAll("[data-o]").forEach((b) => (b.onclick = () => { const l = getSaved()[+b.dataset.o]; aplicarCampos(l.metodo, l.v); calc(); }));
    $("lista").querySelectorAll("[data-d]").forEach((b) => (b.onclick = () => {
      const a = getSaved(), l = a[+b.dataset.d];
      if (!confirm(`Excluir o laudo "${l.nome || "Sem nome"}"?`)) return;
      a.splice(+b.dataset.d, 1); putSaved(a); renderSaved();
    }));
  }

  // ------------------------------------------------------------ entrada no Gestor

  UI.render = function (el) {
    if (!window.SoloMotor || !window.SoloTabelas) {
      el.innerHTML = '<div class="card"><div class="mu sm">A Recomendação de Solo não carregou (arquivos gestor/solo/*.js). Recarregue a página.</div></div>';
      return;
    }
    if (!document.getElementById("solo-css")) {
      const s = document.createElement("style"); s.id = "solo-css"; s.textContent = CSS; document.head.appendChild(s);
    }
    if (!cfg) carregarCfg();
    el.innerHTML = htmlPagina();

    document.querySelectorAll("#so-metodo .tab").forEach((b) => (b.onclick = () => setMetodo(b.dataset.v)));
    $("cult").onchange = () => { $("prod").value = ""; onCrop(); };
    $("corr").onchange = onCrop;
    $("modo").onchange = () => $("fBox").classList.toggle("hide", $("modo").value !== "formula");
    $("calc").onclick = () => calc();
    $("limpar").onclick = () => { LAUDO.forEach((f) => ($(f).value = "")); $("nome").value = ""; $("out").innerHTML = ""; ultimo = null; rascunho = null; };
    $("save").onclick = () => {
      const v = lerCampos();
      if (!v.nome.trim()) { if (typeof toast === "function") toast("Dê um nome ao laudo (cliente / talhão).", true); $("nome").focus(); return; }
      const a = getSaved();
      a.unshift({ nome: v.nome.trim(), metodo, v, data: new Date().toLocaleDateString("pt-BR") });
      putSaved(a.slice(0, 100)); renderSaved();
      if (typeof toast === "function") toast("Laudo salvo.");
    };
    $("saveJson").onclick = () => {
      try {
        const o = JSON.parse($("json").value);
        if (!o.nome || o.V2 == null) throw new Error("faltam nome ou V2");
        cfg.DEF[metodo].crops[$("cult").value] = o; salvarCfg();
        $("jsonMsg").textContent = "Tabela salva."; if (ultimo) calc(false);
      } catch (e) { $("jsonMsg").textContent = "Não salvei: o texto não é um JSON válido (" + e.message + ")."; }
    };
    $("resetCfg").onclick = () => {
      const k = $("cult").value;
      cfg.DEF[metodo].crops[k] = clone(window.SoloTabelas.DEF[metodo].crops[k]); salvarCfg(); onCrop();
      $("jsonMsg").textContent = "Valores originais restaurados."; if (ultimo) calc(false);
    };
    // guarda o que foi digitado para não perder ao trocar de página no Gestor
    document.getElementById("solo").addEventListener("input", () => (rascunho = { metodo, v: lerCampos() }));
    document.getElementById("solo").addEventListener("change", () => (rascunho = { metodo, v: lerCampos() }));

    if (rascunho) { aplicarCampos(rascunho.metodo, rascunho.v); if (ultimo) calc(false); }
    else setMetodo(metodo);
    renderSaved();
  };
})();
