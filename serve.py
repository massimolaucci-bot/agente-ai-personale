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

# Round 20quinquies: "include_granted_scopes=true" (vedi oauth_start piu'
# sotto) serve apposta a permettere che lo scope concesso da Google cresca
# nel tempo (es. aggiungere "spreadsheets"/"documents" senza perdere i
# permessi gia' dati in precedenza) - e' esattamente il meccanismo con cui
# Massimo ha ricollegato l'account condiviso in questo round. Il problema:
# la libreria oauthlib usata sotto al cofano da google-auth-oauthlib, per
# difetto, considera QUALSIASI differenza tra lo scope richiesto e quello
# davvero concesso da Google come un errore fatale (solleva un'eccezione
# "Scope has changed from ... to ..." dentro flow.fetch_token(), che
# interromperebbe con una pagina di errore un ricollegamento altrimenti
# riuscito) - un comportamento documentato che va in diretto conflitto con
# "include_granted_scopes=true". Va disattivato esplicitamente PRIMA di
# qualunque fetch_token(), altrimenti un domani un ricollegamento legittimo
# (es. scope concesso leggermente diverso da quello richiesto) fallirebbe
# con un errore 500 invece di completarsi normalmente.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

import requests
import streamlit as st
from starlette.responses import Response, RedirectResponse, HTMLResponse, PlainTextResponse, JSONResponse
from starlette.routing import Route
from cryptography.fernet import Fernet
from google_auth_oauthlib.flow import Flow

# Bot Telegram + Smart Morning Briefing: la logica Google (calendario/lista
# della spesa) e la classificazione d'intento vivono in google_agent_core.py,
# non in app.py - vedi il commento in cima a quel file per il perche' (app.py
# e' uno script Streamlit, non importabile come libreria da qui).
import google_agent_core as gac

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
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
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
        # Round 20quinquies: qui andava salvato lo scope DAVVERO concesso da
        # Google (creds.granted_scopes, che arriva dal campo "scope" della
        # risposta reale del token endpoint), non "creds.scopes" - quello e'
        # solo l'elenco RICHIESTO (lo stesso identico GOOGLE_OAUTH_SCOPES
        # passato a Flow.from_client_config, quindi sempre "vero" a
        # prescindere da cosa Google abbia realmente concesso). E' lo stesso
        # bug di fondo gia' corretto in _get_google_credentials nel round
        # 20quater (li' capitava ad ogni refresh silenzioso, qui capiterebbe
        # gia' al primo collegamento): scambiare il desiderio dell'app per il
        # dato reale restituito da Google. Con "include_granted_scopes=true"
        # (vedi oauth_start) e OAUTHLIB_RELAX_TOKEN_SCOPE=1 qui sopra, uno
        # scope concesso diverso da quello richiesto e' un caso normale, non
        # un'eccezione - quindi va gestito correttamente, non ignorato.
        scope_concesso = getattr(creds, "granted_scopes", None) or creds.scopes
        ok = _save_google_tokens(
            conn_type,
            user_id,
            creds.token,
            creds.refresh_token,
            expires_at_iso,
            " ".join(scope_concesso) if scope_concesso else "",
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


# --- Bot Telegram + Smart Morning Briefing ----------------------------------
# Architettura a webhook (non polling): Telegram manda una POST ad ogni nuovo
# messaggio, invece di tenere un processo separato sempre acceso a chiedere
# "ci sono novita'?" (application.run_polling(...), come nella prima bozza).
# Un processo di polling avrebbe richiesto un secondo servizio Render sempre
# attivo (probabilmente a pagamento, dato che il piano gratuito attuale va in
# stand-by quando non riceve richieste): il webhook invece e' solo un'altra
# rotta di questo stesso servizio, senza bisogno di nulla in piu'.
#
# TELEGRAM_BOT_TOKEN: da ottenere parlando con @BotFather su Telegram (serve
# un'azione dell'utente, non automatizzabile da qui) e da impostare come
# variabile d'ambiente su Render.
# TELEGRAM_WEBHOOK_SECRET: stringa a scelta (es. generata a caso), messa
# nell'indirizzo del webhook registrato su Telegram, cosi' che questa rotta
# rifiuti richieste che non arrivano davvero da Telegram.
# CRON_SECRET: stessa idea, ma per proteggere /cron/morning-briefing (chiamata
# da uno scheduler esterno una volta al giorno, non da Telegram).
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
CRON_SECRET = os.environ.get("CRON_SECRET")
TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else None

# Comandi rapidi (slash command): stessi nomi registrati nel menu "/" del bot
# lato Telegram (vedi setMyCommands, fatto una tantum via browser durante
# l'attivazione - non da questo codice). Ogni voce punta al nome di
# un'azione reale gia' presente in TELEGRAM_TOOLS_SCHEMA (google_agent_core.py):
# nessun comando qui sotto deve esistere senza una funzione vera dietro,
# stesso principio del blocco allucinazioni gia' in uso nel resto del progetto.
_COMANDI_RAPIDI_TELEGRAM = {
    "/oggi": "richiedi_briefing_mattutino",
    "/briefing": "richiedi_briefing_mattutino",
    "/calendario": "leggi_calendario",
    "/spesa": "lista_spesa_mostra",
}
_TESTO_AIUTO_TELEGRAM = (
    "Ciao! Sono Carpanet AI, anche qui su Telegram \U0001F44B\n\n"
    "Puoi scrivermi (anche a voce) in linguaggio naturale, es. \"aggiungi il latte alla lista della spesa\" "
    "oppure \"cosa ho oggi?\" - oppure usare questi comandi rapidi:\n\n"
    "/oggi - riepilogo/briefing degli impegni di oggi\n"
    "/calendario - prossimi impegni nel calendario\n"
    "/spesa - mostra la lista della spesa\n"
    "/aiuto - questo messaggio\n\n"
    "Per email e verbali audio, per ora, usa l'app web."
)


def _telegram_pronto():
    return bool(TELEGRAM_API_BASE and TELEGRAM_WEBHOOK_SECRET and SUPABASE_HEADERS)


def _telegram_invia_messaggio(chat_id, testo):
    if not TELEGRAM_API_BASE:
        return False
    try:
        r = requests.post(
            f"{TELEGRAM_API_BASE}/sendMessage",
            json={"chat_id": chat_id, "text": testo},
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[telegram] invio messaggio fallito: {e}", flush=True)
        return False


def _telegram_utente_da_id(telegram_id):
    if not SUPABASE_HEADERS:
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/family_users",
            headers=SUPABASE_HEADERS,
            params={"select": "id,name,role,telegram_id", "telegram_id": f"eq.{telegram_id}"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        righe = r.json()
        return righe[0] if righe else None
    except Exception as e:
        print(f"[telegram] lettura utente fallita: {e}", flush=True)
        return None


def _telegram_utenti_con_id_collegato():
    if not SUPABASE_HEADERS:
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/family_users",
            headers=SUPABASE_HEADERS,
            params={"select": "id,name,role,telegram_id", "telegram_id": "not.is.null"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        print(f"[telegram] lettura utenti collegati fallita: {e}", flush=True)
        return []


def _telegram_trascrivi_audio(file_id):
    """Scarica un vocale Telegram (file_id) e lo trascrive con lo stesso
    modello Whisper gia' usato dalla chat principale (app.py)."""
    try:
        r = requests.get(f"{TELEGRAM_API_BASE}/getFile", params={"file_id": file_id}, timeout=15)
        r.raise_for_status()
        _file_path = r.json()["result"]["file_path"]
        _url_file = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{_file_path}"
        _audio_bytes = requests.get(_url_file, timeout=30).content
        from groq import Groq
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        _trascrizione = _client.audio.transcriptions.create(
            model="whisper-large-v3", file=("audio.ogg", _audio_bytes), language="it",
        )
        return (_trascrizione.text or "").strip()
    except Exception as e:
        print(f"[telegram] trascrizione audio fallita: {e}", flush=True)
        return ""


async def telegram_webhook(request):
    _secret_url = request.path_params.get("secret", "")
    if not _telegram_pronto() or not hmac.compare_digest(_secret_url, TELEGRAM_WEBHOOK_SECRET or ""):
        return PlainTextResponse("Non trovato.", status_code=404)
    try:
        update = await request.json()
    except Exception:
        return JSONResponse({"ok": True})

    _messaggio = update.get("message") or update.get("edited_message")
    if not _messaggio:
        return JSONResponse({"ok": True})  # altri tipi di update (es. callback_query) ignorati per ora

    _chat_id = _messaggio.get("chat", {}).get("id")
    _telegram_id = _messaggio.get("from", {}).get("id")
    if not _chat_id or not _telegram_id:
        return JSONResponse({"ok": True})

    _utente = _telegram_utente_da_id(_telegram_id)
    if not _utente:
        _nome_da = _messaggio.get("from", {}).get("first_name", "")
        print(
            f"[telegram] utente non riconosciuto: telegram_id={_telegram_id} chat_id={_chat_id} nome={_nome_da!r}",
            flush=True,
        )
        _telegram_invia_messaggio(
            _chat_id,
            "Non riconosco questo account Telegram: collegalo prima dall'app web, sezione \"Collegamenti Google\" "
            "(a breve anche un collegamento diretto Telegram), oppure chiedi a chi gestisce l'app di aggiungerlo.",
        )
        return JSONResponse({"ok": True})

    _testo = (_messaggio.get("text") or "").strip()
    if not _testo and _messaggio.get("voice"):
        _testo = _telegram_trascrivi_audio(_messaggio["voice"]["file_id"])
        if not _testo:
            _telegram_invia_messaggio(_chat_id, "Non sono riuscito a trascrivere il vocale: puoi riprovare o scrivere il messaggio?")
            return JSONResponse({"ok": True})
    if not _testo and (
        _messaggio.get("photo") or _messaggio.get("document") or _messaggio.get("video")
        or _messaggio.get("video_note") or _messaggio.get("sticker") or _messaggio.get("animation")
    ):
        # Bug round 20 (segnalato dall'utente): prima di questo fix, foto/
        # documenti/video arrivavano qui senza testo e senza corrispondere a
        # "voice", quindi cadevano nel "if not _testo: return" sottostante e
        # il bot restava in silenzio totale, senza dire nulla - sembrava
        # rotto invece di limitato. Ora risponde onestamente.
        _telegram_invia_messaggio(
            _chat_id,
            "Da qui su Telegram non sono ancora in grado di leggere foto, documenti o video: per ora capisco solo "
            "testo e messaggi vocali. Per allegati e verbali audio usa l'app web.",
        )
        return JSONResponse({"ok": True})
    if not _testo:
        return JSONResponse({"ok": True})

    # Comandi rapidi (slash command, registrati anche nel menu "/" del bot via
    # setMyCommands): bypassano il classificatore Groq per velocita' e
    # affidabilita' su queste poche azioni note, invece di passare sempre dal
    # riconoscimento in linguaggio naturale.
    _comando_rapido = _testo.split()[0].lower().split("@")[0] if _testo.startswith("/") else None
    if _comando_rapido in _COMANDI_RAPIDI_TELEGRAM:
        try:
            _risposta = gac._handle_google_agent_logic_telegram(
                _COMANDI_RAPIDI_TELEGRAM[_comando_rapido], {}, _utente, _testo,
            )
        except Exception as e:
            print(f"[telegram] comando rapido fallito: {e}", flush=True)
            _risposta = "Mi dispiace, si e' verificato un errore: riprova tra poco."
        _telegram_invia_messaggio(_chat_id, _risposta or "Non ho una risposta per questo, mi dispiace.")
        return JSONResponse({"ok": True})
    if _comando_rapido in ("/start", "/aiuto", "/help"):
        _telegram_invia_messaggio(_chat_id, _TESTO_AIUTO_TELEGRAM)
        return JSONResponse({"ok": True})

    try:
        _risposta = gac.elabora_messaggio_telegram(_testo, _utente)
    except Exception as e:
        print(f"[telegram] elaborazione messaggio fallita: {e}", flush=True)
        _risposta = "Mi dispiace, si e' verificato un errore: riprova tra poco."
    _telegram_invia_messaggio(_chat_id, _risposta or "Non ho una risposta per questo, mi dispiace.")
    return JSONResponse({"ok": True})


async def cron_morning_briefing(request):
    if not CRON_SECRET or request.query_params.get("secret") != CRON_SECRET:
        return PlainTextResponse("Non trovato.", status_code=404)
    if not _telegram_pronto():
        return PlainTextResponse("Bot Telegram non configurato.", status_code=500)
    _utenti = _telegram_utenti_con_id_collegato()
    _inviati = 0
    for _u in _utenti:
        try:
            _testo_briefing = gac.genera_morning_briefing(_u)
        except Exception as e:
            print(f"[cron] briefing fallito per {_u.get('name')}: {e}", flush=True)
            _testo_briefing = None
        if _testo_briefing and _telegram_invia_messaggio(_u["telegram_id"], _testo_briefing):
            _inviati += 1
    return JSONResponse({"ok": True, "inviati": _inviati, "totale_utenti": len(_utenti)})


async def health(request):
    """Endpoint leggerissimo (nessuna chiamata a Google/Groq/Supabase) usato
    dai monitor uptime esterni (es. UptimeRobot) per tenere sveglio il
    servizio su Render free tier senza caricare la pagina Streamlit intera."""
    return JSONResponse({"ok": True})


app = st.App(
    "app.py",
    routes=[
        Route("/sw.js", _service_worker_endpoint, methods=["GET"]),
        Route("/health", health, methods=["GET", "HEAD"]),
        Route("/oauth/google/start", oauth_start, methods=["GET"]),
        Route("/oauth/google/callback", oauth_callback, methods=["GET"]),
        Route("/webhook/telegram/{secret}", telegram_webhook, methods=["POST"]),
        Route("/cron/morning-briefing", cron_morning_briefing, methods=["GET"]),
    ],
)

if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8501"))
    app.run(config={"server.port": porta, "server.address": "0.0.0.0", "server.headless": True})
