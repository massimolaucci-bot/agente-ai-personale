"""Punto di avvio alternativo dell'app, usato al posto di "streamlit run".

Perche' serve: Chrome/Android installa una PWA "sul serio" (icona + finestra
a se stante, non solo un segnalibro) solo se il service worker registrato ha
uno "scope" che copre l'indirizzo principale del sito ("/"). Il file statico
servito da Streamlit vive pero' sempre sotto "/app/static/", e quella cartella
non puo' controllare "/" (limite del browser, non di questa app). Streamlit
1.60+ permette di avviare l'app come applicazione ASGI (st.App) aggiungendo
rotte extra: la usiamo qui per servire "/sw.js" dalla radice del sito, cosi'
il suo scope di default copre gia' tutto senza bisogno di header speciali.

Su Render, il comando di avvio del servizio va cambiato da
    streamlit run app.py --server.port $PORT --server.address 0.0.0.0
a
    python serve.py
Tutto il resto (variabili d'ambiente, build, ecc.) resta invariato.
"""
import os

import streamlit as st
from starlette.responses import Response
from starlette.routing import Route

SW_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "sw.js")

with open(SW_JS_PATH, "r", encoding="utf-8") as _f:
    _SW_JS_CONTENT = _f.read()


async def _service_worker_endpoint(request):
    return Response(content=_SW_JS_CONTENT, media_type="application/javascript")


app = st.App(
    "app.py",
    routes=[Route("/sw.js", _service_worker_endpoint, methods=["GET"])],
)

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8501"))
    app.run(config={"server.port": porta, "server.address": "0.0.0.0", "server.headless": True})
