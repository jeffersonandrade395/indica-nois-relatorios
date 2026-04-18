import json
import logging
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


def _get_client() -> bigquery.Client:
    global _client
    if _client is not None:
        return _client
    try:
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            creds = service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"])
            )
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
               uf, municipio, telefone1, telefone2, email_cadastral,
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
