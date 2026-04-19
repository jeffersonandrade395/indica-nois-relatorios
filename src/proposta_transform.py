"""
Transformação de dados para a Proposta Plus.

Baseline confirmado pelo analista (não Anatel): base, ticket e janela são inputs manuais.
"""

from datetime import datetime, timedelta
from typing import Optional

from .transform import format_currency_brl_short


def prepare_proposta_context(
    cnpj: str,
    base_operacional: int,
    ticket_medio_brl: float,
    janela_meses: int,
    modalidade: str,
    gap_operacional: str,
    validade_dias: int = 7,
    data_emissao: Optional[datetime] = None,
    relatorio_context: Optional[dict] = None,
    razao_social: Optional[str] = None,
    municipio: Optional[str] = None,
    uf: Optional[str] = None,
) -> dict:
    """
    Prepara contexto completo da Proposta Plus.

    Modo standalone: preencher razao_social, municipio, uf manualmente.
    Modo com relatório: passar relatorio_context — dados extraídos dele.
    """
    data_emissao = data_emissao or datetime.now()
    data_validade = data_emissao + timedelta(days=validade_dias)

    # META — dados do prospect
    if relatorio_context:
        meta = {
            "razao_social_completa": relatorio_context["meta"]["razao_social_completa"],
            "nome_curto": relatorio_context["meta"]["nome_curto"],
            "cnpj_completo": relatorio_context["meta"]["cnpj_completo"],
            "municipio_sede": relatorio_context["meta"]["municipio_sede"],
            "uf_sede": relatorio_context["meta"]["uf_sede"],
            "tem_relatorio_previo": True,
        }
    else:
        if not all([razao_social, municipio, uf]):
            raise ValueError("Modo standalone requer razao_social, municipio e uf.")
        meta = {
            "razao_social_completa": razao_social,
            "nome_curto": razao_social.split()[0],
            "cnpj_completo": _format_cnpj(cnpj),
            "municipio_sede": municipio,
            "uf_sede": uf,
            "tem_relatorio_previo": False,
        }

    # BASELINE — cenários de receita adicional
    cenarios = []
    for taxa, label in [(0.03, "Conservador"), (0.05, "Realista"), (0.10, "Otimista")]:
        novos_clientes = int(round(base_operacional * taxa))
        receita_total = novos_clientes * ticket_medio_brl * janela_meses
        cenarios.append({
            "label": label,
            "taxa_fmt": f"{int(taxa * 100)}%",
            "receita_fmt": format_currency_brl_short(receita_total),
            "destaque": label == "Realista",
        })

    baseline = {
        "base_operacional": base_operacional,
        "base_operacional_fmt": f"{base_operacional:,}".replace(",", "."),
        "ticket_medio": ticket_medio_brl,
        "ticket_medio_fmt": format_currency_brl_short(ticket_medio_brl),
        "janela_meses": janela_meses,
        "janela_fmt": f"{janela_meses} meses",
        "cenarios": cenarios,
    }

    # OFERTA — modalidade e preço
    if modalidade == "anual":
        oferta = {
            "modalidade": "anual",
            "modalidade_fmt": "cobrado anualmente",
            "preco_mensal": 990,
            "preco_fmt": "R$ 990",
        }
    elif modalidade == "mensal":
        oferta = {
            "modalidade": "mensal",
            "modalidade_fmt": "cobrado mensalmente",
            "preco_mensal": 1290,
            "preco_fmt": "R$ 1.290",
        }
    else:
        raise ValueError(f"Modalidade inválida: {modalidade}")

    # METADATA — datas e validade
    metadata = {
        "data_emissao": data_emissao,
        "data_emissao_fmt": data_emissao.strftime("%d/%m/%Y"),
        "mes_ano_fmt": _formatar_mes_ano_pt(data_emissao),
        "validade_dias": validade_dias,
        "validade_fmt": f"{validade_dias} dias corridos",
        "data_validade": data_validade,
        "data_validade_fmt": data_validade.strftime("%d/%m/%Y"),
    }

    analise = {"gap_operacional": gap_operacional}

    return {
        "meta": meta,
        "baseline": baseline,
        "oferta": oferta,
        "metadata": metadata,
        "analise": analise,
    }


def _format_cnpj(cnpj_raw: str) -> str:
    digits = "".join(c for c in cnpj_raw if c.isdigit()).zfill(14)
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def _formatar_mes_ano_pt(dt: datetime) -> str:
    meses = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
        5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
        9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }
    return f"{meses[dt.month]}/{dt.year}"
