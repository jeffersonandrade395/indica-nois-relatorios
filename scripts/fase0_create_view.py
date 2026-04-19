"""
Fase 0 — Cria vw_arena_competitiva no BigQuery.
SQL corrigido para o schema real de anatel_acessos_raw:
  - `periodo` em vez de `mes_referencia`
  - `assinaturas` em vez de `assinaturas_banda_larga_fixa`
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.cloud import bigquery
from google.oauth2 import service_account

CREDS_PATH = Path(__file__).parent.parent.parent / "meu-n8n-458300-a6e9c2e03f26.json"
PROJECT = "meu-n8n-458300"
DATASET = "indica_nois_prospeccao"
P = f"`{PROJECT}.{DATASET}`"

CREATE_VIEW_SQL = f"""
CREATE OR REPLACE VIEW {P}.vw_arena_competitiva AS

WITH pares_arena AS (
  SELECT
    a.cnpj_basico AS cnpj_alvo,
    c.cnpj_basico AS cnpj_concorrente,
    c.empresa AS empresa_concorrente,
    a.municipio,
    a.uf,
    c.assinaturas AS assinantes_concorrente_municipio_atual,
    SUBSTR(c.periodo, 1, 7) AS mes_ref
  FROM {P}.anatel_acessos_raw a
  INNER JOIN {P}.anatel_acessos_raw c
    ON a.municipio = c.municipio
    AND a.uf = c.uf
    AND a.periodo = c.periodo
  WHERE a.periodo = (
    SELECT MAX(periodo) FROM {P}.anatel_acessos_raw
  )
),

pares_arena_anterior AS (
  SELECT
    a.cnpj_basico AS cnpj_alvo,
    c.cnpj_basico AS cnpj_concorrente,
    a.municipio,
    c.assinaturas AS assinantes_concorrente_municipio_anterior,
    SUBSTR(c.periodo, 1, 7) AS mes_ref_anterior
  FROM {P}.anatel_acessos_raw a
  INNER JOIN {P}.anatel_acessos_raw c
    ON a.municipio = c.municipio
    AND a.uf = c.uf
    AND a.periodo = c.periodo
  WHERE a.periodo = (
    SELECT MAX(periodo)
    FROM {P}.anatel_acessos_raw
    WHERE DATE_DIFF(
      DATE(SUBSTR((SELECT MAX(periodo) FROM {P}.anatel_acessos_raw), 1, 10)),
      DATE(SUBSTR(periodo, 1, 10)),
      MONTH
    ) >= 10
  )
),

agregacao_arena AS (
  SELECT
    p.cnpj_alvo,
    p.cnpj_concorrente,
    ANY_VALUE(p.empresa_concorrente) AS empresa_concorrente,
    SUM(COALESCE(p.assinantes_concorrente_municipio_atual, 0)) AS assinantes_na_arena_atual,
    SUM(COALESCE(pa.assinantes_concorrente_municipio_anterior, 0)) AS assinantes_na_arena_anterior,
    COUNT(DISTINCT p.municipio) AS qtd_municipios_em_comum,
    STRING_AGG(DISTINCT p.municipio ORDER BY p.municipio LIMIT 3) AS municipios_top3,
    COUNT(DISTINCT p.municipio) > 3 AS tem_mais_municipios,
    ANY_VALUE(p.mes_ref) AS mes_ref_atual,
    ANY_VALUE(pa.mes_ref_anterior) AS mes_ref_anterior
  FROM pares_arena p
  LEFT JOIN pares_arena_anterior pa
    ON p.cnpj_alvo = pa.cnpj_alvo
    AND p.cnpj_concorrente = pa.cnpj_concorrente
    AND p.municipio = pa.municipio
  GROUP BY p.cnpj_alvo, p.cnpj_concorrente
),

final AS (
  SELECT
    ar.cnpj_alvo,
    ar.cnpj_concorrente,
    COALESCE(rt.razao_social, ar.empresa_concorrente) AS razao_social_concorrente,
    (ar.cnpj_alvo = ar.cnpj_concorrente) AS eh_o_proprio_alvo,
    REGEXP_CONTAINS(
      UPPER(COALESCE(rt.razao_social, ar.empresa_concorrente, '')),
      r'^(TELEFONICA|VIVO|CLARO|TIM|BRISANET|UNIFIQUE|ALGAR|OI\\s|OI$)'
    ) AS eh_operadora_grande,
    ar.assinantes_na_arena_atual,
    ar.assinantes_na_arena_anterior,
    (ar.assinantes_na_arena_atual - ar.assinantes_na_arena_anterior) AS variacao_absoluta_arena,
    CASE
      WHEN ar.assinantes_na_arena_anterior = 0 AND ar.assinantes_na_arena_atual > 0 THEN NULL
      WHEN ar.assinantes_na_arena_anterior = 0 THEN 0.0
      ELSE ROUND(
        (ar.assinantes_na_arena_atual - ar.assinantes_na_arena_anterior) * 100.0 / ar.assinantes_na_arena_anterior,
        1
      )
    END AS variacao_percentual_arena,
    ar.qtd_municipios_em_comum,
    CASE
      WHEN ar.tem_mais_municipios THEN CONCAT(ar.municipios_top3, ', ...')
      ELSE ar.municipios_top3
    END AS lista_municipios_em_comum,
    (ar.assinantes_na_arena_anterior = 0 AND ar.assinantes_na_arena_atual > 0) AS entrou_na_arena_periodo,
    (ar.assinantes_na_arena_anterior > 0 AND ar.assinantes_na_arena_atual = 0) AS saiu_da_arena_periodo,
    ar.mes_ref_atual AS mes_referencia_atual,
    ar.mes_ref_anterior AS mes_referencia_anterior
  FROM agregacao_arena ar
  LEFT JOIN {P}.receita_telecom rt
    ON ar.cnpj_concorrente = rt.cnpj_basico
)

SELECT * FROM final
WHERE assinantes_na_arena_atual > 0 OR assinantes_na_arena_anterior > 0
"""

VALIDATION_QUERIES = [
    (
        "Contagem de concorrentes para Estrelas (esperado >= 30)",
        f"SELECT COUNT(*) AS total FROM {P}.vw_arena_competitiva WHERE cnpj_alvo = '12130171'",
    ),
    (
        "Próprio prospect (esperado: ~25.144 assinantes)",
        f"SELECT assinantes_na_arena_atual FROM {P}.vw_arena_competitiva WHERE cnpj_alvo = '12130171' AND eh_o_proprio_alvo = TRUE",
    ),
    (
        "Grandes operadoras na arena (esperado: Claro, Vivo, etc.)",
        f"SELECT razao_social_concorrente FROM {P}.vw_arena_competitiva WHERE cnpj_alvo = '12130171' AND eh_operadora_grande = TRUE LIMIT 5",
    ),
]


def main():
    print("=== FASE 0: Criando vw_arena_competitiva ===\n")
    creds = service_account.Credentials.from_service_account_file(str(CREDS_PATH))
    client = bigquery.Client(credentials=creds, project=PROJECT)

    print("Executando CREATE OR REPLACE VIEW...")
    job = client.query(CREATE_VIEW_SQL)
    job.result(timeout=120)
    print("OK View criada com sucesso.\n")

    print("=== Validacoes ===")
    all_ok = True
    for desc, sql in VALIDATION_QUERIES:
        rows = list(client.query(sql).result())
        print(f"\n>> {desc}")
        for row in rows:
            print(f"   {dict(row)}")
        if not rows:
            print("   AVISO: Sem resultados")
            all_ok = False

    if all_ok:
        print("\nOK Fase 0 concluida. View validada.")
    else:
        print("\nERRO Validacao falhou.")
        sys.exit(1)


if __name__ == "__main__":
    main()
