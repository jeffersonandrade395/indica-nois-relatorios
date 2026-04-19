"""Testes de render para Proposta Plus."""
import pytest
from src.proposta_transform import prepare_proposta_context
from src.render import render_proposta_html

RELATORIO_CTX_MOCK = {
    "meta": {
        "razao_social_completa": "Estrelas Tecnologia da Informação Ltda",
        "nome_curto": "Estrelas",
        "cnpj_completo": "12.130.171/0001-14",
        "municipio_sede": "Paço do Lumiar",
        "uf_sede": "MA",
    }
}


def test_render_proposta_com_relatorio_nao_lanca_erro():
    ctx = prepare_proposta_context(
        cnpj="12130171",
        base_operacional=25144,
        ticket_medio_brl=111.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Teste de gap operacional com dados confirmados em call.",
        relatorio_context=RELATORIO_CTX_MOCK,
    )
    html = render_proposta_html(ctx)
    assert "Plano Plus" in html
    assert "R$ 2,01 mi" in html   # conservador
    assert "R$ 3,35 mi" in html   # realista
    assert "R$ 6,70 mi" in html   # otimista
    assert "Estrelas Tecnologia da Informação Ltda" in html
    assert "Jefferson Andrade" in html
    assert "Founder, Indica Nóis" in html


def test_render_proposta_standalone():
    ctx = prepare_proposta_context(
        cnpj="99999999",
        razao_social="Teste Ltda",
        municipio="São Paulo",
        uf="SP",
        base_operacional=1000,
        ticket_medio_brl=100.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Teste gap.",
    )
    html = render_proposta_html(ctx)
    assert "Teste Ltda" in html
    assert "preparada com base nos dados operacionais" in html
    assert "Plano Plus" in html


def test_render_proposta_contem_3_paginas():
    ctx = prepare_proposta_context(
        cnpj="12130171",
        base_operacional=25144,
        ticket_medio_brl=111.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Gap de teste.",
        relatorio_context=RELATORIO_CTX_MOCK,
    )
    html = render_proposta_html(ctx)
    assert "Página 1" in html or "CAPA" in html
    assert "Página 2 de 3" in html
    assert "Página 3 de 3" in html


def test_render_proposta_card_financeiro_byo():
    ctx = prepare_proposta_context(
        cnpj="12130171",
        base_operacional=25144,
        ticket_medio_brl=111.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Gap de teste.",
        relatorio_context=RELATORIO_CTX_MOCK,
    )
    html = render_proposta_html(ctx)
    assert "BYO-ASAAS" in html or "BYO-ASAAS" in html.upper()


def test_render_proposta_checklist_aceite():
    ctx = prepare_proposta_context(
        cnpj="12130171",
        base_operacional=25144,
        ticket_medio_brl=111.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Gap de teste.",
        relatorio_context=RELATORIO_CTX_MOCK,
    )
    html = render_proposta_html(ctx)
    assert "COMO ACEITAR" in html
    assert "Aceito a proposta Plus" in html
    assert "QUANDO PLUS, QUANDO PRO" in html


def test_render_proposta_modalidade_mensal():
    ctx = prepare_proposta_context(
        cnpj="99999999",
        razao_social="ISP Mensal Ltda",
        municipio="Recife",
        uf="PE",
        base_operacional=500,
        ticket_medio_brl=89.0,
        janela_meses=12,
        modalidade="mensal",
        gap_operacional="Gap mensal.",
    )
    html = render_proposta_html(ctx)
    assert "R$ 1.290" in html
    assert "cobrado mensalmente" in html
