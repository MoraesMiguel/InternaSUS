"""Utilitários genéricos de ingestão."""

import asyncio
from collections.abc import Awaitable, Callable
import time

from loguru import logger


def tentar_novamente[T](
    fn: Callable[[], T],
    tentativas: int = 3,
    espera_segundos: float = 2.0,
    excecoes: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Executa fn() até `tentativas` vezes, com espera fixa entre falhas.

    Relança a última exceção se todas as tentativas falharem.
    """
    ultimo_erro: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            return fn()
        except excecoes as erro:
            ultimo_erro = erro
            if tentativa < tentativas:
                logger.warning(
                    f"Tentativa {tentativa}/{tentativas} falhou: {erro}. "
                    f"Aguardando {espera_segundos}s antes de tentar de novo."
                )
                time.sleep(espera_segundos)
            else:
                logger.error(f"Todas as {tentativas} tentativas falharam: {erro}")
    raise ultimo_erro  # type: ignore[misc]


async def tentar_novamente_async[T](
    fn: Callable[[], Awaitable[T]],
    tentativas: int = 3,
    espera_segundos: float = 2.0,
    excecoes: tuple[type[Exception], ...] = (Exception,),
) -> T:
    """Variante assíncrona de `tentar_novamente`, para chamadas de rede via asyncio."""
    ultimo_erro: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            return await fn()
        except excecoes as erro:
            ultimo_erro = erro
            if tentativa < tentativas:
                logger.warning(
                    f"Tentativa {tentativa}/{tentativas} falhou: {erro}. "
                    f"Aguardando {espera_segundos}s antes de tentar de novo."
                )
                await asyncio.sleep(espera_segundos)
            else:
                logger.error(f"Todas as {tentativas} tentativas falharam: {erro}")
    raise ultimo_erro  # type: ignore[misc]
