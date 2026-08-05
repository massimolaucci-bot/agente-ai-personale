"""Punto di avvio alternativo dell'app, usato al posto di "streamlit run".

Perche' serve: Chrome/Android installa una PWA "sul serio" (icona + finestra
a se stante, non solo un segnalibro) solo se il service worker registrato ha
uno "scope" che copre l'indirizzo principale del sito ("/"). Il file statico
servito da Streamlit vive pero' sempre sotto "/app/static/", e quella cartella
non puo' controllare "/" (limite del browser, non di questa app). Streamlit
1.60+ permette di avviare l'app come applicazione ASGI (st.App) aggiungendo
rotte extra: la usiamo qui per servire "/sw.js" dalla radice del sito, cosi'
il suo scope di default copre gia' tutto senza bisogno di header speciali.

Da questo round, le stesse rotte extra servono anche per il flusso OAuth di
Google (Calendar + Gmail): "/oauth/google/start" e "/oauth/google/callback".
Le rotte "semplici" di Starlette non hanno accesso a st.session_state (che
esiste solo dentro una sessione Streamlit vera e propria), quindi tutto il
contesto necessario (tipo di collegamento, utente, ruolo) viaggia dentro un
parametro "state" firmato con HMAC, invece di essere letto dalla sessione.

Su Render, il comando di avvio del servizio va cambiato da
    streamlit run app.py --server.port $PORT --server.address 0.0.0.0
a
    python serve.py
Tutto il resto (variabili d'ambiente, build, ecc.) resta invariato.
"""
import os
import json
import time
import hmac
import hashlib
import base64

import requests
import streamlit as st
from starlette.responses import Response, RedirectResponse, HTMLResponse, PlainTextResponse
from starlette.routing import Route
from cryptography.fernet import Fernet
from google_auth_oauthlib.flow import Flow

SW_JS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "sw.js")

with open(SW_JS_PATH, "r", encoding="utf-8") as _f:
    _SW_JS_CONTENT = _f.read()


async def _service_worker_endpoint(request):
    return Response(content=_SW_JS_CONTENT, media_type="application/javascript")


# --- Google OAuth (Calendar + Gmail) ----------------------------------------
APP_BASE_URL = (os.environ.get("APP_BASE_URL") or "https://agente-ai-vocale.onrender.com").rstrip("/")
SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_TIMEOUT = 8

SUPABASE_HEADERS = None
if SUPABASE_URL and SUPABASE_KEY:
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }

OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET")
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = f"{APP_BASE_URL}/oauth/google/callback"
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]
OAUTH_STATE_TTL_SECONDI = 600  # 10 minuti: tempo massimo per completare il consenso su Google

_fernet = None
if TOKEN_ENCRYPTION_KEY:
    try:
        _chiave = TOKEN_ENCRYPTION_KEY.encode("utf-8") if isinstance(TOKEN_ENCRYPTION_KEY, str) else TOKEN_ENCRYPTION_KEY
        _fernet = Fernet(_chiave)
    except Exception:
        _fernet = None


def _oauth_pronto():
    return bool(OAUTH_STATE_SECRET and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and _fernet and SUPABASE_HEADERS)


def _sign_oauth_state(payload_dict):
    # Stato auto-contenuto e firmato (HMAC, libreria standard, niente JWT):
    # porta tipo di connessione/utente/ruolo attraverso il giro di
    # reindirizzamento su Google e ritorno. Firmato con compare_digest per
    # essere resistente ai timing attack; scade da solo dopo pochi minuti.
    payload_dict = dict(payload_dict)
    payload_dict["exp"] = int(time.time()) + OAUTH_STATE_TTL_SECONDI
    raw = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
    raw_b64 = base64.urlsafe_b64encode(raw).decode("ascii")
    sig = hmac.new(OAUTH_STATE_SECRET.encode("utf-8"), raw_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{raw_b64}.{sig}"


def _verify_oauth_state(token):
    try:
        raw_b64, sig = token.split(".", 1)
        expected_sig = hmac.new(OAUTH_STATE_SECRET.encode("utf-8"), raw_b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw_b64.encode("ascii")).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def _encrypt_token(value):
    if not value or not _fernet:
        return None
    return _fernet.encrypt(value.encode("utf-8")).decode("ascii")


def _fetch_google_tokens(conn_type, user_id=None):
    if not SUPABASE_HEADERS:
        return None
    try:
        if conn_type == "shared":
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/google_shared_connection",
                headers=SUPABASE_HEADERS,
                params={"select": "id,access_token_enc,refresh_token_enc,expires_at,scope,updated_at", "limit": 1},
                timeout=SUPABASE_TIMEOUT,
            )
        else:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/google_personal_connections",
                headers=SUPABASE_HEADERS,
                params={
                    "select": "id,user_id,access_token_enc,refresh_token_enc,expires_at,scope,updated_at",
                    "user_id": f"eq.{user_id}",
                },
                timeout=SUPABASE_TIMEOUT,
            )
        r.raise_for_status()
        rows = r.json()
        return rows[0] if rows else None
    except Exception:
        return None


def _save_google_tokens(conn_type, user_id, access_token, refresh_token, expires_at_iso, scope):
    # Stesso schema "fetch poi patch/post" usato in app.py: la colonna id e'
    # "generated always as identity", quindi non si puo' forzare un id fisso
    # per la riga singola dell'account condiviso.
    if not SUPABASE_HEADERS:
        return False
    try:
        payload = {
            "access_token_enc": _encrypt_token(access_token),
            "expires_at": expires_at_iso,
            "scope": scope,
        }
        if refresh_token:
            payload["refresh_token_enc"] = _encrypt_token(refresh_token)
        existing = _fetch_google_tokens(conn_type, user_id)
        headers = dict(SUPABASE_HEADERS)
        headers["Prefer"] = "return=representation"
        if conn_type == "shared":
            table = "google_shared_connection"
        else:
            table = "google_personal_connections"
            payload["user_id"] = user_id
        if existing:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                params={"id": f"eq.{existing['id']}"},
                json=payload,
                timeout=SUPABASE_TIMEOUT,
            )
        else:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=headers,
                json=payload,
                timeout=SUPABASE_TIMEOUT,
            )
        r.raise_for_status()
        return True
    except Exception:
        return False


def _google_flow():
    client_config = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [GOOGLE_REDIRECT_URI],
        }
    }
    # PKCE disattivato di proposito: la libreria lo genererebbe di default,
    # ma il "code_verifier" vivrebbe solo sull'istanza Flow che lo crea (qui
    # dentro oauth_start) e andrebbe perso, perche' oauth_callback e' una
    # richiesta HTTP separata che crea una Flow NUOVA (nessuno session_state
    # condiviso tra le due route, per lo stesso motivo per cui usiamo lo
    # "state" firmato). Il sintomo reale osservato in produzione era
    # "(invalid_grant) Missing code verifier" al momento dello scambio del
    # codice: la richiesta di autorizzazione includeva un code_challenge (PKCE
    # auto-generato) ma quello di verifica non arrivava mai al token exchange.
    # Questo client e' comunque "confidential" (usa GOOGLE_CLIENT_SECRET per
    # autenticarsi), quindi PKCE non e' necessario per la sicurezza qui.
    return Flow.from_client_config(
        client_config,
        scopes=GOOGLE_OAUTH_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI,
        autogenerate_code_verifier=False,
    )


async def oauth_start(request):
    if not _oauth_pronto():
        return PlainTextResponse("Integrazione Google non configurata sul server.", status_code=500)
    conn_type = request.query_params.get("type", "personal")
    user_id = request.query_params.get("user_id", "")
    role = request.query_params.get("role", "")
    state = _sign_oauth_state({"type": conn_type, "user_id": user_id, "role": role})
    flow = _google_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return RedirectResponse(auth_url)


async def oauth_callback(request):
    error = request.query_params.get("error", "")
    if error:
        return HTMLResponse(
            f"<html><body style='font-family: sans-serif; text-align:center; padding-top: 60px;'>"
            f"<p>Accesso Google annullato o negato: {error}</p>"
            f"<a href='{APP_BASE_URL}'>Torna all'app</a></body></html>"
        )

    state_token = request.query_params.get("state", "")
    payload = _verify_oauth_state(state_token)
    if not payload:
        return PlainTextResponse("Stato non valido o scaduto. Riprova dal collegamento nell'app.", status_code=400)

    code = request.query_params.get("code", "")
    if not code:
        return PlainTextResponse("Codice di autorizzazione mancante.", status_code=400)

    try:
        flow = _google_flow()
        flow.fetch_token(code=code)
        creds = flow.credentials
        # google-auth imposta gia' .expiry come datetime "naive" (UTC): il
        # .replace(tzinfo=None) e' qui solo una rete di sicurezza, e' un
        # no-op se e' gia' naive.
        expires_at_iso = None
        if creds.expiry:
            expires_at_iso = creds.expiry.replace(tzinfo=None).isoformat() + "Z"
        conn_type = payload.get("type", "personal")
        user_id = payload.get("user_id") or None
        ok = _save_google_tokens(
            conn_type,
            user_id,
            creds.token,
            creds.refresh_token,
            expires_at_iso,
            " ".join(creds.scopes) if creds.scopes else "",
        )
        if not ok:
            return PlainTextResponse("Connessione riuscita con Google ma il salvataggio e' fallito. Riprova.", status_code=500)
    except Exception as e:
        return PlainTextResponse(f"Errore durante il collegamento con Google: {e}", status_code=500)

    return HTMLResponse(f"""
    <html><body style="font-family: sans-serif; text-align:center; padding-top: 60px;">
        <h2>✅ Collegamento con Google riuscito</h2>
        <p>Puoi tornare all'app.</p>
        <a href="{APP_BASE_URL}">Torna all'app</a>
        <script>
        setTimeout(function() {{ window.location.href = "{APP_BASE_URL}"; }}, 3000);
        </script>
    </body></html>
    """)


app = st.App(
    "app.py",
    routes=[
        Route("/sw.js", _service_worker_endpoint, methods=["GET"]),
        Route("/oauth/google/start", oauth_start, methods=["GET"]),
        Route("/oauth/google/callback", oauth_callback, methods=["GET"]),
    ],
)

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8501"))
    app.run(config={"server.port": porta, "server.address": "0.0.0.0", "server.headless": True})
