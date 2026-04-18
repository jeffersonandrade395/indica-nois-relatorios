import logging
import re
import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src import config as cfg
from src.extract import CNPJNotFoundError, BigQueryTimeoutError, extract_prospect_data
from src.validate import validate_prospect_data, validate_projection_warning
from src.transform import prepare_report_context, fmt_brl, fmt_num, fmt_pct
from src.render import render_report_html
from src.export import export_html_to_pdf

# -- Logging --
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

# -- Page --
st.set_page_config(
    page_title="Gerador de Relatórios — Indica Nóis",
    page_icon="🔶",
    layout="wide",
)

# -- Sidebar --
with st.sidebar:
    st.markdown(
        "<div style='font-weight:900;font-size:18px;letter-spacing:-0.5px'>Indica Nóis</div>"
        "<div style='font-size:11px;color:#757575;margin-top:2px'>Gerador de Relatórios v1.0</div>",
        unsafe_allow_html=True,
    )
    st.divider()
    st.caption("Jefferson Andrade · Fundador")
    st.caption("jeffersonandrade@indicanois.com.br")
    st.divider()
    if st.button("Limpar sessão"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# -- Helpers --
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
    "<p style='color:#757575;margin-bottom:24px'>Indica Nóis · Prospecção ativa de ISPs</p>",
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
                    data = extract_prospect_data(cnpj)
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

ident  = data["identificacao"]
anatel = data.get("anatel_agregado") or {}
comp   = data.get("competitivo_municipal") or []

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Identificação**")
    st.write(f"**Razão social:** {ident.get('razao_social', '—')}")
    st.write(f"**CNPJ completo:** {ident.get('cnpj_completo', '—')}")
    st.write(f"**Cidade:** {ident.get('municipio', '—').title()} · {ident.get('uf', '—')}")
    st.write(f"**Porte:** {ident.get('porte', '—')}")
    st.write(f"**Capital social:** {fmt_brl(ident.get('capital_social'))}")
    st.write(f"**Anos de atividade:** {ident.get('anos_atividade', '—')}")
    st.write(f"**CNAE:** {ident.get('cnae_descricao', '—')}")

with col2:
    st.markdown("**Dados Anatel**")
    st.metric("Assinantes BL Fixa", fmt_num(anatel.get("acessos_total")))
    st.write(f"**Referência:** {anatel.get('mes_referencia', '—')}")
    st.write(f"**UFs de atuação:** {anatel.get('ufs_atuacao', '—')}")
    st.write(f"**Qtd. estados:** {anatel.get('qtd_ufs', '—')}")

with col3:
    st.markdown("**Top municípios**")
    if comp:
        for r in comp[:4]:
            mun = r.get("municipio", "").title()
            share = fmt_pct(r.get("market_share_pct"))
            rank = r.get("ranking_local", "—")
            st.write(f"• **{mun}** — {share} share · #{rank}")
    else:
        st.caption("Sem dados de posicionamento municipal.")


# ================================================================
# SECTION 3 — PREMISSAS + ANÁLISE MANUAL
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

acessos = int(anatel.get("acessos_total") or 0)
proj_warn = validate_projection_warning(acessos, ticket, meses, ident.get("porte", ""))
if proj_warn:
    st.warning(proj_warn)

st.divider()
st.subheader("Sua análise")
st.caption("3 leituras que faço olhando esses dados — mínimo 200 caracteres, máximo 1200.")

manual = st.text_area(
    "Análise manual",
    height=200,
    max_chars=1200,
    placeholder="1. ...\n\n2. ...\n\n3. ...",
    help="Seja específico. Referencie números do relatório. Conecte com o problema de aquisição de clientes.",
    label_visibility="collapsed",
)
n_chars = len(manual)
color = "green" if n_chars >= 200 else "red"
st.markdown(
    f"<small style='color:{color}'>{n_chars} / 1200 caracteres</small>",
    unsafe_allow_html=True,
)


# ================================================================
# SECTION 4 — PREVIEW HTML
# ================================================================
st.divider()
if st.button("Gerar preview do relatório", use_container_width=False):
    if n_chars < 200:
        st.error("A análise manual precisa ter pelo menos 200 caracteres.")
    else:
        with st.spinner("Renderizando relatório..."):
            try:
                ctx = prepare_report_context(data, ticket, meses)
                html_str = render_report_html(ctx, manual)
                st.session_state["html"] = html_str
                st.session_state["ctx"] = ctx
                log.info("Preview gerado CNPJ=%s", cnpj)
            except Exception as e:
                st.error(f"Erro ao renderizar: {e}")
                log.exception("Erro no render CNPJ=%s", cnpj)

if st.session_state.get("html"):
    st.components.v1.html(st.session_state["html"], height=900, scrolling=True)


# ================================================================
# SECTION 5 — EXPORT PDF
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
        st.caption("Gere o preview do relatório antes de exportar.")

if export_btn:
    if n_chars < 200:
        st.error("Análise manual incompleta — mínimo 200 caracteres.")
    else:
        with st.spinner("Gerando PDF..."):
            try:
                pdf = export_html_to_pdf(st.session_state["html"])
                filename = f"{cnpj}_{date.today().isoformat().replace('-', '')}.pdf"
                st.download_button(
                    label="Baixar PDF",
                    data=pdf,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                )
                log.info("PDF gerado: %s (%d KB)", filename, len(pdf) // 1024)
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
                log.exception("Erro no export CNPJ=%s", cnpj)
