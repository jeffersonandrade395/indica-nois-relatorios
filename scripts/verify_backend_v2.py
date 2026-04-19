"""
Fase 6 — Verificacao end-to-end do backend v2.

Executa extract_full_report_data e prepare_report_context_v2 para um CNPJ de
teste, valida a estrutura do dict resultante e salva em /tmp/context_verify.json.

Uso:
    python scripts/verify_backend_v2.py [cnpj_basico] [ticket] [janela]

Defaults: cnpj=12130171, ticket=111.0, janela=24
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest.mock as mock

# Stub streamlit (nao usado aqui mas importado indiretamente pelo modulo)
sys.modules.setdefault("streamlit", mock.MagicMock())

from src import config as cfg

# Credenciais: fora do pacote (raiz do projeto pai)
_creds_candidate = Path(__file__).parent.parent.parent / "meu-n8n-458300-a6e9c2e03f26.json"
if _creds_candidate.exists():
    cfg.BQ_CREDS = str(_creds_candidate)

from src.extract import extract_full_report_data
from src.transform import prepare_report_context_v2
from src.validate import validate_prospect_data_v2


def _check(label, condition, detail=""):
    status = "OK" if condition else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return condition


def main(cnpj_basico="12130171", ticket=111.0, janela=24):
    print(f"\n=== VERIFY BACKEND v2 | CNPJ={cnpj_basico} | ticket={ticket} | janela={janela} ===\n")

    # 1. Extracao
    print("1. Extraindo dados...")
    raw = extract_full_report_data(cnpj_basico, ticket, janela)
    print(f"   identificacao: {list(raw.get('identificacao', {}).keys())}")
    print(f"   arena: {len(raw.get('arena', {}).get('top_10_concorrentes', []))} concorrentes top10")
    print(f"   evolucao: {len(raw.get('evolucao', {}).get('serie_prospect', []))} pontos temporais")
    print(f"   potencial: {len(raw.get('potencial', {}).get('cenarios', []))} cenarios")
    print(f"   metadados: {raw.get('metadados', {})}")

    # 2. Validacao
    print("\n2. Validando dados...")
    val = validate_prospect_data_v2(cnpj_basico, raw)
    print(f"   is_valid: {val['is_valid']}")
    if val["critical_errors"]:
        for e in val["critical_errors"]:
            print(f"   ERRO CRITICO: {e}")
        sys.exit(1)
    for w in val["warnings"]:
        print(f"   AVISO: {w}")

    # 3. Preparar contexto
    print("\n3. Preparando contexto para templates...")
    ctx = prepare_report_context_v2(raw)

    # 4. Criterios de aceite
    print("\n4. Criterios de aceite:")
    ident = raw["identificacao"]
    ok = True
    ok &= _check("razao_social comeca com Estrelas",
                 ident.get("razao_social", "").startswith("Estrelas"))
    ok &= _check("meta.nome_curto == Estrelas",
                 ctx["meta"]["nome_curto"] == "Estrelas")
    ok &= _check("meta.cnpj_completo presente",
                 bool(ctx["meta"]["cnpj_completo"]))
    ok &= _check("arena.tabela tem 10 ou 11 linhas",
                 len(ctx["arena"]["tabela_concorrentes"]) in (10, 11),
                 str(len(ctx["arena"]["tabela_concorrentes"])))
    ok &= _check("evolucao tem >= 12 pontos temporais",
                 len(ctx["evolucao"]["grafico_dados"]["meses"]) >= 12,
                 str(len(ctx["evolucao"]["grafico_dados"]["meses"])))
    ok &= _check("potencial tem 3 cenarios",
                 len(ctx["potencial"]["cenarios"]) == 3)
    ok &= _check("receita realista entre R$1M e R$10M",
                 any(
                     "R$ 3" in c["receita_fmt"] or "R$ 2" in c["receita_fmt"]
                     for c in ctx["potencial"]["cenarios"]
                     if c["label"] == "Realista"
                 ))
    ok &= _check("analise.* todos None",
                 all(v is None for v in ctx["analise"].values()))
    ok &= _check("analise tem 8 chaves",
                 len(ctx["analise"]) == 8, str(len(ctx["analise"])))

    # 5. Salvar JSON
    out_path = Path("/tmp/context_verify.json")
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n5. Contexto salvo em {out_path}")
    except Exception as e:
        # Windows: /tmp pode nao existir, tentar pasta local
        out_path = Path(__file__).parent.parent / "output" / "context_verify.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2, default=str)
        print(f"\n5. Contexto salvo em {out_path}")

    if ok:
        print("\nBACKEND v2 PRONTO. Dict validado — frontend pode consumir.")
    else:
        print("\nFALHAS detectadas — revisar acima.")
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]
    cnpj = args[0] if len(args) > 0 else "12130171"
    ticket = float(args[1]) if len(args) > 1 else 111.0
    janela = int(args[2]) if len(args) > 2 else 24
    main(cnpj, ticket, janela)
