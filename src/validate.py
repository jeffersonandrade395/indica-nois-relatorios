from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool = True
    critical_errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_prospect_data(data: dict) -> ValidationResult:
    r = ValidationResult()

    ident = data.get("identificacao")
    if not ident or not ident.get("razao_social"):
        r.is_valid = False
        r.critical_errors.append("Razão social não encontrada — dado Receita Federal ausente ou inválido.")
        return r

    anatel = data.get("anatel_agregado")
    if not anatel or not anatel.get("acessos_total"):
        r.is_valid = False
        r.critical_errors.append(
            "Dados Anatel não encontrados para este CNPJ. "
            "Verifique se o ISP reporta banda larga fixa à Anatel ou se o CNPJ está atualizado."
        )
        return r

    if not data.get("competitivo_municipal"):
        r.warnings.append("Sem dados de posicionamento municipal — página 3 exibirá apenas totais agregados.")

    if not data.get("movimento_mercado"):
        r.warnings.append("Sem dados de movimento de mercado — página 4 exibirá texto alternativo.")

    acessos = anatel.get("acessos_total", 0) or 0
    if acessos > 50_000:
        r.warnings.append(
            f"Prospect tem {acessos:,} assinantes — acima do ICP declarado (5k–50k). "
            "Considere abordagem diferenciada."
        )

    anos = ident.get("anos_atividade", 0) or 0
    if anos < 2:
        r.warnings.append("Empresa com menos de 2 anos de atividade. Capital social pode estar subestimado.")

    return r


# ─────────────────────────────────────────────────────────────
#  VALIDAÇÕES v2 — para raw_data de extract_full_report_data
# ─────────────────────────────────────────────────────────────

def validate_prospect_data_v2(cnpj_basico: str, raw_data: dict) -> dict:
    """
    Valida raw_data produzido por extract_full_report_data.

    Returns:
        dict com is_valid (bool), critical_errors (list), warnings (list).
    """
    from datetime import date as _date

    critical_errors: list[str] = []
    warnings: list[str] = []

    # ── Critical errors ──────────────────────────────────────
    ident = raw_data.get("identificacao", {})
    if not ident or not ident.get("razao_social"):
        critical_errors.append(
            "razao_social vazia — dado Receita Federal ausente ou inválido."
        )

    arena = raw_data.get("arena", {})
    total_arena = (arena.get("totais") or {}).get("total_assinantes_arena", 0)
    if total_arena == 0:
        critical_errors.append(
            "Arena competitiva sem assinantes — prospect sem dado Anatel ou vw_arena_competitiva vazia."
        )

    if critical_errors:
        return {"is_valid": False, "critical_errors": critical_errors, "warnings": warnings}

    # ── Warnings ─────────────────────────────────────────────

    # Defasagem Anatel > 4 meses
    mes_ref = raw_data.get("metadados", {}).get("fonte_anatel", "")
    if mes_ref:
        try:
            ano, mes = mes_ref.split("-")
            data_anatel = _date(int(ano), int(mes), 1)
            defasagem = (
                (_date.today().year - data_anatel.year) * 12
                + _date.today().month - data_anatel.month
            )
            if defasagem > 4:
                warnings.append(
                    f"Dado Anatel com {defasagem} meses de defasagem (referencia: {mes_ref}). "
                    "Exibir banner na UI."
                )
        except Exception:
            pass

    # Série temporal incompleta (< 12 pontos)
    ev = raw_data.get("evolucao", {})
    periodos = ev.get("periodos_disponiveis", 0)
    if periodos < 12:
        warnings.append(
            f"Evolução temporal com apenas {periodos} períodos (mínimo recomendado: 12). "
            "Gráfico P3 ficará parcial."
        )

    # Arena com menos de 5 concorrentes
    qtd_conc = (arena.get("totais") or {}).get("qtd_concorrentes_diretos", 0)
    if qtd_conc < 5:
        warnings.append(
            f"Arena com apenas {qtd_conc} concorrentes diretos. "
            "Tabela P2 pode ficar empobrecida."
        )

    # Prospect é único ISP na arena
    if qtd_conc == 0:
        warnings.append(
            "Prospect é o único ISP reportado na arena. "
            "Relatório gera com texto adaptado."
        )

    # Validações de premissas (P4)
    pot = raw_data.get("potencial", {})
    ticket = pot.get("ticket_medio_brl", 111.0)
    janela = pot.get("janela_meses", 24)
    if ticket < 10 or ticket > 500:
        warnings.append(
            f"Ticket médio R$ {ticket:.0f} fora do range recomendado (R$ 10–R$ 500)."
        )
    if janela < 6 or janela > 60:
        warnings.append(
            f"Janela de projeção {janela} meses fora do range recomendado (6–60 meses)."
        )

    return {
        "is_valid":       len(critical_errors) == 0,
        "critical_errors": critical_errors,
        "warnings":        warnings,
    }


def validate_projection_warning(acessos: int, ticket: float, meses: int, porte: str) -> str | None:
    receita_otimista = acessos * 0.10 * ticket * meses
    if receita_otimista > 50_000_000:
        return (
            f"Projeção otimista supera R$ 50 milhões com ticket R$ {ticket:,.0f} "
            f"e janela de {meses} meses. Revise as premissas."
        )
    if receita_otimista > 10_000_000 and porte in ("ME", "EPP"):
        return (
            f"Projeção otimista supera R$ 10M para ISP de porte {porte}. "
            "Revise ticket médio e janela antes de continuar."
        )
    return None
