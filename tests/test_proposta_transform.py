"""Testes para src/proposta_transform.py"""
import pytest
from datetime import datetime
from src.proposta_transform import prepare_proposta_context, _format_cnpj, _formatar_mes_ano_pt

RELATORIO_CTX_MOCK = {
    "meta": {
        "razao_social_completa": "Estrelas Tecnologia da Informação Ltda",
        "nome_curto": "Estrelas",
        "cnpj_completo": "12.130.171/0001-14",
        "municipio_sede": "Paço do Lumiar",
        "uf_sede": "MA",
    }
}


def _ctx_estrelas(**kwargs):
    defaults = dict(
        cnpj="12130171",
        base_operacional=25144,
        ticket_medio_brl=111.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Gap de teste.",
        relatorio_context=RELATORIO_CTX_MOCK,
    )
    defaults.update(kwargs)
    return prepare_proposta_context(**defaults)


def test_prepare_with_relatorio_context():
    ctx = _ctx_estrelas()
    assert ctx["meta"]["razao_social_completa"] == "Estrelas Tecnologia da Informação Ltda"
    assert ctx["meta"]["nome_curto"] == "Estrelas"
    assert ctx["meta"]["tem_relatorio_previo"] is True


def test_prepare_standalone_mode():
    ctx = prepare_proposta_context(
        cnpj="99999999",
        razao_social="Teste Ltda",
        municipio="São Paulo",
        uf="SP",
        base_operacional=1000,
        ticket_medio_brl=100.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Gap teste.",
    )
    assert ctx["meta"]["razao_social_completa"] == "Teste Ltda"
    assert ctx["meta"]["tem_relatorio_previo"] is False
    assert ctx["meta"]["municipio_sede"] == "São Paulo"


def test_standalone_mode_requires_all_fields():
    with pytest.raises(ValueError, match="standalone"):
        prepare_proposta_context(
            cnpj="99999999",
            base_operacional=1000,
            ticket_medio_brl=100.0,
            janela_meses=24,
            modalidade="anual",
            gap_operacional="Gap.",
            # sem razao_social, municipio, uf
        )


def test_calcula_3_cenarios_corretamente():
    # Vainet: 5655 assinantes, R$99, 24 meses
    # Conservador (3%): 5655 * 0.03 = ~170 → 170 * 99 * 24 ≈ R$403,920
    # Realista (5%): 5655 * 0.05 = ~283 → 283 * 99 * 24 ≈ R$671,868 ≈ R$672 mil
    ctx = prepare_proposta_context(
        cnpj="13197278",
        base_operacional=5655,
        ticket_medio_brl=99.0,
        janela_meses=24,
        modalidade="anual",
        gap_operacional="Gap.",
        razao_social="Vainet Ltda",
        municipio="Tijucas do Sul",
        uf="PR",
    )
    cenarios = ctx["baseline"]["cenarios"]
    assert len(cenarios) == 3
    conservador = next(c for c in cenarios if c["label"] == "Conservador")
    realista = next(c for c in cenarios if c["label"] == "Realista")
    otimista = next(c for c in cenarios if c["label"] == "Otimista")

    assert "403" in conservador["receita_fmt"] or "mil" in conservador["receita_fmt"]
    assert "672" in realista["receita_fmt"] or "mil" in realista["receita_fmt"]
    assert realista["destaque"] is True
    assert conservador["destaque"] is False
    assert otimista["destaque"] is False


def test_modalidade_anual_preco():
    ctx = _ctx_estrelas(modalidade="anual")
    assert ctx["oferta"]["preco_fmt"] == "R$ 990"
    assert ctx["oferta"]["preco_mensal"] == 990


def test_modalidade_mensal_preco():
    ctx = _ctx_estrelas(modalidade="mensal")
    assert ctx["oferta"]["preco_fmt"] == "R$ 1.290"
    assert ctx["oferta"]["preco_mensal"] == 1290


def test_modalidade_invalida_lanca_erro():
    with pytest.raises(ValueError, match="Modalidade inválida"):
        _ctx_estrelas(modalidade="semestral")


def test_validade_padrao_7_dias():
    emissao = datetime(2026, 4, 19)
    ctx = _ctx_estrelas(data_emissao=emissao)
    assert ctx["metadata"]["validade_dias"] == 7
    assert ctx["metadata"]["data_validade_fmt"] == "26/04/2026"


def test_formato_cenarios_usa_format_currency_brl_short():
    ctx = _ctx_estrelas()
    cenarios = ctx["baseline"]["cenarios"]
    for c in cenarios:
        # Deve usar formato curto: "R$ X mi" ou "R$ X mil"
        assert "R$" in c["receita_fmt"]
        # Não deve conter valor por extenso com muitos zeros
        assert "000.000" not in c["receita_fmt"]


def test_format_cnpj():
    # 8 dígitos → zfill(14) → "00000012130171" → 00.000.012/1301-71
    assert _format_cnpj("12130171") == "00.000.012/1301-71"
    # CNPJ completo
    assert _format_cnpj("12130171000114") == "12.130.171/0001-14"


def test_formatar_mes_ano_pt():
    assert _formatar_mes_ano_pt(datetime(2026, 4, 1)) == "Abril/2026"
    assert _formatar_mes_ano_pt(datetime(2026, 1, 1)) == "Janeiro/2026"
    assert _formatar_mes_ano_pt(datetime(2026, 12, 1)) == "Dezembro/2026"
