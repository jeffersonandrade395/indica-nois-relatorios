import io
import base64
import logging
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from . import config as cfg

log = logging.getLogger(__name__)

ORANGE = "#F04E23"
DARK   = "#1A1A1A"
GREEN  = "#1CB85A"
BORDER = "#EAE6DF"
MUTED  = "#757575"
SOFT   = "#F5F2EC"

MESES_PT = {
    1: "janeiro", 2: "fevereiro", 3: "março", 4: "abril",
    5: "maio", 6: "junho", 7: "julho", 8: "agosto",
    9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

PREPS = {"de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas", "a", "o", "com"}

_SUFFIXES     = {'Ltda', 'S.A.', 'S/A', 'ME', 'EPP', 'S.a.', 'Sa', 'LTDA', 'SA'}
_ARTICLES     = {'A', 'O', 'As', 'Os', 'Um', 'Uma'}
_TOPO_PREPS   = {'de', 'do', 'da', 'dos', 'das', 'e'}

ACENTUACAO_MAP = {
    "INFORMACAO": "Informação",   "INFORMACOES": "Informações",
    "SERVICOS": "Serviços",       "SERVICO": "Serviço",
    "COMUNICACOES": "Comunicações","COMUNICACAO": "Comunicação",
    "TELECOMUNICACOES": "Telecomunicações", "TELECOMUNICACAO": "Telecomunicação",
    "OPERACOES": "Operações",     "OPERACAO": "Operação",
    "INDUSTRIA": "Indústria",     "COMERCIO": "Comércio",
    "TECNOLOGIA": "Tecnologia",
    "SOLUCOES": "Soluções",       "SOLUCAO": "Solução",
    "GESTAO": "Gestão",           "ADMINISTRACAO": "Administração",
    "RECUPERACAO": "Recuperação", "JUDICIAL": "Judicial",
    "PARTICIPACOES": "Participações", "CONCESSAO": "Concessão",
    "DISTRIBUICAO": "Distribuição",
    "PACO": "Paço",  "SAO": "São",  "LUIS": "Luís",  "JOSE": "José",
    "ANTONIO": "Antônio", "JULIO": "Júlio", "MUNICIPIO": "Município",
}

PREPOSICOES_MIN = {"da", "de", "do", "das", "dos", "e", "em", "na", "no"}
_SEPARADORES    = {"-", "–", "/"}


def format_razao_social(razao_social: str) -> str:
    """Aplica title case e acentuação pt-BR em razão social extraída sem acentos da Receita Federal."""
    if not razao_social:
        return razao_social
    palavras = razao_social.upper().split()
    resultado: list[str] = []
    for i, palavra in enumerate(palavras):
        if palavra in ("S.A.", "S.A", "LTDA", "ME", "EPP", "EIRELI"):
            resultado.append("Ltda" if palavra == "LTDA" else palavra)
            continue
        if palavra in ACENTUACAO_MAP:
            resultado.append(ACENTUACAO_MAP[palavra])
            continue
        palavra_lower = palavra.lower()
        prev = resultado[-1] if resultado else ""
        if i > 0 and palavra_lower in PREPOSICOES_MIN and prev not in _SEPARADORES:
            resultado.append(palavra_lower)
            continue
        resultado.append(palavra.capitalize())
    return " ".join(resultado)


def derive_short_name(razao_social: str) -> str:
    tokens = [t for t in razao_social.split()
              if t not in _SUFFIXES and t.lower() not in PREPS]
    if not tokens:
        return "vocês"
    first = tokens[0]
    if first in _ARTICLES or (len(first) <= 2 and first.isupper()):
        return "vocês"
    return first


def format_toponym(name: str) -> str:
    words = name.split()
    return ' '.join(
        w.lower() if w.lower() in _TOPO_PREPS else w.capitalize()
        for w in words
    )


def fmt_brl(value, decimals=2) -> str:
    if value is None:
        return "—"
    try:
        v = float(value)
        s = f"{v:,.{decimals}f}"
        return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "—"


def fmt_num(value) -> str:
    if value is None:
        return "—"
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "—"


def fmt_pct(value, decimals=1) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{decimals}f}%".replace(".", ",")
    except (ValueError, TypeError):
        return "—"


def fmt_date(value) -> str:
    if not value:
        return "—"
    try:
        if isinstance(value, date):
            return f"{MESES_PT[value.month].capitalize()} de {value.year}"
        parts = str(value).split("-")
        return f"{MESES_PT[int(parts[1])].capitalize()} de {parts[0]}"
    except Exception:
        return str(value)


def fmt_mes_ref(value: str) -> str:
    if not value:
        return "—"
    try:
        ano, mes = value.split("-")
        return f"{MESES_PT[int(mes)].capitalize()}/{ano}"
    except Exception:
        return value


def title_ptbr(text: str) -> str:
    if not text:
        return ""
    words = text.lower().split()
    return " ".join(w if (i > 0 and w in PREPS) else w.capitalize() for i, w in enumerate(words))


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def chart_panorama_ufs(top_ufs: list[dict]) -> str:
    if not top_ufs:
        return ""
    ufs    = [r["uf"] for r in top_ufs]
    totais = [r["total_isps"] for r in top_ufs]
    fig, ax = plt.subplots(figsize=(6.5, 3.2))
    ax.barh(ufs[::-1], totais[::-1], color=ORANGE, height=0.55)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{int(x):,}".replace(",", ".")))
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="both", labelsize=8)
    ax.tick_params(axis="x", colors=MUTED)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return _fig_to_b64(fig)


def chart_porte(top_ufs: list[dict]) -> str:
    if not top_ufs:
        return ""
    me     = sum(r.get("porte_me", 0) or 0 for r in top_ufs)
    epp    = sum(r.get("porte_epp", 0) or 0 for r in top_ufs)
    demais = sum(r.get("porte_demais", 0) or 0 for r in top_ufs)
    sizes  = [me, epp, demais]
    if sum(sizes) == 0:
        return ""
    fig, ax = plt.subplots(figsize=(3.2, 3.2))
    wedges, _, autotexts = ax.pie(
        sizes, labels=["ME", "EPP", "Demais"], autopct="%1.0f%%",
        colors=[ORANGE, "#C93D1A", DARK], startangle=90,
        textprops={"fontsize": 9}, pctdistance=0.75,
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(8)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return _fig_to_b64(fig)


def chart_share_municipal(competitivo: list[dict]) -> str:
    if not competitivo:
        return ""
    municipios = [r["municipio"].title() for r in competitivo]
    shares     = [float(r.get("market_share_pct") or 0) for r in competitivo]
    fig, ax = plt.subplots(figsize=(6.5, 2.5))
    cores = [GREEN if s >= 30 else ORANGE for s in shares]
    ax.barh(municipios[::-1], shares[::-1], color=cores[::-1], height=0.5)
    ax.set_xlabel("Market share (%)", fontsize=8, color=MUTED)
    ax.set_xlim(0, 105)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="both", labelsize=8)
    ax.tick_params(axis="x", colors=MUTED)
    for i, (share, mun) in enumerate(zip(shares[::-1], municipios[::-1])):
        ax.text(share + 1, i, f"{share:.1f}%".replace(".", ","), va="center", fontsize=7.5, color=DARK)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout(pad=0.4)
    return _fig_to_b64(fig)


def chart_projecao(cenarios: list[dict]) -> str:
    if not cenarios:
        return ""
    receitas = [c["receita"] for c in cenarios]
    labels   = ["Conservador\n(3%)", "Realista\n(5%)", "Otimista\n(10%)"]
    fig, ax  = plt.subplots(figsize=(5, 3))
    bars = ax.bar(range(3), receitas, color=[SOFT, ORANGE, DARK], width=0.5,
                  edgecolor=[BORDER, ORANGE, DARK])
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(labels, fontsize=8.5)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: f"R$ {v/1e6:.1f}M" if v >= 1e6 else f"R$ {int(v/1e3)}K"
    ))
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", labelsize=8, colors=MUTED)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    max_v = max(receitas) if receitas else 1
    for bar, val in zip(bars, receitas):
        lbl = f"R$ {val/1e6:.2f}M".replace(".", ",") if val >= 1e6 else f"R$ {int(val/1e3)}K"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_v * 0.03,
                lbl, ha="center", fontsize=8, color=DARK, fontweight="bold")
    fig.tight_layout(pad=0.4)
    return _fig_to_b64(fig)


def compute_projecao(acessos: int, ticket: float, meses: int) -> list[dict]:
    return [
        {
            "pct": pct,
            "label": f"{int(pct * 100)}%",
            "novos_clientes": round(acessos * pct),
            "receita": round(acessos * pct * ticket * meses),
            "receita_fmt": fmt_brl(round(acessos * pct * ticket * meses), decimals=0),
            "novos_fmt": fmt_num(round(acessos * pct)),
        }
        for pct in cfg.SCENARIOS
    ]


_GRANDES = {'telefonica brasil', 'claro nxt', 'claro s.a', 'tim s a', 'brisanet', 'unifique', 'algar', 'oi'}


def _is_grande(empresa: str) -> bool:
    e = empresa.lower()
    return any(g in e for g in _GRANDES)


def _prepare_movimento(mov: list[dict]) -> list[dict]:
    enriched = []
    for r in mov:
        assin_atual    = int(r.get("assinaturas") or 0)
        assin_anterior = int(r.get("assinaturas_anterior") or 0)
        variacao_pct   = float(r.get("variacao_pct") or 0)
        relevante = (assin_atual >= 10 or assin_anterior >= 10)
        if not relevante:
            continue
        empresa = r.get("empresa", "")
        grande = r.get("grande_operadora") or _is_grande(empresa)
        enriched.append({
            **r,
            "municipio_fmt":    format_toponym(r.get("municipio", "")),
            "empresa_fmt":      title_ptbr(empresa),
            "grande_operadora": grande,
            "assinaturas_fmt":  fmt_num(assin_atual),
            "variacao_fmt":     fmt_pct(variacao_pct),
            "variacao_positiva": variacao_pct > 0,
            "entrou_no_periodo": bool(r.get("entrou_no_periodo") or r.get("flag_entrada")),
            "saiu_no_periodo":   bool(r.get("saiu_no_periodo") or r.get("flag_saida")),
        })

    by_municipio: dict[str, list] = {}
    for r in enriched:
        by_municipio.setdefault(r["municipio"], []).append(r)

    result = []
    for mun_rows in by_municipio.values():
        positivas = sorted([r for r in mun_rows if r["variacao_positiva"]],
                           key=lambda r: abs(float(r.get("variacao_pct") or 0)), reverse=True)[:3]
        negativas = sorted([r for r in mun_rows if not r["variacao_positiva"]],
                           key=lambda r: abs(float(r.get("variacao_pct") or 0)), reverse=True)[:3]
        result.extend(positivas + negativas)

    return result


# ─────────────────────────────────────────────────────────────
#  FORMATADORES v2 — nomes canônicos conforme spec v2
#  Os formatadores v1 acima (fmt_brl, fmt_num, etc.) são preservados.
# ─────────────────────────────────────────────────────────────

_MESES_ABREV = {
    "01": "janeiro",  "02": "fevereiro", "03": "março",    "04": "abril",
    "05": "maio",     "06": "junho",     "07": "julho",    "08": "agosto",
    "09": "setembro", "10": "outubro",   "11": "novembro", "12": "dezembro",
}
_MESES_CURTO = {
    "01": "jan", "02": "fev", "03": "mar", "04": "abr",
    "05": "mai", "06": "jun", "07": "jul", "08": "ago",
    "09": "set", "10": "out", "11": "nov", "12": "dez",
}


def format_currency_brl(value: float, millions: bool = False) -> str:
    """R$ 1.290,00  ou  R$ 3,35 mi (se millions=True e value >= 1_000_000)."""
    if value is None:
        return "—"
    try:
        v = float(value)
        if millions and v >= 1_000_000:
            m = v / 1_000_000
            return f"R$ {m:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")
        s = f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except (ValueError, TypeError):
        return "—"


def format_number_brl(value) -> str:
    """1.290"""
    if value is None:
        return "—"
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "—"


def format_percent_brl(value: float, decimals: int = 1, signed: bool = False) -> str:
    """25,3%  ou  +25,3% se signed=True"""
    if value is None:
        return "—"
    try:
        v = float(value)
        s = f"{v:.{decimals}f}".replace(".", ",")
        if signed and v > 0:
            return f"+{s}%"
        return f"{s}%"
    except (ValueError, TypeError):
        return "—"


def format_pp_brl(value: float, decimals: int = 1) -> str:
    """+1,7 pp  ou  -1,3 pp (sempre signed)."""
    if value is None:
        return "—"
    try:
        v = float(value)
        s = f"{abs(v):.{decimals}f}".replace(".", ",")
        sign = "+" if v >= 0 else "-"
        return f"{sign}{s} pp"
    except (ValueError, TypeError):
        return "—"


def format_mes_brl(mes_yyyymm: str, abrev: bool = False) -> str:
    """'2025-04' → 'abril/2025' (ou 'abr/2025' se abrev=True)"""
    if not mes_yyyymm:
        return "—"
    try:
        ano, mes = str(mes_yyyymm)[:7].split("-")
        _map = _MESES_CURTO if abrev else _MESES_ABREV
        return f"{_map.get(mes, mes)}/{ano}"
    except Exception:
        return mes_yyyymm


def format_variacao_arena(row: dict) -> tuple[str, str]:
    """
    Retorna (texto_formatado, classe_css) para a coluna Variação 12m.
    Ex: ('↗ +12,3%', 'up') ou ('Entrou', 'entrou') ou ('↘ -18,6%', 'down')
    """
    if row.get("entrou_na_arena_periodo"):
        return "Entrou", "entrou"
    if row.get("saiu_da_arena_periodo"):
        return "Saiu", "saiu"
    pct = row.get("variacao_percentual_arena")
    if pct is None:
        return "—", "neutral"
    try:
        v = float(pct)
        if v > 0:
            return f"↗ {format_percent_brl(v, signed=True)}", "up"
        if v < 0:
            return f"↘ {format_percent_brl(v)}", "down"
        return "0%", "neutral"
    except (ValueError, TypeError):
        return "—", "neutral"


# ─────────────────────────────────────────────────────────────
#  FASE 3 — prepare_report_context_v2
#  Consolida raw_data de extract_full_report_data no dict
#  pronto para os templates Jinja2 do relatório v2 (5 páginas).
# ─────────────────────────────────────────────────────────────

_CORES_SERIE = ["#D97757", "#6B4FBB", "#1CB85A", "#4A90D9", "#A678DE"]


def prepare_report_context_v2(raw_data: dict) -> dict:
    """
    Consolida raw_data (de extract_full_report_data) em contexto estruturado
    para os templates Jinja2 do relatório v2.

    Returns:
        dict com: meta, arena, evolucao, potencial, analise.
    """
    ident    = raw_data.get("identificacao", {})
    arena_r  = raw_data.get("arena", {})
    ev_r     = raw_data.get("evolucao", {})
    pot_r    = raw_data.get("potencial", {})
    meta_r   = raw_data.get("metadados", {})

    razao_social = ident.get("razao_social", "")
    nome_curto   = derive_short_name(razao_social)
    municipio    = format_razao_social(ident.get("municipio_sede", ""))

    anos = int(ident.get("anos_atividade") or 0)
    anos_fmt = f"{anos} ano" if anos == 1 else f"{anos} anos"

    # ── META (capa) ──────────────────────────────────────────
    fonte_anatel = meta_r.get("fonte_anatel", "")
    meta = {
        "razao_social_completa": format_razao_social(razao_social),
        "nome_curto":            nome_curto,
        "cnpj_completo":         ident.get("cnpj_completo", ""),
        "municipio_sede":        municipio,
        "uf_sede":               ident.get("uf_sede", ""),
        "porte_fmt":             ident.get("porte", ""),
        "anos_atividade_fmt":    anos_fmt,
        "data_geracao_fmt":      format_mes_brl(meta_r.get("data_geracao", "")[:7] if meta_r.get("data_geracao") else ""),
        "fonte_anatel_fmt":      format_mes_brl(fonte_anatel, abrev=True) if fonte_anatel else "—",
        "fonte_receita_fmt":     format_mes_brl(meta_r.get("data_geracao", "")[:7] if meta_r.get("data_geracao") else "", abrev=True),
    }

    # ── ARENA (P2) ───────────────────────────────────────────
    totais = arena_r.get("totais", {})
    proprio = arena_r.get("proprio_prospect") or {}
    top10   = arena_r.get("top_10_concorrentes", [])
    prospect_no_top_10 = arena_r.get("prospect_no_top_10", False)

    total_arena = totais.get("total_assinantes_arena", 0)

    def _share(assin):
        return round(int(assin or 0) * 100 / total_arena, 1) if total_arena > 0 else 0.0

    def _row_arena(r, rank):
        variacao_txt, variacao_classe = format_variacao_arena(r)
        assin = int(r.get("assinantes_na_arena_atual") or 0)
        return {
            "rank":               rank,
            "razao_social_fmt":   format_razao_social(r.get("razao_social_concorrente") or ""),
            "eh_prospect":        bool(r.get("eh_o_proprio_alvo")),
            "eh_operadora_grande": bool(r.get("eh_operadora_grande")),
            "assinantes_fmt":     format_number_brl(assin),
            "share_fmt":          format_percent_brl(_share(assin)),
            "variacao_fmt":       variacao_txt,
            "variacao_classe":    variacao_classe,
            "entrou":             bool(r.get("entrou_na_arena_periodo")),
        }

    # Monta tabela: top 10 concorrentes (sem o prospect) + prospect no topo
    # Ordem real por assinantes desc inclui o prospect na posição correta
    from google.cloud import bigquery as _bq  # importado só para tipagem; não usado aqui
    todos_ordenados = sorted(
        top10 + ([proprio] if proprio and not prospect_no_top_10 else []),
        key=lambda r: int(r.get("assinantes_na_arena_atual") or 0),
        reverse=True,
    )

    # Reconstrói tabela com ranks corretos: se prospect está no top10 aparece na lista;
    # caso contrário aparece como linha extra após o top10
    tabela: list[dict] = []
    if prospect_no_top_10:
        # top10 já contém o prospect; ordenar todos por assinantes
        todos_com_proprio = sorted(
            top10 + [proprio] if proprio else top10,
            key=lambda r: int(r.get("assinantes_na_arena_atual") or 0),
            reverse=True,
        )
        for rank, row in enumerate(todos_com_proprio[:10], 1):
            tabela.append(_row_arena(row, rank))
    else:
        # top10 sem o prospect
        for rank, row in enumerate(top10, 1):
            tabela.append(_row_arena(row, rank))
        # descobre rank real do prospect
        rank_proprio = totais.get("qtd_concorrentes_diretos", len(top10))
        if proprio:
            extra = _row_arena(proprio, rank_proprio)
            tabela.append(extra)  # linha separada (template colocará divider)

    arena = {
        "municipios_alvo":               totais.get("qtd_municipios_alvo", 0),
        "concorrentes_diretos":          totais.get("qtd_concorrentes_diretos", 0),
        "total_assinantes_arena_fmt":    format_number_brl(total_arena),
        "share_agregado_prospect_fmt":   format_percent_brl(totais.get("share_agregado_prospect", 0)),
        "tabela_concorrentes":           tabela,
        "prospect_no_top_10":            prospect_no_top_10,
    }

    # ── EVOLUÇÃO TEMPORAL (P3) ───────────────────────────────
    serie_prospect = ev_r.get("serie_prospect", [])
    serie_top3     = ev_r.get("serie_top_3_concorrentes", [])
    serie_demais   = ev_r.get("serie_demais_agregados", [])
    destaques_r    = ev_r.get("destaques", {})

    meses_labels = [p["mes"] for p in serie_prospect]

    grafico_dados = {
        "meses": meses_labels,
        "serie_prospect": {
            "nome":     nome_curto,
            "valores":  [p["share_pct"] for p in serie_prospect],
            "cor":      "#F04E23",
            "destaque": True,
        },
        "serie_concorrentes": [
            {
                "nome":   format_razao_social(s["nome"]),
                "valores": [p["share_pct"] for p in s["valores"]],
                "cor":    _CORES_SERIE[i % len(_CORES_SERIE)],
            }
            for i, s in enumerate(serie_top3)
        ],
        "serie_agregado": {
            "nome":   "Demais concorrentes agregados",
            "valores": [p["share_pct"] for p in serie_demais],
            "cor":    "#9A9591",
            "dashed": True,
        },
    }

    def _destaque_classe(pp: float) -> str:
        if pp > 0.1:
            return "up"
        if pp < -0.1:
            return "down"
        return "neutral"

    mc = destaques_r.get("maior_crescimento", {})
    mq = destaques_r.get("maior_queda", {})
    pp = destaques_r.get("posicao_prospect", {})

    evolucao = {
        "grafico_dados": grafico_dados,
        "destaques": {
            "maior_crescimento": {
                "empresa":   format_razao_social(mc.get("empresa") or ""),
                "valor_fmt": format_pp_brl(mc.get("variacao_pp", 0)),
                "classe":    _destaque_classe(mc.get("variacao_pp", 0)),
            },
            "maior_queda": {
                "empresa":   format_razao_social(mq.get("empresa") or ""),
                "valor_fmt": format_pp_brl(mq.get("variacao_pp", 0)),
                "classe":    _destaque_classe(mq.get("variacao_pp", 0)),
            },
            "posicao_prospect": {
                "empresa":   nome_curto,
                "valor_fmt": format_pp_brl(pp.get("variacao_pp", 0)),
                "classe":    _destaque_classe(pp.get("variacao_pp", 0)),
            },
        },
        "contadores": ev_r.get("contadores", {}),
    }

    # ── POTENCIAL (P4) ───────────────────────────────────────
    base_anatel  = pot_r.get("base_anatel", 0)
    ticket       = pot_r.get("ticket_medio_brl", 111.0)
    janela       = pot_r.get("janela_meses", 24)

    cenarios_fmt = []
    for i, c in enumerate(pot_r.get("cenarios", [])):
        cenarios_fmt.append({
            "label":               c["label"],
            "taxa_fmt":            f"{int(c['taxa'] * 100)}% de conversao",
            "receita_fmt":         format_currency_brl(c["receita_total"], millions=True),
            "novos_clientes_fmt":  f"{format_number_brl(c['novos_clientes'])} novos clientes",
            "periodo_fmt":         f"em {janela} meses",
            "destaque":            c["label"] == "Realista",
        })

    potencial = {
        "base_anatel_fmt":  format_number_brl(base_anatel),
        "ticket_medio_fmt": f"R$ {int(ticket)}",
        "janela_fmt":       f"{janela} meses",
        "cenarios":         cenarios_fmt,
    }

    # ── ANÁLISE (campos manuais) ─────────────────────────────
    analise = {
        "pontos_de_atencao":           None,
        "descricao_maior_crescimento": None,
        "descricao_maior_queda":       None,
        "descricao_posicao_prospect":  None,
        "contexto_integrador":         None,
        "leitura_1":                   None,
        "leitura_2":                   None,
        "leitura_3":                   None,
    }

    return {
        "meta":     meta,
        "arena":    arena,
        "evolucao": evolucao,
        "potencial": potencial,
        "analise":  analise,
    }


def prepare_report_context(raw_data: dict, ticket_medio: float, janela_meses: int) -> dict:
    ident    = raw_data.get("identificacao", {})
    anatel   = raw_data.get("anatel_agregado", {}) or {}
    comp     = raw_data.get("competitivo_municipal", [])
    mov      = raw_data.get("movimento_mercado", [])
    panorama = raw_data.get("panorama_brasil", {})
    socios   = raw_data.get("socios", [])

    acessos  = int(anatel.get("acessos_total") or 0)
    cenarios = compute_projecao(acessos, ticket_medio, janela_meses)

    razao_social = ident.get("razao_social", "")
    nome_curto   = derive_short_name(razao_social)

    return {
        "identificacao": {
            **ident,
            "razao_social_fmt":  title_ptbr(razao_social),
            "municipio_fmt":     format_toponym(ident.get("municipio", "")),
            "data_abertura_fmt": fmt_date(ident.get("data_abertura")),
            "capital_fmt":       fmt_brl(ident.get("capital_social")),
            "anos_atividade":    ident.get("anos_atividade", 0),
            "nome_curto":        nome_curto,
        },
        "nome_curto": nome_curto,
        "socios": socios,
        "anatel": {
            **anatel,
            "acessos_fmt":  fmt_num(acessos),
            "mes_ref_fmt":  fmt_mes_ref(anatel.get("mes_referencia", "")),
        },
        "competitivo_municipal": [
            {
                **r,
                "municipio_fmt":     format_toponym(r.get("municipio", "")),
                "assinaturas_fmt":   fmt_num(r.get("assinaturas")),
                "market_share_fmt":  fmt_pct(r.get("market_share_pct")),
                "total_mun_fmt":     fmt_num(r.get("total_assinaturas_municipio")),
            }
            for r in comp
        ],
        "movimento_mercado": _prepare_movimento(mov),
        "panorama_brasil": {
            **panorama,
            "total_isps_fmt":   fmt_num(panorama.get("total_isps_brasil")),
            "media_anos_fmt":   f"{float(panorama.get('media_anos_atividade') or 0):.1f}".replace(".", ","),
        },
        "projecao": {
            "cenarios":      cenarios,
            "ticket_fmt":    fmt_brl(ticket_medio, decimals=0),
            "janela_meses":  janela_meses,
            "acessos_fmt":   fmt_num(acessos),
        },
        "charts": {
            "panorama_ufs":    chart_panorama_ufs(panorama.get("top_ufs", [])),
            "porte":           chart_porte(panorama.get("top_ufs", [])),
            "share_municipal": chart_share_municipal(comp),
            "projecao":        chart_projecao(cenarios),
        },
        "data_relatorio_fmt": fmt_date(date.today()),
        "ticket_medio":  ticket_medio,
        "janela_meses":  janela_meses,
    }
