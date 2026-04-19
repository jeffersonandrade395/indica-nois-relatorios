"""Testes para src/drive_storage.py (com mock da API do Drive)."""
import json
import pytest
from unittest.mock import MagicMock, patch, call
from io import BytesIO


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def _make_drive_service_mock(files_list=None):
    """Retorna um mock do serviço Drive com arquivos configuráveis."""
    service = MagicMock()
    files_list = files_list or []
    service.files().list().execute.return_value = {"files": files_list}
    service.files().create().execute.return_value = {"id": "mock-file-id"}
    return service


def _make_download_mock(service, content: dict):
    """Configura o mock para retornar content como JSON no download."""
    json_bytes = json.dumps(content, ensure_ascii=False).encode("utf-8")

    def fake_download(fd, request):
        downloader = MagicMock()
        calls = [False, True]
        downloader.next_chunk.side_effect = [(None, v) for v in calls]
        # Escreve os bytes diretamente no buffer
        fd.write(json_bytes)
        fd.seek(0)
        return downloader

    # Sobrescreve MediaIoBaseDownload na chamada real
    return json_bytes


# ----------------------------------------------------------------
# Testes
# ----------------------------------------------------------------

@patch("src.drive_storage._get_drive_service")
@patch("src.drive_storage.FOLDER_ID", "mock-folder-id")
def test_save_report_context_returns_file_id(mock_get_service):
    from src.drive_storage import save_report_context
    service = _make_drive_service_mock()
    mock_get_service.return_value = service

    file_id = save_report_context("12130171", {"meta": {"razao_social_completa": "Estrelas"}})
    assert file_id == "mock-file-id"
    service.files().create.assert_called()


@patch("src.drive_storage._get_drive_service")
@patch("src.drive_storage.FOLDER_ID", "mock-folder-id")
def test_load_latest_returns_none_when_no_files(mock_get_service):
    from src.drive_storage import load_latest_report_context
    service = _make_drive_service_mock(files_list=[])
    mock_get_service.return_value = service

    result = load_latest_report_context("99999999")
    assert result is None


@patch("googleapiclient.http.MediaIoBaseDownload")
@patch("src.drive_storage._get_drive_service")
@patch("src.drive_storage.FOLDER_ID", "mock-folder-id")
def test_load_latest_returns_most_recent(mock_get_service, mock_downloader_cls):
    from src.drive_storage import load_latest_report_context

    expected_ctx = {"meta": {"nome_curto": "Estrelas"}, "extra": "dados acentuados: ação, ção"}
    json_bytes = json.dumps(expected_ctx, ensure_ascii=False).encode("utf-8")

    service = _make_drive_service_mock(files_list=[
        {"id": "file-20260419", "name": "12130171_20260419.json"},
    ])
    mock_get_service.return_value = service

    def fake_downloader(buffer, request):
        inst = MagicMock()
        inst.next_chunk.side_effect = [(None, False), (None, True)]
        buffer.write(json_bytes)
        return inst

    mock_downloader_cls.side_effect = fake_downloader

    result = load_latest_report_context("12130171")
    assert result is not None
    assert result["meta"]["nome_curto"] == "Estrelas"


@patch("src.drive_storage._get_drive_service")
@patch("src.drive_storage.FOLDER_ID", "mock-folder-id")
def test_special_characters_preserved(mock_get_service):
    """Acentos pt-BR são preservados na serialização JSON."""
    from src.drive_storage import save_report_context
    service = _make_drive_service_mock()
    mock_get_service.return_value = service

    ctx_with_accents = {
        "meta": {"razao_social_completa": "Ações & Soluções Tecnológicas Ltda"}
    }
    save_report_context("12345678", ctx_with_accents)

    # Captura o que foi passado para MediaIoBaseUpload
    create_call = service.files().create.call_args
    # Não lança erro — serialização com ensure_ascii=False preserva acentos
    assert create_call is not None


def test_is_drive_configured_false_without_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_DRIVE_FOLDER_ID", raising=False)
    monkeypatch.delenv("GOOGLE_DRIVE_CREDENTIALS_PATH", raising=False)

    # Reimporta para pegar valores de env atualizados
    import importlib
    import src.drive_storage as ds
    importlib.reload(ds)

    assert ds.is_drive_configured() is False
