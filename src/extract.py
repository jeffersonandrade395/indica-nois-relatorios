import json
import logging
import re
from datetime import datetime, timedelta

import streamlit as st
from google.cloud import bigquery
from google.oauth2 import service_account

from . import config as cfg

log = logging.getLogger(__name__)

P = f"`{cfg.BQ_PROJECT}.{cfg.BQ_DATASET}`"

_client: bigquery.Client | None = None


class CNPJNotFoundError(Exception):
    pass


class BigQueryTimeoutError(Exception):
    pass


def _normalize_pem(pk: str) -> str:
    pk = str(pk).replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n").strip()
    return pk + "\n"


def _get_client() -> bigquery.Client:
    global _client
    if _client is not None:
        return _client
    try:
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            info["private_key"] = _normalize_pem(info["private_key"])
            creds = service_account.Credentials.from_service_account_info(info)
            _client = bigquery.Client(credentials=creds, project=cfg.BQ_PROJECT)
        else:
            _client = bigquery.Client.from_service_account_json(cfg.BQ_CREDS, project=cfg.BQ_PROJECT)
    except Exception as e:
        log.error("Falha ao criar cliente BigQuery: %s", e)
        raise
    return _client


def _cache_path(cnpj: str):
    return cfg.CACHE_DIR / f"{cnpj}.json"


def _cache_valid(path) -> bool:
    if not cfg.CACHE_ON or not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=cfg.CACHE_TTL)


def _run(sql: str, params: list) -> list[dict]:
    client = _get_client()
    job_config = bigquery.QueryJobConfig(query_parameters=params)
    try:
        job = client.query(sql, job_config=job_config)
        return [dict(row) for row in job.result(timeout=cfg.BQ_TIMEOUT)]
    except Exception as e:
        if "timeout" in str(e).lower():
            raise BigQueryTimeoutError(str(e))
        raise


def _serialize(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def extract_prospect_data(cnpj_basico: str) -> dict:
    cache_file = _cache_path(cnpj_basico)
    if _cache_valid(cache_file):
        log.info("Cache hit CNPJ=%s", cnpj_basico)
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    log.info("Iniciando extração CNPJ=%s", cnpj_basico)
    p = [bigquery.ScalarQueryParameter("cnpj_basico", "STRING", cnpj_basico)]

    # Query 1 — Identificação
    rows = _run(f"""
        SELECT cnpj_basico, cnpj_completo, razao_social, nome_fantasia,
               cnae_principal, cnae_descricao, cnae_prioridade,
               porte, capital_social, natureza_juridica_descricao,
               data_abertura, anos_atividade,
               uf, municipio_codigo AS municipio, telefone1, telefone2, email_cadastral,
               uf_prioritaria, tem_email, tem_telefone
        FROM {P}.receita_telecom
        WHERE cnpj_basico = @cnpj_basico LIMIT 1
    """, p)
    if not rows:
        raise CNPJNotFoundError(f"CNPJ {cnpj_basico} não encontrado na base Receita Federal.")
    identificacao = {k: _serialize(v) if hasattr(v, "isoformat") else v for k, v in rows[0].items()}

    # Query 2 — Sócios
    socios_raw = _run(f"""
        SELECT qualificacao_descricao, data_entrada, eh_pessoa_fisica, nome_socio
        FROM {P}.receita_socios
        WHERE cnpj_basico = @cnpj_basico ORDER BY data_entrada DESC
    """, p)
    socios = [{k: _serialize(v) if hasattr(v, "isoformat") else v for k, v in s.items()}
              for s in socios_raw]

    # Query 3 — Anatel agregado
    anatel_rows = _run(f"""
        SELECT acessos_total, qtd_ufs, ufs_atuacao, mes_referencia
        FROM {P}.anatel_acessos
        WHERE cnpj_basico = @cnpj_basico LIMIT 1
    """, p)
    anatel_agregado = anatel_rows[0] if anatel_rows else None

    # Query 4 — Competitivo municipal (top 5, último período)
    competitivo = _run(f"""
        SELECT municipio, uf, assinaturas, total_assinaturas_municipio,
               market_share_pct, ranking_local, total_operadoras_municipio
        FROM {P}.vw_competitivo_municipal
        WHERE cnpj_basico = @cnpj_basico
          AND periodo = (SELECT MAX(periodo) FROM {P}.vw_competitivo_municipal)
        ORDER BY assinaturas DESC LIMIT 5
    """, p)

    # Query 5 — Movimento de mercado (top 3 praças)
    movimento = _run(f"""
        SELECT municipio, uf, empresa, assinaturas, assinaturas_periodo_anterior,
               variacao_pct, entrou_no_periodo, saiu_no_periodo, grande_operadora
        FROM {P}.vw_movimento_mercado
        WHERE municipio IN (
            SELECT municipio FROM {P}.vw_competitivo_municipal
            WHERE cnpj_basico = @cnpj_basico
              AND periodo = (SELECT MAX(periodo) FROM {P}.vw_competitivo_municipal)
            ORDER BY assinaturas DESC LIMIT 3
        )
        AND periodo = (SELECT MAX(periodo) FROM {P}.vw_movimento_mercado)
        ORDER BY municipio, ABS(variacao_pct) DESC
    """, p)

    # Query 6 — Panorama Brasil
    nacional = _run(f"""
        SELECT COUNT(DISTINCT cnpj_basico) AS total_isps_brasil,
               ROUND(AVG(anos_atividade), 1) AS media_anos_atividade
        FROM {P}.receita_telecom
    """, [])
    top_ufs = _run(f"""
        SELECT uf, total_isps, porte_me, porte_epp, porte_demais
        FROM {P}.vw_resumo_por_uf
        ORDER BY total_isps DESC LIMIT 10
    """, [])
    panorama_brasil = {**(nacional[0] if nacional else {}), "top_ufs": top_ufs}

    result = {
        "identificacao":       identificacao,
        "socios":              socios,
        "anatel_agregado":     anatel_agregado,
        "competitivo_municipal": competitivo,
        "movimento_mercado":   movimento,
        "panorama_brasil":     panorama_brasil,
    }

    cfg.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, default=str, indent=2)

    log.info("Extração concluída CNPJ=%s", cnpj_basico)
    return result


# ─────────────────────────────────────────────────────────────
#  FUNÇÕES v2 — Relatório Setorial v2 (5 páginas)
#  Não alteram as funções v1 acima.
# ─────────────────────────────────────────────────────────────

def extract_identificacao_completa(cnpj_basico: str) -> dict:
    """
    Extrai dados completos de identificação do prospect para a capa (P1).
    Nome do município vem de anatel_acessos_raw (praça com mais assinantes).

    Returns:
        dict com razao_social, cnpj_completo, municipio_sede, uf_sede,
        porte, anos_atividade, data_abertura.
    """
    p = [bigquery.ScalarQueryParameter("cnpj_basico", "STRING", cnpj_basico)]
    rows = _run(f"""
        SELECT razao_social, cnpj_completo, uf, municipio_codigo,
               porte, anos_atividade, data_abertura
        FROM {P}.receita_telecom
        WHERE cnpj_basico = @cnpj_basico LIMIT 1
    """, p)
    if not rows:
        raise CNPJNotFoundError(f"CNPJ {cnpj_basico} não encontrado na base Receita Federal.")
    row = rows[0]

    return {
        "razao_social":   row["razao_social"],
        "cnpj_completo":  row["cnpj_completo"],
        "municipio_sede": row["municipio_codigo"],  # receita_telecom armazena nome aqui
        "uf_sede":        row["uf"],
        "porte":          row["porte"],
        "anos_atividade": int(row["anos_atividade"] or 0),
        "data_abertura":  _serialize(row["data_abertura"]),
    }


def extract_arena_competitiva(cnpj_basico: str) -> dict:
    """
    Extrai dados da arena competitiva (P2) via vw_arena_competitiva.

    Returns:
        dict com top_10_concorrentes, proprio_prospect, totais, prospect_no_top_10.
    """
    p = [bigquery.ScalarQueryParameter("cnpj_basico", "STRING", cnpj_basico)]

    # Todos os concorrentes ordenados por assinantes desc (exceto o próprio)
    concorrentes = _run(f"""
        SELECT cnpj_concorrente, razao_social_concorrente,
               eh_o_proprio_alvo, eh_operadora_grande,
               assinantes_na_arena_atual, assinantes_na_arena_anterior,
               variacao_absoluta_arena, variacao_percentual_arena,
               entrou_na_arena_periodo, saiu_da_arena_periodo,
               qtd_municipios_em_comum, lista_municipios_em_comum,
               mes_referencia_atual, mes_referencia_anterior
        FROM {P}.vw_arena_competitiva
        WHERE cnpj_alvo = @cnpj_basico
        ORDER BY assinantes_na_arena_atual DESC
    """, p)

    if not concorrentes:
        raise CNPJNotFoundError(
            f"CNPJ {cnpj_basico} não encontrado na arena competitiva (vw_arena_competitiva)."
        )

    proprio = next((r for r in concorrentes if r["eh_o_proprio_alvo"]), None)
    outros = [r for r in concorrentes if not r["eh_o_proprio_alvo"]]
    top_10 = outros[:10]

    prospect_no_top_10 = proprio is not None and any(
        r["cnpj_concorrente"] == cnpj_basico for r in top_10
    )
    # O prospect está no top 10 se seu rank entre TODOS (incluindo si mesmo) for <= 10
    rank_proprio = next(
        (i + 1 for i, r in enumerate(concorrentes) if r["eh_o_proprio_alvo"]), None
    )
    prospect_no_top_10 = rank_proprio is not None and rank_proprio <= 10

    # Totais: qtd_municipios_alvo via vw_competitivo_municipal
    mun_rows = _run(f"""
        SELECT COUNT(DISTINCT municipio) AS qtd_municipios
        FROM {P}.vw_competitivo_municipal
        WHERE cnpj_basico = @cnpj_basico
          AND periodo = (SELECT MAX(periodo) FROM {P}.vw_competitivo_municipal)
    """, p)
    qtd_municipios_alvo = int(mun_rows[0]["qtd_municipios"]) if mun_rows else 0

    total_assinantes_arena = sum(
        int(r["assinantes_na_arena_atual"] or 0) for r in concorrentes if not r["eh_o_proprio_alvo"]
    )
    if proprio:
        total_assinantes_arena += int(proprio["assinantes_na_arena_atual"] or 0)

    share_prospect = 0.0
    if total_assinantes_arena > 0 and proprio:
        share_prospect = round(
            int(proprio["assinantes_na_arena_atual"] or 0) * 100 / total_assinantes_arena, 1
        )

    return {
        "top_10_concorrentes": top_10,
        "proprio_prospect":    proprio,
        "totais": {
            "qtd_municipios_alvo":      qtd_municipios_alvo,
            "qtd_concorrentes_diretos": len(outros),
            "total_assinantes_arena":   total_assinantes_arena,
            "share_agregado_prospect":  share_prospect,
        },
        "prospect_no_top_10": prospect_no_top_10,
        "mes_referencia_atual": concorrentes[0]["mes_referencia_atual"] if concorrentes else None,
    }


def extract_evolucao_temporal(cnpj_basico: str) -> dict:
    """
    Extrai série temporal de share na arena dos últimos 14 períodos disponíveis (P3).

    Returns:
        dict com serie_prospect, serie_top_3_concorrentes, serie_demais_agregados,
        destaques (maior_crescimento, maior_queda, posicao_prospect), contadores.
    """
    p = [bigquery.ScalarQueryParameter("cnpj_basico", "STRING", cnpj_basico)]

    # Todos os municipios onde o prospect opera no periodo mais recente
    municipios_rows = _run(f"""
        SELECT DISTINCT municipio
        FROM {P}.anatel_acessos_raw
        WHERE cnpj_basico = @cnpj_basico
          AND periodo = (SELECT MAX(periodo) FROM {P}.anatel_acessos_raw)
    """, p)
    municipios = [r["municipio"] for r in municipios_rows]
    if not municipios:
        raise CNPJNotFoundError(f"CNPJ {cnpj_basico} sem dados Anatel recentes.")

    mun_params = [
        bigquery.ScalarQueryParameter(f"m{i}", "STRING", m)
        for i, m in enumerate(municipios)
    ]
    mun_list = ", ".join(f"@m{i}" for i in range(len(municipios)))

    # Série temporal: assinaturas por cnpj × periodo nos municipios do prospect
    serie_raw = _run(f"""
        SELECT cnpj_basico, SUBSTR(periodo, 1, 7) AS mes, SUM(assinaturas) AS assinaturas
        FROM {P}.anatel_acessos_raw
        WHERE municipio IN ({mun_list})
          AND periodo IN (
              SELECT DISTINCT periodo FROM {P}.anatel_acessos_raw
              ORDER BY periodo DESC LIMIT 14
          )
        GROUP BY cnpj_basico, mes
        ORDER BY mes
    """, p + mun_params)

    # Organiza por periodo → total arena e por cnpj
    from collections import defaultdict
    por_periodo: dict[str, dict[str, int]] = defaultdict(dict)
    for r in serie_raw:
        por_periodo[r["mes"]][r["cnpj_basico"]] = int(r["assinaturas"])

    periodos_sorted = sorted(por_periodo.keys())

    # Série do prospect
    serie_prospect_vals = [por_periodo[m].get(cnpj_basico, 0) for m in periodos_sorted]
    totais_por_periodo  = [sum(por_periodo[m].values()) for m in periodos_sorted]

    def share_serie(vals):
        return [
            round(v * 100 / t, 2) if t > 0 else 0.0
            for v, t in zip(vals, totais_por_periodo)
        ]

    serie_prospect = [
        {"mes": _fmt_mes_label(m), "share_pct": s}
        for m, s in zip(periodos_sorted, share_serie(serie_prospect_vals))
    ]

    # Identifica todos os cnpjs presentes (exceto o próprio)
    todos_cnpjs = {cnpj for vals in por_periodo.values() for cnpj in vals} - {cnpj_basico}

    # Variação de share para selecionar top 3 concorrentes
    def variacao_share(cnpj):
        vals = [por_periodo[m].get(cnpj, 0) for m in periodos_sorted]
        shares = share_serie(vals)
        if len(shares) < 2:
            return 0.0, 0, shares
        return abs(shares[-1] - shares[0]), int(por_periodo[periodos_sorted[-1]].get(cnpj, 0)), shares

    candidatos = [
        (cnpj, *variacao_share(cnpj))
        for cnpj in todos_cnpjs
        if int(por_periodo[periodos_sorted[-1]].get(cnpj, 0)) >= 500
    ]
    candidatos.sort(key=lambda x: x[1], reverse=True)
    top3_cnpjs = [c[0] for c in candidatos[:3]]

    # Busca razao social dos top 3
    rs_map: dict[str, str] = {}
    if top3_cnpjs:
        rs_params = [bigquery.ScalarQueryParameter(f"c{i}", "STRING", c) for i, c in enumerate(top3_cnpjs)]
        rs_list = ", ".join(f"@c{i}" for i in range(len(top3_cnpjs)))
        rs_rows = _run(f"""
            SELECT cnpj_basico, razao_social FROM {P}.receita_telecom
            WHERE cnpj_basico IN ({rs_list})
        """, rs_params)
        rs_map = {r["cnpj_basico"]: r["razao_social"] for r in rs_rows}

    serie_top3 = []
    for cnpj in top3_cnpjs:
        _, _, _, shares = next(c for c in [(*c[:3], c[3]) for c in candidatos] if c[0] == cnpj)
        serie_top3.append({
            "cnpj":   cnpj,
            "nome":   rs_map.get(cnpj, cnpj),
            "valores": [
                {"mes": _fmt_mes_label(m), "share_pct": s}
                for m, s in zip(periodos_sorted, shares)
            ],
        })

    # Série demais agregados (tudo que não é prospect nem top3)
    top3_set = set(top3_cnpjs) | {cnpj_basico}
    serie_demais = []
    for m in periodos_sorted:
        soma_demais = sum(
            v for c, v in por_periodo[m].items() if c not in top3_set
        )
        t = totais_por_periodo[periodos_sorted.index(m)]
        serie_demais.append({
            "mes": _fmt_mes_label(m),
            "share_pct": round(soma_demais * 100 / t, 2) if t > 0 else 0.0,
        })

    # Destaques: maior crescimento e queda entre todos os cnpjs (min 500 assinantes atuais)
    def _delta_share(cnpj):
        vals = [por_periodo[m].get(cnpj, 0) for m in periodos_sorted]
        shares = share_serie(vals)
        if len(shares) < 2:
            return 0.0
        return round(shares[-1] - shares[0], 2)

    # cnpjs com >= 500 assinantes no período mais recente
    cnpjs_relevantes = [
        c for c in todos_cnpjs
        if int(por_periodo[periodos_sorted[-1]].get(c, 0)) >= 500
    ]

    if cnpjs_relevantes:
        deltas = {c: _delta_share(c) for c in cnpjs_relevantes}
        maior_cresc_cnpj = max(deltas, key=lambda c: deltas[c])
        maior_queda_cnpj = min(deltas, key=lambda c: deltas[c])
    else:
        maior_cresc_cnpj = maior_queda_cnpj = None

    # Busca razão social dos destaques (se não estiverem já no rs_map)
    destaques_cnpjs = [c for c in [maior_cresc_cnpj, maior_queda_cnpj] if c and c not in rs_map]
    if destaques_cnpjs:
        d_params = [bigquery.ScalarQueryParameter(f"d{i}", "STRING", c) for i, c in enumerate(destaques_cnpjs)]
        d_list = ", ".join(f"@d{i}" for i in range(len(destaques_cnpjs)))
        d_rows = _run(f"""
            SELECT cnpj_basico, razao_social FROM {P}.receita_telecom
            WHERE cnpj_basico IN ({d_list})
        """, d_params)
        rs_map.update({r["cnpj_basico"]: r["razao_social"] for r in d_rows})

    # Prospect: razão social
    rs_prospect_rows = _run(f"""
        SELECT razao_social FROM {P}.receita_telecom WHERE cnpj_basico = @cnpj_basico LIMIT 1
    """, p)
    rs_prospect = rs_prospect_rows[0]["razao_social"] if rs_prospect_rows else cnpj_basico

    delta_prospect = _delta_share(cnpj_basico)
    shares_prospect = share_serie(serie_prospect_vals)
    cresc_arena_pct  = round(totais_por_periodo[-1] * 100 / totais_por_periodo[0] - 100, 1) if totais_por_periodo[0] > 0 else 0.0
    cresc_proprio_pct = round(serie_prospect_vals[-1] * 100 / serie_prospect_vals[0] - 100, 1) if serie_prospect_vals[0] > 0 else 0.0

    # Novos entrantes (0 no primeiro periodo, > 0 no último)
    novos_entrantes = sum(
        1 for c in todos_cnpjs
        if por_periodo[periodos_sorted[0]].get(c, 0) == 0
        and por_periodo[periodos_sorted[-1]].get(c, 0) > 0
    )
    perderam_mais_10pct = sum(
        1 for c in cnpjs_relevantes
        if _delta_share(c) < -1.0  # queda > 1 ponto percentual de share
    ) if cnpjs_relevantes else 0

    return {
        "serie_prospect": serie_prospect,
        "serie_top_3_concorrentes": serie_top3,
        "serie_demais_agregados": serie_demais,
        "destaques": {
            "maior_crescimento": {
                "cnpj":             maior_cresc_cnpj,
                "empresa":          rs_map.get(maior_cresc_cnpj, "") if maior_cresc_cnpj else "",
                "variacao_pp":      deltas.get(maior_cresc_cnpj, 0.0) if maior_cresc_cnpj and 'deltas' in dir() else 0.0,
                "entrou_no_periodo": (maior_cresc_cnpj is not None and
                    por_periodo[periodos_sorted[0]].get(maior_cresc_cnpj, 0) == 0),
            },
            "maior_queda": {
                "cnpj":    maior_queda_cnpj,
                "empresa": rs_map.get(maior_queda_cnpj, "") if maior_queda_cnpj else "",
                "variacao_pp": deltas.get(maior_queda_cnpj, 0.0) if maior_queda_cnpj and 'deltas' in dir() else 0.0,
            },
            "posicao_prospect": {
                "empresa":                  rs_prospect,
                "variacao_pp":              delta_prospect,
                "cresceu_mais_que_arena":   cresc_proprio_pct > cresc_arena_pct,
                "cresc_arena_pct":          cresc_arena_pct,
                "cresc_proprio_pct":        cresc_proprio_pct,
            },
        },
        "contadores": {
            "novos_entrantes":       novos_entrantes,
            "perderam_mais_de_10pct": perderam_mais_10pct,
        },
        "periodos_disponiveis": len(periodos_sorted),
    }


def extract_potencial(cnpj_basico: str, ticket_medio_brl: float, janela_meses: int) -> dict:
    """
    Calcula potencial de crescimento via indicação em 3 cenários (P4).
    Cálculo feito em Python puro — não usa vw_potencial_indicacao.

    Returns:
        dict com base_anatel, ticket_medio_brl, janela_meses, cenarios.
    """
    p = [bigquery.ScalarQueryParameter("cnpj_basico", "STRING", cnpj_basico)]
    rows = _run(f"""
        SELECT SUM(assinaturas) AS total
        FROM {P}.anatel_acessos_raw
        WHERE cnpj_basico = @cnpj_basico
          AND periodo = (SELECT MAX(periodo) FROM {P}.anatel_acessos_raw)
    """, p)
    base_anatel = int(rows[0]["total"] or 0) if rows else 0

    cenarios = []
    for taxa, label in [(0.03, "Conservador"), (0.05, "Realista"), (0.10, "Otimista")]:
        novos = round(base_anatel * taxa)
        receita = novos * ticket_medio_brl * janela_meses
        cenarios.append({
            "label":         label,
            "taxa":          taxa,
            "novos_clientes": novos,
            "receita_total":  receita,
        })

    return {
        "base_anatel":      base_anatel,
        "ticket_medio_brl": ticket_medio_brl,
        "janela_meses":     janela_meses,
        "cenarios":         cenarios,
    }


def extract_full_report_data(
    cnpj_basico: str,
    ticket_medio_brl: float = 111.0,
    janela_meses: int = 24,
) -> dict:
    """
    Orquestra todas as extrações v2 e retorna dict estruturado para as 5 páginas.

    Returns:
        dict com identificacao, arena, evolucao, potencial, metadados.
    """
    from datetime import date as _date

    identificacao = extract_identificacao_completa(cnpj_basico)
    arena         = extract_arena_competitiva(cnpj_basico)
    evolucao      = extract_evolucao_temporal(cnpj_basico)
    potencial     = extract_potencial(cnpj_basico, ticket_medio_brl, janela_meses)

    mes_anatel = arena.get("mes_referencia_atual") or ""

    return {
        "identificacao": identificacao,
        "arena":         arena,
        "evolucao":      evolucao,
        "potencial":     potencial,
        "metadados": {
            "data_geracao":  _date.today().isoformat(),
            "fonte_anatel":  mes_anatel,
            "versao_spec":   "v2",
        },
    }


def _fmt_mes_label(mes_yyyymm: str) -> str:
    """'2025-02' → 'fev/25'"""
    _ABREV = {
        "01": "jan", "02": "fev", "03": "mar", "04": "abr",
        "05": "mai", "06": "jun", "07": "jul", "08": "ago",
        "09": "set", "10": "out", "11": "nov", "12": "dez",
    }
    try:
        ano, mes = mes_yyyymm.split("-")
        return f"{_ABREV.get(mes, mes)}/{ano[2:]}"
    except Exception:
        return mes_yyyymm
