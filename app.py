import logging
import re
import sys
from datetime import date
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))

from src import config as cfg
from src.extract import CNPJNotFoundError, BigQueryTimeoutError, extract_full_report_data
from src.validate import validate_prospect_data_v2, validate_projection_warning
from src.transform import prepare_report_context_v2, fmt_brl, fmt_num, fmt_pct
from src.render import render_report_html_v2, render_proposta_html
from src.export import export_report_to_pdf, export_proposta_to_pdf
from src.proposta_transform import prepare_proposta_context

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
    page_title="Gerador de Documentos — Indica Nóis",
    page_icon="🔶",
    layout="wide",
)

with st.sidebar:
    st.markdown(
        "<div style='font-weight:900;font-size:18px;letter-spacing:-0.5px'>Indica Nóis</div>"
        "<div style='font-size:11px;color:#757575;margin-top:2px'>Gerador de Documentos v2.1</div>",
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
# HEADER + SELETOR DE TIPO DE DOCUMENTO
# ================================================================
st.markdown(
    "<h1 style='font-size:28px;font-weight:900;letter-spacing:-0.5px;margin-bottom:4px'>"
    "Gerador de Documentos</h1>"
    "<p style='color:#757575;margin-bottom:24px'>Indica Nóis · Prospecção ativa de ISPs · v2.1</p>",
    unsafe_allow_html=True,
)

tipo_documento = st.radio(
    "Tipo de documento:",
    options=["📊 Relatório de Prospecção", "📋 Proposta Plus"],
    horizontal=True,
    key="tipo_documento",
)

st.divider()

col_input, col_btn = st.columns([3, 1])
with col_input:
    cnpj_raw = st.text_input("CNPJ do prospect", placeholder="12.345.678/0001-90 ou 12345678")
with col_btn:
    st.write("")
    buscar = st.button("Buscar dados", type="primary", use_container_width=True)


# ================================================================
# FLUXO RELATÓRIO DE PROSPECÇÃO
# ================================================================
def render_relatorio_ui(cnpj_raw: str, buscar: bool) -> None:
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
                        # Tentar salvar contexto no Drive se disponível
                        try:
                            from src.drive_storage import is_drive_configured, save_report_context
                            if is_drive_configured():
                                ctx_tmp = prepare_report_context_v2(data)
                                save_report_context(cnpj, ctx_tmp)
                                st.toast("✓ Contexto salvo no Drive", icon="✅")
                        except Exception as e:
                            log.warning("Contexto não persistido no Drive: %s", e)
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

    if "data" not in st.session_state:
        st.stop()

    data = st.session_state["data"]
    cnpj = st.session_state["cnpj"]

    vr = validate_prospect_data_v2(cnpj, data)
    if not vr["is_valid"]:
        for err in vr["critical_errors"]:
            st.error(f"**Erro crítico:** {err}")
        st.stop()

    for w in vr["warnings"]:
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

    st.divider()
    st.subheader("Análise do analista")
    st.caption("Preencha antes de gerar o relatório. Campos vazios aparecem como placeholder no PDF.")

    st.markdown("**Página 2 — Arena competitiva**")
    pontos_de_atencao = st.text_area(
        "Pontos de Atenção", height=100,
        placeholder="• Liderança em 2 de 4 praças, mas 3 concorrentes novos entrando...",
        help="Uma linha por ponto. Use • ou - como prefixo (opcional).",
    )

    st.markdown("**Página 3 — Evolução temporal**")
    col_mc, col_mq, col_pp = st.columns(3)
    with col_mc:
        descricao_maior_crescimento = st.text_area(
            "Maior crescimento — descrição", height=80,
            placeholder="Contexto sobre a empresa que mais cresceu...",
        )
    with col_mq:
        descricao_maior_queda = st.text_area(
            "Maior queda — descrição", height=80,
            placeholder="Contexto sobre a empresa que mais caiu...",
        )
    with col_pp:
        descricao_posicao_prospect = st.text_area(
            "Sua posição — descrição", height=80,
            placeholder="Leitura da posição do prospect no período...",
        )

    contexto_integrador = st.text_area(
        "Contexto integrador (parágrafo de ligação)", height=80,
        placeholder="Em 12 meses, 3 concorrentes novos entraram na arena...",
    )

    st.markdown("**Página 5 — Leituras do analista**")
    leitura_1 = st.text_area("Leitura 1", height=90, placeholder="Primeira leitura estratégica...")
    leitura_2 = st.text_area("Leitura 2", height=90, placeholder="Segunda leitura...")
    leitura_3 = st.text_area("Leitura 3", height=90, placeholder="Terceira leitura...")

    analise = {
        "pontos_de_atencao": pontos_de_atencao or None,
        "descricao_maior_crescimento": descricao_maior_crescimento or None,
        "descricao_maior_queda": descricao_maior_queda or None,
        "descricao_posicao_prospect": descricao_posicao_prospect or None,
        "contexto_integrador": contexto_integrador or None,
        "leitura_1": leitura_1 or None,
        "leitura_2": leitura_2 or None,
        "leitura_3": leitura_3 or None,
    }

    campos_preenchidos = sum(1 for v in analise.values() if v)
    cor = "green" if campos_preenchidos >= 6 else ("orange" if campos_preenchidos >= 3 else "red")
    st.markdown(
        f"<small style='color:{cor}'>{campos_preenchidos} / 8 campos preenchidos</small>",
        unsafe_allow_html=True,
    )

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


# ================================================================
# FLUXO PROPOSTA PLUS
# ================================================================
def render_proposta_plus_ui(cnpj_raw: str) -> None:
    if not cnpj_raw or not _valid_cnpj(cnpj_raw):
        st.info("Insira um CNPJ válido para continuar.")
        return

    cnpj = _normalize(cnpj_raw)

    # Verifica relatório prévio no Drive
    relatorio_context = None
    try:
        from src.drive_storage import is_drive_configured, load_latest_report_context
        if is_drive_configured():
            with st.spinner("Verificando relatório prévio no Drive..."):
                relatorio_context = load_latest_report_context(cnpj)
        else:
            st.caption("Drive não configurado — modo standalone disponível.")
    except Exception as e:
        log.warning("Falha ao buscar contexto do Drive: %s", e)
        st.warning(f"⚠ Não foi possível verificar o Drive: {e}")

    if relatorio_context:
        st.success(f"✓ Relatório encontrado: {relatorio_context['meta']['razao_social_completa']}")
        modo = "com_relatorio"
    else:
        st.warning("⚠ Nenhum relatório prévio encontrado. Modo standalone.")
        modo = "standalone"

    st.subheader("1. Dados validados na call")
    st.caption("Preencha com os valores confirmados pelo prospect durante a call de diagnóstico.")

    col1, col2, col3 = st.columns(3)
    with col1:
        base_operacional = st.number_input(
            "Base ativa confirmada *", min_value=0, value=None,
            placeholder="Ex: 25144", key="pp_base",
        )
    with col2:
        ticket_medio = st.number_input(
            "Ticket médio (R$/mês) *", min_value=0.0, value=None,
            placeholder="Ex: 111.00", step=0.01, key="pp_ticket",
        )
    with col3:
        janela = st.number_input(
            "Janela (meses) *", min_value=1, max_value=60, value=24, key="pp_janela",
        )

    razao_social = municipio = uf = None
    if modo == "standalone":
        st.subheader("2. Dados do prospect (standalone)")
        st.caption("Como não há relatório prévio, preencha os dados do prospect.")

        col_rs, col_mun, col_uf = st.columns([3, 2, 1])
        with col_rs:
            razao_social = st.text_input("Razão social *", key="pp_razao_social")
        with col_mun:
            municipio = st.text_input("Município *", key="pp_municipio")
        with col_uf:
            uf = st.selectbox(
                "UF *",
                options=["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
                         "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"],
                key="pp_uf",
            )

    st.subheader("3. Configuração comercial")

    col_mod, col_val = st.columns(2)
    with col_mod:
        modalidade = st.radio(
            "Modalidade",
            options=["anual", "mensal"],
            format_func=lambda x: {"anual": "Anual (R$ 990/mês)", "mensal": "Mensal (R$ 1.290/mês)"}[x],
            horizontal=True,
            key="pp_modalidade",
        )
    with col_val:
        validade = st.number_input(
            "Validade (dias)", min_value=1, max_value=30, value=7, key="pp_validade",
        )

    st.subheader("4. Análise comercial")
    gap_operacional = st.text_area(
        "Gap operacional identificado *",
        placeholder="Ex: Na call, identificamos que a operação não rastreia origem de indicação informal...",
        help="3-4 linhas amarrando fato da base + mecanismo da perda + como a Plus preenche",
        max_chars=400,
        key="pp_gap",
    )

    # Validação
    campos = [base_operacional, ticket_medio, gap_operacional]
    if modo == "standalone":
        campos.extend([razao_social, municipio, uf])

    todos_preenchidos = all(
        c is not None and (not isinstance(c, str) or c.strip() != "")
        for c in campos
    )

    if not todos_preenchidos:
        st.warning("⚠ Preencha todos os campos obrigatórios (*)")
        return

    if st.button("📄 Gerar Proposta Plus", type="primary"):
        with st.spinner("Gerando proposta..."):
            try:
                kwargs = {
                    "cnpj": cnpj,
                    "base_operacional": int(base_operacional),
                    "ticket_medio_brl": float(ticket_medio),
                    "janela_meses": int(janela),
                    "modalidade": modalidade,
                    "gap_operacional": gap_operacional,
                    "validade_dias": int(validade),
                }
                if modo == "com_relatorio":
                    kwargs["relatorio_context"] = relatorio_context
                else:
                    kwargs["razao_social"] = razao_social
                    kwargs["municipio"] = municipio
                    kwargs["uf"] = uf

                context = prepare_proposta_context(**kwargs)
                pdf = export_proposta_to_pdf(context)

                nome_curto = context["meta"]["nome_curto"]
                filename = f"Proposta_Plus_{nome_curto}_{cnpj}_{date.today().isoformat().replace('-', '')}.pdf"

                st.success("✅ Proposta gerada!")
                st.download_button(
                    "⬇ Baixar Proposta Plus",
                    pdf,
                    file_name=filename,
                    mime="application/pdf",
                    type="primary",
                )
                log.info("Proposta Plus gerada: %s (%d KB)", filename, len(pdf) // 1024)
            except Exception as e:
                st.error(f"Erro ao gerar proposta: {e}")
                log.exception("Erro na geração da Proposta Plus CNPJ=%s", cnpj)


# ================================================================
# ROTEAMENTO POR TIPO DE DOCUMENTO
# ================================================================
if tipo_documento == "📊 Relatório de Prospecção":
    render_relatorio_ui(cnpj_raw, buscar)
elif tipo_documento == "📋 Proposta Plus":
    render_proposta_plus_ui(cnpj_raw)
