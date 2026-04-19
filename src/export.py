import logging
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from . import config as cfg

log = logging.getLogger(__name__)


def _ensure_chromium() -> None:
    """Baixa o Chromium do Playwright se ainda não estiver no cache.

    No Streamlit Cloud o pip instala o pacote playwright mas não baixa o
    browser — esse passo precisa acontecer na primeira execução.
    --with-deps também instala dependências de sistema via apt.
    """
    cache = Path.home() / ".cache" / "ms-playwright"
    if not any(cache.glob("chromium-*")):
        log.info("Chromium não encontrado — baixando via playwright install...")
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
        log.info("Chromium instalado com sucesso.")


def export_report_to_pdf(html_content: str, output_path: str | None = None) -> bytes:
    """
    Converte HTML em PDF via Playwright (Chromium headless).

    Mantém assinatura idêntica à versão WeasyPrint para compatibilidade com app.py.

    Por que Playwright e não WeasyPrint:
    - WeasyPrint não suporta @font-face com subsets modernos de forma confiável
    - WeasyPrint renderiza gradientes e cores de fundo diferente do Chrome
    - Playwright usa o mesmo engine do Chrome — PDF visualmente idêntico ao mockup
    """
    _ensure_chromium()

    # Escreve o HTML em arquivo temporário DENTRO do diretório de templates.
    # Isso garante que URLs relativas no CSS (ex: ./fonts/Nunito-VF.ttf)
    # sejam resolvidas corretamente pelo Chromium via file://.
    templates_dir = cfg.TEMPLATES_DIR.resolve()
    tmp_html = templates_dir / "_export_tmp.html"

    try:
        tmp_html.write_text(html_content, encoding="utf-8")
        file_url = tmp_html.as_uri()

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # goto com file:// resolve recursos relativos (fontes, imagens)
            # networkidle garante que @font-face carregou antes de gerar o PDF
            page.goto(file_url, wait_until="networkidle", timeout=30000)

            # Aguarda todas as fontes CSS estarem prontas
            page.wait_for_function("document.fonts.ready")

            pdf_bytes = page.pdf(
                format="A4",
                margin={"top": "20mm", "right": "20mm", "bottom": "20mm", "left": "20mm"},
                print_background=True,   # obrigatório: cores de fundo, badges, gradientes
                prefer_css_page_size=True,
            )

            browser.close()

    finally:
        if tmp_html.exists():
            tmp_html.unlink()

    if output_path:
        Path(output_path).write_bytes(pdf_bytes)
        log.info("PDF salvo em %s (%d KB)", output_path, len(pdf_bytes) // 1024)
    else:
        log.info("PDF gerado em memória (%d KB)", len(pdf_bytes) // 1024)

    return pdf_bytes


def export_proposta_to_pdf(context: dict, output_path: str | None = None) -> bytes:
    """
    Renderiza contexto de Proposta Plus em HTML e converte para PDF via Playwright.
    Reutiliza o mesmo pipeline do relatório.
    """
    from .render import render_proposta_html
    html_content = render_proposta_html(context)
    return export_report_to_pdf(html_content, output_path)


def export_html_to_pdf(html_content: str) -> bytes:
    """Alias mantido para compatibilidade. Usar export_report_to_pdf."""
    return export_report_to_pdf(html_content)
