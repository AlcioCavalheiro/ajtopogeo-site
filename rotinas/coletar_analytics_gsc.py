#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coleta dados da semana no Google Analytics (GA4) e no Search Console, compara
com a semana anterior e faz uma checagem técnica do site (sitemap, status HTTP,
canonical). Grava tudo num JSON (o "dossiê") que alimenta a análise e o PDF.

Uso:
    py rotinas/coletar_analytics_gsc.py <saida.json>

Credenciais: lê de C:\\Users\\ALCIO\\.ajtopogeo\\google_analytics.env
(formato CHAVE=VALOR, uma por linha):

    GOOGLE_APPLICATION_CREDENTIALS=C:\\Users\\ALCIO\\.ajtopogeo\\credentials\\google-analytics-sa.json
    GA4_PROPERTY_ID=123456789
    GSC_SITE_URL=https://ajtopogeo.com.br/

Não decide nada sozinho — só levanta os números. A leitura e a decisão
(o que virou alteração no site) ficam para quem chama este script.
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import re
import defusedxml.ElementTree as ET

ENV_PATH = Path.home() / ".ajtopogeo" / "google_analytics.env"
SITE_ROOT = "https://ajtopogeo.com.br"


def carregar_env(caminho):
    if not caminho.exists():
        sys.exit(
            f"Não achei {caminho}. Crie o arquivo com GOOGLE_APPLICATION_CREDENTIALS, "
            "GA4_PROPERTY_ID e GSC_SITE_URL (veja o cabeçalho deste script)."
        )
    cfg = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        cfg[chave.strip()] = valor.strip()
    faltando = [k for k in ("GOOGLE_APPLICATION_CREDENTIALS", "GA4_PROPERTY_ID", "GSC_SITE_URL") if k not in cfg]
    if faltando:
        sys.exit(f"Faltando no {caminho}: {', '.join(faltando)}")
    if not Path(cfg["GOOGLE_APPLICATION_CREDENTIALS"]).exists():
        sys.exit(f"Chave da service account não encontrada: {cfg['GOOGLE_APPLICATION_CREDENTIALS']}")
    return cfg


def periodos():
    """Semana fechada (segunda a domingo) mais recente, e a anterior a ela."""
    hoje = date.today()
    # último domingo (se hoje é domingo, é ele mesmo só se já virou o dia todo;
    # como a rotina roda 1x/semana, tratamos hoje como fora do período fechado)
    dias_desde_domingo = (hoje.weekday() - 6) % 7
    if dias_desde_domingo == 0:
        dias_desde_domingo = 7
    fim_atual = hoje - timedelta(days=dias_desde_domingo)
    inicio_atual = fim_atual - timedelta(days=6)
    fim_anterior = inicio_atual - timedelta(days=1)
    inicio_anterior = fim_anterior - timedelta(days=6)
    return {
        "atual": (inicio_atual, fim_atual),
        "anterior": (inicio_anterior, fim_anterior),
    }


def coletar_ga4(cfg, periodo_atual, periodo_anterior):
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest,
    )
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_file(
        cfg["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/analytics.readonly"],
    )
    client = BetaAnalyticsDataClient(credentials=creds)
    propriedade = f"properties/{cfg['GA4_PROPERTY_ID']}"

    dr_atual = DateRange(start_date=periodo_atual[0].isoformat(), end_date=periodo_atual[1].isoformat(), name="atual")
    dr_anterior = DateRange(start_date=periodo_anterior[0].isoformat(), end_date=periodo_anterior[1].isoformat(), name="anterior")

    def rodar(dimensoes, metricas, limite=None, order_metric=None):
        req = RunReportRequest(
            property=propriedade,
            date_ranges=[dr_atual, dr_anterior],
            dimensions=[Dimension(name=d) for d in dimensoes],
            metrics=[Metric(name=m) for m in metricas],
            limit=limite or 100000,
        )
        if order_metric:
            from google.analytics.data_v1beta.types import OrderBy
            req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order_metric), desc=True)]
        resp = client.run_report(req)
        linhas = []
        for row in resp.rows:
            dims = [dv.value for dv in row.dimension_values]
            mets = [float(mv.value) for mv in row.metric_values]
            linhas.append({"dims": dims, "mets": mets})
        return linhas

    def por_periodo(linhas, campos_dim, campos_met, chave_periodo_idx):
        """Separa linhas em dict atual/anterior, indexado pela 1a dimensão (ou 'total')."""
        out = {"atual": {}, "anterior": {}}
        for l in linhas:
            periodo = l["dims"][chave_periodo_idx]
            chave = "atual" if periodo == "atual" else "anterior"
            nome = l["dims"][0] if chave_periodo_idx > 0 else "total"
            registro = dict(zip(campos_met, l["mets"]))
            out[chave][nome] = registro
        return out

    # Totais gerais (sem dimensão extra, só o período)
    totais_raw = rodar([], ["sessions", "totalUsers", "newUsers", "engagedSessions", "averageSessionDuration"])
    totais = {"atual": {}, "anterior": {}}
    for l in totais_raw:
        periodo = l["dims"][0]
        chave = "atual" if periodo == "atual" else "anterior"
        totais[chave] = dict(zip(["sessions", "totalUsers", "newUsers", "engagedSessions", "averageSessionDuration"], l["mets"]))

    # Páginas mais vistas
    paginas_raw = rodar(["pagePath"], ["screenPageViews", "sessions"], limite=50, order_metric="screenPageViews")
    paginas = {"atual": {}, "anterior": {}}
    for l in paginas_raw:
        pagina, periodo = l["dims"]
        chave = "atual" if periodo == "atual" else "anterior"
        paginas[chave][pagina] = dict(zip(["screenPageViews", "sessions"], l["mets"]))

    # Canal de aquisição
    canal_raw = rodar(["sessionDefaultChannelGroup"], ["sessions"], limite=20)
    canais = {"atual": {}, "anterior": {}}
    for l in canal_raw:
        canal, periodo = l["dims"]
        chave = "atual" if periodo == "atual" else "anterior"
        canais[chave][canal] = l["mets"][0]

    # Eventos de conversão (cta_click_*, lead_formulario)
    eventos_raw = rodar(["eventName"], ["eventCount"], limite=50)
    eventos = {"atual": {}, "anterior": {}}
    for l in eventos_raw:
        nome, periodo = l["dims"]
        if not (nome.startswith("cta_click") or nome == "lead_formulario"):
            continue
        chave = "atual" if periodo == "atual" else "anterior"
        eventos[chave][nome] = l["mets"][0]

    return {
        "totais": totais,
        "paginas_mais_vistas": paginas,
        "canais_aquisicao": canais,
        "eventos_conversao": eventos,
    }


def coletar_gsc(cfg, periodo_atual, periodo_anterior):
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        cfg["GOOGLE_APPLICATION_CREDENTIALS"],
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
    )
    servico = build("searchconsole", "v1", credentials=creds)
    site_url = cfg["GSC_SITE_URL"]

    def consultar(inicio, fim, dimensoes, limite=25000):
        body = {
            "startDate": inicio.isoformat(),
            "endDate": fim.isoformat(),
            "dimensions": dimensoes,
            "rowLimit": limite,
        }
        resp = servico.searchanalytics().query(siteUrl=site_url, body=body).execute()
        return resp.get("rows", [])

    def totais(inicio, fim):
        linhas = consultar(inicio, fim, [])
        if not linhas:
            return {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}
        l = linhas[0]
        return {"clicks": l.get("clicks", 0), "impressions": l.get("impressions", 0),
                "ctr": l.get("ctr", 0), "position": l.get("position", 0)}

    def por_dimensao(inicio, fim, dimensao):
        linhas = consultar(inicio, fim, [dimensao])
        out = {}
        for l in linhas:
            chave = l["keys"][0]
            out[chave] = {"clicks": l.get("clicks", 0), "impressions": l.get("impressions", 0),
                          "ctr": l.get("ctr", 0), "position": l.get("position", 0)}
        return out

    return {
        "site_url": site_url,
        "totais": {
            "atual": totais(*periodo_atual),
            "anterior": totais(*periodo_anterior),
        },
        "consultas": {
            "atual": por_dimensao(*periodo_atual, "query"),
            "anterior": por_dimensao(*periodo_anterior, "query"),
        },
        "paginas": {
            "atual": por_dimensao(*periodo_atual, "page"),
            "anterior": por_dimensao(*periodo_anterior, "page"),
        },
    }


def checar_saude_site():
    """Baixa o sitemap.xml em produção e confere status HTTP + canonical de cada URL."""
    problemas = []
    total_urls = 0
    try:
        with urlopen(f"{SITE_ROOT}/sitemap.xml", timeout=15) as resp:
            xml_bytes = resp.read()
    except (HTTPError, URLError) as e:
        return {"erro": f"não consegui baixar o sitemap.xml: {e}", "total_urls": 0, "problemas": []}

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(xml_bytes)
    urls = [el.text.strip() for el in root.findall(".//sm:url/sm:loc", ns) if el.text]
    total_urls = len(urls)

    for url in urls:
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (AJTopoGeo-healthcheck)"})
            with urlopen(req, timeout=15) as resp:
                status = resp.status
                html = resp.read().decode("utf-8", errors="ignore")
        except HTTPError as e:
            problemas.append({"url": url, "tipo": "status_http", "detalhe": f"HTTP {e.code}"})
            continue
        except URLError as e:
            problemas.append({"url": url, "tipo": "erro_conexao", "detalhe": str(e.reason)})
            continue

        if status != 200:
            problemas.append({"url": url, "tipo": "status_http", "detalhe": f"HTTP {status}"})

        m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
        if not m:
            problemas.append({"url": url, "tipo": "canonical_ausente", "detalhe": "sem tag canonical"})
        else:
            canonical = m.group(1).rstrip("/")
            esperado = url.rstrip("/")
            if canonical != esperado:
                problemas.append({"url": url, "tipo": "canonical_divergente",
                                  "detalhe": f"canonical aponta para {canonical}"})

    return {"total_urls": total_urls, "problemas": problemas}


def main():
    if len(sys.argv) < 2:
        sys.exit("Uso: py rotinas/coletar_analytics_gsc.py <saida.json>")
    saida = Path(sys.argv[1])

    cfg = carregar_env(ENV_PATH)
    p = periodos()

    print(f"Período atual: {p['atual'][0]} a {p['atual'][1]}", file=sys.stderr)
    print(f"Período anterior: {p['anterior'][0]} a {p['anterior'][1]}", file=sys.stderr)

    print("Coletando GA4...", file=sys.stderr)
    ga4 = coletar_ga4(cfg, p["atual"], p["anterior"])

    print("Coletando Search Console...", file=sys.stderr)
    gsc = coletar_gsc(cfg, p["atual"], p["anterior"])

    print("Checando saúde do site (sitemap, status, canonical)...", file=sys.stderr)
    saude = checar_saude_site()

    dossie = {
        "gerado_em": date.today().isoformat(),
        "periodo_atual": [p["atual"][0].isoformat(), p["atual"][1].isoformat()],
        "periodo_anterior": [p["anterior"][0].isoformat(), p["anterior"][1].isoformat()],
        "ga4": ga4,
        "gsc": gsc,
        "saude_site": saude,
        "decisoes": [],
    }
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(dossie, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dossiê gravado: {saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
