"""Extração da tabela oficial CID-10 (capítulos/grupos/categorias/
subcategorias) para data/external/cid10/.

Diferente de CNES/SIA/SIH/SIDRA, não é um dataset particionado por
UF/ano/competência — é uma referência estática usada por
`internasus.processing.gold` (dim_diagnostico) para traduzir os códigos de
`SIH.DIAG_PRINC`.
"""

import io
from pathlib import Path

from loguru import logger
import pandas as pd
import requests

from internasus.ingestion.util import tentar_novamente

# Espelho no GitHub das 4 tabelas oficiais CID-10 do DATASUS (mesmos arquivos
# publicados em www2.datasus.gov.br/cid10/V2008/downloads/CID10CSV.zip).
# Usado como fonte porque o servidor legado do DATASUS é lento/instável
# (testado: ~15s de latência por request em HTTP, HTTPS indisponível) —
# raw.githubusercontent.com é rápido e confiável para quem for rodar isso.
CID10_BASE_URL = "https://raw.githubusercontent.com/SidneyBissoli/cid10-br-mcp/master/data"

ARQUIVOS = {
    "capitulos": "CID-10-CAPITULOS.CSV",
    "grupos": "CID-10-GRUPOS.CSV",
    "categorias": "CID-10-CATEGORIAS.CSV",
    "subcategorias": "CID-10-SUBCATEGORIAS.CSV",
}


def baixar_cid10(
    base_dir: Path,
    session: requests.Session | None = None,
    tentativas: int = 3,
    espera_segundos: float = 2.0,
    forcar: bool = False,
) -> dict:
    """Baixa as 4 tabelas CID-10 (originais em latin-1, separadas por ';') e
    grava em `<base_dir>/cid10/<nome>.csv` já convertidas para UTF-8.

    Pula cada arquivo que já existir em disco, a menos que `forcar=True`
    (a tabela é estática — não muda entre execuções, ao contrário das
    competências mensais de CNES/SIA/SIH).
    """
    sess = session or requests.Session()
    destino_dir = base_dir / "cid10"
    resultado = {"baixados": 0, "pulados": 0, "falhas": []}

    for nome, arquivo_remoto in ARQUIVOS.items():
        destino = destino_dir / f"{nome}.csv"
        if destino.exists() and not forcar:
            logger.info(f"Pulando (já existe): {destino}")
            resultado["pulados"] += 1
            continue

        url = f"{CID10_BASE_URL}/{arquivo_remoto}"

        def _baixar(url: str = url) -> bytes:
            resposta = sess.get(url, timeout=30)
            resposta.raise_for_status()
            return resposta.content

        try:
            conteudo = tentar_novamente(
                _baixar,
                tentativas=tentativas,
                espera_segundos=espera_segundos,
                excecoes=(requests.exceptions.RequestException,),
            )
            df = pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin-1")
            # o CSV original termina cada linha com ';', o que o pandas lê
            # como uma coluna extra sem nome e totalmente vazia — descarta.
            df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]

            destino_dir.mkdir(parents=True, exist_ok=True)
            df.to_csv(destino, index=False, encoding="utf-8")
            resultado["baixados"] += 1
            logger.success(f"Gravado: {destino} ({len(df)} linhas)")
        except Exception as erro:  # noqa: BLE001 — isola a falha deste arquivo, sem abortar os demais
            logger.error(f"Falha ao baixar CID-10 '{nome}': {erro}")
            resultado["falhas"].append({"arquivo": nome, "erro": str(erro)})

    return resultado

if __name__ == "__main__":
    from internasus.config import PROJ_ROOT

    # Executa o download salvando em data/external/
    resultado = baixar_cid10(base_dir=PROJ_ROOT / "data" / "external")
    print(resultado)