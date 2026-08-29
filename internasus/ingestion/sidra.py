"""Extração de dados populacionais do IBGE via API SIDRA (HTTP puro)."""

from pathlib import Path
from urllib.parse import quote

from loguru import logger
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests

from internasus.ingestion.paths import ja_existe, pasta_sidra
from internasus.ingestion.util import tentar_novamente
from internasus.ingestion.validacao import validar_parquet

SIDRA_BASE_URL = "https://apisidra.ibge.gov.br/values"


def montar_url(
    tabela: int,
    variaveis: list[int],
    periodos: list[int],
    filtro_territorial: str = "n3 35",
) -> str:
    """Monta a URL da API SIDRA restrita aos municípios de SP (n6/in n3 35).

    Uma única URL cobre todos os municípios e todos os anos pedidos.
    """
    variaveis_str = ",".join(str(v) for v in variaveis)
    periodos_str = ",".join(str(p) for p in periodos)
    filtro_codificado = quote(f"in {filtro_territorial}")
    return f"{SIDRA_BASE_URL}/t/{tabela}/n6/{filtro_codificado}/v/{variaveis_str}/p/{periodos_str}"


def _mapear_colunas(cabecalho: dict) -> dict[str, str]:
    """Identifica dinamicamente quais chaves D<n>C/D<n>N correspondem a
    Município e Ano, já que a ordem das dimensões no SIDRA pode variar.
    """
    mapa: dict[str, str] = {}
    for chave, valor in cabecalho.items():
        if not chave.endswith("N") or not chave.startswith("D"):
            continue
        base = chave[:-1]
        if valor == "Município":
            mapa["municipio_codigo"] = f"{base}C"
            mapa["municipio_nome"] = chave
        elif valor == "Ano":
            mapa["ano_codigo"] = f"{base}C"
    if "municipio_codigo" not in mapa or "ano_codigo" not in mapa:
        raise ValueError(f"Não foi possível identificar colunas de Município/Ano: {cabecalho}")
    return mapa


def _parsear_resposta(dados: list[dict]) -> pd.DataFrame:
    """Converte a resposta JSON da API SIDRA (cabeçalho + linhas) num DataFrame."""
    if not dados:
        return pd.DataFrame(columns=["municipio_codigo", "municipio_nome", "ano", "valor"])

    cabecalho, linhas = dados[0], dados[1:]
    mapa = _mapear_colunas(cabecalho)

    registros = [
        {
            "municipio_codigo": linha[mapa["municipio_codigo"]],
            "municipio_nome": linha[mapa["municipio_nome"]],
            "ano": int(linha[mapa["ano_codigo"]]),
            "valor": linha["V"],
        }
        for linha in linhas
    ]
    df = pd.DataFrame(registros)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    return df


def buscar_populacao(
    tabela: int,
    variaveis: list[int],
    ano_inicio: int,
    ano_fim: int,
    session: requests.Session | None = None,
    tentativas: int = 3,
    espera_segundos: float = 2.0,
) -> pd.DataFrame:
    """Busca dados de uma tabela SIDRA para todos os municípios de SP,
    numa única requisição HTTP cobrindo o intervalo de anos inteiro.

    A API do SIDRA não retorna erro para anos sem publicação: eles
    simplesmente não aparecem na resposta. Nesse caso, um aviso é
    logado, mas não é tratado como falha.
    """
    sess = session or requests.Session()
    periodos = list(range(ano_inicio, ano_fim + 1))
    url = montar_url(tabela, variaveis, periodos)

    def _requisitar() -> list[dict]:
        resposta = sess.get(url, timeout=30)
        resposta.raise_for_status()
        return resposta.json()

    dados = tentar_novamente(
        _requisitar,
        tentativas=tentativas,
        espera_segundos=espera_segundos,
        excecoes=(requests.exceptions.RequestException,),
    )
    df = _parsear_resposta(dados)

    anos_presentes = set(df["ano"].unique()) if not df.empty else set()
    anos_ausentes = sorted(set(periodos) - anos_presentes)
    if anos_ausentes:
        logger.warning(
            f"Tabela SIDRA {tabela}: anos sem publicação (ignorados, não é erro): {anos_ausentes}"
        )

    return df


def baixar_sidra(
    tabelas_config: list[dict],
    ano_inicio: int,
    ano_fim: int,
    base_dir: Path,
    tentativas: int = 3,
    espera_segundos: float = 2.0,
) -> dict:
    """Extrai cada tabela SIDRA configurada e grava uma partição Parquet por ano."""
    resultado = {"baixados": 0, "pulados": 0, "falhas": []}
    session = requests.Session()

    for cfg in tabelas_config:
        tabela = cfg["tabela"]
        try:
            df = buscar_populacao(
                tabela=tabela,
                variaveis=cfg["variaveis"],
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                session=session,
                tentativas=tentativas,
                espera_segundos=espera_segundos,
            )
        except Exception as erro:  # noqa: BLE001 — isola a falha desta tabela, sem abortar as demais
            logger.error(f"Falha ao buscar tabela SIDRA {tabela}: {erro}")
            resultado["falhas"].append({"tabela": tabela, "erro": str(erro)})
            continue

        for ano, df_ano in df.groupby("ano"):
            pasta = pasta_sidra(base_dir, int(ano), tabela)
            destino = pasta / "dados.parquet"
            if ja_existe(destino):
                logger.info(f"Pulando (já existe): {destino}")
                resultado["pulados"] += 1
                continue

            try:
                pasta.mkdir(parents=True, exist_ok=True)
                pq.write_table(pa.Table.from_pandas(df_ano, preserve_index=False), destino)
                validar_parquet(destino)
                resultado["baixados"] += 1
                logger.success(f"Gravado: {destino} ({len(df_ano)} linhas)")
            except Exception as erro:  # noqa: BLE001 — isola a falha desta partição, sem abortar as demais
                logger.error(f"Falha ao gravar partição SIDRA {destino}: {erro}")
                destino.unlink(missing_ok=True)
                resultado["falhas"].append({"tabela": tabela, "ano": int(ano), "erro": str(erro)})

    return resultado
