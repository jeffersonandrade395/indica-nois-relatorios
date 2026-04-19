"""
Persistência de contextos de relatórios no Google Cloud Storage.

Cada contexto é salvo como JSON com nome {cnpj}_{YYYYMMDD}.json.
Ao buscar, retorna o mais recente por CNPJ (ordem lexicográfica decrescente).

Autenticação: mesma service account do BigQuery (st.secrets["gcp_service_account"]).
Bucket: indica-nois-contextos (criado no projeto meu-n8n-458300).
"""

import json
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

BUCKET_NAME = "indica-nois-contextos"


def _get_gcs_client():
    from google.cloud import storage
    from google.oauth2 import service_account

    try:
        import streamlit as st
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
            creds = service_account.Credentials.from_service_account_info(info)
            return storage.Client(credentials=creds, project=info.get("project_id"))
    except Exception as e:
        log.debug("st.secrets nao disponivel: %s", e)

    # Fallback: credenciais padrão do ambiente
    return storage.Client()


def save_report_context(cnpj: str, context: dict) -> str:
    """
    Salva contexto do relatório no GCS como {cnpj}_{YYYYMMDD}.json.

    Returns:
        Nome do blob criado.
    """
    client = _get_gcs_client()
    bucket = client.bucket(BUCKET_NAME)

    blob_name = f"{cnpj}_{datetime.now().strftime('%Y%m%d')}.json"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(context, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    log.info("Contexto salvo no GCS: %s", blob_name)
    return blob_name


def load_latest_report_context(cnpj: str) -> Optional[dict]:
    """
    Busca o contexto mais recente de um CNPJ no GCS.

    Returns:
        dict com o contexto, ou None se não existir.
    """
    client = _get_gcs_client()
    bucket = client.bucket(BUCKET_NAME)

    blobs = sorted(
        client.list_blobs(bucket, prefix=f"{cnpj}_"),
        key=lambda b: b.name,
        reverse=True,
    )

    if not blobs:
        log.info("Nenhum contexto encontrado no GCS para CNPJ=%s", cnpj)
        return None

    latest = blobs[0]
    log.info("Contexto encontrado: %s", latest.name)
    data = latest.download_as_text(encoding="utf-8")
    return json.loads(data)


def list_all_contexts_by_cnpj(cnpj: str) -> list:
    """
    Lista todos os contextos disponíveis para um CNPJ.

    Returns:
        list[str] com nomes dos blobs, do mais recente ao mais antigo.
    """
    client = _get_gcs_client()
    bucket = client.bucket(BUCKET_NAME)
    blobs = sorted(
        client.list_blobs(bucket, prefix=f"{cnpj}_"),
        key=lambda b: b.name,
        reverse=True,
    )
    return [b.name for b in blobs]


def is_drive_configured() -> bool:
    """Retorna True se a service account está disponível para acessar o GCS."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            return True
    except Exception:
        pass
    return False
