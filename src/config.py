from pathlib import Path
import yaml

BASE_DIR = Path(__file__).parent.parent

_DEFAULT = {
    "bigquery": {
        "project_id": "meu-n8n-458300",
        "dataset": "indica_nois_prospeccao",
        "credentials_path": str(BASE_DIR.parent / "meu-n8n-458300-a6e9c2e03f26.json"),
        "query_timeout_seconds": 30,
    },
    "output":  {"directory": str(BASE_DIR / "output")},
    "cache":   {"enabled": True, "ttl_hours": 24, "directory": str(BASE_DIR / "cache")},
    "report":  {"ltv_default_ticket": 80.0, "ltv_default_months": 24, "scenarios": [0.03, 0.05, 0.10]},
    "logging": {"level": "INFO", "file": str(BASE_DIR / "logs" / "execucao.log")},
}


def _load() -> dict:
    cfg_path = BASE_DIR / "config.yaml"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return _DEFAULT


CFG = _load()

BQ_PROJECT = CFG["bigquery"]["project_id"]
BQ_DATASET = CFG["bigquery"]["dataset"]
BQ_CREDS   = CFG["bigquery"]["credentials_path"]
BQ_TIMEOUT = CFG["bigquery"]["query_timeout_seconds"]

OUTPUT_DIR = Path(CFG["output"]["directory"])
CACHE_DIR  = Path(CFG["cache"]["directory"])
CACHE_TTL  = CFG["cache"]["ttl_hours"]
CACHE_ON   = CFG["cache"]["enabled"]

DEFAULT_TICKET = float(CFG["report"]["ltv_default_ticket"])
DEFAULT_MONTHS = int(CFG["report"]["ltv_default_months"])
SCENARIOS      = CFG["report"]["scenarios"]

LOG_LEVEL = CFG["logging"]["level"]
LOG_FILE  = Path(CFG["logging"]["file"])

TEMPLATES_DIR = BASE_DIR / "templates"
ASSETS_DIR    = BASE_DIR / "assets"
