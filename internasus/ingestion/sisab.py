"""
internasus.ingestion.sisab
Ingestão da cobertura de Atenção Primária (ESF/eAB) via API pública do
e-Gestor AB (relatorioaps-prd.saude.gov.br), por município de SP.

Essa API não é documentada oficialmente e não faz parte do PySUS — foi
descoberta inspecionando as chamadas de rede do relatório público em
https://relatorioaps.saude.gov.br/cobertura/aps (sem necessidade de login).

Estratégia:
- A API só aceita no máximo 1 ano por chamada (nuCompInicio/nuCompFim).
- Faz uma chamada por (município, ano), salvando cada resposta como um
  parquet individual em data/raw/fonte=SISAB/uf=SP/ano=YYYY/dataset=COBERTURA_AB/.
- Pula arquivos já baixados, então o script pode ser interrompido e
  retomado sem perder progresso (útil pra listas grandes/conexão instável).
- Usa pausa entre requisições para não sobrecarregar o servidor público.
"""

import time
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

PROJ_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_RAW = PROJ_ROOT / "data" / "raw"
DATA_SILVER = PROJ_ROOT / "data" / "silver"

BASE_URL = "https://relatorioaps-prd.saude.gov.br/cobertura/aps"
CO_REGIAO_SUDESTE = "3"
CO_UF_SP = "35"

# Pausa entre requisições (segundos) — educado com o servidor público.
PAUSA_ENTRE_REQUISICOES = 0.4

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://relatorioaps.saude.gov.br/cobertura/aps",
}


def _listar_municipios_sp() -> pd.DataFrame:
    """
    Lê os códigos de município de SP a partir da camada silver do IBGE
    (já ingerida via SIDRA). Espera colunas com código (6 dígitos) e nome.
    Ajuste os nomes de coluna abaixo se forem diferentes no seu ibge_pop.parquet.
    """
    caminho = DATA_SILVER / "ibge" / "ibge_pop.parquet"
    if not caminho.exists():
        raise FileNotFoundError(
            f"Não encontrei {caminho}. Rode a ingestão/silver do IBGE antes de rodar o SISAB."
        )

    df = pd.read_parquet(caminho)
    # Tenta achar as colunas de código e nome do município de forma flexível.
    col_codigo = next((c for c in df.columns if "cod" in c.lower() and "mun" in c.lower()), None)
    col_nome = next((c for c in df.columns if "nome" in c.lower() and "mun" in c.lower()), None)

    if col_codigo is None:
        raise ValueError(
            f"Não achei uma coluna de código de município em {caminho}. "
            f"Colunas disponíveis: {list(df.columns)}"
        )

    municipios = df[[col_codigo] + ([col_nome] if col_nome else [])].drop_duplicates()
    municipios.columns = ["co_municipio"] + (["nome_municipio"] if col_nome else [])
    municipios["co_municipio"] = municipios["co_municipio"].astype(str).str.zfill(6)
    return municipios.reset_index(drop=True)


def baixar_cobertura_municipio(co_municipio: str, ano: int, session: requests.Session) -> list[dict]:
    """Baixa a cobertura de um município para um ano específico (jan-dez)."""
    params = {
        "unidadeGeografica": "MUNICIPIO",
        "coRegiao": CO_REGIAO_SUDESTE,
        "coUf": CO_UF_SP,
        "coMunicipio": co_municipio,
        "nuCompInicio": f"{ano}01",
        "nuCompFim": f"{ano}12",
    }
    resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def ingerir_sisab(anos: list[int], uf: str = "SP") -> None:
    """
    Baixa a cobertura de Atenção Primária de todos os municípios de SP,
    para os anos informados, salvando um parquet por (município, ano) em
    data/raw/fonte=SISAB/uf=SP/ano=<ano>/dataset=COBERTURA_AB/<co_municipio>.parquet
    """
    municipios = _listar_municipios_sp()
    logger.info(f"{len(municipios)} municípios de SP encontrados. Anos: {anos}")

    session = requests.Session()
    total = len(municipios) * len(anos)
    feito = 0
    erros = []

    for ano in anos:
        destino_ano = DATA_RAW / "fonte=SISAB" / f"uf={uf}" / f"ano={ano}" / "dataset=COBERTURA_AB"
        destino_ano.mkdir(parents=True, exist_ok=True)

        # Teste rápido: se o primeiro município do ano vier vazio, o ano
        # inteiro provavelmente não tem dado na API (fora do intervalo
        # disponível) — pula o ano todo em vez de gastar tempo testando
        # os outros 644 municípios.
        primeiro_co = municipios.iloc[0]["co_municipio"]
        try:
            teste = baixar_cobertura_municipio(primeiro_co, ano, session)
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro testando o ano {ano}: {e}. Pulando o ano inteiro.")
            continue

        if not teste:
            logger.warning(
                f"Ano {ano} parece não ter dado disponível na API (teste com {primeiro_co} veio vazio). "
                f"Pulando o ano inteiro — confira o intervalo disponível no site do e-Gestor AB."
            )
            feito += len(municipios)
            continue

        # Já baixado no teste acima — grava e segue pros demais municípios.
        destino_arquivo = destino_ano / f"{primeiro_co}.parquet"
        if not destino_arquivo.exists():
            pd.DataFrame(teste).to_parquet(destino_arquivo, index=False)
        feito += 1
        time.sleep(PAUSA_ENTRE_REQUISICOES)

        for _, row in municipios.iloc[1:].iterrows():
            co_municipio = row["co_municipio"]
            destino_arquivo = destino_ano / f"{co_municipio}.parquet"
            feito += 1

            if destino_arquivo.exists():
                continue  # já baixado — permite retomar depois de interrupção

            try:
                dados = baixar_cobertura_municipio(co_municipio, ano, session)
                if dados:
                    pd.DataFrame(dados).to_parquet(destino_arquivo, index=False)
                    logger.success(f"[{feito}/{total}] {co_municipio} ({ano}) -> {destino_arquivo.name}")
                else:
                    logger.warning(f"[{feito}/{total}] {co_municipio} ({ano}): resposta vazia, pulando.")
            except requests.exceptions.RequestException as e:
                logger.error(f"[{feito}/{total}] Erro em {co_municipio} ({ano}): {e}")
                erros.append((co_municipio, ano, str(e)))

            time.sleep(PAUSA_ENTRE_REQUISICOES)

    if erros:
        logger.warning(f"{len(erros)} falha(s). Rode ingerir_sisab() de novo para tentar as que faltaram.")
    else:
        logger.success("Ingestão do SISAB concluída sem erros.")


if __name__ == "__main__":
    # A API do e-Gestor AB só tem dados a partir de 2021 (confirmado no site).
    ingerir_sisab(anos=[2021, 2022, 2023, 2024, 2025])