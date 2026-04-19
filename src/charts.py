import base64
import io
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

log = logging.getLogger(__name__)

_FONT_SIZE_TICK = 7
_FONT_SIZE_LEGEND = 7


def generate_evolucao_temporal_chart(grafico_dados: dict) -> str:
    """Renders share-% time series as a PNG and returns base64-encoded string."""
    meses = grafico_dados["meses"]
    serie_prospect = grafico_dados["serie_prospect"]
    serie_concorrentes = grafico_dados.get("serie_concorrentes") or []
    serie_agregado = grafico_dados.get("serie_agregado")

    n = len(meses)
    x = list(range(n))

    fig, ax = plt.subplots(figsize=(7.8, 2.9))
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FAF8F5")

    ax.grid(axis="y", color="#EAE6DF", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    # Calcular ylim excluindo a série agregada (que representa o resto do mercado
    # e distorceria a escala, tornando as séries dos competidores ativos invisíveis)
    valores_para_escala = list(serie_prospect["valores"][:n])
    for s in serie_concorrentes:
        valores_para_escala.extend(s["valores"][:n])
    max_val = max((v for v in valores_para_escala if v is not None), default=10)
    y_limit = max(max_val * 1.25, 10)
    ax.set_ylim(0, y_limit)

    tick_step = 5 if y_limit <= 30 else 10
    ax.set_yticks(range(0, int(y_limit) + 1, tick_step))
    ax.set_yticklabels(
        [f"{v}%" for v in range(0, int(y_limit) + 1, tick_step)],
        fontsize=_FONT_SIZE_TICK, color="#757575",
    )

    if serie_agregado:
        vals = serie_agregado["valores"][:n]
        # Clipa a série agregada ao teto do gráfico para não dominar visualmente
        vals_clip = [min(v, y_limit * 0.98) if v is not None else None for v in vals]
        ax.plot(x[:len(vals_clip)], vals_clip,
                color=serie_agregado["cor"], linewidth=1.5,
                linestyle="--", zorder=1, alpha=0.5)

    for s in serie_concorrentes:
        vals = s["valores"][:n]
        # find first non-zero index for entrantes
        start = next((i for i, v in enumerate(vals) if v and v > 0), 0)
        ax.plot(x[start:start + len(vals)], vals[start:],
                color=s["cor"], linewidth=2.0, zorder=2)
        if start > 0:
            ax.plot(x[start], vals[start], "o", color=s["cor"], markersize=4, zorder=3)

    prospect_vals = serie_prospect["valores"][:n]
    ax.plot(x[:len(prospect_vals)], prospect_vals,
            color=serie_prospect["cor"], linewidth=3.5, zorder=4,
            solid_capstyle="round", solid_joinstyle="round")

    # X axis — show every 3rd label to avoid crowding
    tick_labels = []
    for i, m in enumerate(meses):
        if i == 0 or i == n - 1 or i % 3 == 0:
            tick_labels.append(m)
        else:
            tick_labels.append("")
    ax.set_xticks(x)
    ax.set_xticklabels(tick_labels, fontsize=_FONT_SIZE_TICK)

    ax.tick_params(axis="both", length=0)

    for spine in ax.spines.values():
        spine.set_visible(False)

    plt.tight_layout(pad=0.4)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    result = base64.b64encode(buf.read()).decode()
    log.info("chart gerado (%d KB)", len(result) // 1024)
    return result
