import logging
import re
import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src import config as cfg
from src.extract import CNPJNotFoundError, BigQueryTimeoutError, extract_full_report_data
from src.validate import validate_prospect_data, validate_projection_warning
from src.transform import prepare_report_context_v2, fmt_brl, fmt_num, fmt_pct
from src.render import render_report_html_v2
from src.export import export_report_to_pdf

cfg.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=cfg.LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(cfg.LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("app")

st.set_page_config(
    page_title="Gerador de Relatórios — Indica Nóis",
    page_icon="🔶",
    layout="wide",
)

with st.sidebar:
    st.markdown(
        "<div style='font-weight:900;font-size:18px;letter-spacing:-0.5px'>Indica Nóis</div>"
        "<div style='font-size:11px;color:#757575;margin-top:2px'>Gerador de Relatórios v2.0</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Jefferson Andrade · Fundador")
    st.caption("jefferson@indicanois.com.br")
    st.divider()
    if st.button("Limpar sessão"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


def _normalize(raw: str) -> str:
    return re.sub(r"\D", "", raw)[:8]

def _valid_cnpj(raw: str) -> bool:
    return len(re.sub(r"\D", "", raw)) in (8, 14)


# ================================================================
# SECTION 1 — INPUT
# ================================================================
st.markdown(
    "<h1 style='font-size:28px;font-weight:900;letter-spacing:-0.5px;margin-bottom:4px'>"
    "Gerador de Relatórios Setoriais</h1>"
    "<p style='color:#757575;margin-bottom:24px'>Indica Nóis · Prospecção ativa de ISPs · v2</p>",
    unsafe_allow_html=True,
)

col_input, col_btn = st.columns([3, 1])
with col_input:
    cnpj_raw = st.text_input("CNPJ do prospect", placeholder="12.345.678/0001-90 ou 12345678")
with col_btn:
    st.write("")
    buscar = st.button("Buscar dados", type="primary", use_container_width=True)

if buscar:
    if not cnpj_raw:
        st.error("Informe o CNPJ do prospect.")
    elif not _valid_cnpj(cnpj_raw):
        st.error("CNPJ inválido — informe 8 ou 14 dígitos.")
    else:
        cnpj = _normalize(cnpj_raw)
        with st.spinner("Consultando BigQuery..."):
            for attempt in range(3):
                try:
                    data = extract_full_report_data(cnpj)
                    st.session_state.update({"data": data, "cnpj": cnpj, "html": None})
                    break
                except CNPJNotFoundError as e:
                    st.error(str(e))
                    break
                except BigQueryTimeoutError:
                    if attempt < 2:
                        st.warning(f"Timeout na tentativa {attempt + 1}/3. Aguarde...")
                    else:
                        st.error("BigQuery não respondeu após 3 tentativas.")
                except Exception as e:
                    st.error(f"Erro inesperado: {e}")
                    log.exception("Erro na extração CNPJ=%s", cnpj_raw)
                    break


# ================================================================
# SECTION 2 — PREVIEW DOS DADOS
# ================================================================
if "data" not in st.session_state:
    st.stop()

data = st.session_state["data"]
cnpj = st.session_state["cnpj"]

vr = validate_prospect_data(data)
if not vr.is_valid:
    for err in vr.critical_errors:
        st.error(f"**Erro crítico:** {err}")
    st.stop()

for w in vr.warnings:
    st.warning(w)

st.divider()
st.subheader("Dados extraídos")

ident = data["identificacao"]
arena_raw = data.get("arena") or {}
totais = arena_raw.get("totais") or {}

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Identificação**")
    st.write(f"**Razão social:** {ident.get('razao_social', '—')}")
    st.write(f"**CNPJ:** {ident.get('cnpj_completo', '—')}")
    st.write(f"**Município:** {ident.get('municipio_sede', '—')} · {ident.get('uf_sede', '—')}")
    st.write(f"**Porte:** {ident.get('porte', '—')}")
    st.write(f"**Anos de atividade:** {ident.get('anos_atividade', '—')}")
with col2:
    st.markdown("**Arena competitiva**")
    st.metric("Municípios de atuação", totais.get("qtd_municipios_alvo", "—"))
    st.metric("Concorrentes diretos", totais.get("qtd_concorrentes_diretos", "—"))
    st.metric("Assinantes na arena", fmt_num(totais.get("total_assinantes_arena")))
with col3:
    st.markdown("**Prospect na arena**")
    prospect = arena_raw.get("proprio_prospect") or {}
    st.metric("Assinantes (Anatel)", fmt_num(prospect.get("assinantes_na_arena_atual")))
    share = totais.get("share_agregado_prospect")
    st.metric("Share na arena", f"{share:.1f}%".replace(".", ",") if share else "—")
    st.write(f"**No top 10?** {'Sim' if arena_raw.get('prospect_no_top_10') else 'Não'}")


# ================================================================
# SECTION 3 — PREMISSAS DE PROJEÇÃO
# ================================================================
st.divider()
st.subheader("Premissas de projeção")

col_t, col_m = st.columns(2)
with col_t:
    ticket = st.number_input(
        "Ticket médio (R$/mês)", min_value=10.0, max_value=5000.0,
        value=float(cfg.DEFAULT_TICKET), step=5.0, format="%.2f",
    )
with col_m:
    meses = st.number_input(
        "Janela de projeção (meses)", min_value=6, max_value=60,
        value=int(cfg.DEFAULT_MONTHS), step=6,
    )

acessos = int(prospect.get("assinantes_na_arena_atual") or 0)
proj_warn = validate_projection_warning(acessos, ticket, meses, ident.get("porte", ""))
if proj_warn:
    st.warning(proj_warn)


# ================================================================
# SECTION 4 — ANÁLISE DO ANALISTA (8 campos)
# ================================================================
st.divider()
st.subheader("Análise do analista")
st.caption("Preencha antes de gerar o relatório. Campos vazios aparecem como placeholder no PDF.")

st.markdown("**Página 2 — Arena competitiva**")
pontos_de_atencao = st.text_area(
    "Pontos de Atenção",
    height=100,
    placeholder="• Liderança em 2 de 4 praças, mas 3 concorrentes novos entrando...\n• W J dos Santos caiu 18,6% — janela de oportunidade...\n• Dutra e Dias entrou do zero com 1.871 assinantes...",
    help="Uma linha por ponto. Use • ou - como prefixo (opcional).",
)

st.markdown("**Página 3 — Evolução temporal**")
col_mc, col_mq, col_pp = st.columns(3)
with col_mc:
    descricao_maior_crescimento = st.text_area(
        "Maior crescimento — descrição",
        height=80,
        placeholder="Contexto sobre a empresa que mais cresceu...",
        help="Até 200 caracteres. Aparece no card 'Maior crescimento'.",
    )
with col_mq:
    descricao_maior_queda = st.text_area(
        "Maior queda — descrição",
        height=80,
        placeholder="Contexto sobre a empresa que mais caiu...",
        help="Até 200 caracteres. Aparece no card 'Maior queda'.",
    )
with col_pp:
    descricao_posicao_prospect = st.text_area(
        "Sua posição — descrição",
        height=80,
        placeholder="Leitura da posição do prospect no período...",
        help="Até 200 caracteres. Aparece no card 'Sua posição'.",
    )

contexto_integrador = st.text_area(
    "Contexto integrador (parágrafo de ligação)",
    height=80,
    placeholder="Em 12 meses, 3 concorrentes novos entraram na arena e 2 perderam mais de 10% de share...",
    help="Até 400 caracteres. Aparece abaixo dos 3 cards de destaque.",
)

st.markdown("**Página 5 — Leituras do analista**")
leitura_1 = st.text_area(
    "Leitura 1",
    height=90,
    placeholder="Primeira leitura estratégica sobre os dados...",
    help="Até 400 caracteres.",
)
leitura_2 = st.text_area(
    "Leitura 2",
    height=90,
    placeholder="Segunda leitura — foco em riscos ou oportunidades...",
    help="Até 400 caracteres.",
)
leitura_3 = st.text_area(
    "Leitura 3",
    height=90,
    placeholder="Terceira leitura — conexão com o programa de indicação...",
    help="Até 400 caracteres.",
)

analise = {
    "pontos_de_atencao":         pontos_de_atencao or None,
    "descricao_maior_crescimento": descricao_maior_crescimento or None,
    "descricao_maior_queda":     descricao_maior_queda or None,
    "descricao_posicao_prospect": descricao_posicao_prospect or None,
    "contexto_integrador":       contexto_integrador or None,
    "leitura_1":                 leitura_1 or None,
    "leitura_2":                 leitura_2 or None,
    "leitura_3":                 leitura_3 or None,
}

campos_preenchidos = sum(1 for v in analise.values() if v)
cor = "green" if campos_preenchidos >= 6 else ("orange" if campos_preenchidos >= 3 else "red")
st.markdown(
    f"<small style='color:{cor}'>{campos_preenchidos} / 8 campos preenchidos</small>",
    unsafe_allow_html=True,
)


# ================================================================
# SECTION 5 — PREVIEW HTML
# ================================================================
st.divider()
if st.button("Gerar preview do relatório", use_container_width=False):
    with st.spinner("Renderizando relatório v2..."):
        try:
            data_v2 = extract_full_report_data(cnpj, ticket_medio_brl=ticket, janela_meses=int(meses))
            ctx = prepare_report_context_v2(data_v2)
            ctx["analise"].update({k: v for k, v in analise.items() if v is not None})
            html_str = render_report_html_v2(ctx)
            st.session_state["html"] = html_str
            st.session_state["ctx"] = ctx
            log.info("Preview v2 gerado CNPJ=%s", cnpj)
        except Exception as e:
            st.error(f"Erro ao renderizar: {e}")
            log.exception("Erro no render v2 CNPJ=%s", cnpj)

if st.session_state.get("html"):
    st.components.v1.html(st.session_state["html"], height=900, scrolling=True)


# ================================================================
# SECTION 6 — EXPORT PDF
# ================================================================
st.divider()
col_ex, col_hint = st.columns([2, 3])
with col_ex:
    export_btn = st.button(
        "Exportar PDF",
        type="primary",
        disabled=not st.session_state.get("html"),
        use_container_width=True,
    )
with col_hint:
    if not st.session_state.get("html"):
        st.caption("Gere o preview antes de exportar.")

if export_btn:
    with st.spinner("Gerando PDF..."):
        try:
            pdf = export_report_to_pdf(st.session_state["html"])
            filename = f"{cnpj}_{date.today().isoformat().replace('-', '')}_v2.pdf"
            st.download_button(
                label="Baixar PDF",
                data=pdf,
                file_name=filename,
                mime="application/pdf",
                type="primary",
            )
            log.info("PDF v2 gerado: %s (%d KB)", filename, len(pdf) // 1024)
        except Exception as e:
            st.error(f"Erro ao gerar PDF: {e}")
            log.exception("Erro no export v2 CNPJ=%s", cnpj)
