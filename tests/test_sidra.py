from pathlib import Path

import pytest
import requests
from requests_mock import ANY as URL_ANY

from internasus.ingestion.sidra import baixar_sidra, buscar_populacao, montar_url

CABECALHO = {
    "NC": "Nível Territorial (Código)",
    "NN": "Nível Territorial",
    "MC": "Unidade de Medida (Código)",
    "MN": "Unidade de Medida",
    "V": "Valor",
    "D1C": "Município (Código)",
    "D1N": "Município",
    "D2C": "Variável (Código)",
    "D2N": "Variável",
    "D3C": "Ano (Código)",
    "D3N": "Ano",
}


def _linha(municipio_codigo: str, municipio_nome: str, ano: str, valor: str) -> dict:
    return {
        "NC": "6",
        "NN": "Município",
        "MC": "45",
        "MN": "Pessoas",
        "V": valor,
        "D1C": municipio_codigo,
        "D1N": municipio_nome,
        "D2C": "9324",
        "D2N": "População residente estimada",
        "D3C": ano,
        "D3N": ano,
    }


PAYLOAD_EXEMPLO = [
    CABECALHO,
    _linha("3500105", "Adamantina - SP", "2020", "35111"),
    _linha("3500204", "Adolfo - SP", "2021", "3554"),
]


def test_montar_url_inclui_filtro_estado_sp_e_todos_os_anos():
    url = montar_url(tabela=6579, variaveis=[9324], periodos=[2020, 2021, 2022])

    assert "/t/6579" in url
    assert "n3%2035" in url  # "in n3 35" codificado
    assert "/v/9324" in url
    assert "/p/2020,2021,2022" in url


def test_buscar_populacao_faz_uma_unica_chamada_http(requests_mock):
    mock = requests_mock.get(URL_ANY, json=PAYLOAD_EXEMPLO)

    buscar_populacao(tabela=6579, variaveis=[9324], ano_inicio=2020, ano_fim=2021)

    assert mock.call_count == 1


def test_buscar_populacao_parseia_json_para_dataframe_correto(requests_mock):
    requests_mock.get(URL_ANY, json=PAYLOAD_EXEMPLO)

    df = buscar_populacao(tabela=6579, variaveis=[9324], ano_inicio=2020, ano_fim=2021)

    assert list(df.columns) == ["municipio_codigo", "municipio_nome", "ano", "valor"]
    assert len(df) == 2
    assert set(df["ano"]) == {2020, 2021}
    assert df.loc[df["ano"] == 2020, "valor"].iloc[0] == 35111


def test_buscar_populacao_retry_em_erro_5xx_transitorio(requests_mock):
    requests_mock.get(
        URL_ANY,
        [
            {"status_code": 503},
            {"json": PAYLOAD_EXEMPLO, "status_code": 200},
        ],
    )

    df = buscar_populacao(
        tabela=6579,
        variaveis=[9324],
        ano_inicio=2020,
        ano_fim=2021,
        tentativas=3,
        espera_segundos=0,
    )

    assert len(df) == 2


def test_buscar_populacao_esgota_tentativas_em_falha_persistente(requests_mock):
    requests_mock.get(URL_ANY, status_code=503)

    with pytest.raises(requests.exceptions.RequestException):
        buscar_populacao(
            tabela=6579,
            variaveis=[9324],
            ano_inicio=2020,
            ano_fim=2021,
            tentativas=2,
            espera_segundos=0,
        )


def test_baixar_sidra_particiona_por_ano_a_partir_de_uma_unica_resposta(
    requests_mock, base_dir: Path
):
    requests_mock.get(URL_ANY, json=PAYLOAD_EXEMPLO)
    tabelas_config = [{"tabela": 6579, "variaveis": [9324], "nome_dataset": "populacao"}]

    resultado = baixar_sidra(tabelas_config, ano_inicio=2020, ano_fim=2021, base_dir=base_dir)

    assert resultado["baixados"] == 2
    assert (base_dir / "fonte=IBGE_SIDRA" / "uf=SP" / "ano=2020" / "dataset=6579" / "dados.parquet").exists()
    assert (base_dir / "fonte=IBGE_SIDRA" / "uf=SP" / "ano=2021" / "dataset=6579" / "dados.parquet").exists()


def test_baixar_sidra_pula_particao_ja_existente(requests_mock, base_dir: Path):
    requests_mock.get(URL_ANY, json=PAYLOAD_EXEMPLO)
    tabelas_config = [{"tabela": 6579, "variaveis": [9324], "nome_dataset": "populacao"}]

    baixar_sidra(tabelas_config, ano_inicio=2020, ano_fim=2021, base_dir=base_dir)
    resultado = baixar_sidra(tabelas_config, ano_inicio=2020, ano_fim=2021, base_dir=base_dir)

    assert resultado["baixados"] == 0
    assert resultado["pulados"] == 2
