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
