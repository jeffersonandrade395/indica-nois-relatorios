"""Testes unitários — extract v2 com mocks de BigQuery."""

import sys
import unittest.mock as mock
from unittest.mock import MagicMock, patch

sys.modules.setdefault("streamlit", MagicMock())

import pytest


def _make_row(**kwargs):
    """Cria um objeto que simula uma linha de resultado do BigQuery."""
    row = MagicMock()
    row.items.return_value = kwargs.items()
    row.__iter__ = lambda self: iter(kwargs.items())
    row.__getitem__ = lambda self, k: kwargs[k]
    row.get = lambda self, k, d=None: kwargs.get(k, d)
    # simula dict(row) via items()
    row._data = kwargs
    return row


def _rows(*dicts):
    """Retorna lista de dicts simples (extract usa dict(row) internamente via _run)."""
    return list(dicts)


# ── _fmt_mes_label ───────────────────────────────────────────

class TestFmtMesLabel:
    def test_fevereiro(self):
        from src.extract import _fmt_mes_label
        assert _fmt_mes_label("2025-02") == "fev/25"

    def test_dezembro(self):
        from src.extract import _fmt_mes_label
        assert _fmt_mes_label("2025-12") == "dez/25"

    def test_abril(self):
        from src.extract import _fmt_mes_label
        assert _fmt_mes_label("2026-04") == "abr/26"


# ── extract_potencial (sem BigQuery, cálculo puro) ──────────

class TestExtractPotencial:
    def test_calculo_cenarios(self):
        with patch("src.extract._run") as mock_run:
            mock_run.return_value = [{"total": 25144}]
            from src.extract import extract_potencial

            result = extract_potencial("12130171", 111.0, 24)

        assert result["base_anatel"] == 25144
        assert result["ticket_medio_brl"] == 111.0
        assert result["janela_meses"] == 24
        assert len(result["cenarios"]) == 3

        cons = result["cenarios"][0]
        assert cons["label"] == "Conservador"
        assert cons["taxa"] == 0.03
        assert cons["novos_clientes"] == 754

        real = result["cenarios"][1]
        assert real["label"] == "Realista"
        assert real["taxa"] == 0.05
        assert real["novos_clientes"] == 1257
        # receita realista ~3.34M
        assert 3_300_000 <= real["receita_total"] <= 3_400_000

        otim = result["cenarios"][2]
        assert otim["label"] == "Otimista"
        assert otim["taxa"] == 0.10
        assert otim["novos_clientes"] == 2514

    def test_cenario_receita_formula(self):
        with patch("src.extract._run") as mock_run:
            mock_run.return_value = [{"total": 1000}]
            from src.extract import extract_potencial

            result = extract_potencial("00000001", 100.0, 12)

        # 1000 * 0.05 * 100 * 12 = 60_000
        real = result["cenarios"][1]
        assert real["receita_total"] == 60_000.0


# ── extract_identificacao_completa ───────────────────────────

class TestExtractIdentificacaoCompleta:
    def test_campos_retornados(self):
        mock_row = {
            "razao_social": "Estrelas Tecnologia Da Informacao Ltda",
            "cnpj_completo": "12.130.171/0001-14",
            "uf": "MA",
            "municipio_codigo": "PACO DO LUMIAR",
            "porte": "Demais",
            "anos_atividade": 15,
            "data_abertura": "2011-03-01",
        }
        with patch("src.extract._run") as mock_run:
            mock_run.return_value = [mock_row]
            from src.extract import extract_identificacao_completa

            result = extract_identificacao_completa("12130171")

        assert result["razao_social"].startswith("Estrelas")
        assert result["cnpj_completo"] == "12.130.171/0001-14"
        assert result["municipio_sede"] == "PACO DO LUMIAR"
        assert result["uf_sede"] == "MA"
        assert result["anos_atividade"] == 15

    def test_cnpj_nao_encontrado(self):
        with patch("src.extract._run") as mock_run:
            mock_run.return_value = []
            from src.extract import extract_identificacao_completa, CNPJNotFoundError

            with pytest.raises(CNPJNotFoundError):
                extract_identificacao_completa("99999999")


# ── extract_full_report_data (integração mocked) ─────────────

class TestExtractFullReportData:
    def test_chaves_retornadas(self):
        with patch("src.extract.extract_identificacao_completa") as m_ident, \
             patch("src.extract.extract_arena_competitiva") as m_arena, \
             patch("src.extract.extract_evolucao_temporal") as m_ev, \
             patch("src.extract.extract_potencial") as m_pot:

            m_ident.return_value = {"razao_social": "Teste"}
            m_arena.return_value = {"totais": {}}
            m_ev.return_value = {"serie_prospect": []}
            m_pot.return_value = {"cenarios": []}

            from src.extract import extract_full_report_data
            result = extract_full_report_data("12130171")

        assert "identificacao" in result
        assert "arena" in result
        assert "evolucao" in result
        assert "potencial" in result
        assert "metadados" in result
        assert result["metadados"]["versao_spec"] == "v2"
