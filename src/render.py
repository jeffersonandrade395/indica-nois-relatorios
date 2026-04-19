import base64
import logging

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt

from . import config as cfg

log = logging.getLogger(__name__)
_md = MarkdownIt()


def _logo_data_uri(filename: str) -> str:
    path = cfg.ASSETS_DIR / filename
    if not path.exists():
        log.warning("Logo não encontrado: %s", path)
        return ""
    data = base64.b64encode(path.read_bytes()).decode()
    return f"data:image/svg+xml;base64,{data}"


def _build_logos() -> dict:
    return {
        "full":    _logo_data_uri("logo_full.svg"),
        "compact": _logo_data_uri("logo_compact.svg"),
        "mark":    _logo_data_uri("logo_mark.svg"),
    }


def _env(logos: dict) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(cfg.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
    )
    env.globals["logos"] = logos
    return env


def render_report_html(context: dict, manual_analysis: str) -> str:
    logos = _build_logos()
    log.info("logos carregados: full=%d bytes, compact=%d bytes, mark=%d bytes",
             len(logos["full"]), len(logos["compact"]), len(logos["mark"]))

    env = _env(logos)
    template = env.get_template("relatorio.html.j2")

    render_ctx: dict = {}
    render_ctx.update(context)
    render_ctx["logos"] = logos
    render_ctx["manual_analysis_html"] = _md.render(manual_analysis)
    render_ctx["inline_css"] = (cfg.TEMPLATES_DIR / "styles.css").read_text(encoding="utf-8")

    log.info("render_ctx keys: %s", sorted(render_ctx.keys()))

    html = template.render(render_ctx)
    log.info("HTML renderizado (%d KB)", len(html) // 1024)
    return html
