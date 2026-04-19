"""Testes unitários — formatadores e prepare_report_context_v2."""

import json
import sys
import unittest.mock as mock
from pathlib import Path

# Stub streamlit antes de importar módulos que o usam
sys.modules.setdefault("streamlit", mock.MagicMock())

import pytest

from src.transform import (
    derive_short_name,
    format_currency_brl,
    format_mes_brl,
    format_number_brl,
    format_percent_brl,
    format_pp_brl,
    format_razao_social,
    format_toponym,
    format_variacao_arena,
    prepare_report_context_v2,
)

FIXTURES = Path(__file__).parent / "fixtures" / "estrelas_mock.json"


@pytest.fixture
def raw_data():
    with open(FIXTURES, encoding="utf-8") as f:
        return json.load(f)


# ── format_currency_brl ─────────────────────────────────────

class TestFormatCurrencyBrl:
    def test_regular(self):
        assert format_currency_brl(1290.00) == "R$ 1.290,00"

    def test_millions_below_threshold(self):
        # < 1_000_000 mesmo com millions=True deve formatar normal
        assert format_currency_brl(990000, millions=True) == "R$ 990.000,00"

    def test_millions_above_threshold(self):
        assert format_currency_brl(3350000, millions=True) == "R$ 3,35 mi"

    def test_millions_conservador(self):
        assert format_currency_brl(2004552.0, millions=True) == "R$ 2,00 mi"

    def test_none(self):
        assert format_currency_brl(None) == "—"


# ── format_number_brl ────────────────────────────────────────

class TestFormatNumberBrl:
    def test_standard(self):
        assert format_number_brl(25144) == "25.144"

    def test_small(self):
        assert format_number_brl(754) == "754"

    def test_large(self):
        assert format_number_brl(107450) == "107.450"

    def test_none(self):
        assert format_number_brl(None) == "—"


# ── format_percent_brl ───────────────────────────────────────

class TestFormatPercentBrl:
    def test_basic(self):
        assert format_percent_brl(23.4) == "23,4%"

    def test_signed_positive(self):
        assert format_percent_brl(12.3, signed=True) == "+12,3%"

    def test_signed_negative(self):
        assert format_percent_brl(-18.6, signed=True) == "-18,6%"

    def test_zero(self):
        assert format_percent_brl(0.0) == "0,0%"

    def test_none(self):
        assert format_percent_brl(None) == "—"


# ── format_pp_brl ────────────────────────────────────────────

class TestFormatPpBrl:
    def test_positive(self):
        assert format_pp_brl(1.7) == "+1,7 pp"

    def test_negative(self):
        assert format_pp_brl(-1.3) == "-1,3 pp"

    def test_zero(self):
        assert format_pp_brl(0.0) == "+0,0 pp"

    def test_none(self):
        assert format_pp_brl(None) == "—"


# ── format_mes_brl ───────────────────────────────────────────

class TestFormatMesBrl:
    def test_abril(self):
        assert format_mes_brl("2025-04") == "abril/2025"

    def test_fevereiro(self):
        assert format_mes_brl("2026-02") == "fevereiro/2026"

    def test_empty(self):
        assert format_mes_brl("") == "—"

    def test_abrev_fevereiro(self):
        assert format_mes_brl("2026-02", abrev=True) == "fev/2026"

    def test_abrev_abril(self):
        assert format_mes_brl("2025-04", abrev=True) == "abr/2025"


# ── derive_short_name ────────────────────────────────────────

class TestDeriveShortName:
    def test_estrelas(self):
        assert derive_short_name("Estrelas Tecnologia da Informacao Ltda") == "Estrelas"

    def test_iniciais_fallback(self):
        result = derive_short_name("A P Telecomunicacoes Ltda")
        assert "voc" in result.lower()  # "vocês" ou "voces"

    def test_vainet(self):
        assert derive_short_name("Vainet Tecnologia Ltda") == "Vainet"

    def test_arias(self):
        assert derive_short_name("Arias Telecomunicacoes Ltda") == "Arias"


# ── format_toponym ───────────────────────────────────────────

# ── format_razao_social ─────────────────────────────────────

class TestFormatRazaoSocial:
    def test_estrelas(self):
        assert format_razao_social("ESTRELAS TECNOLOGIA DA INFORMACAO LTDA") == \
               "Estrelas Tecnologia da Informação Ltda"

    def test_client_co(self):
        assert format_razao_social("CLIENT CO SERVICOS DE REDE NORDESTE S.A.") == \
               "Client Co Serviços de Rede Nordeste S.A."

    def test_oi_recuperacao(self):
        assert format_razao_social("OI S.A. - EM RECUPERACAO JUDICIAL") == \
               "Oi S.A. - Em Recuperação Judicial"

    def test_paco_do_lumiar(self):
        assert format_razao_social("PACO DO LUMIAR TELECOMUNICACOES LTDA") == \
               "Paço do Lumiar Telecomunicações Ltda"

    def test_preposicoes(self):
        result = format_razao_social("SERVICOS DE TECNOLOGIA DA INFORMACAO S.A.")
        assert " de " in result
        assert " da " in result

    def test_sa_preservado(self):
        assert format_razao_social("TELEFONICA BRASIL S.A.").endswith("S.A.")

    def test_municipio_paco(self):
        assert format_razao_social("PACO DO LUMIAR") == "Paço do Lumiar"


# ── format_toponym ───────────────────────────────────────────
    def test_sao_jose(self):
        result = format_toponym("sao jose de ribamar")
        assert result == "Sao Jose de Ribamar"

    def test_paco_do_lumiar(self):
        result = format_toponym("paco do lumiar")
        assert result == "Paco do Lumiar"


# ── format_variacao_arena ────────────────────────────────────

class TestFormatVariacaoArena:
    def test_entrou(self):
        txt, cls = format_variacao_arena({"entrou_na_arena_periodo": True})
        assert txt == "Entrou"
        assert cls == "entrou"

    def test_positiva(self):
        txt, cls = format_variacao_arena({"variacao_percentual_arena": 12.3})
        assert "12,3" in txt
        assert cls == "up"

    def test_negativa(self):
        txt, cls = format_variacao_arena({"variacao_percentual_arena": -18.6})
        assert "18,6" in txt
        assert cls == "down"


# ── prepare_report_context_v2 ────────────────────────────────

class TestPrepareReportContextV2:
    def test_meta(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        assert ctx["meta"]["nome_curto"] == "Estrelas"
        assert ctx["meta"]["cnpj_completo"] == "12.130.171/0001-14"
        assert ctx["meta"]["uf_sede"] == "MA"
        assert "15" in ctx["meta"]["anos_atividade_fmt"]
        assert ctx["meta"]["razao_social_completa"] == "Estrelas Tecnologia da Informação Ltda"
        assert ctx["meta"]["municipio_sede"] == "Paço do Lumiar"
        assert ctx["meta"]["fonte_anatel_fmt"] == "fev/2026"
        assert ctx["meta"]["fonte_receita_fmt"] == "abr/2026"

    def test_arena_tabela(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        assert len(ctx["arena"]["tabela_concorrentes"]) in (10, 11)

    def test_arena_share_fmt(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        assert ctx["arena"]["share_agregado_prospect_fmt"] == "23,4%"

    def test_potencial_cenarios(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        assert len(ctx["potencial"]["cenarios"]) == 3
        # Realista deve ter destaque=True
        realista = next(c for c in ctx["potencial"]["cenarios"] if c["label"] == "Realista")
        assert realista["destaque"] is True

    def test_potencial_receita_realista(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        realista = next(c for c in ctx["potencial"]["cenarios"] if c["label"] == "Realista")
        assert "3,34" in realista["receita_fmt"] or "3,35" in realista["receita_fmt"]

    def test_analise_todos_none(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        assert all(v is None for v in ctx["analise"].values())

    def test_analise_chaves(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        expected_keys = {
            "pontos_de_atencao",
            "descricao_maior_crescimento",
            "descricao_maior_queda",
            "descricao_posicao_prospect",
            "contexto_integrador",
            "leitura_1", "leitura_2", "leitura_3",
        }
        assert expected_keys == set(ctx["analise"].keys())

    def test_evolucao_meses(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        assert len(ctx["evolucao"]["grafico_dados"]["meses"]) == 12

    def test_evolucao_destaques(self, raw_data):
        ctx = prepare_report_context_v2(raw_data)
        d = ctx["evolucao"]["destaques"]
        assert "pp" in d["maior_crescimento"]["valor_fmt"]
        assert "pp" in d["maior_queda"]["valor_fmt"]
        assert d["maior_crescimento"]["classe"] == "up"
        assert d["maior_queda"]["classe"] == "down"
