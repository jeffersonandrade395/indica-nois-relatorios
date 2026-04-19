import base64
import logging

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

from . import config as cfg

log = logging.getLogger(__name__)
_md = MarkdownIt()


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(cfg.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    return env


def _logo_data_uri(filename: str) -> str:
    path = cfg.ASSETS_DIR / filename
    if not path.exists():
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/svg+xml;base64,{data}"


def render_report_html(context: dict, manual_analysis: str) -> str:
    env = _env()
    template = env.get_template("relatorio.html.j2")
    context["manual_analysis_html"] = _md.render(manual_analysis)
    css = (cfg.TEMPLATES_DIR / "styles.css").read_text(encoding="utf-8")
    context["inline_css"] = css
    context["logos"] = {
        "full":    _logo_data_uri("logo_full.svg"),
        "compact": _logo_data_uri("logo_compact.svg"),
        "mark":    _logo_data_uri("logo_mark.svg"),
    }
    html = template.render(**context)
    log.info("HTML renderizado (%d KB)", len(html) // 1024)
    return html
