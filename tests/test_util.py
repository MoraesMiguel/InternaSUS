import asyncio

import pytest

from internasus.ingestion.util import tentar_novamente, tentar_novamente_async


def test_tentar_novamente_sucede_apos_falhas(mocker):
    fn = mocker.Mock(side_effect=[ConnectionError("falhou"), ConnectionError("falhou"), "ok"])

    resultado = tentar_novamente(fn, tentativas=3, espera_segundos=0)

    assert resultado == "ok"
    assert fn.call_count == 3


def test_tentar_novamente_esgota_tentativas_e_relanca(mocker):
    fn = mocker.Mock(side_effect=ConnectionError("sempre falha"))

    with pytest.raises(ConnectionError):
        tentar_novamente(fn, tentativas=3, espera_segundos=0)

    assert fn.call_count == 3


def test_tentar_novamente_async_sucede_apos_falhas():
    chamadas = {"n": 0}

    async def fn():
        chamadas["n"] += 1
        if chamadas["n"] < 3:
            raise ConnectionError("falhou")
        return "ok"

    resultado = asyncio.run(tentar_novamente_async(fn, tentativas=3, espera_segundos=0))

    assert resultado == "ok"
    assert chamadas["n"] == 3
