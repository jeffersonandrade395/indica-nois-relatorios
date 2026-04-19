import logging

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from . import config as cfg

log = logging.getLogger(__name__)


def export_html_to_pdf(html_content: str) -> bytes:
    font_config = FontConfiguration()
    doc = HTML(string=html_content, base_url=str(cfg.TEMPLATES_DIR))
    pdf = doc.write_pdf(font_config=font_config)
    log.info("PDF gerado em memória (%d KB)", len(pdf) // 1024)
    return pdf
