"""Test PDF generation with mock data — run via MSYS2 Python."""
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mplcfg")
os.makedirs("/tmp/mplcfg", exist_ok=True)

from src.transform import prepare_report_context
from src.render import render_report_html
from src.export import export_html_to_pdf

MOCK = {
    "identificacao": {
        "cnpj_basico": "12130171",
        "razao_social": "INFOBRAS TELECOMUNICACOES LTDA",
        "municipio": "PACO DO LUMIAR",
        "uf": "MA",
        "data_abertura": "2011-03-15",
        "capital_social": 50000.0,
        "anos_atividade": 13,
    },
    "anatel_agregado": {
        "acessos_total": 4820,
        "mes_referencia": "2024-09",
        "ranking_estadual": 12,
        "total_isps_uf": 87,
        "market_share_estadual_pct": 1.8,
    },
    "competitivo_municipal": [
        {
            "municipio": "PACO DO LUMIAR",
            "empresa": "INFOBRAS TELECOMUNICACOES LTDA",
            "assinaturas": 4820,
            "market_share_pct": 38.2,
            "total_assinaturas_municipio": 12620,
        },
        {
            "municipio": "PACO DO LUMIAR",
            "empresa": "CLARO S.A",
            "assinaturas": 3100,
            "market_share_pct": 24.6,
            "total_assinaturas_municipio": 12620,
        },
        {
            "municipio": "PACO DO LUMIAR",
            "empresa": "TELEFONICA BRASIL S.A",
            "assinaturas": 2800,
            "market_share_pct": 22.2,
            "total_assinaturas_municipio": 12620,
        },
        {
            "municipio": "SAO LUIS",
            "empresa": "INFOBRAS TELECOMUNICACOES LTDA",
            "assinaturas": 890,
            "market_share_pct": 2.1,
            "total_assinaturas_municipio": 42000,
        },
    ],
    "movimento_mercado": [
        {
            "municipio": "PACO DO LUMIAR",
            "empresa": "INFOBRAS TELECOMUNICACOES LTDA",
            "assinaturas": 4820,
            "assinaturas_anterior": 4100,
            "variacao_pct": 17.6,
            "grande_operadora": False,
            "entrou_no_periodo": False,
            "saiu_no_periodo": False,
        },
        {
            "municipio": "PACO DO LUMIAR",
            "empresa": "CLARO S.A",
            "assinaturas": 3100,
            "assinaturas_anterior": 3400,
            "variacao_pct": -8.8,
            "grande_operadora": True,
            "entrou_no_periodo": False,
            "saiu_no_periodo": False,
        },
        {
            "municipio": "PACO DO LUMIAR",
            "empresa": "NET VELOZ TELECOM LTDA",
            "assinaturas": 320,
            "assinaturas_anterior": 0,
            "variacao_pct": 100.0,
            "grande_operadora": False,
            "entrou_no_periodo": True,
            "saiu_no_periodo": False,
        },
        {
            "municipio": "SAO LUIS",
            "empresa": "INFOBRAS TELECOMUNICACOES LTDA",
            "assinaturas": 890,
            "assinaturas_anterior": 710,
            "variacao_pct": 25.4,
            "grande_operadora": False,
            "entrou_no_periodo": False,
            "saiu_no_periodo": False,
        },
    ],
    "panorama_brasil": {
        "total_isps_brasil": 14832,
        "media_anos_atividade": 6.4,
        "top_ufs": [
            {"uf": "SP", "total_isps": 3200, "porte_me": 1800, "porte_epp": 900, "porte_demais": 500},
            {"uf": "MG", "total_isps": 1800, "porte_me": 1000, "porte_epp": 500, "porte_demais": 300},
            {"uf": "PR", "total_isps": 1200, "porte_me": 700, "porte_epp": 350, "porte_demais": 150},
            {"uf": "RS", "total_isps": 1100, "porte_me": 600, "porte_epp": 350, "porte_demais": 150},
            {"uf": "MA", "total_isps": 420, "porte_me": 280, "porte_epp": 100, "porte_demais": 40},
        ],
    },
    "socios": [
        {"nome": "MARCOS JOSE SILVA COSTA", "qualificacao": "Sócio-Administrador"},
        {"nome": "ANA LUCIA FERREIRA", "qualificacao": "Sócia"},
    ],
}

MANUAL_ANALYSIS = """
1. **Você está crescendo onde importa.** Com 17,6% de crescimento em Paço do Lumiar no último período,
enquanto a Claro recua 8,8%, você está ganhando terreno na sua praça principal. Esse é o momento
de consolidar — não só atrair clientes novos, mas transformar a base atual em canal de aquisição.

2. **38% de share em Paço do Lumiar é uma posição defensável — se você souber usá-la.**
Uma base de ~4.800 assinantes satisfeitos é o maior ativo de marketing que você tem. O canal de
indicação bem estruturado captura exatamente esse ativo: clientes que já confiam na marca e têm
vizinhos com as mesmas necessidades.

3. **A NET VELOZ acabou de entrar na sua praça.** Novos entrantes normalmente chegam com preço
agressivo. O melhor antídoto não é guerra de preço — é fidelização. Um programa de indicação bem
desenhado cria âncoras relacionais que o concorrente novo não consegue comprar.
"""

print("Preparando contexto...")
ctx = prepare_report_context(MOCK, ticket_medio=89.90, janela_meses=12)

print("Renderizando HTML...")
html = render_report_html(ctx, MANUAL_ANALYSIS)

print("Exportando PDF...")
pdf_bytes = export_html_to_pdf(html)

out_path = "output/12130171_v2_final.pdf"
os.makedirs("output", exist_ok=True)
with open(out_path, "wb") as f:
    f.write(pdf_bytes)

print(f"PDF gerado: {out_path} ({len(pdf_bytes)//1024} KB)")
