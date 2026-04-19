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
