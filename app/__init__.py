"""Notivoz."""

# Arreglo para Python 3.15.1: concurrent.futures carga ThreadPoolExecutor de forma
# diferida ("lazy from .thread import ..."). Si alguna librería importa antes
# concurrent.futures.thread directamente, el nombre queda como un objeto
# 'lazy_import' sin resolver y asyncio falla con "'lazy_import' object is not
# callable" (lo usa aiohttp → edge-tts, la voz natural). Se fija la clase real.
import concurrent.futures
import concurrent.futures.thread

concurrent.futures.ThreadPoolExecutor = concurrent.futures.thread.ThreadPoolExecutor
