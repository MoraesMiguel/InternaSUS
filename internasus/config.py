import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# Load environment variables from .env file if it exists
load_dotenv()

# Paths
PROJ_ROOT = Path(__file__).resolve().parents[1]
logger.info(f"PROJ_ROOT path is: {PROJ_ROOT}")

# Cache do pysus dentro do projeto (não em ~/pysus) — reprodutibilidade entre máquinas.
# Precisa ser definido via variável de ambiente ANTES de "import pysus": os submódulos
# internos da lib fazem `from pysus import CACHEPATH` na hora do import, então chamar
# `pysus.set_cache(...)` depois de importar não tem efeito nos caminhos já resolvidos.
os.environ.setdefault("PYSUS_CACHEPATH", str(PROJ_ROOT / ".pysus_cache"))

DATA_DIR = PROJ_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
INTERIM_DATA_DIR = DATA_DIR / "interim"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
EXTERNAL_DATA_DIR = DATA_DIR / "external"

MODELS_DIR = PROJ_ROOT / "models"

REPORTS_DIR = PROJ_ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

# --- Parâmetros de Ingestão (README §5.1) ---

UF_ALVO: str = "SP"
ANO_INICIO: int = 2020
ANO_FIM: int = 2026  # inclusive; meses/anos futuros sem publicação são pulados, não é erro

CNES_GRUPOS: list[str] = ["PF", "EQ", "LT", "SR", "ST"]
SIA_GRUPOS: list[str] = ["PA"]
SIH_GRUPOS: list[str] = ["RD"]

SIDRA_TABELAS: list[dict] = [
    {"tabela": 6579, "variaveis": [9324], "nome_dataset": "populacao_estimada"},
]

RETRY_TENTATIVAS: int = 3
RETRY_ESPERA_SEGUNDOS: float = 2.0

# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass
