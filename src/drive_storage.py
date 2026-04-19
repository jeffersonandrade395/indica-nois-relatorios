"""
Persistência de contextos de relatórios no Google Drive.

Cada contexto é salvo como JSON com nome {cnpj}_{YYYYMMDD}.json.
Ao buscar, retorna o mais recente por CNPJ (ordem alfabética decrescente).

Autenticação (mesma lógica do BigQuery em extract.py):
  1. Streamlit Cloud / local com secrets.toml → st.secrets["gcp_service_account"]
  2. Fallback: GOOGLE_DRIVE_CREDENTIALS_PATH (JSON file)

Setup da pasta Drive:
  1. Habilitar Drive API na service account existente (Google Cloud Console)
  2. Criar pasta "IndicaNois_Contextos" no Drive
  3. Compartilhar com servi-o-radarlink@meu-n8n-458300.iam.gserviceaccount.com
  4. Definir GOOGLE_DRIVE_FOLDER_ID no .env ou st.secrets
"""

import json
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Optional

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_folder_id() -> Optional[str]:
    """Retorna o ID da pasta Drive, de st.secrets ou env."""
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "GOOGLE_DRIVE_FOLDER_ID" in st.secrets:
            return st.secrets["GOOGLE_DRIVE_FOLDER_ID"]
    except Exception:
        pass
    return os.getenv("GOOGLE_DRIVE_FOLDER_ID")


def _get_drive_service():
    """Retorna serviço Drive autenticado via st.secrets ou JSON file."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = None

    # Tenta st.secrets["gcp_service_account"] (mesmo padrão do BigQuery)
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            info = dict(st.secrets["gcp_service_account"])
            if "private_key" in info:
                info["private_key"] = str(info["private_key"]).replace("\\n", "\n")
            credentials = service_account.Credentials.from_service_account_info(
                info, scopes=SCOPES
            )
            log.info("Drive: credenciais carregadas de st.secrets")
    except Exception as e:
        log.debug("st.secrets não disponível: %s", e)

    # Fallback: JSON file
    if credentials is None:
        creds_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")
        if creds_path and os.path.exists(creds_path):
            credentials = service_account.Credentials.from_service_account_file(
                creds_path, scopes=SCOPES
            )
            log.info("Drive: credenciais carregadas de %s", creds_path)

    if credentials is None:
        raise RuntimeError(
            "Credenciais Drive não encontradas. Configure gcp_service_account em "
            "st.secrets ou GOOGLE_DRIVE_CREDENTIALS_PATH no .env."
        )

    return build("drive", "v3", credentials=credentials)


def save_report_context(cnpj: str, context: dict) -> str:
    """
    Salva contexto do relatório no Drive como {cnpj}_{YYYYMMDD}.json.

    Returns:
        ID do arquivo criado no Drive.
    """
    from googleapiclient.http import MediaIoBaseUpload

    folder_id = _get_folder_id()
    service = _get_drive_service()
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"{cnpj}_{date_str}.json"

    json_bytes = json.dumps(context, ensure_ascii=False, indent=2).encode("utf-8")
    file_metadata = {
        "name": filename,
        "parents": [folder_id],
        "mimeType": "application/json",
    }
    media = MediaIoBaseUpload(BytesIO(json_bytes), mimetype="application/json", resumable=False)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file.get("id")
    log.info("Contexto salvo no Drive: %s → %s", filename, file_id)
    return file_id


def load_latest_report_context(cnpj: str) -> Optional[dict]:
    """
    Busca contexto mais recente de um CNPJ no Drive.

    Returns:
        dict com o contexto, ou None se não existir.
    """
    from googleapiclient.http import MediaIoBaseDownload

    folder_id = _get_folder_id()
    service = _get_drive_service()
    query = f"'{folder_id}' in parents and name contains '{cnpj}_' and trashed = false"
    results = service.files().list(
        q=query,
        orderBy="name desc",
        pageSize=1,
        fields="files(id, name)",
    ).execute()

    files = results.get("files", [])
    if not files:
        log.info("Nenhum contexto encontrado no Drive para CNPJ=%s", cnpj)
        return None

    file_id = files[0]["id"]
    log.info("Contexto encontrado: %s (id=%s)", files[0]["name"], file_id)

    request = service.files().get_media(fileId=file_id)
    buffer = BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    buffer.seek(0)
    return json.loads(buffer.read().decode("utf-8"))


def list_all_contexts_by_cnpj(cnpj: str) -> list:
    """
    Lista todos os contextos disponíveis para um CNPJ (histórico).

    Returns:
        list[dict] com {id, name, createdTime} do mais recente ao mais antigo.
    """
    folder_id = _get_folder_id()
    service = _get_drive_service()
    query = f"'{folder_id}' in parents and name contains '{cnpj}_' and trashed = false"
    results = service.files().list(
        q=query,
        orderBy="name desc",
        fields="files(id, name, createdTime)",
    ).execute()
    return results.get("files", [])


def is_drive_configured() -> bool:
    """Retorna True se credenciais e folder ID estão disponíveis."""
    folder_id = _get_folder_id()
    if not folder_id:
        return False

    # Verifica se tem credenciais via st.secrets ou JSON file
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            return True
    except Exception:
        pass

    creds_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")
    return bool(creds_path and os.path.exists(creds_path))
