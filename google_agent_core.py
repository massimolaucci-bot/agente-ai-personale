"""Nucleo "leggero" della logica Google (Calendar + Lista della spesa) usato
dal bot Telegram (vedi rotte /webhook/telegram e /cron/morning-briefing in
serve.py).

PERCHE' QUESTO FILE ESISTE INVECE DI IMPORTARE app.py:
app.py e' uno script Streamlit (eseguito da cima a fondo ad ogni sessione,
con chiamate dirette a st.session_state fuori da qualunque funzione): non e'
importabile come libreria da un altro processo/route senza far partire tutta
l'interfaccia e senza un vero ScriptRunContext attivo, quindi si romperebbe
subito. serve.py invece e' la parte "ASGI pura" (Starlette) dello stesso
servizio, che deve rispondere anche quando non c'e' nessuna sessione
Streamlit in corso (es. una richiesta Telegram in arrivo).

Questo file contiene quindi una COPIA volutamente snella e verificata "pura"
(nessuna chiamata a st.*) della logica di calendario/lista della spesa gia'
presente in app.py, cosi' com'era al round in cui e' stata copiata (vedi
_crea_evento_calendario_generico, _gestisci_lista_spesa, ecc. in app.py). Se
la logica corrispondente cambia in app.py, va aggiornata anche qui - stesso
schema gia' adottato nei test unitari del progetto (es.
test_dispatch_google_unit.py), solo applicato al codice di produzione invece
che ai test.

Copertura in questo round (deliberatamente NON tutto quello che sa fare la
chat principale): calendario (lettura + creazione promemoria/eventi) e lista
della spesa (aggiungi/mostra/segna comprato). Email e verbali audio restano
disponibili solo dall'app web per ora: userebbero ulteriore codice non
ancora duplicato qui, e allargare la superficie senza poterla verificare con
un bot reale (serve un token da @BotFather che non e' ancora disponibile)
avrebbe significato consegnare codice non testato. Qualunque messaggio che
non riguarda calendario/lista della spesa passa comunque alla chat generica
(stesso modello Groq della chat principale), quindi il bot resta utile da
subito anche per conversazione libera.
"""
import os
import re
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from groq import Groq
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build as google_build
from googleapiclient.errors import HttpError as GoogleHttpError

PRIMARY_MODEL = "groq/compound"
FALLBACK_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MAX_TOKENS = 500

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

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")

_fernet = None
if TOKEN_ENCRYPTION_KEY:
    try:
        _chiave = TOKEN_ENCRYPTION_KEY.encode("utf-8") if isinstance(TOKEN_ENCRYPTION_KEY, str) else TOKEN_ENCRYPTION_KEY
        _fernet = Fernet(_chiave)
    except Exception:
        _fernet = None


def _supabase_enabled():
    return SUPABASE_HEADERS is not None


def _google_oauth_enabled():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and _fernet and _supabase_enabled())


def _adesso_roma():
    try:
        return datetime.now(ZoneInfo("Europe/Rome"))
    except Exception:
        return datetime.now()


_GIORNI_IT = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
_MESI_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
            "settembre", "ottobre", "novembre", "dicembre"]


def _contesto_temporale():
    now = _adesso_roma()
    giorno = _GIORNI_IT[now.weekday()]
    mese = _MESI_IT[now.month - 1]
    return (
        f"Oggi e {giorno} {now.day} {mese} {now.year}, sono le {now.strftime('%H:%M')} "
        f"(ora italiana, fuso orario Europe/Rome)."
    )


def _decrypt_token(value_enc):
    if not value_enc or not _fernet:
        return None
    try:
        return _fernet.decrypt(value_enc.encode("ascii")).decode("utf-8")
    except Exception:
        return None


# --- Token Google (stessa tabella/schema di app.py e serve.py) -------------
def _fetch_google_tokens(conn_type, user_id=None):
    if not _supabase_enabled():
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
            if not user_id:
                return None
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
    if not SUPABASE_HEADERS:
        return False
    try:
        payload = {
            "access_token_enc": _fernet.encrypt(access_token.encode("utf-8")).decode("ascii") if access_token and _fernet else None,
            "expires_at": expires_at_iso,
            "scope": scope,
        }
        if refresh_token and _fernet:
            payload["refresh_token_enc"] = _fernet.encrypt(refresh_token.encode("utf-8")).decode("ascii")
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
                f"{SUPABASE_URL}/rest/v1/{table}", headers=headers,
                params={"id": f"eq.{existing['id']}"}, json=payload, timeout=SUPABASE_TIMEOUT,
            )
        else:
            r = requests.post(f"{SUPABASE_URL}/rest/v1/{table}", headers=headers, json=payload, timeout=SUPABASE_TIMEOUT)
        r.raise_for_status()
        return True
    except Exception:
        return False


def _get_google_credentials(conn_type, user_id=None):
    if not _google_oauth_enabled():
        return None
    tokens = _fetch_google_tokens(conn_type, user_id)
    if not tokens:
        return None
    access_token = _decrypt_token(tokens.get("access_token_enc"))
    refresh_token = _decrypt_token(tokens.get("refresh_token_enc")) if tokens.get("refresh_token_enc") else None
    if not access_token:
        return None
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        scopes=GOOGLE_OAUTH_SCOPES,
    )
    expires_at = tokens.get("expires_at")
    if expires_at:
        try:
            _dt_scadenza = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
            creds.expiry = _dt_scadenza.replace(tzinfo=None)
        except Exception:
            pass
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(GoogleAuthRequest())
            _nuova_scadenza = (creds.expiry.isoformat() + "Z") if creds.expiry else None
            _save_google_tokens(
                conn_type, user_id, creds.token, None, _nuova_scadenza,
                " ".join(creds.scopes) if creds.scopes else tokens.get("scope"),
            )
        except Exception:
            return None
    return creds


def _richiesta_riguarda_famiglia(testo):
    t = (testo or "").lower()
    return any(k in t for k in [
        "di famiglia", "della famiglia", "familiare", "familiari",
        "condiviso", "condivisa", "comune", "di tutti", "per tutti", "nostro", "nostra",
    ])


def _scegli_connessione_google(utente, testo_completo=""):
    _uid = utente.get("id")
    _shared_collegato = _fetch_google_tokens("shared")
    if _richiesta_riguarda_famiglia(testo_completo) and _shared_collegato:
        return ("shared", None)
    if _fetch_google_tokens("personal", _uid):
        return ("personal", _uid)
    if utente.get("role") == "genitore" and _shared_collegato:
        return ("shared", None)
    return (None, None)


# --- Calendario --------------------------------------------------------
def _list_calendar_events(creds, max_results=10):
    try:
        service = google_build("calendar", "v3", credentials=creds)
        now_utc = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary", timeMin=now_utc, maxResults=max_results,
            singleEvents=True, orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception:
        return None


def _list_calendar_events_oggi(creds):
    """Solo gli eventi di OGGI (fuso Europe/Rome): usato dal morning briefing,
    a differenza di _list_calendar_events che prende i prossimi N eventi
    senza limite di data."""
    try:
        service = google_build("calendar", "v3", credentials=creds)
        _oggi = _adesso_roma().date()
        _inizio = datetime.combine(_oggi, datetime.min.time(), tzinfo=ZoneInfo("Europe/Rome"))
        _fine = _inizio + timedelta(days=1)
        result = service.events().list(
            calendarId="primary", timeMin=_inizio.isoformat(), timeMax=_fine.isoformat(),
            maxResults=15, singleEvents=True, orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception:
        return None


def _crea_evento_calendario_generico(creds, titolo, data_str, ora_str=None):
    try:
        _data = datetime.strptime((data_str or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    try:
        calendar_service = google_build("calendar", "v3", credentials=creds)
        if ora_str:
            try:
                _ora = datetime.strptime(ora_str.strip(), "%H:%M").time()
            except ValueError:
                _ora = None
        else:
            _ora = None
        if _ora:
            _inizio = datetime.combine(_data, _ora, tzinfo=ZoneInfo("Europe/Rome"))
            _fine = _inizio + timedelta(hours=1)
            evento = {"summary": titolo, "start": {"dateTime": _inizio.isoformat()}, "end": {"dateTime": _fine.isoformat()}}
        else:
            evento = {
                "summary": titolo,
                "start": {"date": _data.strftime("%Y-%m-%d")},
                "end": {"date": (_data + timedelta(days=1)).strftime("%Y-%m-%d")},
            }
        return calendar_service.events().insert(calendarId="primary", body=evento).execute()
    except Exception as e:
        print(f"[telegram/calendario] creazione evento fallita: {e}", flush=True)
        return None


# --- Lista della spesa ---------------------------------------------------
_NOME_FOGLIO_LISTA_SPESA = "Lista_Spesa_Carpanet"
_NOME_SCHEDA_LISTA_SPESA = "Attiva"
_INTESTAZIONI_LISTA_SPESA = ["Data", "Articolo", "Categoria", "Stato", "Richiesto da"]
_CATEGORIE_SPESA = {
    "caffe": "Bevande", "caffè": "Bevande", "acqua": "Bevande", "vino": "Bevande", "birra": "Bevande",
    "latte": "Latte & Derivati", "yogurt": "Latte & Derivati", "formaggio": "Latte & Derivati", "burro": "Latte & Derivati",
    "pasta": "Pasta & Riso", "riso": "Pasta & Riso",
    "pane": "Panificio", "pizza": "Panificio",
    "uova": "Uova",
    "pomodoro": "Conserve", "passata": "Conserve",
    "carne": "Macelleria", "pollo": "Macelleria", "salumi": "Macelleria", "prosciutto": "Macelleria",
    "verdura": "Frutta & Verdura", "frutta": "Frutta & Verdura", "insalata": "Frutta & Verdura",
    "detersivo": "Pulizia casa", "sapone": "Igiene", "shampoo": "Igiene", "dentifricio": "Igiene",
}


def _categoria_articolo_spesa(articolo):
    _a = (articolo or "").lower()
    for _parola, _categoria in _CATEGORIE_SPESA.items():
        if _parola in _a:
            return _categoria
    return "Varie"


def _trova_o_crea_foglio_spesa(creds):
    drive_service = google_build("drive", "v3", credentials=creds)
    risultati = drive_service.files().list(
        q=f"name='{_NOME_FOGLIO_LISTA_SPESA}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false",
        fields="files(id, name)",
    ).execute()
    trovati = risultati.get("files", [])
    if trovati:
        return trovati[0]["id"]
    sheets_service = google_build("sheets", "v4", credentials=creds)
    nuovo = sheets_service.spreadsheets().create(body={
        "properties": {"title": _NOME_FOGLIO_LISTA_SPESA},
        "sheets": [{"properties": {"title": _NOME_SCHEDA_LISTA_SPESA}}],
    }).execute()
    spreadsheet_id = nuovo["spreadsheetId"]
    sheets_service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id, range=f"{_NOME_SCHEDA_LISTA_SPESA}!A:E",
        valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
        body={"values": [_INTESTAZIONI_LISTA_SPESA]},
    ).execute()
    return spreadsheet_id


def _gestisci_lista_spesa(creds, azione, articoli, nome_utente):
    try:
        spreadsheet_id = _trova_o_crea_foglio_spesa(creds)
        sheets_service = google_build("sheets", "v4", credentials=creds)
        dati = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{_NOME_SCHEDA_LISTA_SPESA}!A:E",
        ).execute().get("values", [])
        righe = dati[1:] if len(dati) > 1 else []

        if azione == "aggiungi":
            if not articoli:
                return "Dimmi anche cosa aggiungere, ad esempio \"aggiungi latte e pane alla lista della spesa\"."
            _attivi = {r[1].strip().lower() for r in righe if len(r) > 3 and r[3].lower() != "comprato" and len(r) > 1}
            _oggi = datetime.now(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y")
            _nuove_righe = []
            _gia_presenti = []
            for _articolo in articoli:
                if _articolo.lower() in _attivi:
                    _gia_presenti.append(_articolo)
                    continue
                _nuove_righe.append([_oggi, _articolo, _categoria_articolo_spesa(_articolo), "Da comprare", nome_utente or "?"])
            if _nuove_righe:
                sheets_service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id, range=f"{_NOME_SCHEDA_LISTA_SPESA}!A:E",
                    valueInputOption="USER_ENTERED", insertDataOption="INSERT_ROWS",
                    body={"values": _nuove_righe},
                ).execute()
            _msg = ""
            if _nuove_righe:
                _msg += "Aggiunti alla lista della spesa: " + ", ".join(r[1] for r in _nuove_righe) + "."
            if _gia_presenti:
                _msg += (" " if _msg else "") + "Gia' presenti (non duplicati): " + ", ".join(_gia_presenti) + "."
            return _msg or "Nessun articolo aggiunto."

        if azione == "mostra":
            _da_comprare = {}
            for r in righe:
                if len(r) > 3 and r[3].lower() != "comprato":
                    _cat = r[2] if len(r) > 2 and r[2] else "Varie"
                    _chi = r[4] if len(r) > 4 else ""
                    _da_comprare.setdefault(_cat, []).append(f"{r[1]}" + (f" (richiesto da {_chi})" if _chi else ""))
            if not _da_comprare:
                return "La lista della spesa e' vuota: tutto e' gia' stato comprato! 🎉"
            _righe_risposta = ["🛒 Lista della spesa:"]
            for _cat in sorted(_da_comprare):
                _righe_risposta.append(f"\n{_cat}")
                _righe_risposta.extend(f"- {a}" for a in _da_comprare[_cat])
            return "\n".join(_righe_risposta)

        if azione == "comprato":
            if not articoli:
                return "Dimmi cosa hai comprato, ad esempio \"ho comprato il latte\"."
            _aggiornamenti = []
            for _i, r in enumerate(righe, start=2):
                if len(r) < 2:
                    continue
                if len(r) > 3 and r[3].lower() == "comprato":
                    continue
                if any(art.lower() in r[1].lower() for art in articoli):
                    _aggiornamenti.append({"range": f"{_NOME_SCHEDA_LISTA_SPESA}!D{_i}", "values": [["Comprato"]]})
            if not _aggiornamenti:
                return "Non ho trovato questi articoli nella lista attiva."
            sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id, body={"data": _aggiornamenti, "valueInputOption": "USER_ENTERED"},
            ).execute()
            return f"Segnati come comprati: {', '.join(articoli)}."

        return None
    except GoogleHttpError as e:
        if getattr(e, "status_code", None) == 403 or " 403" in str(e) or "insufficient" in str(e).lower():
            return (
                "Per usare la lista della spesa serve un permesso in piu' (Fogli Google) che il collegamento "
                "attuale non ha ancora: vai nell'app web, sezione \"Collegamenti Google\", disconnetti e ricollega."
            )
        print(f"[telegram/spesa] fallita: {e}", flush=True)
        return "Non sono riuscito ad accedere alla lista della spesa in questo momento."
    except Exception as e:
        print(f"[telegram/spesa] fallita: {e}", flush=True)
        return "Non sono riuscito ad accedere alla lista della spesa in questo momento."


# --- Riconoscimento intento (Groq function calling) - schema ridotto -------
TELEGRAM_TOOLS_SCHEMA = [
    {"type": "function", "function": {
        "name": "leggi_calendario",
        "description": "Legge i prossimi impegni dal calendario (personale o di famiglia). Non richiede parametri.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "crea_promemoria_calendario",
        "description": "Crea un nuovo evento/promemoria/appuntamento sul calendario. Usa questo per 'aggiungi un promemoria', 'segnami in calendario', 'ricordami di...', 'metti un appuntamento...'.",
        "parameters": {
            "type": "object",
            "properties": {
                "titolo": {"type": "string", "description": "Titolo breve dell'evento/promemoria."},
                "data": {"type": "string", "description": "Data in formato AAAA-MM-GG. Se relativa ('domani', ecc.), calcolala dalla data odierna nel contesto: non lasciarla mai relativa."},
                "ora": {"type": "string", "description": "Ora in formato HH:MM (24 ore). Lascia vuoto se non specificata: verra' creato come promemoria per l'intera giornata."},
            },
            "required": ["titolo", "data"],
        },
    }},
    {"type": "function", "function": {
        "name": "lista_spesa_aggiungi",
        "description": "Aggiunge articoli alla lista della spesa di famiglia.",
        "parameters": {"type": "object", "properties": {
            "articoli": {"type": "array", "items": {"type": "string"}, "description": "Elenco degli articoli da aggiungere."},
        }, "required": ["articoli"]},
    }},
    {"type": "function", "function": {
        "name": "lista_spesa_mostra",
        "description": "Mostra la lista della spesa attuale (solo da comprare).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "lista_spesa_segna_comprato",
        "description": "Segna come gia' comprati gli articoli indicati.",
        "parameters": {"type": "object", "properties": {
            "articoli": {"type": "array", "items": {"type": "string"}, "description": "Elenco degli articoli gia' comprati."},
        }, "required": ["articoli"]},
    }},
]


def _classifica_intento_telegram(testo_completo, utente):
    """Stessa logica/schema di parsing di _classifica_intento_google in
    app.py, ridotta al sottoinsieme di azioni disponibili da Telegram in
    questo round (vedi commento in cima al file)."""
    if not _google_oauth_enabled():
        return ("NESSUNA", None)
    system_prompt = (
        "Sei il modulo di riconoscimento intenti di Carpanet AI (via Telegram). Il tuo unico compito e' "
        "decidere se il messaggio dell'utente vuole attivare una delle azioni disponibili (tools) - non devi "
        "rispondere nel merito, ne' conversare.\n\n"
        f"{_contesto_temporale()} Usa questa data odierna per calcolare qualunque espressione relativa "
        "('domani', 'dopodomani', 'venerdi' prossimo', 'tra tre giorni', ecc.): non lasciare mai una data relativa nei parametri.\n\n"
        "REGOLE FERREE:\n"
        "1. Se il messaggio corrisponde chiaramente a un'azione E hai tutti i parametri richiesti, chiama il tool.\n"
        "2. Se sembra riguardare un'azione ma mancano dettagli, NON chiamare nessun tool: rispondi con una domanda "
        "di chiarimento breve in italiano.\n"
        "3. Se il messaggio non riguarda nessuna di queste azioni, NON chiamare nessun tool e rispondi ESATTAMENTE "
        "con il testo NESSUNA_AZIONE, senza nient'altro.\n"
        "4. Non inventare MAI un titolo o un articolo che non compare nel messaggio: se manca, chiedilo (regola 2)."
    )
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": testo_completo}]
    try:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        completion = _client.chat.completions.create(
            model=FALLBACK_MODEL, messages=messages, tools=TELEGRAM_TOOLS_SCHEMA, tool_choice="auto", max_tokens=500,
        )
        messaggio = completion.choices[0].message
        if messaggio.tool_calls:
            _chiamata = messaggio.tool_calls[0]
            try:
                _argomenti = json.loads(_chiamata.function.arguments or "{}")
            except (ValueError, TypeError):
                _argomenti = {}
            return ("AZIONE", {"name": _chiamata.function.name, "arguments": _argomenti})
        _contenuto = (messaggio.content or "").strip()
        if _contenuto == "NESSUNA_AZIONE" or not _contenuto:
            return ("NESSUNA", None)
        return ("DOMANDA", _contenuto)
    except Exception as e:
        print(f"[telegram] classificazione intento fallita: {e}", flush=True)
        return ("NESSUNA", None)


def _handle_google_agent_logic_telegram(azione_nome, argomenti, utente, testo_completo):
    argomenti = argomenti or {}
    if not _google_oauth_enabled():
        return "La connessione con Google non e' ancora configurata su questo server."
    conn_type, conn_user_id = _scegli_connessione_google(utente, testo_completo)
    if not conn_type:
        return (
            "Non risulta ancora nessun account Google collegato: collegalo dall'app web, sezione "
            "\"Collegamenti Google\"."
        )
    creds = _get_google_credentials(conn_type, conn_user_id)
    if not creds:
        return "Non riesco ad accedere al tuo account Google in questo momento: prova a ricollegarlo dall'app web."

    if azione_nome == "leggi_calendario":
        eventi = _list_calendar_events(creds, max_results=10)
        if eventi is None:
            return "Non sono riuscito a leggere il calendario in questo momento."
        if not eventi:
            return "Non ci sono impegni in programma nel calendario."
        righe = []
        for ev in eventi:
            _inizio = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "?"
            _titolo = ev.get("summary", "(senza titolo)")
            righe.append(f"- {_inizio}: {_titolo}")
        return "Ecco i prossimi impegni nel calendario:\n" + "\n".join(righe)

    if azione_nome == "crea_promemoria_calendario":
        _titolo_evento = (argomenti.get("titolo") or "").strip()
        _data_evento = (argomenti.get("data") or "").strip()
        _ora_evento = (argomenti.get("ora") or "").strip() or None
        if not _titolo_evento or not _data_evento:
            return "Non ho capito bene cosa devo segnare in calendario o per quando: puoi ripetere con titolo e data?"
        _evento_creato = _crea_evento_calendario_generico(creds, _titolo_evento, _data_evento, _ora_evento)
        if not _evento_creato:
            return "Non sono riuscito a creare l'evento nel calendario: la data potrebbe non essere valida."
        _quando = _data_evento + (f" alle {_ora_evento}" if _ora_evento else " (per l'intera giornata)")
        return f"✅ Aggiunto al calendario: \"{_titolo_evento}\" — {_quando}."

    if azione_nome == "lista_spesa_aggiungi":
        _articoli = argomenti.get("articoli") or []
        if not _articoli:
            return "Non ho capito quali articoli aggiungere: puoi ripetermeli?"
        return _gestisci_lista_spesa(creds, "aggiungi", _articoli, utente.get("name")) or "Non sono riuscito a completare l'operazione."

    if azione_nome == "lista_spesa_mostra":
        return _gestisci_lista_spesa(creds, "mostra", [], utente.get("name")) or "Non sono riuscito a leggere la lista della spesa."

    if azione_nome == "lista_spesa_segna_comprato":
        _articoli = argomenti.get("articoli") or []
        if not _articoli:
            return "Non ho capito quali articoli segnare come comprati: puoi ripetermeli?"
        return _gestisci_lista_spesa(creds, "comprato", _articoli, utente.get("name")) or "Non sono riuscito a completare l'operazione."

    return "Non so ancora fare questa azione da Telegram: prova dall'app web."


def elabora_messaggio_telegram(testo_completo, utente):
    """Nucleo condiviso: riconosce l'intento e lo esegue, altrimenti risponde
    con la chat generica (stesso modello Groq della chat principale). Non
    gestisce audio (fatto a monte dal chiamante, che trascrive prima di
    passare qui) ne' allegati/addestramento/verbali."""
    _tipo, _valore = _classifica_intento_telegram(testo_completo, utente)
    if _tipo == "AZIONE":
        return _handle_google_agent_logic_telegram(_valore["name"], _valore["arguments"], utente, testo_completo)
    if _tipo == "DOMANDA":
        return _valore
    try:
        _client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        completion = _client.chat.completions.create(
            model=PRIMARY_MODEL,
            messages=[
                {"role": "system", "content": (
                    "Sei Carpanet AI, assistente di famiglia, qui via Telegram. Rispondi in italiano, breve e "
                    "diretto. Non inventare mai azioni che non sai fare davvero (calendario e lista della spesa "
                    "sono le uniche azioni reali disponibili da qui; per email e verbali audio indirizza "
                    "l'utente all'app web)."
                )},
                {"role": "user", "content": testo_completo},
            ],
            max_tokens=500,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[telegram] risposta generica fallita: {e}", flush=True)
        return "Mi dispiace, in questo momento non riesco a rispondere: riprova tra poco."


# --- Smart Morning Briefing --------------------------------------------
def genera_morning_briefing(utente):
    """Riassunto mattutino: impegni di oggi dal calendario dell'utente (o di
    famiglia se non ha un account personale collegato). Ritorna None se non
    c'e' nessun account Google utilizzabile (il chiamante decide se e come
    segnalarlo)."""
    conn_type, conn_user_id = _scegli_connessione_google(utente, "")
    if not conn_type:
        return None
    creds = _get_google_credentials(conn_type, conn_user_id)
    if not creds:
        return None
    eventi = _list_calendar_events_oggi(creds)
    _saluto = "Buongiorno"
    _nome = utente.get("name") or ""
    if eventi is None:
        _sezione = "📅 Non sono riuscito a leggere il calendario stamattina."
    elif not eventi:
        _sezione = "📅 Nessun impegno in programma per oggi: giornata libera!"
    else:
        _righe = []
        for ev in eventi:
            _inizio = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "?"
            if "T" in str(_inizio):
                try:
                    _ora_fmt = datetime.fromisoformat(_inizio).strftime("%H:%M")
                except Exception:
                    _ora_fmt = _inizio
            else:
                _ora_fmt = "tutto il giorno"
            _righe.append(f"- {_ora_fmt}: {ev.get('summary', '(senza titolo)')}")
        _sezione = "📅 Impegni di oggi:\n" + "\n".join(_righe)
    return f"☀️ {_saluto} {_nome}!\n\n{_sezione}"
