"""Testes de integração — pipeline render v2 (sem WeasyPrint)."""

import json
import sys
import unittest.mock as mock
from pathlib import Path

sys.modules.setdefault("streamlit", mock.MagicMock())

import pytest

from src.transform import prepare_report_context_v2
from src.render import render_report_html_v2
from src.charts import generate_evolucao_temporal_chart

FIXTURES = Path(__file__).parent / "fixtures" / "estrelas_mock.json"


@pytest.fixture
def raw_data():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def ctx(raw_data):
    return prepare_report_context_v2(raw_data)


# ── charts.py ───────────────────────────────────────────────────

class TestCharts:
    def test_returns_nonempty_base64(self, ctx):
        b64 = generate_evolucao_temporal_chart(ctx["evolucao"]["grafico_dados"])
        assert isinstance(b64, str)
        assert len(b64) > 1000

    def test_no_crash_empty_concorrentes(self, ctx):
        dados = dict(ctx["evolucao"]["grafico_dados"])
        dados["serie_concorrentes"] = []
        b64 = generate_evolucao_temporal_chart(dados)
        assert len(b64) > 100

    def test_no_crash_no_agregado(self, ctx):
        dados = dict(ctx["evolucao"]["grafico_dados"])
        dados["serie_agregado"] = None
        b64 = generate_evolucao_temporal_chart(dados)
        assert len(b64) > 100


# ── render_report_html_v2 ────────────────────────────────────────

class TestRenderV2:
    def test_renders_html(self, ctx):
        html = render_report_html_v2(ctx)
        assert "<!DOCTYPE html>" in html
        assert "Estrelas" in html

    def test_meta_in_html(self, ctx):
        html = render_report_html_v2(ctx)
        assert "12.130.171/0001-14" in html
        assert "Paço do Lumiar" in html
        assert "fev/2026" in html

    def test_arena_table_rendered(self, ctx):
        html = render_report_html_v2(ctx)
        assert "arena-table" in html
        assert "badge-prospect" in html

    def test_chart_img_embedded(self, ctx):
        html = render_report_html_v2(ctx)
        assert "data:image/png;base64," in html

    def test_cenario_realista_in_html(self, ctx):
        html = render_report_html_v2(ctx)
        assert "realista" in html.lower()
        assert "R$" in html

    def test_placeholder_when_analise_none(self, ctx):
        html = render_report_html_v2(ctx)
        assert "Preencher antes de exportar" in html

    def test_analise_leitura_rendered(self, ctx):
        ctx["analise"]["leitura_1"] = "Estrelas lidera em duas praças mas cresce abaixo da arena."
        ctx["analise"]["leitura_2"] = "W J dos Santos perdeu share — janela de oportunidade."
        ctx["analise"]["leitura_3"] = "Programa de indicação pode gerar R$ 3 mi em 24 meses."
        html = render_report_html_v2(ctx)
        assert "lidera em duas praças" in html
        assert "janela de oportunidade" in html
        assert "R$ 3 mi" in html

    def test_pontos_de_atencao_rendered(self, ctx):
        ctx["analise"]["pontos_de_atencao"] = "• Liderança em 2 praças\n• Novo entrante com 1.871 assinantes"
        html = render_report_html_v2(ctx)
        assert "pontos-atencao" in html
        assert "Liderança em 2 praças" in html

    def test_no_v1_variable_leak(self, ctx):
        html = render_report_html_v2(ctx)
        assert "identificacao.razao_social_fmt" not in html
        assert "{{ " not in html
