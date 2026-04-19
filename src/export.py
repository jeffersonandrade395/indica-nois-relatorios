import logging

from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

from . import config as cfg

log = logging.getLogger(__name__)


def export_report_to_pdf(html_content: str, output_path: str | None = None) -> bytes:
    """Renders HTML to PDF. Optionally writes to output_path and always returns bytes."""
    font_config = FontConfiguration()
    doc = HTML(string=html_content, base_url=str(cfg.TEMPLATES_DIR))
    pdf = doc.write_pdf(font_config=font_config)
    if output_path:
        from pathlib import Path
        Path(output_path).write_bytes(pdf)
        log.info("PDF salvo em %s (%d KB)", output_path, len(pdf) // 1024)
    else:
        log.info("PDF v2 gerado em memória (%d KB)", len(pdf) // 1024)
    return pdf


def export_html_to_pdf(html_content: str) -> bytes:
    font_config = FontConfiguration()
    doc = HTML(string=html_content, base_url=str(cfg.TEMPLATES_DIR))
    pdf = doc.write_pdf(font_config=font_config)
    log.info("PDF gerado em memória (%d KB)", len(pdf) // 1024)
    return pdf
