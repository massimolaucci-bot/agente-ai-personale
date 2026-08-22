import os
import re
import io
import json
import base64
import hashlib
import hmac
import secrets
import time
import requests
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build as google_build
from googleapiclient.errors import HttpError as GoogleHttpError
from googleapiclient.http import MediaIoBaseUpload

MEMORY_FILE = "chat_memory.json"
KNOWLEDGE_FILE = "knowledge.json"

MAX_HISTORY_MESSAGES = 6    # quante battute recenti mandare al modello ad ogni richiesta
MAX_MESSAGE_CHARS = 1500    # lunghezza massima di un singolo messaggio inviato al modello
MAX_SAVED_MESSAGES = 200    # quante battute tenere salvate su disco per la visualizzazione

PRIMARY_MODEL = "groq/compound"
# Round 20bis: "llama-3.3-70b-versatile" viene dismesso da Groq il 16/08/2026
# (piano free/developer - vedi https://console.groq.com/docs/deprecations).
# Sostituito con "openai/gpt-oss-120b", il primo dei due rimpiazzi
# consigliati ufficialmente da Groq per questo identico modello, con
# supporto pieno al tool/function calling (necessario per tutte le azioni
# reali: calendario, lista spesa, email, verbali) come il modello precedente.
FALLBACK_MODEL = "openai/gpt-oss-120b"
PRIMARY_MAX_TOKENS = 900
FALLBACK_MAX_TOKENS = 500

LOGO_B64 = "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"


SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
SUPABASE_TIMEOUT = 6  # secondi: mai bloccare l'avvio dell'app in caso di problemi di rete

SUPABASE_HEADERS = None
if SUPABASE_URL and SUPABASE_KEY:
    SUPABASE_HEADERS = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _supabase_enabled():
    return SUPABASE_HEADERS is not None


# --- Google Calendar + Gmail (OAuth2, token cifrati su Supabase) ------------
# Indirizzo pubblico dell'app: serve per costruire i link di collegamento a
# Google (redirect_uri gia' registrato su Google Cloud Console) e i link di
# ritorno mostrati nella pagina di conferma dopo il collegamento.
APP_BASE_URL = (os.environ.get("APP_BASE_URL") or "https://agente-ai-vocale.onrender.com").rstrip("/")

OAUTH_STATE_SECRET = os.environ.get("OAUTH_STATE_SECRET")
TOKEN_ENCRYPTION_KEY = os.environ.get("TOKEN_ENCRYPTION_KEY")
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

# access_token/refresh_token sono piu' sensibili dei PIN/token "ricordami"
# (quelli sono salvati solo come hash): qui serve la forma cifrata ma
# reversibile, perche' il refresh_token deve poter essere riusato per
# ottenere nuovi access_token. Fernet e' simmetrica: stessa chiave
# (TOKEN_ENCRYPTION_KEY, generata una volta e salvata su Render) per
# cifrare e decifrare.
_google_fernet = None
if TOKEN_ENCRYPTION_KEY:
    try:
        _chiave_fernet = TOKEN_ENCRYPTION_KEY.encode("utf-8") if isinstance(TOKEN_ENCRYPTION_KEY, str) else TOKEN_ENCRYPTION_KEY
        _google_fernet = Fernet(_chiave_fernet)
    except Exception:
        _google_fernet = None


def _google_oauth_enabled():
    return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and _google_fernet and _supabase_enabled())


# --- Cloudflare R2 (storage: allegati chat + documenti di addestramento) ------
# R2 e' compatibile con l'API S3 di Amazon: usiamo boto3, la libreria standard
# per parlare con storage "a oggetti". A differenza di Google Drive con un
# account di servizio, qui lo spazio appartiene davvero al bucket (nessun
# problema di "quota zero"). Due bucket separati per tenere distinti gli
# allegati occasionali della chat dai documenti caricati per l'addestramento.
# Variabili d'ambiente su Render:
# - R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY: credenziali del
#   token API R2 generato su Cloudflare.
# - R2_BUCKET_ALLEGATI / R2_BUCKET_ADDESTRAMENTO: nomi dei due bucket.
# - R2_PUBLIC_URL_ALLEGATI / R2_PUBLIC_URL_ADDESTRAMENTO: indirizzo pubblico
#   (r2.dev) di ciascun bucket, per costruire link diretti ai file caricati.
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_ALLEGATI = os.environ.get("R2_BUCKET_ALLEGATI", "carpanet-allegati")
R2_BUCKET_ADDESTRAMENTO = os.environ.get("R2_BUCKET_ADDESTRAMENTO", "carpanet-addestramento")
R2_PUBLIC_URL_ALLEGATI = (os.environ.get("R2_PUBLIC_URL_ALLEGATI") or "").rstrip("/")
R2_PUBLIC_URL_ADDESTRAMENTO = (os.environ.get("R2_PUBLIC_URL_ADDESTRAMENTO") or "").rstrip("/")

_r2_client = None


def _r2_enabled():
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY)


def _get_r2_client():
    """Crea (una sola volta per processo) e ritorna il client Cloudflare R2.
    Ritorna None se le credenziali non sono configurate o non sono valide."""
    global _r2_client
    if not _r2_enabled():
        print("[R2] Non configurato: mancano R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY.", flush=True)
        return None
    if _r2_client is not None:
        return _r2_client
    try:
        import boto3
        _r2_client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        return _r2_client
    except Exception as e:
        print(f"[R2] ERRORE creazione client: {type(e).__name__}: {e}", flush=True)
        _r2_client = None
        return None


def r2_upload(file_bytes, filename, bucket, public_base_url):
    """Carica un file su Cloudflare R2 (nel bucket indicato). Ritorna un link
    pubblico se riuscito, altrimenti None. Non solleva mai eccezioni: se R2 non
    e configurato o la chiamata fallisce, l'app deve continuare a funzionare
    comunque (file semplicemente non salvato)."""
    client = _get_r2_client()
    if client is None or not bucket:
        return None
    try:
        import mimetypes
        import time
        import re
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
        key = f"{int(time.time())}_{safe_name}"
        mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        client.put_object(Bucket=bucket, Key=key, Body=file_bytes, ContentType=mime_type)
        return f"{public_base_url}/{key}" if public_base_url else key
    except Exception as e:
        print(f"[R2] ERRORE durante il caricamento di '{filename}' nel bucket '{bucket}': {type(e).__name__}: {e}", flush=True)
        return None


def _extract_pdf_text(file_bytes):
    """Estrae il testo da un PDF. Ritorna stringa vuota se non riesce (es. PDF
    scansionato senza testo selezionabile, o file corrotto)."""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    except Exception as e:
        print(f"[Addestramento] ERRORE estrazione testo PDF: {type(e).__name__}: {e}", flush=True)
        return ""


def _extract_docx_text(file_bytes):
    """Estrae il testo da un documento Word (.docx). Ritorna stringa vuota se
    non riesce."""
    try:
        import io
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    except Exception as e:
        print(f"[Addestramento] ERRORE estrazione testo Word: {type(e).__name__}: {e}", flush=True)
        return ""


def _load_memory_file():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_memory_file(messages):
    try:
        trimmed = messages[-MAX_SAVED_MESSAGES:]
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_knowledge_file():
    if os.path.exists(KNOWLEDGE_FILE):
        try:
            with open(KNOWLEDGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("text", "")
        except Exception:
            return ""
    return ""


def _save_knowledge_file(text):
    try:
        with open(KNOWLEDGE_FILE, "w", encoding="utf-8") as f:
            json.dump({"text": text}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_memory():
    if _supabase_enabled():
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/chat_messages",
                headers=SUPABASE_HEADERS,
                params={
                    "select": "role,content",
                    "order": "id.asc",
                    "limit": str(MAX_SAVED_MESSAGES),
                },
                timeout=SUPABASE_TIMEOUT,
            )
            r.raise_for_status()
            return [{"role": row["role"], "content": row["content"]} for row in r.json()]
        except Exception:
            pass
    return _load_memory_file()


def save_memory(messages):
    if _supabase_enabled():
        try:
            trimmed = messages[-MAX_SAVED_MESSAGES:]
            r = requests.delete(
                f"{SUPABASE_URL}/rest/v1/chat_messages",
                headers=SUPABASE_HEADERS,
                params={"id": "gte.0"},
                timeout=SUPABASE_TIMEOUT,
            )
            r.raise_for_status()
            if trimmed:
                r = requests.post(
                    f"{SUPABASE_URL}/rest/v1/chat_messages",
                    headers=SUPABASE_HEADERS,
                    json=[{"role": m["role"], "content": m["content"]} for m in trimmed],
                    timeout=SUPABASE_TIMEOUT,
                )
                r.raise_for_status()
            return
        except Exception:
            pass
    _save_memory_file(messages)


# --- Conversazioni archiviate (una lista di chat separate, come nelle altre AI) --
# Ogni volta che si entra nella chat (dopo il login) si riparte da una conversazione
# nuova e vuota; le conversazioni precedenti restano salvate e consultabili dalla
# barra laterale. Richiede la memoria persistente su Supabase (tabella
# "conversations", collegata a "chat_messages" tramite conversation_id): senza
# database esterno l'app torna al comportamento precedente (una sola cronologia
# condivisa, senza archivio).
def _create_conversation(user_name, title=None):
    if not _supabase_enabled():
        return None
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/conversations",
            headers={**SUPABASE_HEADERS, "Prefer": "return=representation"},
            json={"user_name": user_name, "title": title},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        return rows[0]["id"] if rows else None
    except Exception:
        return None


def _list_conversations(user_name, limit=100):
    if not _supabase_enabled():
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/conversations",
            headers=SUPABASE_HEADERS,
            params={
                "select": "id,title,created_at,pinned",
                "user_name": f"eq.{user_name}",
                # Le conversazioni "fissate" (pinned) vengono sempre prima,
                # poi le altre in ordine dalla piu recente.
                "order": "pinned.desc,id.desc",
                "limit": str(limit),
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def _toggle_pin_conversation(conversation_id, pinned):
    if not _supabase_enabled() or conversation_id is None:
        return
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/conversations",
            headers=SUPABASE_HEADERS,
            params={"id": f"eq.{conversation_id}"},
            json={"pinned": pinned},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
    except Exception:
        pass


def _delete_conversation(conversation_id):
    """Cancella una conversazione e (grazie a ON DELETE CASCADE sul database)
    tutti i suoi messaggi insieme, in un solo passaggio."""
    if not _supabase_enabled() or conversation_id is None:
        return
    try:
        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/conversations",
            headers=SUPABASE_HEADERS,
            params={"id": f"eq.{conversation_id}"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
    except Exception:
        pass


def _search_conversations(user_name, query_text, limit=100):
    """Cerca sia nei titoli delle conversazioni sia nel testo dei messaggi al
    loro interno (ricerca 'ipertestuale' sulla cronologia), e ritorna le
    conversazioni corrispondenti, con le preferite e le piu recenti prima.
    Non solleva mai eccezioni: in caso di problemi di rete torna alla lista
    normale (senza filtro), cosi la barra laterale non si rompe mai."""
    if not _supabase_enabled():
        return []
    query = (query_text or "").strip()
    if not query:
        return _list_conversations(user_name, limit=limit)
    try:
        r_titoli = requests.get(
            f"{SUPABASE_URL}/rest/v1/conversations",
            headers=SUPABASE_HEADERS,
            params={
                "select": "id,title,created_at,pinned",
                "user_name": f"eq.{user_name}",
                "title": f"ilike.*{query}*",
                "order": "pinned.desc,id.desc",
                "limit": str(limit),
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r_titoli.raise_for_status()
        trovate = {c["id"]: c for c in r_titoli.json()}
    except Exception:
        trovate = {}

    try:
        r_msg = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_messages",
            headers=SUPABASE_HEADERS,
            params={
                "select": "conversation_id",
                "content": f"ilike.*{query}*",
                "limit": "300",
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r_msg.raise_for_status()
        ids_da_messaggi = {
            row["conversation_id"] for row in r_msg.json() if row.get("conversation_id") is not None
        }
        ids_mancanti = [cid for cid in ids_da_messaggi if cid not in trovate]
        if ids_mancanti:
            ids_lista = ",".join(str(i) for i in ids_mancanti)
            r_conv = requests.get(
                f"{SUPABASE_URL}/rest/v1/conversations",
                headers=SUPABASE_HEADERS,
                params={
                    "select": "id,title,created_at,pinned",
                    "user_name": f"eq.{user_name}",
                    "id": f"in.({ids_lista})",
                },
                timeout=SUPABASE_TIMEOUT,
            )
            r_conv.raise_for_status()
            for c in r_conv.json():
                trovate[c["id"]] = c
    except Exception:
        pass

    risultati = list(trovate.values())
    risultati.sort(key=lambda c: (not c.get("pinned", False), -(c.get("id") or 0)))
    return risultati[:limit]


def _update_conversation_title(conversation_id, title):
    if not _supabase_enabled() or conversation_id is None:
        return
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/conversations",
            headers=SUPABASE_HEADERS,
            params={"id": f"eq.{conversation_id}"},
            json={"title": title},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
    except Exception:
        pass


def _load_conversation_messages(conversation_id):
    if not _supabase_enabled() or conversation_id is None:
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/chat_messages",
            headers=SUPABASE_HEADERS,
            params={
                "select": "role,content",
                "conversation_id": f"eq.{conversation_id}",
                "order": "id.asc",
                "limit": str(MAX_SAVED_MESSAGES),
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return [{"role": row["role"], "content": row["content"]} for row in r.json()]
    except Exception:
        return []


def _append_message(conversation_id, role, content):
    """Salva un singolo messaggio nella conversazione indicata. A differenza di
    save_memory() (che cancella e riscrive tutta la cronologia condivisa), qui si
    aggiunge una sola riga: conversazioni diverse convivono nello stesso database
    senza cancellarsi a vicenda."""
    if not _supabase_enabled() or conversation_id is None:
        return
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/chat_messages",
            headers=SUPABASE_HEADERS,
            json={"role": role, "content": content, "conversation_id": conversation_id},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
    except Exception:
        pass


def load_knowledge():
    if _supabase_enabled():
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/knowledge_base",
                headers=SUPABASE_HEADERS,
                params={"select": "text_content", "id": "eq.1"},
                timeout=SUPABASE_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return data[0].get("text_content", "") if data else ""
        except Exception:
            pass
    return _load_knowledge_file()


def save_knowledge(text):
    if _supabase_enabled():
        try:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/knowledge_base",
                headers=SUPABASE_HEADERS,
                params={"id": "eq.1"},
                json={"text_content": text},
                timeout=SUPABASE_TIMEOUT,
            )
            r.raise_for_status()
            return
        except Exception:
            pass
    _save_knowledge_file(text)


# --- Documenti di addestramento (PDF/Word caricati, letti e usati dall'AI) -----
# A differenza delle "istruzioni permanenti" (un unico testo scritto a mano),
# qui si caricano interi documenti: il testo viene estratto una volta al
# caricamento e salvato nel database (tabella "knowledge_documents"). Quando
# arriva una domanda, si cerca automaticamente nei documenti con la ricerca
# full-text nativa di Postgres (nessun servizio esterno, nessuna chiave API in
# piu, nessun rischio di cancellazione dati come con un database a grafo).
def save_knowledge_document(filename, content_text, file_url, user_name=None):
    """user_name=None salva nel livello generale/condiviso (visibile e usato da
    tutta la famiglia, modificabile solo dai genitori). Un user_name valorizzato
    salva invece nella memoria PERSONALE di quell'account (usata solo nelle sue
    conversazioni, oltre a quella condivisa), visibile anche ai genitori tramite
    la sezione di supervisione dedicata."""
    if not _supabase_enabled():
        return False
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/knowledge_documents",
            headers=SUPABASE_HEADERS,
            json={"filename": filename, "content_text": content_text, "file_url": file_url, "user_name": user_name},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[Addestramento] ERRORE salvataggio documento '{filename}': {type(e).__name__}: {e}", flush=True)
        return False


def list_knowledge_documents(limit=50, user_name=None):
    """user_name=None elenca il livello generale/condiviso (user_name NULL nel
    database). Un user_name valorizzato elenca invece solo la memoria personale
    di quell'account."""
    if not _supabase_enabled():
        return []
    try:
        params = {"select": "id,filename,file_url,created_at", "order": "id.desc", "limit": str(limit)}
        params["user_name"] = "is.null" if user_name is None else f"eq.{user_name}"
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/knowledge_documents",
            headers=SUPABASE_HEADERS,
            params=params,
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def delete_knowledge_document(doc_id):
    if not _supabase_enabled():
        return
    try:
        r = requests.delete(
            f"{SUPABASE_URL}/rest/v1/knowledge_documents",
            headers=SUPABASE_HEADERS,
            params={"id": f"eq.{doc_id}"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
    except Exception:
        pass


def search_knowledge_documents(query_text, user_name=None, limit=3):
    """Cerca nei documenti di addestramento caricati i passaggi piu pertinenti
    rispetto al messaggio dell'utente, usando la ricerca full-text nativa di
    Postgres (via Supabase REST). Ritorna una lista vuota se non ci sono
    corrispondenze o il database non e raggiungibile: non blocca mai la chat.
    Include sempre i documenti del livello condiviso (user_name NULL) e, se
    user_name e' indicato, anche quelli della memoria personale di
    quell'account: cosi ogni utente vede in automatico le istruzioni generali
    di famiglia PIU le proprie, senza mai vedere quelle personali di altri."""
    if not _supabase_enabled() or not query_text or not query_text.strip():
        return []
    try:
        import re
        parole = re.findall(r"\w+", query_text.lower())
        parole = [p for p in parole if len(p) > 2][:8]
        if not parole:
            return []
        query_fts = " | ".join(parole)
        params = {
            "select": "filename,content_text",
            "content_text": f"fts(italian).{query_fts}",
            "limit": str(limit),
        }
        if user_name:
            params["or"] = f"(user_name.is.null,user_name.eq.{user_name})"
        else:
            params["user_name"] = "is.null"
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/knowledge_documents",
            headers=SUPABASE_HEADERS,
            params=params,
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Addestramento] ERRORE ricerca documenti: {type(e).__name__}: {e}", flush=True)
        return []


# --- Comando "addestramento" scritto/detto direttamente in chat --------------
# Se un messaggio (scritto o dettato a voce) inizia con la parola
# "addestramento", il contenuto che segue (testo, oppure un file/foto/vocale
# allegato) viene salvato come materiale di addestramento permanente, invece
# di essere mandato all'AI come una domanda normale. Riusa la stessa
# infrastruttura gia' esistente per i documenti PDF/Word caricati dalla barra
# laterale (tabella "knowledge_documents", bucket R2 dedicato).
IMMAGINI_ADDESTRAMENTO_EXT = (".png", ".jpg", ".jpeg", ".heic", ".webp")


def _testo_comando_addestramento(testo):
    """Se il messaggio inizia con 'addestramento', ritorna il testo che segue
    (puo' essere una stringa vuota). Altrimenti ritorna None (non e' un
    comando di addestramento, va trattato come domanda normale)."""
    if not testo:
        return None
    t = testo.strip()
    if not t.lower().startswith("addestramento"):
        return None
    resto = t[len("addestramento"):].strip()
    resto = resto.lstrip(":").strip()
    return resto


def _gestisci_addestramento(resto_testo, files, user_name, is_parent):
    """Salva testo e/o file (documenti, foto) come materiale di addestramento
    permanente. Ritorna il messaggio da mostrare come risposta dell'assistente.

    Un genitore che scrive "addestramento" aggiorna il livello generale,
    condiviso con tutta la famiglia (comportamento invariato). Un figlio che
    scrive "addestramento" aggiorna invece la propria memoria PERSONALE: resta
    valida solo nelle sue conversazioni (oltre a quella generale dei genitori),
    cosi non deve piu ripetere ogni volta chi e o le sue preferenze, ma non puo
    in nessun caso modificare le istruzioni generali di famiglia."""
    if not resto_testo and not files:
        return (
            "Certo! Per l'addestramento scrivi (o dettami) il testo subito dopo "
            "\"addestramento\", oppure allega un file, una foto o un vocale con "
            "quello che vuoi che ricordi sempre."
        )

    scope_user_name = None if is_parent else user_name
    salvati = []
    errori = []

    for f in files:
        file_bytes = f.getvalue()
        nome = f.name
        estensione = os.path.splitext(nome)[1].lower()
        if estensione == ".pdf":
            testo_estratto = _extract_pdf_text(file_bytes)
        elif estensione in (".doc", ".docx"):
            testo_estratto = _extract_docx_text(file_bytes)
        else:
            testo_estratto = ""

        contenuto = testo_estratto
        if resto_testo:
            contenuto = (resto_testo + "\n\n" + contenuto).strip() if contenuto else resto_testo
        if not contenuto:
            if estensione in IMMAGINI_ADDESTRAMENTO_EXT:
                contenuto = f"[Foto caricata per l'addestramento: {nome}, senza testo o descrizione aggiuntiva fornita]"
            else:
                contenuto = f"[File caricato per l'addestramento: {nome}, non e stato possibile estrarne il testo]"

        link = r2_upload(file_bytes, nome, R2_BUCKET_ADDESTRAMENTO, R2_PUBLIC_URL_ADDESTRAMENTO)
        if save_knowledge_document(nome, contenuto, link, user_name=scope_user_name):
            salvati.append(nome)
        else:
            errori.append(nome)

    if not files and resto_testo:
        nome_nota = f"nota_{user_name}_{int(datetime.now().timestamp())}.txt"
        if save_knowledge_document(nome_nota, resto_testo, None, user_name=scope_user_name):
            salvati.append("una nota di testo")
        else:
            errori.append("la nota di testo")

    parti = []
    if salvati:
        dove = "nella tua memoria personale" if scope_user_name else "nella memoria di addestramento generale"
        parti.append(
            f"Ho salvato {dove}: " + ", ".join(salvati)
            + ". Da ora in poi ne terro' conto quando mi fai domande pertinenti."
        )
    if errori:
        parti.append("Non sono riuscito a salvare: " + ", ".join(errori) + ".")
    if not parti:
        parti.append("Non sono riuscito a salvare nulla per l'addestramento, riprova.")
    if not (_r2_enabled() and _supabase_enabled()):
        parti.append(
            "Nota: lo spazio di archiviazione dedicato all'addestramento non risulta ancora "
            "configurato del tutto, quindi il salvataggio potrebbe non essere permanente."
        )
    return " ".join(parti)


def _render_gestione_documenti_addestramento(scope_user_name, key_prefix):
    """Disegna il caricatore multi-file + l'elenco con cancellazione dei
    documenti di addestramento per un livello specifico: scope_user_name=None
    per il livello generale/condiviso, oppure il nome di un account per la sua
    memoria personale. Riusata in tre punti della barra laterale (livello
    generale per i genitori, memoria personale propria per i figli, e
    supervisione dei genitori sulla memoria personale di ciascun figlio), cosi
    la logica di caricamento/elenco/cancellazione resta identica ovunque."""
    _addestramento_attivo = _r2_enabled() and _supabase_enabled()
    doc_uploads = st.file_uploader(
        "Carica documenti",
        type=["pdf", "docx"],
        label_visibility="collapsed",
        key=f"doc_uploader_{key_prefix}",
        disabled=not _addestramento_attivo,
        accept_multiple_files=True,
    )
    _num_da_caricare = len(doc_uploads) if doc_uploads else 0
    _etichetta_bottone = (
        f"Aggiungi {_num_da_caricare} documenti"
        if _num_da_caricare > 1
        else "Aggiungi documento"
    )
    if _num_da_caricare > 0 and st.button(_etichetta_bottone, key=f"btn_upload_{key_prefix}", disabled=not _addestramento_attivo):
        _riusciti = []
        _falliti = []
        with st.spinner(f"Carico {_num_da_caricare} documento/i..."):
            for _doc in doc_uploads:
                _file_bytes = _doc.getvalue()
                if _doc.name.lower().endswith(".pdf"):
                    _testo_estratto = _extract_pdf_text(_file_bytes)
                else:
                    _testo_estratto = _extract_docx_text(_file_bytes)
                if not _testo_estratto:
                    _falliti.append((_doc.name, "contenuto non leggibile (forse un PDF scansionato senza testo selezionabile)"))
                    continue
                _doc_link = r2_upload(_file_bytes, _doc.name, R2_BUCKET_ADDESTRAMENTO, R2_PUBLIC_URL_ADDESTRAMENTO)
                if save_knowledge_document(_doc.name, _testo_estratto, _doc_link, user_name=scope_user_name):
                    _riusciti.append(_doc.name)
                else:
                    _falliti.append((_doc.name, "errore nel salvataggio nel database"))
        if _riusciti:
            if len(_riusciti) == 1:
                st.success(f"Documento '{_riusciti[0]}' aggiunto.")
            else:
                st.success(f"{len(_riusciti)} documenti aggiunti: {', '.join(_riusciti)}.")
        for _nome, _motivo in _falliti:
            st.error(f"'{_nome}' non caricato: {_motivo}.")
        if _riusciti:
            st.rerun()

    _documenti_esistenti = list_knowledge_documents(user_name=scope_user_name) if _supabase_enabled() else []
    if _documenti_esistenti:
        st.caption(f"Documenti caricati ({len(_documenti_esistenti)}):")
        for _doc in _documenti_esistenti:
            _col1, _col2 = st.columns([4, 1])
            with _col1:
                if _doc.get("file_url"):
                    st.markdown(f"📄 [{_doc['filename']}]({_doc['file_url']})")
                else:
                    st.markdown(f"📄 {_doc['filename']}")
            with _col2:
                if st.button("🗑️", key=f"del_doc_{key_prefix}_{_doc['id']}", help="Rimuovi questo documento"):
                    delete_knowledge_document(_doc["id"])
                    st.rerun()
    else:
        st.caption("Nessun documento caricato per ora.")


# --- Login familiare e ruoli (genitore = accesso completo, figlio = limitato) --
# Richiede la memoria persistente su Supabase: senza database esterno non c'e
# un posto sicuro dove conservare gli account, quindi in quel caso il login
# viene saltato e tutti vengono trattati come "genitore" (comportamento identico
# a prima di questa modifica).
def _hash_pin(pin):
    return hashlib.sha256((str(pin) + "carpanet_family_salt_v1").encode("utf-8")).hexdigest()


_GIORNI_IT = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
_MESI_IT = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]


def _adesso_roma():
    """Ora corrente nel fuso di Roma. Il server (Render) gira in UTC, quindi senza
    questa conversione esplicita saluti e data/ora sarebbero sbagliati per buona
    parte della giornata."""
    try:
        return datetime.now(ZoneInfo("Europe/Rome"))
    except Exception:
        return datetime.now()


def _saluto_orario():
    ora = _adesso_roma().hour
    if ora < 12:
        return "buongiorno"
    elif ora < 18:
        return "buon pomeriggio"
    else:
        return "buonasera"


def _contesto_temporale():
    """Stringa con data, giorno della settimana e ora correnti (fuso Europe/Rome),
    da inserire nel system prompt: il modello altrimenti non ha alcun modo di
    sapere che giorno o che ora sia."""
    now = _adesso_roma()
    giorno = _GIORNI_IT[now.weekday()]
    mese = _MESI_IT[now.month - 1]
    return (
        f"Oggi e {giorno} {now.day} {mese} {now.year}, sono le {now.strftime('%H:%M')} "
        f"(ora italiana, fuso orario Europe/Rome)."
    )


def _reverse_geocode(lat, lon):
    """Trasforma coordinate GPS in un nome di luogo leggibile (citta, paese) usando
    il servizio gratuito e senza chiave OpenStreetMap Nominatim. Nessuna nuova
    dipendenza pip: usa 'requests', gia presente. Non solleva mai eccezioni."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "json", "lat": lat, "lon": lon, "zoom": 10, "addressdetails": 1},
            headers={"User-Agent": "CarpanetAI-uso-personale/1.0"},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json()
        addr = data.get("address", {})
        citta = addr.get("city") or addr.get("town") or addr.get("village") or addr.get("county")
        paese = addr.get("country")
        if citta and paese:
            return f"{citta}, {paese}"
        return data.get("display_name")
    except Exception:
        return None


def _load_family_users():
    if not _supabase_enabled():
        return []
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/family_users",
            headers=SUPABASE_HEADERS,
            params={"select": "id,name,role", "order": "id.asc"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


def _verify_family_login(name, pin):
    if not _supabase_enabled():
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/family_users",
            headers=SUPABASE_HEADERS,
            params={"select": "id,name,role,pin_hash", "name": f"eq.{name}"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if rows and rows[0].get("pin_hash") == _hash_pin(pin):
            return {"id": rows[0]["id"], "name": rows[0]["name"], "role": rows[0]["role"]}
        return None
    except Exception:
        return None


def _create_family_user(name, pin, role):
    # Ritorna il record creato (con "id") invece di un semplice True/False:
    # serve a chi crea l'account per poter subito generare un token
    # "ricordami" senza dover fare una query in piu' per ritrovare l'id.
    # Nei punti in cui serve solo sapere se e' andato a buon fine, un `if`
    # sul risultato funziona comunque (None e' falsy, il dict e' truthy).
    if not _supabase_enabled():
        return None
    try:
        headers = dict(SUPABASE_HEADERS)
        headers["Prefer"] = "return=representation"
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/family_users",
            headers=headers,
            json={"name": name, "pin_hash": _hash_pin(pin), "role": role},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if rows:
            return {"id": rows[0]["id"], "name": rows[0]["name"], "role": rows[0]["role"]}
        return None
    except Exception:
        return None


# --- "Ricordami" (accesso automatico senza reinserire il PIN ogni volta) --
# Schema: al login, se l'utente sceglie "Ricordami", generiamo un token
# casuale lungo (mai indovinabile). Solo il suo HASH (mai il token in
# chiaro) viene salvato su Supabase insieme a nome/ruolo e una scadenza; il
# token vero viene tenuto SOLO nel localStorage del browser dell'utente,
# mai in un cookie ne' altrove sul server. Ad ogni apertura dell'app, se
# non si e' gia' loggati, un piccolo script (vedi piu' sotto, stesso schema
# gia' usato per la posizione) controlla il localStorage: se trova un
# token lo passa al lato Python tramite l'indirizzo della pagina, che lo
# verifica contro l'hash salvato e, se valido e non scaduto, effettua il
# login senza richiedere di nuovo il PIN.
REMEMBER_TOKEN_GIORNI = 60  # durata del "ricordami": 60 giorni di inattivita'


def _hash_remember_token(token):
    return hashlib.sha256((token + "carpanet_remember_salt_v1").encode("utf-8")).hexdigest()


def _create_remember_token(user_id, user_name, role):
    if not _supabase_enabled():
        return None
    try:
        token = secrets.token_urlsafe(32)
        scadenza = (datetime.now(timezone.utc) + timedelta(days=REMEMBER_TOKEN_GIORNI)).isoformat()
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/remember_tokens",
            headers=SUPABASE_HEADERS,
            json={
                "user_id": user_id,
                "user_name": user_name,
                "role": role,
                "token_hash": _hash_remember_token(token),
                "expires_at": scadenza,
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return token
    except Exception:
        return None


def _verify_remember_token(token):
    if not _supabase_enabled() or not token:
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/remember_tokens",
            headers=SUPABASE_HEADERS,
            params={
                "select": "user_id,user_name,role,expires_at",
                "token_hash": f"eq.{_hash_remember_token(token)}",
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return None
        row = rows[0]
        scadenza = row.get("expires_at")
        if scadenza:
            try:
                if datetime.fromisoformat(scadenza.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    return None  # token scaduto
            except Exception:
                pass
        return {"id": row["user_id"], "name": row["user_name"], "role": row["role"]}
    except Exception:
        return None


def _revoke_remember_tokens(user_id):
    # Chiamata al logout: dimentica tutti i dispositivi "ricordati" per
    # quell'account, cosi' fare "Esci" significa davvero uscire (non
    # ripresentarsi loggati in automatico al giro successivo).
    if not _supabase_enabled() or not user_id:
        return
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/remember_tokens",
            headers=SUPABASE_HEADERS,
            params={"user_id": f"eq.{user_id}"},
            timeout=SUPABASE_TIMEOUT,
        )
    except Exception:
        pass


# --- Google Calendar + Gmail: helper di cifratura, lettura/scrittura token,
# credenziali, chiamate alle API, interfaccia di collegamento in barra
# laterale, comando in chat. Il flusso OAuth vero e proprio (le due route
# /oauth/google/start e /oauth/google/callback) vive in serve.py, perche' le
# route "semplici" di Starlette non hanno accesso a st.session_state; qui in
# app.py leggiamo/usiamo solo il risultato gia' salvato su Supabase.
def _encrypt_google_token(value):
    if not value or not _google_fernet:
        return None
    return _google_fernet.encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_google_token(value_enc):
    if not value_enc or not _google_fernet:
        return None
    try:
        return _google_fernet.decrypt(value_enc.encode("ascii")).decode("utf-8")
    except Exception:
        return None


def _fetch_google_tokens(conn_type, user_id=None):
    # conn_type: "shared" (account unico di famiglia) oppure "personal"
    # (uno per ogni membro, richiede user_id).
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
    # Aggiorna la riga esistente (trovata via fetch, MAI id=1 fisso: la
    # colonna id e' "generated always as identity" e Postgres rifiuta valori
    # manuali senza OVERRIDING SYSTEM VALUE, che PostgREST non manda da solo)
    # oppure ne crea una nuova se non esiste ancora.
    if not _supabase_enabled():
        return False
    try:
        payload = {
            "access_token_enc": _encrypt_google_token(access_token),
            "expires_at": expires_at_iso,
            "scope": scope,
        }
        if refresh_token:
            # Google manda il refresh_token solo al primo consenso: se non
            # arriva di nuovo (rinnovo di un token gia' esistente) non
            # sovrascriviamo quello gia' salvato.
            payload["refresh_token_enc"] = _encrypt_google_token(refresh_token)
        existing = _fetch_google_tokens(conn_type, user_id)
        headers = dict(SUPABASE_HEADERS)
        headers["Prefer"] = "return=representation"
        if conn_type == "shared":
            table = "google_shared_connection"
        else:
            if not user_id:
                return False
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


def _delete_google_tokens(conn_type, user_id=None):
    if not _supabase_enabled():
        return False
    try:
        if conn_type == "shared":
            existing = _fetch_google_tokens("shared")
            if not existing:
                return True
            r = requests.delete(
                f"{SUPABASE_URL}/rest/v1/google_shared_connection",
                headers=SUPABASE_HEADERS,
                params={"id": f"eq.{existing['id']}"},
                timeout=SUPABASE_TIMEOUT,
            )
        else:
            if not user_id:
                return False
            r = requests.delete(
                f"{SUPABASE_URL}/rest/v1/google_personal_connections",
                headers=SUPABASE_HEADERS,
                params={"user_id": f"eq.{user_id}"},
                timeout=SUPABASE_TIMEOUT,
            )
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
    access_token = _decrypt_google_token(tokens.get("access_token_enc"))
    refresh_token = _decrypt_google_token(tokens.get("refresh_token_enc")) if tokens.get("refresh_token_enc") else None
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
            # FIX (verificato empiricamente): google-auth confronta .expiry con
            # datetime.utcnow(), che e' "naive". Un datetime "aware" qui
            # solleverebbe TypeError ad ogni controllo di .expired.
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


def _list_calendar_events(creds, max_results=10):
    try:
        service = google_build("calendar", "v3", credentials=creds)
        now_utc = datetime.now(timezone.utc).isoformat()
        result = service.events().list(
            calendarId="primary",
            timeMin=now_utc,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except Exception:
        return None


def _list_recent_emails(creds, limit=5):
    try:
        service = google_build("gmail", "v1", credentials=creds)
        result = service.users().messages().list(userId="me", maxResults=limit, labelIds=["INBOX"]).execute()
        messages = result.get("messages", [])
        emails = []
        for m in messages:
            msg = service.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            emails.append({
                "id": msg["id"],
                "threadId": msg.get("threadId"),
                "from": headers.get("From", ""),
                "subject": headers.get("Subject", "(senza oggetto)"),
                "date": headers.get("Date", ""),
                "snippet": msg.get("snippet", ""),
            })
        return emails
    except Exception:
        return None


def _create_email_draft(creds, to_addr, subject, body_text):
    try:
        service = google_build("gmail", "v1", credentials=creds)
        message = MIMEText(body_text)
        message["to"] = to_addr
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        return service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    except Exception as e:
        # Log diagnostico (visibile nei log di Render): senza questo, un
        # errore qui era invisibile sia a noi sia all'utente, che vedeva solo
        # un generico "non riuscito" senza nessun indizio sul motivo reale.
        print(f"[google] _create_email_draft fallita: {e}", flush=True)
        return None


def _send_email_draft(creds, draft_id):
    try:
        service = google_build("gmail", "v1", credentials=creds)
        return service.users().drafts().send(userId="me", body={"id": draft_id}).execute()
    except Exception as e:
        print(f"[google] _send_email_draft fallita (draft_id={draft_id}): {e}", flush=True)
        return None


# --- Bozze email in sospeso: persistenza su Supabase, non solo st.session_state ---
# Bug reale segnalato dall'utente (round 19): il pulsante "Invia/Scarta" della
# bozza vive per costruzione in st.session_state, legato alla connessione
# WebSocket del browser. Se quella connessione si interrompe per qualunque
# motivo (pagina ricaricata, app messa in background su mobile, riavvio del
# container Render sul piano gratuito), Streamlit riparte con uno
# session_state vuoto: la bozza esiste ancora davvero su Gmail, ma il
# pulsante per confermarla dalla chat sparisce senza che l'utente capisca
# perche' (l'assistente continua comunque a promettere "usa il pulsante qui
# sopra", cosa non piu' vera in quel momento). Fix: salvare ogni bozza anche
# su Supabase (stesso pattern gia' in uso per i verbali audio in
# "audio_transcriptions": colonna status pending/sent/discarded) e
# ricaricarla in session_state a ogni avvio/rerun se non e' gia' presente,
# cosi' il pulsante sopravvive a qualunque interruzione di sessione.
def _salva_bozza_email_pendente_db(draft_id, conn_type, conn_user_id, to_addr, subject, body):
    if not _supabase_enabled():
        return False
    try:
        payload = {
            "draft_id": draft_id,
            "conn_type": conn_type,
            "conn_user_id": conn_user_id,
            "to_addr": to_addr,
            "subject": subject,
            "body": body,
            "status": "pending",
        }
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/pending_email_drafts",
            headers=SUPABASE_HEADERS, json=payload, timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[email] salvataggio bozza pendente su Supabase fallito: {e}", flush=True)
        return False


def _elenca_bozze_email_pendenti_db(utente):
    if not _supabase_enabled():
        return []
    try:
        _uid = utente.get("id")
        # Un utente vede le bozze pendenti sull'account condiviso di famiglia
        # (chiunque le ha create) e quelle sul proprio account personale -
        # mai le bozze personali di un altro membro della famiglia. Filtro
        # fatto lato Python (non con la sintassi "or" di PostgREST) per
        # restare semplice e facilmente testabile con il mock locale, che
        # implementa solo i filtri "eq."/"ilike."/"lte."/"gte." per colonna.
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/pending_email_drafts",
            headers=SUPABASE_HEADERS,
            params={"select": "*", "status": "eq.pending", "order": "created_at.asc"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        _righe = r.json()
        return [
            _riga for _riga in _righe
            if _riga.get("conn_type") == "shared"
            or (_riga.get("conn_type") == "personal" and str(_riga.get("conn_user_id")) == str(_uid))
        ]
    except Exception as e:
        print(f"[email] lettura bozze pendenti da Supabase fallita: {e}", flush=True)
        return []


def _aggiorna_stato_bozza_email_db(draft_id, nuovo_stato):
    if not _supabase_enabled():
        return False
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/pending_email_drafts",
            headers=SUPABASE_HEADERS,
            params={"draft_id": f"eq.{draft_id}"},
            json={"status": nuovo_stato},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[email] aggiornamento stato bozza pendente fallito: {e}", flush=True)
        return False


# --- Google Sheets: lista della spesa condivisa ------------------------------
# Round 13: aggiunta su richiesta dell'utente (roadmap "Fase 1: Google
# Sheets"). Usa lo scope "drive.file" (non il piu' ampio "drive"): l'app puo'
# vedere/modificare SOLO i file che ha creato lei stessa, mai l'intero Drive
# dell'utente — piu' sicuro, e sufficiente per un foglio che l'app crea e
# gestisce da sola.
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
    # Cerca un foglio con questo nome tra quelli GIA' creati dall'app (lo
    # scope "drive.file" non permette di vedere altri file dell'utente):
    # se non c'e', ne crea uno nuovo con la scheda "Attiva" gia' pronta e le
    # intestazioni corrette — senza questo, la scheda di default creata da
    # Google Sheets si sarebbe chiamata "Foglio1"/"Sheet1", non "Attiva", e
    # ogni lettura/scrittura successiva sarebbe fallita con un errore di
    # intervallo non trovato.
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
        spreadsheetId=spreadsheet_id,
        range=f"{_NOME_SCHEDA_LISTA_SPESA}!A:E",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [_INTESTAZIONI_LISTA_SPESA]},
    ).execute()
    return spreadsheet_id


def _estrai_articoli_spesa(testo, dopo_parole):
    # Estrae la lista di articoli dal testo dopo la prima parola-chiave
    # trovata (es. "aggiungi" in "aggiungi caffe' e latte alla spesa" ->
    # ["caffe'", "latte"]). Nessun vero NLU: stesso limite gia' accettato nel
    # resto del progetto per il riconoscimento comandi.
    t = (testo or "").lower()
    for _parola in dopo_parole:
        if _parola in t:
            _dopo = t.split(_parola, 1)[1]
            # Si ferma a "alla spesa"/"alla lista"/"nella lista" se presente,
            # per non includerla come se fosse un articolo.
            for _fine in [" alla lista della spesa", " alla spesa", " nella lista", " alla lista"]:
                if _fine in _dopo:
                    _dopo = _dopo.split(_fine, 1)[0]
            _pezzi = re.split(r",| e ", _dopo)
            articoli = [p.strip(" .,!?'’") for p in _pezzi]
            articoli = [a for a in articoli if len(a) > 1]
            if articoli:
                return articoli
    return []


def _gestisci_lista_spesa(creds, azione, articoli, nome_utente):
    try:
        spreadsheet_id = _trova_o_crea_foglio_spesa(creds)
        sheets_service = google_build("sheets", "v4", credentials=creds)
        dati = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=f"{_NOME_SCHEDA_LISTA_SPESA}!A:E",
        ).execute().get("values", [])
        righe = dati[1:] if len(dati) > 1 else []  # salta l'intestazione

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
            _righe_risposta = ["🛒 **Lista della spesa**:"]
            for _cat in sorted(_da_comprare):
                _righe_risposta.append(f"\n**{_cat}**")
                _righe_risposta.extend(f"- {a}" for a in _da_comprare[_cat])
            return "\n".join(_righe_risposta)

        if azione == "comprato":
            if not articoli:
                return "Dimmi cosa hai comprato, ad esempio \"ho comprato il latte\"."
            _aggiornamenti = []
            for _i, r in enumerate(righe, start=2):  # riga 1 = intestazione
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
            print(f"[google] _gestisci_lista_spesa: permesso Fogli Google mancante: {e}", flush=True)
            return (
                "Per usare la lista della spesa serve un permesso in piu' (Fogli Google) che il tuo collegamento "
                "attuale non ha ancora: vai in barra laterale, sezione \"Collegamenti Google\", disconnetti e "
                "ricollega il tuo account per concederlo."
            )
        print(f"[google] _gestisci_lista_spesa fallita: {e}", flush=True)
        return "Non sono riuscito ad accedere alla lista della spesa in questo momento."
    except Exception as e:
        print(f"[google] _gestisci_lista_spesa fallita: {e}", flush=True)
        return "Non sono riuscito ad accedere alla lista della spesa in questo momento."


# --- Verbali audio: un messaggio vocale che inizia con "verbale" (stessa
# convenzione gia' in uso per "addestramento") viene trascritto, riassunto
# dall'IA in un verbale ordinato, salvato come Google Doc, mentre l'audio
# originale finisce su Google Drive con un promemoria a 10 giorni per
# decidere se tenerlo o cancellarlo (il verbale scritto resta comunque per
# sempre). Richiede il nuovo permesso "documents", oltre a quelli gia' in
# uso per Calendar/Gmail/Sheets/Drive.
_NOME_CARTELLA_AUDIO_VERBALI = "Registrazioni Verbali"
_NOME_CARTELLA_DOC_VERBALI = "Verbali Scritti"
_GIORNI_SCADENZA_VERBALE = 10


def _testo_comando_verbale_nuovo(testo):
    """True se il messaggio (di solito la trascrizione di un vocale) inizia
    con la parola "verbale": attiva la creazione di un nuovo verbale invece
    del normale flusso di chat. Il chiamante deve comunque controllare che ci
    sia davvero un audio allegato, altrimenti non c'e' nulla da trascrivere/
    archiviare. Esclude le frasi che parlano di scadenze (es. "verbale in
    scadenza"), gestite altrove come domanda sui verbali gia' esistenti, non
    come richiesta di crearne uno nuovo."""
    if not testo:
        return False
    _t = testo.strip().lower()
    if not _t.startswith("verbale"):
        return False
    if "scadenz" in _t:
        return False
    return True


def _trova_o_crea_cartella_drive(creds, nome):
    drive_service = google_build("drive", "v3", credentials=creds)
    risultati = drive_service.files().list(
        q=f"name='{nome}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
    ).execute()
    trovati = risultati.get("files", [])
    if trovati:
        return trovati[0]["id"]
    cartella = drive_service.files().create(
        body={"name": nome, "mimeType": "application/vnd.google-apps.folder"}, fields="id",
    ).execute()
    return cartella["id"]


def _riassumi_verbale_con_ia(trascrizione):
    # Stesso schema gia' in uso per le bozze di risposta email (round 12):
    # client Groq locale dedicato, non quello globale della chat principale,
    # e stesso modello di riserva (FALLBACK_MODEL) per coerenza col resto
    # del progetto.
    try:
        _prompt = (
            "Sei un segretario che scrive verbali. Trasforma questa trascrizione grezza "
            "di una registrazione vocale in un verbale ordinato in italiano, con questa struttura:\n"
            "TITOLO: (breve, basato sul contenuto)\n"
            "PARTECIPANTI: (se menzionati, altrimenti \"non specificati\")\n"
            "PUNTI PRINCIPALI: (elenco puntato)\n"
            "DECISIONI PRESE: (elenco puntato, oppure \"nessuna\" se non ce ne sono)\n"
            "COSE DA FARE: (elenco puntato, con chi se menzionato, oppure \"nessuna\")\n\n"
            f"Trascrizione:\n{trascrizione}"
        )
        _groq_api_key_locale = os.environ.get("GROQ_API_KEY")
        _client_verbale = Groq(api_key=_groq_api_key_locale)
        _completamento = _client_verbale.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=[{"role": "user", "content": _prompt}],
            max_tokens=1200,
        )
        return _completamento.choices[0].message.content
    except Exception as e:
        print(f"[verbali] riassunto IA fallito: {e}", flush=True)
        return None


def _crea_documento_verbale(creds, testo, titolo, cartella_id):
    try:
        drive_service = google_build("drive", "v3", credentials=creds)
        _doc = drive_service.files().create(
            body={
                "name": f"Verbale - {titolo}",
                "mimeType": "application/vnd.google-apps.document",
                "parents": [cartella_id],
            },
            fields="id",
        ).execute()
        doc_id = _doc["id"]
        docs_service = google_build("docs", "v1", credentials=creds)
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": testo}}]},
        ).execute()
        return doc_id
    except Exception as e:
        print(f"[verbali] creazione documento fallita: {e}", flush=True)
        return None


def _crea_evento_calendario_generico(creds, titolo, data_str, ora_str=None):
    # Backing reale per il tool "crea_promemoria_calendario": crea un evento
    # vero su Google Calendar, per data intera (promemoria/appuntamento senza
    # ora precisa) oppure con un orario specifico (durata di default 1 ora).
    # La data arriva gia' come AAAA-MM-GG (il classificatore la calcola da
    # espressioni relative tipo "domani" usando la data odierna nel contesto),
    # ma viene comunque validata qui prima di chiamare Google: mai passare
    # un valore non verificato a un'azione con effetti reali.
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
            evento = {
                "summary": titolo,
                "start": {"dateTime": _inizio.isoformat()},
                "end": {"dateTime": _fine.isoformat()},
            }
        else:
            evento = {
                "summary": titolo,
                "start": {"date": _data.strftime("%Y-%m-%d")},
                "end": {"date": (_data + timedelta(days=1)).strftime("%Y-%m-%d")},
            }
        return calendar_service.events().insert(calendarId="primary", body=evento).execute()
    except Exception as e:
        print(f"[calendario] creazione evento fallita: {e}", flush=True)
        return None


def _crea_promemoria_scadenza_verbale(creds, nome_file, scadenza_dt):
    try:
        calendar_service = google_build("calendar", "v3", credentials=creds)
        evento = {
            "summary": f"🗑️ Decidi: tenere o cancellare l'audio \"{nome_file}\"?",
            "description": (
                f"Sono passati {_GIORNI_SCADENZA_VERBALE} giorni dalla registrazione \"{nome_file}\". "
                f"In chat con Carpanet AI scrivi \"tieni {nome_file}\" per conservarla, oppure "
                f"\"cancella {nome_file}\" per eliminarla (il verbale scritto resta comunque salvato)."
            ),
            "start": {"date": scadenza_dt.strftime("%Y-%m-%d")},
            "end": {"date": (scadenza_dt + timedelta(days=1)).strftime("%Y-%m-%d")},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 1440}]},
        }
        return calendar_service.events().insert(calendarId="primary", body=evento).execute().get("id")
    except Exception as e:
        print(f"[verbali] creazione promemoria fallita: {e}", flush=True)
        return None


def _elimina_evento_calendario(creds, event_id):
    if not event_id:
        return
    try:
        google_build("calendar", "v3", credentials=creds).events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception:
        pass  # evento gia' cancellato/non trovato: non e' un errore da bloccare


def _salva_verbale_db(user_id, file_id_drive, file_name, doc_id_drive, scadenza_dt, calendar_event_id):
    if not _supabase_enabled():
        return False
    try:
        payload = {
            "user_id": user_id,
            "file_id_drive": file_id_drive,
            "file_name": file_name,
            "doc_id_drive": doc_id_drive,
            "status": "pending",
            "deadline_at": scadenza_dt.isoformat(),
            "calendar_event_id": calendar_event_id,
        }
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/audio_transcriptions",
            headers=SUPABASE_HEADERS, json=payload, timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[verbali] salvataggio su Supabase fallito: {e}", flush=True)
        return False


def _trova_verbale_pendente_db(user_id, nome_parziale):
    if not _supabase_enabled():
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/audio_transcriptions",
            headers=SUPABASE_HEADERS,
            params={
                "select": "*",
                "user_id": f"eq.{user_id}",
                "status": "eq.pending",
                "file_name": f"ilike.*{nome_parziale}*",
                "order": "deadline_at.asc",
                "limit": 1,
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        righe = r.json()
        return righe[0] if righe else None
    except Exception as e:
        print(f"[verbali] ricerca verbale pendente fallita: {e}", flush=True)
        return None


def _elenca_verbali_in_scadenza_db(user_id, giorni=3):
    if not _supabase_enabled():
        return []
    try:
        _soglia = (datetime.now(timezone.utc) + timedelta(days=giorni)).isoformat()
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/audio_transcriptions",
            headers=SUPABASE_HEADERS,
            params={
                "select": "*",
                "user_id": f"eq.{user_id}",
                "status": "eq.pending",
                "deadline_at": f"lte.{_soglia}",
                "order": "deadline_at.asc",
            },
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[verbali] elenco scadenze fallito: {e}", flush=True)
        return []


def _aggiorna_stato_verbale_db(record_id, nuovo_stato):
    if not _supabase_enabled():
        return False
    try:
        r = requests.patch(
            f"{SUPABASE_URL}/rest/v1/audio_transcriptions",
            headers=SUPABASE_HEADERS,
            params={"id": f"eq.{record_id}"},
            json={"status": nuovo_stato},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        print(f"[verbali] aggiornamento stato fallito: {e}", flush=True)
        return False


def _crea_verbale_da_audio(creds, audio_bytes, trascrizione, utente):
    try:
        _adesso = datetime.now(ZoneInfo("Europe/Rome"))
        _etichetta = _adesso.strftime("%d-%m-%Y %H%M")
        nome_file = f"{_etichetta}.wav"

        cartella_audio_id = _trova_o_crea_cartella_drive(creds, _NOME_CARTELLA_AUDIO_VERBALI)
        cartella_doc_id = _trova_o_crea_cartella_drive(creds, _NOME_CARTELLA_DOC_VERBALI)

        drive_service = google_build("drive", "v3", credentials=creds)
        # L'audio registrato dal microfono di questa app e' sempre WAV (vedi
        # piu' sotto nel loop della chat, stesso formato gia' usato per la
        # trascrizione Whisper) — mai un mp3 inventato.
        media = MediaIoBaseUpload(io.BytesIO(audio_bytes), mimetype="audio/wav", resumable=False)
        audio_file = drive_service.files().create(
            body={"name": nome_file, "parents": [cartella_audio_id]}, media_body=media, fields="id",
        ).execute()
        audio_id = audio_file["id"]

        verbale_testo = _riassumi_verbale_con_ia(trascrizione) or f"Trascrizione grezza (riassunto automatico non riuscito):\n\n{trascrizione}"
        doc_id = _crea_documento_verbale(creds, verbale_testo, _etichetta, cartella_doc_id)
        if not doc_id:
            return "Ho salvato l'audio su Drive ma non sono riuscito a creare il documento del verbale. Riprova tra poco."

        _scadenza = _adesso + timedelta(days=_GIORNI_SCADENZA_VERBALE)
        evento_id = _crea_promemoria_scadenza_verbale(creds, nome_file, _scadenza)
        _salva_verbale_db(utente.get("id"), audio_id, nome_file, doc_id, _scadenza, evento_id)

        return (
            "✅ Verbale creato e salvato.\n"
            f"- Audio originale su Google Drive (cartella \"{_NOME_CARTELLA_AUDIO_VERBALI}\").\n"
            f"- Verbale scritto: https://docs.google.com/document/d/{doc_id}\n"
            f"- Tra {_GIORNI_SCADENZA_VERBALE} giorni ({_scadenza.strftime('%d/%m/%Y')}) ti ricordero' di decidere se "
            "tenere o cancellare l'audio originale (il verbale scritto resta comunque per sempre)."
        )
    except Exception as e:
        print(f"[verbali] creazione verbale fallita: {e}", flush=True)
        return "Non sono riuscito a creare il verbale in questo momento. Riprova tra poco."


def _gestisci_nuovo_verbale(utente, audio_bytes, trascrizione):
    if not _google_oauth_enabled():
        return "La connessione con Google non e' ancora configurata su questo server."
    if not trascrizione:
        return "Non sono riuscito a trascrivere l'audio: riprova a registrare di nuovo il verbale."
    conn_type, conn_user_id = _scegli_connessione_google(utente, "verbale")
    if not conn_type:
        return (
            "Non risulta ancora nessun account Google collegato (ne' il tuo personale ne' quello di famiglia): "
            "collegalo dalla barra laterale, sezione \"Collegamenti Google\", per poter salvare i verbali."
        )
    creds = _get_google_credentials(conn_type, conn_user_id)
    if not creds:
        return "Non riesco ad accedere al tuo account Google in questo momento: prova a ricollegarlo dalla barra laterale."
    return _crea_verbale_da_audio(creds, audio_bytes, trascrizione, utente)


def _gestisci_verbali_scadenza(utente):
    _righe = _elenca_verbali_in_scadenza_db(utente.get("id"), giorni=3)
    if not _righe:
        return "Non ci sono verbali audio in scadenza nei prossimi giorni."
    _elenco = "\n".join(f"- \"{r['file_name']}\" (scade il {str(r['deadline_at'])[:10]})" for r in _righe)
    return (
        "📅 Verbali audio in scadenza:\n" + _elenco +
        "\n\nRispondi \"tieni [nome]\" per conservarli oppure \"cancella [nome]\" per eliminare l'audio "
        "(il verbale scritto resta comunque salvato)."
    )


def _gestisci_decisione_verbale(creds, azione, nome_parziale, utente):
    if not nome_parziale:
        return "Dimmi anche il nome del verbale, ad esempio \"tieni 05-08-2026 1830\"."
    record = _trova_verbale_pendente_db(utente.get("id"), nome_parziale)
    if not record:
        return f"Non trovo nessun verbale in attesa di decisione con nome simile a \"{nome_parziale}\"."

    if azione == "tieni":
        _elimina_evento_calendario(creds, record.get("calendar_event_id"))
        _aggiorna_stato_verbale_db(record["id"], "kept")
        return f"✅ Audio \"{record['file_name']}\" conservato. Promemoria rimosso dal calendario."

    try:
        google_build("drive", "v3", credentials=creds).files().delete(fileId=record["file_id_drive"]).execute()
    except Exception as e:
        print(f"[verbali] cancellazione audio da Drive fallita: {e}", flush=True)
    _elimina_evento_calendario(creds, record.get("calendar_event_id"))
    _aggiorna_stato_verbale_db(record["id"], "deleted")
    return f"🗑️ Audio \"{record['file_name']}\" eliminato da Drive. Il verbale scritto resta salvato."


def _permessi_google_mancanti(tokens):
    # Un account collegato PRIMA che un permesso venisse aggiunto non lo ha
    # mai concesso (Google non lo fa retroattivamente): senza questo
    # controllo l'utente scoprirebbe il problema solo al primo tentativo
    # fallito di usare la funzione, con un errore poco chiaro.
    if not tokens:
        return []  # non ancora collegato: nessun avviso di "permesso mancante", solo "collega"
    _scope = (tokens.get("scope") or "")
    _mancanti = []
    if "spreadsheets" not in _scope:
        _mancanti.append("Fogli Google (lista della spesa)")
    if "documents" not in _scope:
        _mancanti.append("Documenti Google (verbali)")
    return _mancanti


def _render_google_connection_ui():
    st.markdown("---")
    st.markdown("#### 📅 Collegamenti Google (Calendario, Gmail, Fogli e Documenti)")
    if not _google_oauth_enabled():
        st.caption("Funzione non ancora attiva: mancano le credenziali Google sul server.")
        return

    _utente_corrente = st.session_state.current_user

    if IS_PARENT:
        st.caption("Account condiviso di famiglia: puoi collegarlo insieme al tuo account personale qui sotto. "
                   "Viene usato per le richieste che riguardano la famiglia (es. \"che impegni c'e' nel calendario di famiglia?\"), "
                   "oppure come riserva se non hai collegato un account personale.")
        _shared = _fetch_google_tokens("shared")
        if _shared:
            st.success("Account condiviso collegato.")
            _mancanti_shared = _permessi_google_mancanti(_shared)
            if _mancanti_shared:
                st.warning("Collegato prima di aggiungere questi permessi: ricollega per usare anche " + " e ".join(_mancanti_shared) + ".")
            if st.button("Disconnetti account condiviso", key="disconnetti_google_shared"):
                _delete_google_tokens("shared")
                st.rerun()
        else:
            st.link_button("🔗 Collega account Google condiviso", f"{APP_BASE_URL}/oauth/google/start?type=shared")
        st.caption("L'accesso a Gmail va ricollegato circa ogni 7 giorni (limite dell'app Google in modalita' di test): basta ricliccare il collegamento quando serve.")
        st.markdown("---")

    st.caption(f"Il tuo account Google personale ({_utente_corrente.get('name', 'Utente')}): usato di default per le tue richieste "
               "(es. \"che email ho?\", \"che impegni ho oggi?\", \"lista della spesa\", \"verbale...\" con un vocale). Puoi averlo collegato insieme a quello di famiglia qui sopra.")
    _personal = _fetch_google_tokens("personal", _utente_corrente.get("id"))
    if _personal:
        st.success("Il tuo account personale e' collegato.")
        _mancanti_personal = _permessi_google_mancanti(_personal)
        if _mancanti_personal:
            st.warning("Collegato prima di aggiungere questi permessi: ricollega per usare anche " + " e ".join(_mancanti_personal) + ".")
        if st.button("Disconnetti il mio account", key="disconnetti_google_personal"):
            _delete_google_tokens("personal", _utente_corrente.get("id"))
            st.rerun()
    else:
        _link_personale = f"{APP_BASE_URL}/oauth/google/start?type=personal&user_id={_utente_corrente.get('id')}&role={CURRENT_ROLE}"
        st.link_button("🔗 Collega il mio account Google", _link_personale)
        st.caption("L'accesso a Gmail va ricollegato circa ogni 7 giorni (limite dell'app Google in modalita' di test): basta ricliccare il collegamento quando serve.")


# Elenco dei "tool" (azioni reali) che il modello puo' attivare capendo il
# significato del messaggio, invece del vecchio riconoscimento a parole
# chiave fisse (_testo_comando_google, rimosso in questo round: obbligava a
# ricordare frasi quasi esatte, poco praticabile per un uso di famiglia).
# Deliberatamente NON include azioni che non sono ancora state costruite per
# davvero (es. domotica): un tool nello schema comunica al modello "questa e'
# una cosa che l'app sa fare", quindi elencarne una finta rischierebbe di
# reintrodurre lo stesso problema dell'invenzione di azioni mai avvenute
# (vedi la regola ferrea in build_api_messages). Quando una nuova azione
# reale verra' costruita, si aggiungera' qui insieme alla funzione vera che
# la esegue - mai prima.
GOOGLE_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "leggi_calendario",
            "description": "Legge i prossimi impegni dal calendario (personale o di famiglia). Non richiede parametri.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crea_promemoria_calendario",
            "description": "Crea un nuovo evento/promemoria/appuntamento sul calendario (personale o di famiglia). Usa questo per qualunque richiesta di aggiungere qualcosa in agenda: 'aggiungi un promemoria', 'segnami in calendario', 'ricordami di...', 'metti un appuntamento...'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "titolo": {"type": "string", "description": "Titolo breve dell'evento/promemoria (es. 'Dentista', 'Ritira pacco', 'Chiama Mario')."},
                    "data": {"type": "string", "description": "Data dell'evento in formato AAAA-MM-GG (es. 2026-08-10). Se l'utente usa un'espressione relativa (es. 'domani', 'venerdi' prossimo', 'tra due giorni'), calcolala tu partendo dalla data odierna indicata nel contesto della conversazione: non lasciarla mai relativa."},
                    "ora": {"type": "string", "description": "Ora dell'evento in formato HH:MM (24 ore), es. '15:30'. Lascia vuoto/omesso se l'utente non specifica un orario preciso: verra' creato come promemoria per l'intera giornata."},
                },
                "required": ["titolo", "data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "leggi_posta",
            "description": "Legge le ultime email ricevute. Non richiede parametri.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rispondi_ultima_email",
            "description": "Prepara una bozza di risposta all'ultima email ricevuta (mai inviata subito, resta bozza da confermare). Richiede indicazioni su cosa scrivere.",
            "parameters": {
                "type": "object",
                "properties": {
                    "indicazioni": {"type": "string", "description": "Cosa deve dire la risposta (es. 'digli che arrivo tardi', 'ringrazia per l'invito')."},
                },
                "required": ["indicazioni"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scrivi_nuova_email",
            "description": "Crea una bozza di email nuova (mai inviata subito, resta bozza da confermare). Richiede l'indirizzo email esatto del destinatario, che deve comparire nel messaggio dell'utente: non va mai inventato.",
            "parameters": {
                "type": "object",
                "properties": {
                    "destinatario": {"type": "string", "description": "Indirizzo email esatto del destinatario (es. mario@rossi.it). Deve essere presente nel messaggio dell'utente, mai inventato."},
                    "indicazioni": {"type": "string", "description": "Cosa deve contenere l'email."},
                },
                "required": ["destinatario", "indicazioni"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lista_spesa_aggiungi",
            "description": "Aggiunge articoli alla lista della spesa di famiglia su Google Sheets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "articoli": {"type": "array", "items": {"type": "string"}, "description": "Elenco degli articoli da aggiungere (es. ['latte', 'pane'])."},
                },
                "required": ["articoli"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lista_spesa_mostra",
            "description": "Mostra la lista della spesa attuale (solo gli articoli ancora da comprare).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lista_spesa_segna_comprato",
            "description": "Segna come gia' comprati gli articoli indicati, senza cancellarli dallo storico.",
            "parameters": {
                "type": "object",
                "properties": {
                    "articoli": {"type": "array", "items": {"type": "string"}, "description": "Elenco degli articoli gia' comprati."},
                },
                "required": ["articoli"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verbali_mostra_scadenza",
            "description": "Mostra l'elenco dei verbali audio in attesa di decisione (tenere o cancellare), secondo la regola dei 10 giorni.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "verbale_decidi",
            "description": "Decide cosa fare di un verbale audio in attesa: conservarlo o cancellarlo (elimina l'audio da Drive, il documento scritto del verbale resta comunque salvato).",
            "parameters": {
                "type": "object",
                "properties": {
                    "azione": {"type": "string", "enum": ["tieni", "cancella"], "description": "'tieni' per conservare l'audio, 'cancella' per eliminarlo."},
                    "nome_file": {"type": "string", "description": "Nome (anche parziale) del file audio o del verbale a cui si riferisce l'utente."},
                },
                "required": ["azione", "nome_file"],
            },
        },
    },
]


def _classifica_intento_google(testo_completo, cronologia_recente, utente):
    """Capisce se il messaggio corrente vuole attivare una delle azioni reali
    sopra, usando il function calling di Groq invece del vecchio
    riconoscimento a parole chiave fisse: cosi' non serve piu' ricordare
    frasi quasi esatte, e frasi dette in modi diversi vengono riconosciute lo
    stesso. Se manca un dettaglio necessario (es. quale indirizzo email,
    quale articolo, quale verbale), il modello fa una domanda di chiarimento
    invece di indovinare - e non deve MAI inventare un dato mancante.
    Ritorna una tupla (tipo, valore):
    - ("AZIONE", {"name": ..., "arguments": {...}}) - pronta all'esecuzione;
    - ("DOMANDA", "testo della domanda") - serve un chiarimento;
    - ("NESSUNA", None) - non riguarda queste azioni, o Google non e'
      configurato, o la chiamata a Groq e' fallita: in ogni caso il chiamante
      deve lasciar fluire il messaggio alla chat generica come se questo
      controllo non fosse mai avvenuto.
    Usa FALLBACK_MODEL ("openai/gpt-oss-120b", round 20bis: rimpiazza il
    dismesso llama-3.3-70b-versatile), modello Groq con supporto affidabile
    per i tool personalizzati - non PRIMARY_MODEL ("groq/compound"), il cui
    comportamento con "tools" definiti da noi non e' documentato."""
    if not _google_oauth_enabled():
        return ("NESSUNA", None)

    system_prompt = (
        "Sei il modulo di riconoscimento intenti di Carpanet AI, assistente di famiglia. Il tuo unico compito e' "
        "decidere se il messaggio dell'utente vuole attivare una delle azioni disponibili (tools) - non devi "
        "rispondere nel merito, ne' conversare.\n\n"
        f"{_contesto_temporale()} Usa questa data odierna per calcolare qualunque espressione relativa "
        "('domani', 'dopodomani', 'venerdi' prossimo', 'tra tre giorni', ecc.) quando devi passare una data assoluta "
        "a un tool (es. crea_promemoria_calendario): non lasciare mai una data relativa nei parametri.\n\n"
        "REGOLE FERREE:\n"
        "1. Se il messaggio corrisponde chiaramente a un'azione E hai tutti i parametri richiesti (es. indirizzo "
        "email esplicito, articoli specifici, nome del verbale), chiama il tool corrispondente con quegli argomenti.\n"
        "2. Se sembra riguardare una di queste azioni ma mancano dettagli necessari (es. 'manda una email' senza "
        "destinatario, 'cancella l'audio' senza dire quale), NON chiamare nessun tool: rispondi invece con una "
        "domanda di chiarimento breve e diretta in italiano, cosi' l'utente puo' risponderti con il dettaglio mancante.\n"
        "3. Se il messaggio non riguarda nessuna di queste azioni (conversazione generica, domande su altri "
        "argomenti, richieste che l'app non sa fare come creare presentazioni o altri file), NON chiamare nessun "
        "tool e rispondi ESATTAMENTE con il testo NESSUNA_AZIONE, senza nient'altro.\n"
        "4. Non inventare MAI un indirizzo email, un nome file o un articolo che non compare nel messaggio o nella "
        "cronologia recente: se manca, chiedilo (regola 2).\n"
        "5. Per motivi di sicurezza, un indirizzo email per scrivere/rispondere a una mail viene accettato SOLO se "
        "compare per esteso nell'ULTIMO messaggio dell'utente, anche se lo aveva gia' scritto in un messaggio "
        "precedente della stessa conversazione. Se nella cronologia vedi che l'utente ha gia' indicato un "
        "indirizzo in un turno precedente ma non lo ripete in questo messaggio, NON dire che non hai ricevuto "
        "nessun indirizzo: spiega invece chiaramente che per sicurezza serve riscriverlo per esteso in questo "
        "stesso messaggio, e chiedigli di farlo."
    )
    messages = [{"role": "system", "content": system_prompt}]
    for m in (cronologia_recente or [])[-6:]:
        _contenuto = (m.get("content") or "")[:500]
        messages.append({"role": m.get("role", "user"), "content": _contenuto})
    messages.append({"role": "user", "content": testo_completo})

    try:
        _client_intento = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        completion = _client_intento.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=messages,
            tools=GOOGLE_TOOLS_SCHEMA,
            tool_choice="auto",
            max_tokens=500,
        )
        messaggio = completion.choices[0].message
        if messaggio.tool_calls:
            _chiamata = messaggio.tool_calls[0]
            try:
                _argomenti = json.loads(_chiamata.function.arguments or "{}")
            except (ValueError, TypeError):
                _argomenti = {}
            return ("AZIONE", {"name": _chiamata.function.name, "arguments": _argomenti})
        _contenuto_risposta = (messaggio.content or "").strip()
        if _contenuto_risposta == "NESSUNA_AZIONE" or not _contenuto_risposta:
            return ("NESSUNA", None)
        return ("DOMANDA", _contenuto_risposta)
    except Exception as e:
        # Fallback sicuro: se Groq non risponde o restituisce qualcosa di
        # inatteso, si tratta come "nessuna azione" cosi' il messaggio cade
        # comunque nella chat generica invece di bloccarsi con un errore.
        print(f"[classificazione intento Google] ERRORE: {type(e).__name__}: {e}", flush=True)
        return ("NESSUNA", None)


# Non abbiamo una rubrica (nessun indirizzo Google e' salvato per gli account
# di famiglia): per scrivere un'email nuova serve che il destinatario compaia
# esplicitamente nel messaggio, riconosciuto con questa semplice espressione
# regolare - usata direttamente dentro _handle_google_agent_logic per
# ri-validare l'indirizzo estratto dal modello (mai fidarsi ciecamente di un
# dato "libero" restituito da un LLM per un'azione con effetti reali).
_RE_INDIRIZZO_EMAIL = re.compile(r"[\w.\+\-]+@[\w\-]+\.[a-zA-Z]{2,}")


def _genera_nuova_email(testo_completo):
    # Usa Groq per trasformare le indicazioni dell'utente in un oggetto +
    # corpo dell'email, nello stesso spirito di come "bozza_risposta" genera
    # il testo di una risposta (round 12), ma qui per un'email nuova senza
    # nessuna email precedente a cui agganciarsi.
    try:
        _prompt = (
            "L'utente vuole scrivere una NUOVA email (non e' una risposta a nessuna email ricevuta). "
            "Sulla base di queste indicazioni scrivi un oggetto breve e il testo di un'email educata in italiano.\n\n"
            f"Indicazioni dell'utente: {testo_completo}\n\n"
            "Rispondi SOLO in questo formato esatto, su due righe, senza altro testo:\n"
            "OGGETTO: <oggetto breve>\n"
            "CORPO: <testo del messaggio>"
        )
        _groq_api_key_locale = os.environ.get("GROQ_API_KEY")
        _client_bozza = Groq(api_key=_groq_api_key_locale)
        _completamento = _client_bozza.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=[{"role": "user", "content": _prompt}],
            max_tokens=400,
        )
        _testo = _completamento.choices[0].message.content or ""
    except Exception as e:
        print(f"[google] _genera_nuova_email fallita: {e}", flush=True)
        return None, None

    _oggetto, _corpo = None, None
    for _riga in _testo.splitlines():
        _riga = _riga.strip()
        if _riga.upper().startswith("OGGETTO:"):
            _oggetto = _riga.split(":", 1)[1].strip()
        elif _riga.upper().startswith("CORPO:"):
            _corpo = _riga.split(":", 1)[1].strip()
    if not _corpo:
        # Se il modello non ha seguito il formato richiesto, usa comunque
        # tutto il testo generato come corpo piuttosto che fallire del tutto.
        _corpo = _testo.strip()
    if not _oggetto:
        _oggetto = "(senza oggetto)"
    return _oggetto, _corpo


# --- Composizione email guidata a stati (round 19bis, richiesta esplicita ---
# dell'utente): il vecchio flusso lasciava a Groq (function calling) la
# decisione di quando un'email era "pronta" da inviare, in un solo passaggio
# - quando l'estrazione falliva (indirizzo non compilato, messaggio ambiguo),
# il classificatore poteva rispondere in modo confuso o fuori contesto (bug
# osservato dall'utente: "non ho ricevuto alcun indirizzo" quando l'aveva
# gia' scritto, o risposte generiche su un messaggio successivo non
# pertinente). Qui invece il controllo di flusso e' del tutto deterministico
# (macchina a stati in Python, mai Groq): una volta avviata la composizione,
# OGNI messaggio dell'utente viene interpretato SOLO come risposta alla
# domanda corrente (mai passato al classificatore d'intento), un passo alla
# volta, senza nessuna inferenza IA se non nel passo 4 (formattazione del
# testo finale, esplicitamente richiesta dall'utente). Lo stato e' salvato
# sia in st.session_state sia su Supabase (stesso principio del fix alle
# bozze pendenti sopra): sopravvive a un reload o a una riconnessione.
_STATO_ATTESA_INDIRIZZO = "waiting_address"
_STATO_ATTESA_OGGETTO = "waiting_subject"
_STATO_ATTESA_CORPO = "waiting_body"
_STATO_ATTESA_CONFERMA = "waiting_confirm"

_PAROLE_ANNULLA_COMPOSIZIONE = (
    "annulla", "lascia stare", "niente", "stop", "basta cosi", "basta così",
    "non importa", "cancella tutto", "dimentica",
)
_PAROLE_CONFERMA_INVIO = ("invia", "manda", "mandala", "inviala", "spediscila", "conferma", "si invia", "sì invia")


def _e_messaggio_di_annullamento(testo):
    t = (testo or "").strip().lower()
    return any(t == p or t.startswith(p + " ") or t.startswith(p + ",") for p in _PAROLE_ANNULLA_COMPOSIZIONE)


def _leggi_stato_composizione_email(utente):
    # Prima session_state (rapido, stesso giro), poi Supabase come recupero
    # (sessione persa/riavvio) - stesso schema del fix alle bozze pendenti.
    _stato_sessione = st.session_state.get("email_compose_state")
    if _stato_sessione:
        return _stato_sessione
    if not _supabase_enabled():
        return None
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/email_compose_state",
            headers=SUPABASE_HEADERS,
            params={"select": "*", "user_id": f"eq.{utente.get('id')}"},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        _righe = r.json()
        if not _righe:
            return None
        _riga = _righe[0]
        _stato = {
            "state": _riga.get("state"),
            "conn_type": _riga.get("conn_type"),
            "conn_user_id": _riga.get("conn_user_id"),
            "destinatario": _riga.get("destinatario"),
            "oggetto": _riga.get("oggetto"),
            "indicazioni": _riga.get("indicazioni_corpo"),
            "draft_id": _riga.get("draft_id"),
        }
        st.session_state["email_compose_state"] = _stato
        return _stato
    except Exception as e:
        print(f"[email] lettura stato composizione da Supabase fallita: {e}", flush=True)
        return None


def _salva_stato_composizione_email(utente, stato):
    st.session_state["email_compose_state"] = stato
    if not _supabase_enabled():
        return
    try:
        payload = {
            "user_id": utente.get("id"),
            "state": stato["state"],
            "conn_type": stato.get("conn_type"),
            "conn_user_id": stato.get("conn_user_id"),
            "destinatario": stato.get("destinatario"),
            "oggetto": stato.get("oggetto"),
            "indicazioni_corpo": stato.get("indicazioni"),
            "draft_id": stato.get("draft_id"),
        }
        requests.post(
            f"{SUPABASE_URL}/rest/v1/email_compose_state",
            headers={**SUPABASE_HEADERS, "Prefer": "resolution=merge-duplicates"},
            json=payload, timeout=SUPABASE_TIMEOUT,
        )
    except Exception as e:
        print(f"[email] salvataggio stato composizione su Supabase fallito: {e}", flush=True)


def _cancella_stato_composizione_email(utente):
    st.session_state.pop("email_compose_state", None)
    if not _supabase_enabled():
        return
    try:
        requests.delete(
            f"{SUPABASE_URL}/rest/v1/email_compose_state",
            headers=SUPABASE_HEADERS,
            params={"user_id": f"eq.{utente.get('id')}"},
            timeout=SUPABASE_TIMEOUT,
        )
    except Exception as e:
        print(f"[email] cancellazione stato composizione su Supabase fallita: {e}", flush=True)


def _genera_solo_corpo_email(oggetto, indicazioni):
    # Passo 4 del protocollo: Groq viene usato SOLO per formattare il testo
    # dell'email (tono/contenuto) sulla base delle indicazioni dell'utente -
    # l'oggetto e il destinatario restano quelli decisi dall'utente nei passi
    # precedenti, mai reinventati qui.
    try:
        _prompt = (
            "L'utente vuole scrivere una NUOVA email. Ha gia' deciso oggetto e destinatario altrove: "
            "il tuo unico compito e' scrivere SOLO il testo del messaggio (corpo dell'email), educato e in "
            "italiano, seguendo le indicazioni sul contenuto e sul tono date dall'utente. Non aggiungere "
            "un oggetto, non ripetere l'oggetto nel testo.\n\n"
            f"Oggetto (gia' deciso, solo per contesto): {oggetto}\n"
            f"Indicazioni dell'utente su cosa scrivere e con che tono: {indicazioni}\n\n"
            "Scrivi solo il testo del messaggio, senza premesse ne' indicazioni tecniche."
        )
        _client_corpo = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        _completamento = _client_corpo.chat.completions.create(
            model=FALLBACK_MODEL,
            messages=[{"role": "user", "content": _prompt}],
            max_tokens=400,
        )
        _corpo = (_completamento.choices[0].message.content or "").strip()
        return _corpo or None
    except Exception as e:
        print(f"[email] _genera_solo_corpo_email fallita: {e}", flush=True)
        return None


def _gestisci_step_composizione_email(testo_completo, utente, stato):
    """Avanza di un passo la macchina a stati della composizione email.
    Non chiama MAI il classificatore d'intento: il testo del messaggio viene
    interpretato solo come risposta al passo corrente. Ritorna il testo di
    risposta da mostrare in chat; lo stato viene gia' aggiornato/salvato
    internamente (session_state + Supabase)."""
    if _e_messaggio_di_annullamento(testo_completo):
        _cancella_stato_composizione_email(utente)
        return "Ok, ho annullato la composizione dell'email: non è stata salvata né inviata nessuna bozza."

    _fase = stato["state"]

    if _fase == _STATO_ATTESA_INDIRIZZO:
        _match = _RE_INDIRIZZO_EMAIL.search(testo_completo or "")
        if not _match:
            return "Non ho trovato un indirizzo email valido nel messaggio: a quale indirizzo devo spedirla? (scrivi \"annulla\" per lasciar perdere)"
        stato["destinatario"] = _match.group(0)
        stato["state"] = _STATO_ATTESA_OGGETTO
        _salva_stato_composizione_email(utente, stato)
        return f"Indirizzo salvato: {stato['destinatario']}. Qual è l'oggetto dell'email?"

    if _fase == _STATO_ATTESA_OGGETTO:
        _oggetto = (testo_completo or "").strip()
        if not _oggetto:
            return "Non ho capito l'oggetto: puoi ripeterlo? (scrivi \"annulla\" per lasciar perdere)"
        stato["oggetto"] = _oggetto
        stato["state"] = _STATO_ATTESA_CORPO
        _salva_stato_composizione_email(utente, stato)
        return "Oggetto salvato. Cosa devo scrivere nel testo e con che tono?"

    if _fase == _STATO_ATTESA_CORPO:
        _indicazioni = (testo_completo or "").strip()
        if not _indicazioni:
            return "Non ho capito cosa scrivere: puoi ripetere il contenuto e il tono desiderato? (scrivi \"annulla\" per lasciar perdere)"
        stato["indicazioni"] = _indicazioni
        _corpo = _genera_solo_corpo_email(stato["oggetto"], _indicazioni)
        if not _corpo:
            return "Non sono riuscito a generare il testo dell'email in questo momento: puoi riprovare a descrivere cosa scrivere?"

        creds = _get_google_credentials(stato.get("conn_type"), stato.get("conn_user_id"))
        if not creds:
            _cancella_stato_composizione_email(utente)
            return "Il collegamento con Google non è più disponibile: ho annullato la composizione, ricollega l'account e riprova."
        draft = _create_email_draft(creds, stato["destinatario"], stato["oggetto"], _corpo)
        if not draft:
            _cancella_stato_composizione_email(utente)
            return "Ho preparato il testo ma non sono riuscito a salvarlo come bozza su Gmail. Puoi riprovare da capo."

        st.session_state.setdefault("pending_google_drafts", {})
        st.session_state["pending_google_drafts"][draft["id"]] = {
            "conn_type": stato.get("conn_type"),
            "conn_user_id": stato.get("conn_user_id"),
            "to": stato["destinatario"],
            "subject": stato["oggetto"],
            "body": _corpo,
        }
        _salva_bozza_email_pendente_db(
            draft["id"], stato.get("conn_type"), stato.get("conn_user_id"), stato["destinatario"], stato["oggetto"], _corpo,
        )
        stato["draft_id"] = draft["id"]
        stato["state"] = _STATO_ATTESA_CONFERMA
        _salva_stato_composizione_email(utente, stato)
        return (
            f"Ecco la bozza per {stato['destinatario']} (oggetto: \"{stato['oggetto']}\"):\n\n"
            f"{_corpo}\n\n"
            "Scrivi \"invia\" per spedirla subito, oppure usa il pulsante di conferma qui sopra nella chat "
            "per inviarla o scartarla."
        )

    if _fase == _STATO_ATTESA_CONFERMA:
        _testo_norm = (testo_completo or "").strip().lower()
        if _testo_norm in _PAROLE_CONFERMA_INVIO:
            # Passo 5: esecuzione diretta, nessuna ulteriore inferenza IA -
            # stessa funzione _send_email_draft gia' usata dal pulsante "Invia".
            creds = _get_google_credentials(stato.get("conn_type"), stato.get("conn_user_id"))
            _inviata = creds and _send_email_draft(creds, stato["draft_id"])
            if _inviata:
                st.session_state.get("pending_google_drafts", {}).pop(stato["draft_id"], None)
                _aggiorna_stato_bozza_email_db(stato["draft_id"], "sent")
                _cancella_stato_composizione_email(utente)
                return f"Email inviata a {stato['destinatario']}."
            return "Invio non riuscito, riprova tra poco oppure usa il pulsante di conferma qui sopra nella chat."
        return (
            "La bozza è pronta e in attesa: scrivi \"invia\" per spedirla, \"annulla\" per scartarla, "
            "oppure usa il pulsante qui sopra nella chat."
        )

    # Stato non riconosciuto (non dovrebbe succedere): reset difensivo.
    _cancella_stato_composizione_email(utente)
    return "Qualcosa non ha funzionato nella composizione dell'email: ho annullato, puoi ricominciare."


def _richiesta_riguarda_famiglia(testo):
    # Rilevamento a parole chiave (stesso limite del rilevamento comandi):
    # permette di dire esplicitamente "guarda il calendario di famiglia"
    # per usare l'account condiviso anche quando e' collegato anche un
    # account personale.
    t = (testo or "").lower()
    return any(k in t for k in [
        "di famiglia", "della famiglia", "familiare", "familiari",
        "condiviso", "condivisa", "comune", "di tutti", "per tutti", "nostro", "nostra",
    ])


def _scegli_connessione_google(utente, testo_completo=""):
    # Entrambi gli account (condiviso di famiglia e personale) possono
    # essere collegati insieme: quale usare per un dato comando dipende
    # da cosa viene chiesto, non solo da cosa e' disponibile.
    # - Se la richiesta menziona esplicitamente la famiglia/il condiviso
    #   (e l'account condiviso e' collegato) -> usa quello condiviso.
    # - Altrimenti, se l'utente ha un account personale collegato -> usalo
    #   (le attivita' personali di ognuno restano sul proprio account).
    # - Altrimenti, solo per i genitori, ricade sull'account condiviso di
    #   famiglia come riserva (es. genitore senza account personale collegato).
    _uid = utente.get("id")
    _shared_collegato = _fetch_google_tokens("shared")
    if _richiesta_riguarda_famiglia(testo_completo) and _shared_collegato:
        return ("shared", None)
    if _fetch_google_tokens("personal", _uid):
        return ("personal", _uid)
    if utente.get("role") == "genitore" and _shared_collegato:
        return ("shared", None)
    return (None, None)


def _handle_google_agent_logic(azione_nome, argomenti, utente, testo_completo):
    # NOTA: "testo_completo" arriva qui SOLO per scegliere l'account giusto
    # (_scegli_connessione_google riconosce frasi come "di famiglia"/
    # "condiviso" - logica invariata, non toccata in questo round). Tutti gli
    # altri dati (articoli, destinatario, nome file, indicazioni) arrivano
    # gia' estratti e puliti in "argomenti", decisi dal classificatore
    # d'intento (_classifica_intento_google) invece che da un altro giro di
    # parsing a parole chiave su testo_completo: usare due volte lo stesso
    # testo con due logiche diverse (una per l'account, una per i parametri)
    # sarebbe stato piu' fragile che tenerle separate cosi'.
    argomenti = argomenti or {}
    if not _google_oauth_enabled():
        return "La connessione con Google non e' ancora configurata su questo server."

    conn_type, conn_user_id = _scegli_connessione_google(utente, testo_completo)
    if not conn_type:
        return (
            "Non risulta ancora nessun account Google collegato (ne' il tuo personale ne' quello di famiglia). "
            "Puoi collegarlo dalla barra laterale, sezione \"Collegamenti Google\"."
        )
    creds = _get_google_credentials(conn_type, conn_user_id)
    if not creds:
        return "Non riesco ad accedere al tuo account Google in questo momento: prova a ricollegarlo dalla barra laterale."

    # Se l'utente ha entrambi gli account collegati, chiarisce sempre quale
    # dei due ha risposto (evita ambiguita' su quale calendario/posta si sta
    # leggendo, dato che ora possono essere collegati entrambi insieme).
    _entrambi_collegati = bool(_fetch_google_tokens("personal", utente.get("id"))) and bool(_fetch_google_tokens("shared"))
    _nota_fonte = ""
    if _entrambi_collegati:
        _nota_fonte = "\n\n_(account di famiglia)_" if conn_type == "shared" else "\n\n_(il tuo account personale — per la famiglia, chiedi es. \"calendario di famiglia\")_"

    if azione_nome == "verbali_mostra_scadenza":
        return _gestisci_verbali_scadenza(utente) + _nota_fonte

    if azione_nome == "verbale_decidi":
        _azione_verbale = argomenti.get("azione")
        _nome = (argomenti.get("nome_file") or "").strip()
        if _azione_verbale not in ("tieni", "cancella"):
            return "Non ho capito se vuoi tenere o cancellare questo verbale: puoi ripetere?"
        return _gestisci_decisione_verbale(creds, _azione_verbale, _nome, utente) + _nota_fonte

    if azione_nome == "leggi_calendario":
        eventi = _list_calendar_events(creds, max_results=10)
        if eventi is None:
            return "Non sono riuscito a leggere il calendario in questo momento."
        if not eventi:
            return "Non ci sono impegni in programma nel calendario." + _nota_fonte
        righe = []
        for ev in eventi:
            _inizio = ev.get("start", {}).get("dateTime") or ev.get("start", {}).get("date") or "?"
            _titolo = ev.get("summary", "(senza titolo)")
            righe.append(f"- {_inizio}: {_titolo}")
        return "Ecco i prossimi impegni nel calendario:\n" + "\n".join(righe) + _nota_fonte

    if azione_nome == "crea_promemoria_calendario":
        _titolo_evento = (argomenti.get("titolo") or "").strip()
        _data_evento = (argomenti.get("data") or "").strip()
        _ora_evento = (argomenti.get("ora") or "").strip() or None
        if not _titolo_evento or not _data_evento:
            return "Non ho capito bene cosa devo segnare in calendario o per quando: puoi ripetere con titolo e data (anche relativa, tipo \"domani\")?"
        _evento_creato = _crea_evento_calendario_generico(creds, _titolo_evento, _data_evento, _ora_evento)
        if not _evento_creato:
            return "Non sono riuscito a creare l'evento nel calendario: la data indicata potrebbe non essere valida, o il collegamento con Google potrebbe aver bisogno di essere rinnovato."
        _quando = _data_evento + (f" alle {_ora_evento}" if _ora_evento else " (per l'intera giornata)")
        return f"✅ Aggiunto al calendario: \"{_titolo_evento}\" — {_quando}." + _nota_fonte

    if azione_nome == "lista_spesa_aggiungi":
        _articoli = argomenti.get("articoli") or []
        if not _articoli:
            return "Non ho capito quali articoli aggiungere: puoi ripetermeli?"
        _risultato = _gestisci_lista_spesa(creds, "aggiungi", _articoli, utente.get("name"))
        return (_risultato or "Non sono riuscito a completare l'operazione sulla lista della spesa.") + _nota_fonte

    if azione_nome == "lista_spesa_mostra":
        _risultato = _gestisci_lista_spesa(creds, "mostra", [], utente.get("name"))
        return (_risultato or "Non sono riuscito a leggere la lista della spesa.") + _nota_fonte

    if azione_nome == "lista_spesa_segna_comprato":
        _articoli = argomenti.get("articoli") or []
        if not _articoli:
            return "Non ho capito quali articoli segnare come comprati: puoi ripetermeli?"
        _risultato = _gestisci_lista_spesa(creds, "comprato", _articoli, utente.get("name"))
        return (_risultato or "Non sono riuscito a completare l'operazione sulla lista della spesa.") + _nota_fonte

    if azione_nome == "leggi_posta":
        emails = _list_recent_emails(creds, limit=5)
        if emails is None:
            return "Non sono riuscito a leggere la posta in questo momento."
        if not emails:
            return "Non ci sono email recenti nella posta in arrivo." + _nota_fonte
        righe = [f"- Da {em['from']} — {em['subject']}: {em['snippet']}" for em in emails]
        return "Ecco le email piu' recenti:\n" + "\n".join(righe) + _nota_fonte

    if azione_nome == "scrivi_nuova_email":
        # Round 19bis: la creazione in un solo colpo (estrai indirizzo +
        # genera oggetto/corpo + salva bozza) e' stata sostituita da una
        # macchina a stati esplicita (_gestisci_step_composizione_email),
        # su richiesta diretta dell'utente - qui si fa SOLO il primo passo:
        # capire se l'indirizzo e' gia' presente nel messaggio che ha
        # attivato l'azione (stesso controllo anti-allucinazione di sempre:
        # il modello puo' "completare" un indirizzo plausibile ma inventato
        # da un nome proprio, quindi va verificato che compaia letteralmente
        # nel testo). Se manca, si entra nello stato "in attesa
        # dell'indirizzo" e la domanda viene fatta in modo deterministico,
        # non da Groq.
        _match_indirizzo = _RE_INDIRIZZO_EMAIL.search((argomenti.get("destinatario") or "").strip())
        _destinatario = _match_indirizzo.group(0) if _match_indirizzo else None
        if _destinatario and _destinatario.lower() not in (testo_completo or "").lower():
            _destinatario = None
        if not _destinatario:
            _match_diretto = _RE_INDIRIZZO_EMAIL.search(testo_completo or "")
            if _match_diretto:
                _destinatario = _match_diretto.group(0)

        _nuovo_stato = {
            "state": _STATO_ATTESA_INDIRIZZO,
            "conn_type": conn_type,
            "conn_user_id": conn_user_id,
            "destinatario": None,
            "oggetto": None,
            "indicazioni": None,
            "draft_id": None,
        }
        if _destinatario:
            _nuovo_stato["destinatario"] = _destinatario
            _nuovo_stato["state"] = _STATO_ATTESA_OGGETTO
            _salva_stato_composizione_email(utente, _nuovo_stato)
            return f"Indirizzo: {_destinatario}. Qual è l'oggetto dell'email?"
        _salva_stato_composizione_email(utente, _nuovo_stato)
        return "A quale indirizzo email devo spedirla? (scrivi \"annulla\" in qualsiasi momento per lasciar perdere)"

    if azione_nome == "rispondi_ultima_email":
        emails = _list_recent_emails(creds, limit=1)
        if not emails:
            return "Non trovo nessuna email recente a cui rispondere."
        ultima = emails[0]
        _indicazioni = argomenti.get("indicazioni") or ""
        try:
            _prompt_bozza = (
                "Scrivi una breve risposta educata in italiano a questa email.\n"
                f"Da: {ultima['from']}\nOggetto: {ultima['subject']}\nContenuto: {ultima['snippet']}\n\n"
                f"Indicazioni dell'utente su cosa rispondere: {_indicazioni}\n\n"
                "Scrivi solo il testo della risposta, senza oggetto ne' indicazioni tecniche."
            )
            _groq_api_key_locale = os.environ.get("GROQ_API_KEY")
            _client_bozza = Groq(api_key=_groq_api_key_locale)
            _completamento = _client_bozza.chat.completions.create(
                model=FALLBACK_MODEL,
                messages=[{"role": "user", "content": _prompt_bozza}],
                max_tokens=400,
            )
            _testo_bozza = _completamento.choices[0].message.content
        except Exception:
            return "Non sono riuscito a generare il testo della risposta in questo momento."

        _mittente = ultima["from"]
        _oggetto_risposta = ultima["subject"] or "(senza oggetto)"
        if not _oggetto_risposta.lower().startswith("re:"):
            _oggetto_risposta = "Re: " + _oggetto_risposta
        draft = _create_email_draft(creds, _mittente, _oggetto_risposta, _testo_bozza)
        if not draft:
            return "Ho preparato il testo ma non sono riuscito a salvarlo come bozza su Gmail."
        st.session_state.setdefault("pending_google_drafts", {})
        st.session_state["pending_google_drafts"][draft["id"]] = {
            "conn_type": conn_type,
            "conn_user_id": conn_user_id,
            "to": _mittente,
            "subject": _oggetto_risposta,
            "body": _testo_bozza,
        }
        _salva_bozza_email_pendente_db(draft["id"], conn_type, conn_user_id, _mittente, _oggetto_risposta, _testo_bozza)
        return (
            f"Ho preparato una bozza di risposta a {_mittente} (oggetto: \"{_oggetto_risposta}\"):\n\n"
            f"{_testo_bozza}\n\n"
            "Non l'ho inviata: la trovi anche tra le bozze di Gmail, oppure usa il pulsante di conferma "
            "qui sopra nella chat per inviarla subito o scartarla."
        )

    return "Ho capito cosa intendi ma non sono riuscito a portarlo a termine: puoi riprovare?"


def build_api_messages(history, knowledge_text, history_limit=None, char_limit=None, location_text=None, current_user_name=None, documenti_correnti=None):
    history_limit = history_limit or MAX_HISTORY_MESSAGES
    char_limit = char_limit or MAX_MESSAGE_CHARS

    system_prompt = (
        "Sei Carpanet AI, l'assistente personale di Massimo (Carpanet). "
        "Rispondi sempre in italiano, in modo chiaro, utile e diretto. "
        "Per default sii conciso: vai dritto al punto e approfondisci solo se l'utente lo chiede esplicitamente "
        "(es. 'spiegami meglio', 'in dettaglio', 'più lungo').\n\n"
        f"{_contesto_temporale()}"
    )
    # Regola ferrea sulle capacita' reali: questa e' la chat generica, usata
    # SOLO quando il messaggio non ha attivato uno dei comandi reali gia'
    # riconosciuti automaticamente (calendario/posta/lista della spesa/
    # verbali audio - gestiti altrove, con vere chiamate alle API di Google,
    # MAI qui). Senza questa regola esplicita, un modello linguistico tende a
    # generare una risposta "plausibile" e completa anche per richieste che
    # non puo' davvero eseguire (creare un file, salvarlo su Drive, generare
    # un link di download) - inventando link e dettagli che sembrano reali ma
    # non lo sono. Verificato che questo e' successo davvero (richiesta di
    # una presentazione PowerPoint/Google Slides: risposta con link Drive
    # completamente finti). Questa regola ha sempre la precedenza sulle
    # istruzioni permanenti dell'utente qui sotto, che restano indicazioni di
    # stile/priorita' ma non possono mai concedere una capacita' tecnica che
    # l'app non ha davvero.
    system_prompt += (
        "\n\nREGOLA FERREA SULLE TUE CAPACITA' REALI (non violarla mai, nemmeno se le istruzioni permanenti "
        "piu' sotto sembrano suggerire il contrario): in questa conversazione generica NON hai alcun modo di "
        "creare o modificare davvero file su Google Drive/Sheets/Slides/Docs, ne' di generare link di download "
        "funzionanti. Le uniche azioni reali su Google che l'app sa fare sono attivate da comandi specifici "
        "riconosciuti automaticamente PRIMA di arrivare qui (calendario, lettura/bozze email Gmail, lista della "
        "spesa su un foglio Google dedicato, verbali audio con Google Doc + promemoria) - se stai rispondendo tu "
        "in questa chat generica, quei comandi non si sono attivati. Se l'utente chiede qualcosa che non sai "
        "davvero fare (es. creare una presentazione PowerPoint/Google Slides, un foglio Google generico, "
        "qualsiasi altro file scaricabile), NON DEVI MAI: inventare un link (docs.google.com, drive.google.com o "
        "qualsiasi URL), descrivere un'azione come gia' avvenuta ('ho creato...', 'ho salvato...', 'ecco il "
        "link...') se non l'hai davvero fatta, o dare istruzioni che presuppongono l'esistenza di un file che non "
        "esiste. Di' onestamente che questa funzione non e' ancora disponibile nell'app, e proponi un'alternativa "
        "reale che puoi davvero fare adesso (es. scrivere qui il contenuto in modo che l'utente possa copiarlo o "
        "incollarlo altrove)."
    )
    if location_text:
        system_prompt += f"\nPosizione approssimativa dell'utente: {location_text}."
    if knowledge_text and knowledge_text.strip():
        system_prompt += (
            "\n\nIndicazioni permanenti fornite dall'utente (tono, priorita', contenuti): seguile sempre PER "
            "QUESTO, ma non ti concedono mai una capacita' tecnica in piu' di quelle reali descritte sopra - "
            "in caso di conflitto vince sempre la regola sulle capacita' reali.\n"
            + knowledge_text.strip()
        )

    # Documento/i allegato/i ORA, nel messaggio corrente (round 20ter): a
    # differenza dei documenti di "addestramento" qui sotto (permanenti,
    # cercati per rilevanza), questo e' il contenuto letto al volo da un PDF/
    # Word/testo trascinato nella chat, da usare subito per rispondere -
    # bug segnalato dall'utente: prima veniva solo salvato un link, mai letto
    # davvero, quindi l'IA diceva correttamente (ma inutilmente) di non poter
    # leggere il documento. Iniettato per intero (fino al limite sotto) nel
    # prompt di sistema, cosi' NON e' soggetto al taglio a MAX_MESSAGE_CHARS
    # applicato piu' sotto alla cronologia dei messaggi.
    if documenti_correnti:
        system_prompt += "\n\nDocumento/i appena allegato/i dall'utente in questo messaggio (leggili e usali per rispondere):\n"
        for _nome_doc, _testo_doc in documenti_correnti:
            system_prompt += f"\n--- Da '{_nome_doc}' ---\n{_testo_doc}\n"

    # Documenti di addestramento (PDF/Word) caricati dall'utente: cerca i
    # passaggi piu' pertinenti rispetto all'ultima domanda e li aggiunge come
    # contesto, cosi' l'AI puo' usarli per rispondere senza doverli leggere
    # sempre tutti per intero.
    # Ogni utente vede automaticamente i documenti generali di famiglia PIU i
    # propri personali (mai quelli personali di altri account).
    ultimo_messaggio_utente = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
    estratti_documenti = search_knowledge_documents(ultimo_messaggio_utente, user_name=current_user_name)
    if estratti_documenti:
        system_prompt += "\n\nEstratti rilevanti dai documenti caricati dall'utente (usali se utili per rispondere):\n"
        for doc in estratti_documenti:
            testo_estratto = (doc.get("content_text") or "")[:1200]
            system_prompt += f"\n--- Da '{doc.get('filename')}' ---\n{testo_estratto}\n"

    api_messages = [{"role": "system", "content": system_prompt}]
    recent = history[-history_limit:]
    for m in recent:
        content = m["content"]
        if len(content) > char_limit:
            content = content[:char_limit] + "\n[...contenuto troncato...]"
        api_messages.append({"role": m["role"], "content": content})
    return api_messages


st.set_page_config(page_title="Carpanet AI", page_icon="static/icon-192.png", layout="centered")

# --- [TEST RESTYLING] Login "glassmorphism" --------------------------------
# Sfondo generale (gradient scuro/blu notte) e stile base della card del
# form, condivisi da entrambe le schermate di login (bootstrap/esistente).
# Il restringimento della card a larghezza "login" (vs. gli 820px usati per
# la chat) NON viene fatto qui, ma piu' sotto, dentro il ramo che disegna
# davvero il login (vedi nota li' per il motivo). Non tocca la logica, solo
# l'aspetto. Se in futuro si decide di tenerlo, andra' portato anche nella
# app di produzione insieme a questa modifica.
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background: radial-gradient(circle at 50% 0%, #142240 0%, #0a0e17 55%, #05070d 100%);
}
[data-testid="stHeader"] {
    background: transparent;
}
</style>
""", unsafe_allow_html=True)

# --- PWA: installazione come app sulla schermata Home -----------------------
# IMPORTANTE: un <script> inserito tramite st.markdown(unsafe_allow_html=True)
# NON viene mai eseguito dal browser (i tag <script> impostati via innerHTML
# sono inerti per specifica HTML: e' una nota "trappola" di Streamlit). Il CSS
# funziona con st.markdown perche' i <style> vengono applicati anche cosi', ma
# per eseguire davvero del JavaScript serve st.components.v1.html, che crea
# un vero iframe (srcdoc, stessa origine) in cui gli script sono eseguiti sul
# serio. Da li' si raggiunge il documento reale della pagina con
# window.parent.document, e si registrano manifest/icone/service worker sulla
# pagina vera (non sull'iframe stesso). Il controllo "se non gia' presente"
# evita di duplicare i tag ad ogni rerun di Streamlit.
components.html("""
<script>
(function() {
    var topWin = window.parent || window;
    var doc = topWin.document;
    var head = doc.head;
    if (!head || head.querySelector('link[rel="manifest"]')) { return; }

    function addTag(tag, attrs) {
        var el = doc.createElement(tag);
        for (var k in attrs) { el.setAttribute(k, attrs[k]); }
        head.appendChild(el);
        return el;
    }

    addTag('link', {rel: 'manifest', href: '/app/static/manifest.json'});
    addTag('link', {rel: 'apple-touch-icon', href: '/app/static/apple-touch-icon.png'});
    addTag('link', {rel: 'icon', type: 'image/png', sizes: '32x32', href: '/app/static/favicon-32.png'});
    addTag('link', {rel: 'icon', type: 'image/png', sizes: '16x16', href: '/app/static/favicon-16.png'});
    addTag('meta', {name: 'theme-color', content: '#0a0e17'});
    addTag('meta', {name: 'mobile-web-app-capable', content: 'yes'});
    addTag('meta', {name: 'apple-mobile-web-app-capable', content: 'yes'});
    addTag('meta', {name: 'apple-mobile-web-app-title', content: 'Carpanet AI'});
    // "default" (non "black-translucent"): il contenuto NON disegna sotto la
    // barra di stato del telefono, che resta separata e opaca. E' la scelta
    // che evita che l'orologio del telefono finisca sovrapposto alla barra
    // scura dell'app una volta installata come icona sulla Home.
    addTag('meta', {name: 'apple-mobile-web-app-status-bar-style', content: 'default'});

    // Il tag <meta name="viewport"> e' gia' presente (lo imposta Streamlit):
    // lo aggiorniamo per includere viewport-fit=cover, necessario perche' il
    // padding di sicurezza (safe-area-inset) qui sotto funzioni davvero.
    var vp = head.querySelector('meta[name="viewport"]');
    if (vp) {
        var content = vp.getAttribute('content') || '';
        if (content.indexOf('viewport-fit') === -1) {
            vp.setAttribute('content', content + ', viewport-fit=cover');
        }
    } else {
        addTag('meta', {name: 'viewport', content: 'width=device-width, initial-scale=1, viewport-fit=cover'});
    }

    // Il service worker viene servito dalla radice del sito (vedi serve.py),
    // non da /app/static/: solo cosi' il suo "scope" di default copre l'intera
    // app (incluso l'indirizzo principale "/"), requisito che Chrome/Android
    // controlla per permettere l'installazione vera e propria (altrimenti
    // compare al massimo un collegamento in stile "segnalibro", non un'app
    // installata sul serio).
    if ('serviceWorker' in topWin.navigator) {
        topWin.navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(function() {});
    }
})();
</script>
""", height=0)

# --- Lettura ad alta voce delle risposte: pulsante leggi/pausa --------------
# Un solo script, iniettato una volta sola (controllo "gia' presente" come
# sopra), che ascolta i click su QUALSIASI pulsante con classe
# "carpanet-tts-btn" (anche quelli aggiunti dopo, ad ogni rerun di Streamlit,
# perche' l'ascolto e' "delegato" sul documento intero). Espone anche due
# funzioni globali (__carpanetSpeak / __carpanetStopSpeaking) usate piu' sotto
# per la lettura automatica dopo una domanda fatta a voce e per interrompere
# la lettura quando arriva un nuovo messaggio.
components.html("""
<script>
(function() {
    var topWin = window.parent || window;
    var doc = topWin.document;
    if (!doc.body) { return; }
    if (!('speechSynthesis' in topWin)) { return; }

    // NOTA IMPORTANTE (causa reale del pulsante che "a volte" non risponde al
    // click, trovata con test ripetuti - circa 1 volta su 3): un tentativo
    // (attributo onclick scritto direttamente nell'HTML del pulsante) e'
    // stato scartato perche' Streamlit rimuove sempre gli attributi
    // "onclick" dal markdown per sicurezza (verificato). Un secondo
    // tentativo (listener "delegato" legato UNA SOLA VOLTA su document,
    // dentro l'iframe temporaneo creato da components.html) falliva
    // in modo imprevedibile: il listener risultava registrato, ma a volte
    // non veniva comunque invocato al click - probabilmente per un raro
    // problema di isolamento tra il contesto dell'iframe (che viene
    // ricreato ad ogni "rerun" di Streamlit) e il documento principale.
    // SOLUZIONE: le funzioni condivise (sintetizzatore, lettura, ecc.)
    // restano definite UNA SOLA VOLTA su "window" (persistono tra un giro e
    // l'altro), ma il listener di click viene ora ricollegato ad OGNI
    // giro - rimuovendo prima quello precedente - cosi' e' sempre legato
    // a un contesto "fresco" invece di dipendere da un unico tentativo
    // fatto al primissimo caricamento della pagina.
    if (!topWin.__carpanetTtsReady) {
    topWin.__carpanetTtsReady = true;
    var synth = topWin.speechSynthesis;
    var corrente = { bottone: null };
    // "Riscalda" subito l'elenco delle voci disponibili: su diversi browser
    // la primissima chiamata a getVoices() e' quella che avvia il
    // caricamento (altrimenti resta vuoto finche' non viene richiamata una
    // prima volta) - farlo gia' ora, alla preparazione della pagina, riduce
    // le possibilita' che al momento del click le voci non siano ancora
    // pronte.
    try { synth.getVoices(); } catch (e) {}

    // NOTA (altra causa reale trovata con test ripetuti): qui sotto si usano
    // deliberatamente "topWin.atob", "topWin.Uint8Array" e
    // "topWin.TextDecoder" - MAI le versioni "nude" (atob, Uint8Array,
    // TextDecoder) senza prefisso. Motivo: queste funzioni vivono nel
    // contesto JavaScript di QUESTO iframe temporaneo, che Streamlit puo'
    // riciclare/sostituire per un altro componente dopo il primo utilizzo;
    // quando succede, i costruttori nativi "nudi" catturati da questa
    // funzione smettono di funzionare (errore "non e' un costruttore"),
    // anche se la funzione stessa resta richiamabile da "window" della
    // pagina principale. Usando sempre "topWin.XXX" si punta invece ai
    // costruttori della pagina principale, che non viene mai ricreata.
    function decodificaB64Utf8(b64) {
        var raw = topWin.atob(b64);
        var bytes = new topWin.Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) { bytes[i] = raw.charCodeAt(i); }
        return new topWin.TextDecoder('utf-8').decode(bytes);
    }

    // Cerca una voce italiana tra quelle installate nel browser/sistema. Se
    // non ce n'e' nessuna, e' meglio NON forzare lang='it-IT' sull'utterance:
    // su diversi browser (soprattutto desktop senza pacchetto voce italiano
    // installato dal sistema operativo) questo causa un errore silenzioso
    // "language-unavailable" invece di leggere comunque con la voce di
    // default del browser.
    function trovaVoceItaliana() {
        var voci;
        try { voci = synth.getVoices() || []; } catch (e) { return null; }
        if (!voci.length) { return null; }
        var i;
        for (i = 0; i < voci.length; i++) {
            if (voci[i].lang && voci[i].lang.toLowerCase() === 'it-it') { return voci[i]; }
        }
        for (i = 0; i < voci.length; i++) {
            if (voci[i].lang && voci[i].lang.toLowerCase().indexOf('it') === 0) { return voci[i]; }
        }
        return null;
    }

    function ripristina(bottone) {
        if (corrente.bottone === bottone) {
            bottone.textContent = '🔊';
            corrente.bottone = null;
        }
    }

    // Mostra il motivo REALE dell'errore accanto al pulsante. Finora, quando
    // la lettura falliva, l'unico sintomo visibile era "non succede niente"
    // - impossibile da diagnosticare a distanza. Cosi', se fallisce ancora,
    // il motivo esatto (es. "language-unavailable", "not-allowed",
    // "audio-hardware"...) compare in pagina e puo' essere riferito in chat.
    function mostraErrore(bottone, motivo) {
        var contenitore = bottone.parentElement;
        if (!contenitore) { return; }
        var esistente = contenitore.querySelector('.carpanet-tts-errore');
        if (esistente) { esistente.remove(); }
        var elErrore = doc.createElement('span');
        elErrore.className = 'carpanet-tts-errore';
        elErrore.style.cssText = 'display:block;font-size:0.75rem;color:#ff8a8a;margin-top:2px;';
        elErrore.textContent = 'Lettura non riuscita (motivo: ' + motivo + ')';
        contenitore.appendChild(elErrore);
    }

    // NOTA (dopo due tentativi che hanno peggiorato le cose): la chiamata a
    // cancel()+speak() resta sincrona nello stesso click, senza ritardi
    // artificiali ne' "sblocchi" preventivi - un ritardo puo' far perdere ad
    // alcuni browser (soprattutto mobile) il collegamento tra il tocco
    // dell'utente e l'audio. L'unica eccezione e' l'attesa (breve, max
    // 300ms) delle voci di sintesi quando non sono ancora pronte: capita
    // solo al primissimo utilizzo su alcuni browser, ed e' comunque avviata
    // dentro la stessa catena del click, non con un ritardo indipendente.
    function leggi(bottone) {
        var testo = decodificaB64Utf8(bottone.getAttribute('data-b64'));

        function avvia() {
            var utterance = new topWin.SpeechSynthesisUtterance(testo);
            var voce = trovaVoceItaliana();
            if (voce) {
                utterance.voice = voce;
                utterance.lang = voce.lang;
            } else {
                utterance.lang = 'it-IT';
            }
            utterance.onend = function() { ripristina(bottone); };
            utterance.onerror = function(ev) {
                ripristina(bottone);
                var motivo = (ev && ev.error) ? ev.error : 'sconosciuto';
                if (motivo !== 'canceled' && motivo !== 'interrupted') {
                    mostraErrore(bottone, motivo);
                }
            };
            synth.cancel();
            corrente.bottone = bottone;
            bottone.textContent = '⏸️';
            synth.speak(utterance);
        }

        var voci_pronte = [];
        try { voci_pronte = synth.getVoices() || []; } catch (e) {}
        if (voci_pronte.length > 0) {
            avvia();
        } else {
            var gia_avviato = false;
            var timeoutId = topWin.setTimeout(function() {
                if (!gia_avviato) { gia_avviato = true; avvia(); }
            }, 300);
            synth.onvoiceschanged = function() {
                if (!gia_avviato) {
                    gia_avviato = true;
                    topWin.clearTimeout(timeoutId);
                    avvia();
                }
            };
        }
    }

    // Richiamata dal listener di click delegato (vedi piu' sotto, fuori da
    // questo blocco "una tantum": e' lui che riceve i click reali e trova il
    // pulsante corretto con closest()).
    topWin.__carpanetToggleTts = function(bottone) {
        var contenitore = bottone.parentElement;
        var erroreEsistente = contenitore ? contenitore.querySelector('.carpanet-tts-errore') : null;
        if (erroreEsistente) { erroreEsistente.remove(); }

        if (corrente.bottone === bottone && (synth.speaking || synth.paused)) {
            // Stesso pulsante, lettura in corso o in pausa: alterna pausa / riprendi.
            if (synth.paused) {
                synth.resume();
                bottone.textContent = '⏸️';
            } else {
                synth.pause();
                bottone.textContent = '▶️';
            }
            return;
        }

        // Pulsante nuovo, oppure stesso pulsante ma la lettura precedente e'
        // gia' terminata (si riparte da capo): ferma tutto e avvia quella
        // nuova.
        if (corrente.bottone && corrente.bottone !== bottone) {
            corrente.bottone.textContent = '🔊';
        }
        leggi(bottone);
    };

    // Lettura automatica (dopo una domanda fatta a voce): interrompe quella in
    // corso, se c'e', e legge la nuova risposta.
    topWin.__carpanetSpeak = function(testo) {
        if (corrente.bottone) { corrente.bottone.textContent = '🔊'; corrente.bottone = null; }
        synth.cancel();
        var utterance = new topWin.SpeechSynthesisUtterance(testo);
        var voce = trovaVoceItaliana();
        if (voce) {
            utterance.voice = voce;
            utterance.lang = voce.lang;
        } else {
            utterance.lang = 'it-IT';
        }
        synth.speak(utterance);
    };
    // Interrompe qualunque lettura in corso senza avviarne una nuova: usato
    // quando arriva un nuovo messaggio (scritto o vocale) mentre l'assistente
    // sta ancora leggendo la risposta precedente.
    topWin.__carpanetStopSpeaking = function() {
        synth.cancel();
        if (corrente.bottone) { corrente.bottone.textContent = '🔊'; corrente.bottone = null; }
    };
    } // fine "if (!topWin.__carpanetTtsReady)"

    // Da qui in poi si esegue ad OGNI giro (vedi nota sopra): ricollega il
    // listener di click, rimuovendo prima quello del giro precedente.
    if (topWin.__carpanetClickHandler) {
        doc.removeEventListener('click', topWin.__carpanetClickHandler);
    }
    topWin.__carpanetClickHandler = function(ev) {
        var bottone = ev.target && ev.target.closest ? ev.target.closest('.carpanet-tts-btn') : null;
        if (!bottone) { return; }
        ev.preventDefault();
        if (topWin.__carpanetToggleTts) { topWin.__carpanetToggleTts(bottone); }
    };
    doc.addEventListener('click', topWin.__carpanetClickHandler);
})();
</script>
""", height=0)

# --- Correzione bug nativo di Streamlit: pulsante microfono "rotto" al primo
# caricamento ---------------------------------------------------------------
# Cio' che l'utente ha descritto ("appena si scrive qualcosa il microfono si
# sistema da solo") e' in realta' un piccolo bug di Streamlit stesso: quando
# la pagina si apre, il controllo interno che verifica se la registrazione
# vocale e' disponibile a volte non fa in tempo a concludersi prima del primo
# disegno della casella di testo, e il pulsante del microfono resta bloccato
# nello stato di errore "Recording failed" (icona diventata un pallino pieno
# con un punto esclamativo, invece del microfono). Quel controllo viene
# rifatto correttamente solo quando il contenuto della casella cambia (per
# questo basta scrivere una lettera qualsiasi per "sbloccarlo"). Qui
# automatizziamo la stessa correzione appena la pagina e' pronta: scriviamo e
# cancelliamo subito, senza che l'utente se ne accorga, un carattere
# invisibile nella casella di testo (solo se e' ancora vuota), cosi'
# l'icona del microfono e la forma della casella sono gia' corrette fin dal
# primo istante, senza dover scrivere nulla.
components.html("""
<script>
(function() {
    var topWin = window.parent || window;
    var doc = topWin.document;
    if (!doc.body || doc.body.dataset.carpanetMicFixBound) { return; }
    doc.body.dataset.carpanetMicFixBound = '1';

    var tentativi = 0;
    var intervallo = setInterval(function() {
        tentativi++;
        var textarea = doc.querySelector('[data-testid="stChatInputTextArea"]');
        if (textarea && !textarea.disabled) {
            clearInterval(intervallo);
            if (textarea.value !== '') { return; }
            try {
                var setter = Object.getOwnPropertyDescriptor(
                    topWin.HTMLTextAreaElement.prototype, 'value'
                ).set;
                setter.call(textarea, ' ');
                textarea.dispatchEvent(new topWin.Event('input', { bubbles: true }));
                setTimeout(function() {
                    if (textarea.value === ' ') {
                        setter.call(textarea, '');
                        textarea.dispatchEvent(new topWin.Event('input', { bubbles: true }));
                    }
                }, 150);
            } catch (e) { /* in caso di problemi non blocchiamo la pagina */ }
            return;
        }
        if (tentativi > 30) { clearInterval(intervallo); }
    }, 300);
})();
</script>
""", height=0)

GRADIENT_CSS = "linear-gradient(135deg, #0a0e17 0%, #10162a 100%)"

st.markdown(f"""
<style>
.stApp, [data-testid="stAppViewContainer"], body {{
    background: {GRADIENT_CSS};
    color: #e6f1ff;
}}
[data-testid="stHeader"],
[data-testid="stHeader"] > div {{
    background: {GRADIENT_CSS} !important;
}}
/* Barra colorata animata che Streamlit mostra in cima alla pagina durante il
   caricamento/ricarica dello script (nativa di Streamlit, non nostra):
   rimossa su richiesta esplicita dell'utente. Coperti sia il selettore
   "data-testid" usato dalle versioni piu' recenti sia il vecchio id
   "stDecoration" usato da versioni precedenti, perche' l'elemento e'
   transitorio (visibile solo durante l'esecuzione dello script) e non e'
   stato possibile osservarlo direttamente in questo ambiente di sviluppo
   (la connessione locale e' troppo veloce perche' compaia). */
[data-testid="stDecoration"],
#stDecoration {{
    display: none !important;
}}
/* Spazio di sicurezza per la barra di stato del telefono (notch, isola
   dinamica, orologio) quando l'app e' installata come PWA a schermo intero:
   senza questo padding, sui telefoni con display "edge-to-edge" il contenuto
   puo' finire disegnato proprio sotto l'orario di sistema, facendolo sembrare
   "incollato" sopra la barra colorata dell'app. env(...) vale 0 su schermi
   senza notch/safe-area, quindi qui non cambia nulla in quel caso. */
html, body {{
    padding-top: env(safe-area-inset-top) !important;
}}
[data-testid="stHeader"] {{
    padding-top: env(safe-area-inset-top) !important;
    height: calc(3.5rem + env(safe-area-inset-top)) !important;
}}
[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"] {{
    background: {GRADIENT_CSS} !important;
}}
[data-testid="stChatInput"] {{
    border: 1.5px solid #00e5ff !important;
    border-radius: 24px !important;
    background: rgba(255,255,255,0.04) !important;
    align-items: center !important;
}}
[data-testid="stChatInput"] > div {{
    background: transparent !important;
}}
[data-testid="stChatInputTextArea"] {{
    color: #f2f6ff !important;
    font-size: 1.05rem !important;
}}
[data-testid="stChatInputTextArea"]::placeholder {{
    color: #a9b8d6 !important;
    opacity: 1 !important;
    /* Il testo del placeholder, se troppo lungo per lo schermo, andava a capo
       su piu' righe (fino a 3 su cellulare) e la casella di testo si
       allargava in verticale per contenerle, sembrando "quadrata" invece
       della normale forma a pillola. Qui lo teniamo su una riga sola e lo
       tronchiamo con i puntini: la casella resta sempre della stessa altezza
       compatta, sia vuota che con testo scritto dentro. */
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
}}
/* Icone native di st.chat_input (allega file, microfono, invia):
   NON forziamo background, border-radius, fill o stroke sugli SVG.
   Streamlit gestisce internamente lo stato di questi pulsanti (inclusa la
   visualizzazione audio "wavesurfer" durante la registrazione) e un CSS
   troppo invasivo su di essi rompe sia il contenitore della registrazione
   sia il disegno dell'icona stessa (icone diventate blocchi pieni).
   Le icone native sono gia' chiare su sfondo scuro e ben leggibili;
   ci limitiamo a un lieve aumento di opacita' per sicurezza. */
[data-testid="stChatInput"] button {{
    opacity: 1 !important;
    cursor: pointer !important;
    pointer-events: auto !important;
}}
/* Pulsante "Start recording" (microfono): stile blu neon SOLO tramite
   color/filter (mai background, border-radius o dimensioni), esattamente
   come richiesto, per non rompere la visualizzazione "wavesurfer" della
   registrazione, gia' rotta in passato da CSS troppo invasivo su questo
   pulsante specifico. */
[data-testid="stChatInputMicButton"] {{
    color: #00e5ff !important;
    cursor: pointer !important;
    pointer-events: auto !important;
    filter: drop-shadow(0 0 5px rgba(0, 229, 255, 0.85));
}}
[data-testid="stChatInputMicButton"]:hover {{
    filter: drop-shadow(0 0 9px rgba(0, 229, 255, 1));
}}
[data-testid="stChatInputMicButton"][disabled] {{
    color: #5a6b8c !important;
    filter: none;
}}
.stApp, [data-testid="stAppViewContainer"] {{
    color: #f2f6ff !important;
}}
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div,
[data-testid="stSidebarContent"] {{
    background: {GRADIENT_CSS} !important;
}}
[data-testid="stSidebar"] * {{
    color: #f2f6ff !important;
}}
/* Il tasto per aprire/chiudere la barra laterale (utile soprattutto da
   cellulare) restava "dentro" l'elenco delle conversazioni: scorrendo in
   basso per vedere le conversazioni piu' vecchie, il tasto per richiuderla
   spariva dallo schermo insieme al resto. [data-testid="stSidebarContent"]
   e' il contenitore che scorre davvero (verificato: e' lui ad avere
   overflow-y, non stSidebarUserContent); [data-testid="stSidebarHeader"],
   che contiene il tasto di chiusura, e' un suo elemento interno. Con
   "position: sticky; top: 0" resta agganciato in cima mentre il resto
   scorre sotto di lui, invece di scorrere via insieme al contenuto. */
[data-testid="stSidebarHeader"] {{
    position: sticky !important;
    top: 0 !important;
    z-index: 999999 !important;
    background: {GRADIENT_CSS} !important;
}}
[data-testid="stCaptionContainer"], .stCaption, small {{
    color: #b9c6e6 !important;
}}
.carpanet-logo {{
    display: block;
    margin: 0 auto 1rem auto;
    max-width: 320px;
    width: 100%;
}}
/* Pulsante "leggi ad alta voce / pausa" sotto ogni risposta scritta */
.carpanet-tts-btn {{
    background: rgba(0, 229, 255, 0.08) !important;
    border: 1.5px solid #00e5ff !important;
    color: #00e5ff !important;
    border-radius: 999px !important;
    width: 2.1rem;
    height: 2.1rem;
    font-size: 1.05rem;
    line-height: 1;
    cursor: pointer;
    margin-top: 0.35rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    filter: drop-shadow(0 0 4px rgba(0, 229, 255, 0.6));
}}
.carpanet-tts-btn:hover {{
    filter: drop-shadow(0 0 8px rgba(0, 229, 255, 0.9));
}}

/* --- Chat in stile "Claude": testo piu grande, spaziatura generosa, ------- */
/* --- avatar colorati, colonna di lettura piu ampia e leggibile ----------- */
.block-container {{
    max-width: 820px !important;
    padding-top: 1.5rem !important;
}}
[data-testid="stChatMessage"] {{
    padding: 1.35rem 0 !important;
    gap: 1rem !important;
    align-items: flex-start !important;
}}
[data-testid="stChatMessageContent"] {{
    font-size: 1.15rem !important;
    line-height: 1.75 !important;
}}
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li {{
    font-size: 1.15rem !important;
    line-height: 1.75 !important;
    margin-bottom: 0.6rem !important;
}}
[data-testid="stChatMessageAvatarUser"] {{
    background: linear-gradient(135deg, #00e5ff, #2b6cff) !important;
    color: #08111f !important;
}}
[data-testid="stChatMessageAvatarAssistant"] {{
    background: linear-gradient(135deg, #7c5cff, #00e5ff) !important;
    color: #08111f !important;
}}

/* --- Pagina di benvenuto dopo il login ------------------------------------ */
.carpanet-welcome {{
    text-align: center;
    padding: 2.5rem 1rem 1rem 1rem;
}}
.carpanet-welcome-logo {{
    display: block;
    margin: 0 auto 1.25rem auto;
    max-width: 180px;
    width: 55%;
}}
.carpanet-welcome h1 {{
    font-size: 2.1rem;
    margin-bottom: 0.4rem;
}}
.carpanet-welcome-sub {{
    font-size: 1.15rem;
    color: #b9c6e6;
}}

/* --- Adattamento responsive: telefono / tablet / PC ----------------------- */
@media (max-width: 640px) {{
    .block-container {{ padding-left: 0.75rem !important; padding-right: 0.75rem !important; }}
    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessageContent"] p,
    [data-testid="stChatMessageContent"] li {{
        font-size: 1.05rem !important;
        line-height: 1.65 !important;
    }}
    .carpanet-welcome h1 {{ font-size: 1.6rem; }}
    .carpanet-welcome-sub {{ font-size: 1rem; }}
    .carpanet-logo, .carpanet-welcome-logo {{ max-width: 130px; }}
}}
@media (min-width: 641px) and (max-width: 1024px) {{
    .block-container {{ max-width: 700px !important; }}
}}
@media (min-width: 1025px) {{
    .block-container {{ max-width: 880px !important; }}
    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessageContent"] p,
    [data-testid="stChatMessageContent"] li {{
        font-size: 1.2rem !important;
    }}
}}
</style>
<img class="carpanet-logo" src="data:image/jpeg;base64,{LOGO_B64}">
""", unsafe_allow_html=True)

MEMORIA_PERSISTENTE = _supabase_enabled()

# --- Posizione (best-effort, sperimentale) --------------------------------
# Nessuna nuova dipendenza pip: usiamo un piccolo componente HTML/JS che chiede
# il permesso di geolocalizzazione al browser e, se concesso, aggiunge le
# coordinate all'URL della pagina (una sola volta, alla primissima apertura,
# PRIMA del login, cosi' non si rischia mai di far ricaricare la pagina
# mentre qualcuno sta scrivendo il proprio PIN). Se il permesso viene negato
# o l'utente lo ignora, semplicemente non succede nulla: nessun loop, nessun
# blocco, l'app funziona comunque esattamente come prima.
if "user_location" not in st.session_state:
    st.session_state.user_location = None

_qp = st.query_params
if st.session_state.user_location is None and _qp.get("geo_lat") and _qp.get("geo_lon"):
    try:
        _lat = float(_qp.get("geo_lat"))
        _lon = float(_qp.get("geo_lon"))
        st.session_state.user_location = _reverse_geocode(_lat, _lon) or f"lat {_lat:.2f}, lon {_lon:.2f}"
    except Exception:
        st.session_state.user_location = None

if st.session_state.user_location is None and not _qp.get("geo_lat") and not _qp.get("geo_denied"):
    st.components.v1.html("""
    <script>
    (function () {
        try {
            // IMPORTANTE (bug scoperto e corretto durante i test del "ricordami"):
            // l'iframe di components.html e' sandboxato da Streamlit SENZA il permesso
            // "allow-top-navigation"/"allow-top-navigation-by-user-activation". Impostare
            // direttamente window.top.location.search da qui viene quindi bloccato dal
            // browser (nessun errore visibile all'utente, ma la pagina non si aggiornava
            // mai: la geolocalizzazione automatica non ha mai funzionato). Soluzione: dato
            // che l'iframe ha "allow-same-origin", puo' comunque scrivere liberamente nel
            // documento reale (window.top.document); iniettando li' un vero tag <script>,
            // quello script viene eseguito come parte della pagina reale (non sandboxata),
            // e da li' la navigazione e' permessa senza restrizioni.
            function naviga(params) {
                var topDoc = window.top.document;
                var s = topDoc.createElement('script');
                s.textContent = "(function(){try{var u=new URL(window.location.href);var p=" +
                    JSON.stringify(params) +
                    ";for(var k in p){u.searchParams.set(k,p[k]);}window.location.href=u.toString();}catch(e){}})();";
                topDoc.head.appendChild(s);
            }
            var here = new URLSearchParams(window.top.location.search);
            if (here.has('geo_lat') || here.has('geo_denied')) { return; }
            if (!navigator.geolocation) { return; }
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    naviga({geo_lat: pos.coords.latitude, geo_lon: pos.coords.longitude});
                },
                function () {
                    naviga({geo_denied: '1'});
                },
                { timeout: 8000, maximumAge: 600000 }
            );
        } catch (e) {}
    })();
    </script>
    """, height=0)

# --- Login familiare ------------------------------------------------------
# Attivo solo se la memoria persistente (Supabase) e configurata: senza un
# database esterno non c'e un posto sicuro dove tenere gli account, quindi
# in quel caso si salta il login e si trattano tutti come "genitore" (nessun
# cambiamento di comportamento rispetto a prima).
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# --- "Ricordami": accesso automatico se un token valido arriva dall'indirizzo
# della pagina (messo li' dallo script piu' sotto, che lo legge dal
# localStorage del browser). Va fatto PRIMA di mostrare il modulo di login,
# cosi' chi ha gia' un token valido non vede proprio la schermata del PIN.
_remember_invalidate_needed = st.session_state.pop("_forget_device_on_next_run", False)
if MEMORIA_PERSISTENTE and st.session_state.current_user is None:
    _rt = st.query_params.get("remember_token")
    if _rt:
        _remembered = _verify_remember_token(_rt)
        st.query_params.pop("remember_token", None)  # mai lasciarlo visibile nell'indirizzo
        if _remembered:
            st.session_state.current_user = _remembered
            st.session_state.just_logged_in = True
            st.rerun()
        else:
            # Token assente/scaduto/revocato: puliamo anche il localStorage,
            # altrimenti si ritenterebbe lo stesso token morto a ogni apertura.
            _remember_invalidate_needed = True

if MEMORIA_PERSISTENTE and st.session_state.current_user is None:
    st.components.v1.html(f"""
    <script>
    (function () {{
        try {{
            if ({"true" if _remember_invalidate_needed else "false"}) {{
                window.top.localStorage.removeItem('carpanet_remember_token');
                return;
            }}
            var here = new URLSearchParams(window.top.location.search);
            if (here.has('remember_token')) {{ return; }}
            var t = window.top.localStorage.getItem('carpanet_remember_token');
            if (t) {{
                // Stesso fix del blocco geolocalizzazione qui sopra: l'iframe di
                // components.html non ha il permesso di navigare window.top
                // direttamente (sandbox senza "allow-top-navigation"). Iniettiamo
                // quindi un vero <script> nel documento reale (window.top.document,
                // raggiungibile grazie a "allow-same-origin"), che esegue la
                // navigazione come parte della pagina vera, non sandboxata.
                var topDoc = window.top.document;
                var s = topDoc.createElement('script');
                s.textContent = "(function(){{try{{var u=new URL(window.location.href);u.searchParams.set('remember_token'," +
                    JSON.stringify(t) +
                    ");window.location.href=u.toString();}}catch(e){{}}}})();";
                topDoc.head.appendChild(s);
            }}
        }} catch (e) {{}}
    }})();
    </script>
    """, height=0)

if MEMORIA_PERSISTENTE and st.session_state.current_user is None:
    # --- [TEST RESTYLING] Card di login, versione raffinata -----------------
    # Selettori verificati con Playwright direttamente sul DOM reale di questa
    # versione di Streamlit (1.60.0), NON copiati alla cieca dal riferimento
    # di Qwen:
    #  - ".block-container" esiste davvero (verificato: count=1) ed e' la
    #    stessa classe gia' usata piu' sotto per la larghezza della chat;
    #    "[data-testid='stAppViewBlockContainer']" invece NON esiste in
    #    questa versione (count=0), quindi non va usato.
    #  - Il bottone di submit del form NON e' raggiungibile con
    #    ".stFormSubmit > button" (selettore proposto da Qwen, verificato
    #    assente: count=0) ma con "[data-testid='stForm']
    #    button[kind='secondaryFormSubmit']" (gia' in uso qui sotto),
    #    trovato ispezionando l'outerHTML reale del bottone.
    #  - Il campo "Chi sei?" NON e' un vecchio selectbox BaseWeb
    #    (div[data-baseweb="select"] non esiste piu' in questa versione,
    #    sostituito da un componente react-aria): il PIN e il nome restano
    #    semplici <input type="text"|"password">, quindi li stiliamo
    #    direttamente cosi', senza selettori BaseWeb ormai obsoleti.
    #
    # Questo blocco e' iniettato SOLO qui, dentro la schermata di login,
    # cioe' DOPO (nell'ordine della pagina) il grande blocco CSS piu' sopra
    # che fissa ".block-container" a 820px per la chat: essendo posizionato
    # dopo, questa regola (stessa specificita', anch'essa !important) vince
    # per ordine di sorgente e restringe la card SOLO in questa schermata,
    # senza toccare la larghezza della chat vera.
    st.markdown("""
<style>
.block-container {
    max-width: 440px !important;
    margin-top: 6vh !important;
    padding: 2.25rem 2rem 1.75rem 2rem !important;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 24px;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    box-shadow: 0 15px 40px rgba(0,0,0,0.55), 0 0 24px rgba(0,229,255,0.06);
}
@media (max-width: 480px) {
    .block-container {
        max-width: 92vw !important;
        margin-top: 4vh !important;
        padding: 1.75rem 1.25rem !important;
    }
}
/* Il form era gia' una "card" a se stante nella versione precedente: ora che
   la card e' l'intero .block-container, il form diventa trasparente per non
   avere una card dentro l'altra. */
[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    backdrop-filter: none !important;
    padding: 0.25rem 0 0 0 !important;
}
/* "Orb" luminoso: solo bagliore/glow (nessun logo dentro), come da v2
   approvata. Sfera con gradiente radiale che simula una luce ciano che
   "respira" cambiando leggermente scala. */
.carpanet-orb {
    width: 90px; height: 90px; border-radius: 50%;
    margin: 0 auto 14px auto;
    background: radial-gradient(circle at 35% 30%, rgba(255,255,255,.95), rgba(0,242,254,.5) 35%, rgba(8,15,28,.95) 75%);
    box-shadow: 0 0 30px rgba(0,229,255,.45), inset 0 0 18px rgba(0,0,0,.5);
    animation: carpanet-breathe 3.4s ease-in-out infinite;
}
@keyframes carpanet-breathe {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.08); }
}
.carpanet-login-title { text-align: center; margin: 0 0 0.35rem 0; }
.carpanet-login-sub { text-align: center; color: #9fb3d1; margin-bottom: 1.1rem; }

/* Campi di testo (nome, PIN, e l'input testuale del "Chi sei?"): sfondo
   scuro coerente con la card, stesso trattamento per tutti e tre perche'
   sono tutti <input type="text"|"password"> nel DOM reale. */
[data-testid="stForm"] input[type="text"],
[data-testid="stForm"] input[type="password"] {
    background-color: rgba(0,0,0,0.3) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 12px !important;
    color: #ffffff !important;
    padding: 12px !important;
}
/* Il PIN, in stile "tastierino": font piu' grande, cifre distanziate,
   centrate. Colpisce SOLO input[type="password"] (il PIN), non il nome ne'
   il campo "Chi sei?", che restano a lettura normale. */
[data-testid="stForm"] input[type="password"] {
    font-size: 22px !important;
    letter-spacing: 8px !important;
    text-align: center !important;
}
[data-testid="stForm"] input[type="text"]:focus,
[data-testid="stForm"] input[type="password"]:focus {
    border-color: #00e5ff !important;
    box-shadow: 0 0 0 1px #00e5ff, 0 0 15px rgba(0,229,255,0.25) !important;
    outline: none !important;
}
/* Pulsante di submit: gradient dal blu elettrico al ciano (selettore
   verificato sopra: kind="secondaryFormSubmit" e' quello vero). */
[data-testid="stForm"] button[kind="secondaryFormSubmit"],
[data-testid="stForm"] button[kind="formSubmit"] {
    background: linear-gradient(90deg, #2b6cff 0%, #00e5ff 100%) !important;
    border: none !important;
    color: #04121a !important;
    font-weight: 700 !important;
    width: 100% !important;
    box-shadow: 0 0 16px rgba(0, 229, 255, 0.35);
    transition: filter 0.15s ease, transform 0.15s ease;
}
[data-testid="stForm"] button[kind="secondaryFormSubmit"]:hover,
[data-testid="stForm"] button[kind="formSubmit"]:hover {
    filter: brightness(1.1);
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0, 229, 255, 0.4);
}
[data-testid="stForm"] .stCheckbox { margin-top: 0.5rem; }
</style>
<div class="carpanet-orb"></div>
""", unsafe_allow_html=True)
    st.markdown('<h2 class="carpanet-login-title">Accesso Sicuro</h2>', unsafe_allow_html=True)
    st.markdown('<p class="carpanet-login-sub">Benvenuto nel tuo Agente AI Vocale.</p>', unsafe_allow_html=True)
    existing_users = _load_family_users()
    if not existing_users:
        st.info("Nessun account ancora creato. Crea il primo account (genitore) per iniziare a usare il tuo Agente AI Vocale.")
        with st.form("bootstrap_parent_form"):
            new_name = st.text_input("Il tuo nome")
            new_pin = st.text_input("Scegli un PIN (4-6 cifre)", type="password")
            new_ricordami = st.checkbox("Ricordami su questo dispositivo (non richiedere piu' il PIN)")
            submitted = st.form_submit_button("Crea il mio Assistente")
            if submitted:
                if new_name.strip() and new_pin.strip():
                    _nuovo = _create_family_user(new_name.strip(), new_pin.strip(), "genitore")
                    if _nuovo:
                        st.session_state.current_user = _nuovo
                        st.session_state.just_logged_in = True
                        if new_ricordami:
                            _tok = _create_remember_token(_nuovo["id"], _nuovo["name"], _nuovo["role"])
                            if _tok:
                                st.session_state["_remember_token_to_store"] = _tok
                        st.rerun()
                    else:
                        st.error("Errore nella creazione dell'account. Riprova.")
                else:
                    st.warning("Inserisci nome e PIN.")
    else:
        names = [u["name"] for u in existing_users]
        with st.form("login_form"):
            selected_name = st.selectbox("Chi sei?", names)
            pin_input = st.text_input("PIN", type="password", placeholder="Il tuo PIN a 4-6 cifre")
            ricordami = st.checkbox("Ricordami su questo dispositivo (non richiedere piu' il PIN)")
            submitted = st.form_submit_button("Sblocca Assistente")
            if submitted:
                user = _verify_family_login(selected_name, pin_input)
                if user:
                    st.session_state.current_user = user
                    st.session_state.just_logged_in = True
                    if ricordami:
                        _tok = _create_remember_token(user["id"], user["name"], user["role"])
                        if _tok:
                            st.session_state["_remember_token_to_store"] = _tok
                    st.rerun()
                else:
                    st.error("PIN errato. Riprova, per favore.")
    st.stop()
elif st.session_state.current_user is None:
    # Memoria persistente non configurata: nessun posto sicuro per gli account,
    # quindi si procede senza login, con accesso completo (comportamento invariato).
    st.session_state.current_user = {"name": "Utente", "role": "genitore"}

CURRENT_ROLE = st.session_state.current_user.get("role", "genitore")
IS_PARENT = CURRENT_ROLE == "genitore"

# --- Pagina di benvenuto (a ogni login, prima della chat) -----------------
if st.session_state.get("just_logged_in"):
    # Se al login e' stato scelto "Ricordami", il token generato in quel
    # momento viene scritto ora nel localStorage del browser (qui, e non
    # subito prima del rerun del login, perche' questa pagina resta
    # visibile per un momento e da' il tempo allo script di essere davvero
    # eseguito dal browser prima di un'eventuale nuova ricarica).
    _token_da_salvare = st.session_state.pop("_remember_token_to_store", None)
    if _token_da_salvare:
        st.components.v1.html(f"""
        <script>
        try {{ window.top.localStorage.setItem('carpanet_remember_token', {json.dumps(_token_da_salvare)}); }} catch (e) {{}}
        </script>
        """, height=0)
    _nome_utente = st.session_state.current_user.get("name", "")
    # Il logo compare gia' in cima alla pagina (blocco CSS globale, sempre
    # presente su ogni schermata, .carpanet-logo). Qui sotto NON va ripetuto
    # un secondo logo: causava la "ripetizione del logo" sopra al saluto
    # segnalata dall'utente (round 20).
    st.markdown(f"""
    <div class="carpanet-welcome">
        <h1>Ciao {_nome_utente}!</h1>
        <p class="carpanet-welcome-sub">{_saluto_orario().capitalize()}! Carpanet AI e pronta ad aiutarti.</p>
    </div>
    """, unsafe_allow_html=True)
    _col1, _col2, _col3 = st.columns([1, 2, 1])
    with _col2:
        if st.button("Entra nella chat →", use_container_width=True, type="primary"):
            st.session_state.just_logged_in = False
            # Ogni ingresso in chat riparte da una conversazione nuova e vuota:
            # quelle precedenti restano salvate e consultabili dalla barra
            # laterale ("Conversazioni precedenti"), esattamente come nelle
            # altre app di intelligenza artificiale.
            if MEMORIA_PERSISTENTE:
                st.session_state.conversation_id = _create_conversation(_nome_utente)
            st.session_state.messages = []
            st.rerun()
    st.stop()

with st.sidebar:
    st.markdown("### Carpanet AI")

    if MEMORIA_PERSISTENTE:
        user_name = st.session_state.current_user.get("name", "Utente")
        role_label = "Genitore (accesso completo)" if IS_PARENT else "Figlio (accesso limitato)"
        st.caption(f"👤 {user_name} — {role_label}")
        if st.button("Esci"):
            # "Esci" annulla anche il "Ricordami" su questo dispositivo:
            # altrimenti al giro successivo il token salvato rieffettuerebbe
            # subito il login da solo, vanificando l'uscita esplicita. La
            # cancellazione vera e propria del localStorage avviene al giro
            # successivo (vedi blocco "Ricordami" sopra), non qui: uno script
            # appena prima di un rerun immediato rischierebbe di non fare in
            # tempo a essere eseguito dal browser.
            _revoke_remember_tokens(st.session_state.current_user.get("id"))
            st.session_state["_forget_device_on_next_run"] = True
            st.session_state.current_user = None
            st.rerun()
        st.caption("La memoria e collegata a un database esterno: la cronologia resta anche se Render riavvia il servizio. Al modello viene comunque inviata solo la parte piu recente per evitare errori.")
    else:
        st.caption("La cronologia mostrata resta finche il server e attivo; al modello viene inviata solo la parte piu recente per evitare errori. Se Render riavvia il servizio, tutto si azzera (database esterno non configurato).")

    if st.button("➕ Nuova conversazione", use_container_width=True):
        if MEMORIA_PERSISTENTE:
            st.session_state.conversation_id = _create_conversation(
                st.session_state.current_user.get("name", "Utente")
            )
        else:
            save_memory([])
        st.session_state.messages = []
        st.rerun()

    if MEMORIA_PERSISTENTE:
        st.markdown("---")
        st.markdown("#### 🗂️ Conversazioni precedenti")
        _nome_utente_corrente = st.session_state.current_user.get("name", "Utente")
        _ricerca_conv = st.text_input(
            "Cerca nelle conversazioni",
            placeholder="🔍 Cerca per titolo o contenuto...",
            label_visibility="collapsed",
            key="ricerca_conversazioni",
        )
        if _ricerca_conv.strip():
            _conversazioni = _search_conversations(_nome_utente_corrente, _ricerca_conv)
        else:
            _conversazioni = _list_conversations(_nome_utente_corrente)
        _conv_attiva = st.session_state.get("conversation_id")
        if not _conversazioni:
            st.caption("Nessuna conversazione trovata." if _ricerca_conv.strip() else "Nessuna conversazione precedente ancora.")
        else:
            # Contenitore a scorrimento: con tante conversazioni salvate la
            # barra laterale non si allunga all'infinito, scorre al suo interno.
            with st.container(height=320):
                for _conv in _conversazioni:
                    _titolo = _conv.get("title") or "Nuova conversazione"
                    if len(_titolo) > 28:
                        _titolo = _titolo[:28] + "…"
                    _data = (_conv.get("created_at") or "")[:16].replace("T", " ")
                    _e_pinnata = bool(_conv.get("pinned"))
                    _etichetta = f"{'🔵 ' if _conv['id'] == _conv_attiva else ''}{'📌 ' if _e_pinnata else ''}{_titolo}"
                    _col_a, _col_b, _col_c = st.columns([5, 1, 1])
                    with _col_a:
                        if st.button(_etichetta, key=f"conv_{_conv['id']}", help=_data, use_container_width=True):
                            st.session_state.conversation_id = _conv["id"]
                            st.session_state.messages = _load_conversation_messages(_conv["id"])
                            st.rerun()
                    with _col_b:
                        if st.button(
                            "📍" if _e_pinnata else "📌",
                            key=f"pin_{_conv['id']}",
                            help="Rimuovi dai preferiti" if _e_pinnata else "Fissa in cima come preferita",
                        ):
                            _toggle_pin_conversation(_conv["id"], not _e_pinnata)
                            st.rerun()
                    with _col_c:
                        _conferma_key = f"conferma_del_conv_{_conv['id']}"
                        if st.session_state.get(_conferma_key):
                            if st.button("✅", key=f"del_yes_{_conv['id']}", help="Conferma eliminazione"):
                                _delete_conversation(_conv["id"])
                                st.session_state.pop(_conferma_key, None)
                                if _conv["id"] == _conv_attiva:
                                    st.session_state.conversation_id = _create_conversation(_nome_utente_corrente)
                                    st.session_state.messages = []
                                st.rerun()
                        else:
                            if st.button("🗑️", key=f"del_{_conv['id']}", help="Elimina questa conversazione"):
                                st.session_state[_conferma_key] = True
                                st.rerun()

    st.markdown("---")
    st.markdown("#### Risposte vocali")
    if "tts_enabled" not in st.session_state:
        st.session_state.tts_enabled = True
    st.session_state.tts_enabled = st.toggle(
        "Rispondi a voce quando faccio una domanda a voce",
        value=st.session_state.tts_enabled,
        help=(
            "Se attivo, quando fai una domanda usando il microfono la risposta viene letta "
            "automaticamente ad alta voce. Se scrivi la domanda, la risposta resta solo scritta: "
            "puoi comunque farla leggere in qualsiasi momento con l'icona 🔊 sotto ogni risposta."
        ),
    )

    if IS_PARENT:
        st.markdown("---")
        st.markdown("#### Istruzioni permanenti (addestramento)")
        if MEMORIA_PERSISTENTE:
            st.caption("Scrivi qui cosa Carpanet AI deve sempre sapere o come si deve comportare: resta valido anche se la chat si azzera o Render riavvia il servizio, perche viene salvato su un database esterno.")
        else:
            st.caption("Scrivi qui cosa Carpanet AI deve sempre sapere o come si deve comportare: resta valido anche se la chat si azzera. Nota: su questo piano Render gratuito, se il servizio si riavvia per inattivita, anche queste istruzioni vengono perse finche non le salvi di nuovo (database esterno non configurato).")
        if "knowledge_text" not in st.session_state:
            st.session_state.knowledge_text = load_knowledge()
        knowledge_input = st.text_area(
            "Conoscenza permanente",
            value=st.session_state.knowledge_text,
            height=150,
            label_visibility="collapsed",
        )
        if st.button("Salva istruzioni"):
            save_knowledge(knowledge_input)
            st.session_state.knowledge_text = knowledge_input
            st.success("Istruzioni salvate.")

    _addestramento_attivo = _r2_enabled() and _supabase_enabled()

    if IS_PARENT:
        st.markdown("---")
        st.markdown("#### 📚 Addestramento generale (condiviso)")
        if _addestramento_attivo:
            st.caption(
                "Carica uno o piu PDF/Word insieme: il contenuto viene letto e usato automaticamente da "
                "Carpanet AI per rispondere alle domande pertinenti, in modo permanente, a TUTTA la famiglia. "
                "Puoi selezionarne tanti insieme dalla finestra di scelta file (tenendo premuto Ctrl o Cmd), "
                "oppure trascinarli qui tutti insieme: apri la cartella con i documenti, seleziona tutti i "
                "file al suo interno (Ctrl+A o Cmd+A) e trascina la selezione qui sopra. Nota: i browser non "
                "permettono di trascinare direttamente l'icona di una cartella intera, ma selezionare e "
                "trascinare tutti i file al suo interno funziona allo stesso modo."
            )
        else:
            st.caption("Funzione non ancora attiva: manca la configurazione dello spazio di archiviazione dedicato all'addestramento.")
        _render_gestione_documenti_addestramento(None, "shared")
    else:
        st.markdown("---")
        st.markdown("#### 📚 La tua memoria personale")
        if _addestramento_attivo:
            st.caption(
                "Carica qui uno o piu PDF/Word (anche piu' di uno insieme) con le cose che vuoi che Carpanet AI "
                "ricordi sempre quando parla con te: restano valide in aggiunta alle istruzioni generali di "
                "famiglia. Puoi anche scrivere \"addestramento\" in chat seguito da quello che vuoi ricordi."
            )
        else:
            st.caption("Funzione non ancora attiva: manca la configurazione dello spazio di archiviazione dedicato all'addestramento.")
        _render_gestione_documenti_addestramento(st.session_state.current_user.get("name"), "own")

    if IS_PARENT and MEMORIA_PERSISTENTE:
        st.markdown("---")
        with st.expander("🧒 Memoria personale dei figli"):
            st.caption(
                "Ogni figlio puo' personalizzare la propria memoria scrivendo \"addestramento\" in chat: resta "
                "valida solo nelle sue conversazioni (in aggiunta a quella generale sopra) e non puo' in nessun "
                "caso modificare le istruzioni generali di famiglia. Da qui puoi vedere e modificare la memoria "
                "personale di ciascun figlio."
            )
            _figli_famiglia = [u for u in _load_family_users() if u.get("role") == "figlio"]
            if not _figli_famiglia:
                st.caption("Nessun account 'figlio' creato per ora (puoi aggiungerne uno piu' sotto, in \"Gestione famiglia\").")
            else:
                _nomi_figli = [u["name"] for u in _figli_famiglia]
                _figlio_selezionato = st.selectbox("Figlio", _nomi_figli, key="selezione_figlio_memoria")
                if _figlio_selezionato:
                    _render_gestione_documenti_addestramento(_figlio_selezionato, f"child_{_figlio_selezionato}")

    if IS_PARENT:
        st.markdown("---")
        st.markdown("#### 📊 Graphify — statistiche")
        if MEMORIA_PERSISTENTE:
            try:
                r = requests.get(
                    f"{SUPABASE_URL}/rest/v1/chat_messages",
                    headers=SUPABASE_HEADERS,
                    params={"select": "role,created_at", "order": "id.asc"},
                    timeout=SUPABASE_TIMEOUT,
                )
                r.raise_for_status()
                rows = r.json()
                if rows:
                    import pandas as pd
                    df = pd.DataFrame(rows)
                    df["giorno"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d")
                    per_day = df.groupby("giorno").size()
                    st.caption(f"Messaggi totali salvati: {len(rows)}")
                    st.bar_chart(per_day)
                    per_role = df.groupby("role").size()
                    st.caption("Messaggi per ruolo (utente / assistente):")
                    st.bar_chart(per_role)
                else:
                    st.caption("Nessun dato ancora disponibile per i grafici.")
            except Exception:
                st.caption("Statistiche non disponibili al momento (problema di connessione al database).")
        else:
            st.caption("I grafici dettagliati richiedono la memoria persistente su database (Supabase), attualmente attiva. Se non e raggiungibile, qui non vedrai dati.")

    st.markdown("---")
    st.markdown("#### 📎 Allegati")
    ALLEGATI_ATTIVI = _r2_enabled()
    if ALLEGATI_ATTIVI:
        st.caption("Gli allegati inviati dalla chat vengono salvati in modo permanente nello spazio dedicato.")
    else:
        st.caption("Il salvataggio permanente degli allegati non e ancora configurato: gli allegati verranno comunque accettati nella chat ma non salvati, finche non vengono aggiunte le credenziali dello spazio di archiviazione.")

    if MEMORIA_PERSISTENTE:
        _render_google_connection_ui()

    if IS_PARENT and MEMORIA_PERSISTENTE:
        st.markdown("---")
        st.markdown("#### 👨‍👩‍👧‍👦 Gestione famiglia")
        st.caption("Aggiungi un altro membro della famiglia (genitore o figlio). Chi ha ruolo 'figlio' non vede le istruzioni permanenti, le statistiche Graphify, ne puo azzerare la conversazione.")
        with st.form("add_family_member_form"):
            member_name = st.text_input("Nome")
            member_pin = st.text_input("PIN (4-6 cifre)", type="password")
            member_role = st.selectbox("Ruolo", ["figlio", "genitore"])
            add_submitted = st.form_submit_button("Aggiungi membro")
            if add_submitted:
                if member_name.strip() and member_pin.strip():
                    if _create_family_user(member_name.strip(), member_pin.strip(), member_role):
                        st.success(f"Account creato per {member_name.strip()} ({member_role}).")
                    else:
                        st.error("Errore nella creazione dell'account (nome forse gia usato). Riprova.")
                else:
                    st.warning("Inserisci nome e PIN.")

groq_api_key = os.environ.get("GROQ_API_KEY")

if not groq_api_key:
    st.error("GROQ_API_KEY non trovata nelle impostazioni di Render.")
else:
    client = Groq(api_key=groq_api_key)

    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if MEMORIA_PERSISTENTE and st.session_state.conversation_id is None:
        # Rete di sicurezza: se per qualche motivo si arriva qui senza essere
        # passati dalla pagina di benvenuto (che crea normalmente la nuova
        # conversazione), ne creiamo comunque una invece di lasciare la chat
        # senza un posto dove salvare i messaggi.
        st.session_state.conversation_id = _create_conversation(
            st.session_state.current_user.get("name", "Utente")
        )
    if "messages" not in st.session_state:
        if MEMORIA_PERSISTENTE:
            st.session_state.messages = _load_conversation_messages(st.session_state.conversation_id)
        else:
            st.session_state.messages = load_memory()
    if "knowledge_text" not in st.session_state:
        st.session_state.knowledge_text = load_knowledge()

    # Nota: il messaggio di benvenuto/saluto viene mostrato in una pagina a se'
    # stante subito dopo il login (vedi sopra, prima della sidebar), non piu'
    # come banner dentro la chat.

    # Nota tecnica: Streamlit 1.60 supporta nativamente allegati (accept_file) e
    # registrazione vocale (accept_audio) direttamente dentro st.chat_input, con
    # gestione touch/mobile curata dal team di Streamlit stesso. Usiamo questa
    # funzione nativa invece di ricostruire microfono/allegati a mano via
    # JavaScript: e' il fix definitivo al problema di selezione touch, perche
    # non c'e piu nessun elemento "estraneo" iniettato dentro la barra di input
    # che possa entrare in conflitto con i controlli nativi del browser.

    # Il pulsante 🔊 viene mostrato solo sull'ULTIMO messaggio dell'assistente
    # (non su ogni risposta passata): su richiesta esplicita dell'utente, per
    # ridurre la confusione di avere piu' pulsanti di lettura contemporanei
    # nella stessa schermata.
    # Nota tecnica: qui sotto NON sappiamo ancora se in questo stesso giro di
    # esecuzione arrivera' anche una risposta nuova (lo sapremo solo piu'
    # sotto, dopo aver letto il campo di chat) - percio' per l'ultimo
    # messaggio si usa un segnaposto vuoto (st.empty), riempito subito dopo
    # con il pulsante SOLO se non sta per arrivare una risposta piu' recente
    # nello stesso giro (altrimenti il pulsante verrebbe mostrato due volte:
    # qui e sulla risposta nuova appena generata).
    _indice_ultimo_messaggio = len(st.session_state.messages) - 1
    _segnaposto_pulsante_ultimo = None
    for _indice_messaggio, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and _indice_messaggio == _indice_ultimo_messaggio:
                _segnaposto_pulsante_ultimo = st.empty()

    if not st.session_state.messages:
        st.caption(
            "🎙️ Se il microfono mostra \"Recording failed\" o non registra, il browser ha "
            "probabilmente bloccato il permesso in passato: tocca l'icona del lucchetto/informazioni "
            "accanto all'indirizzo del sito, apri i permessi e consenti il Microfono, poi ricarica la pagina."
        )

    # Bozze email in attesa di conferma (create dal comando Google in chat):
    # restano visibili qui, fuori dal normale ciclo dei messaggi, cosi'
    # sopravvivono a un rerun di Streamlit finche' non vengono inviate o
    # scartate esplicitamente. Non si invia MAI un'email dal solo testo
    # scritto in chat: serve sempre questo pulsante di conferma esplicito.
    #
    # Riconciliazione con Supabase (bug reale round 19, "non vedo il
    # pulsante"): st.session_state da solo non sopravvive a un reload della
    # pagina o a un riavvio del server - la bozza pero' esiste gia' su Gmail
    # E su Supabase (_salva_bozza_email_pendente_db), quindi ad ogni giro si
    # recuperano da li' le bozze ancora pendenti dell'utente corrente e si
    # ricostruisce session_state se mancante, invece di lasciare il pulsante
    # sparire silenziosamente.
    st.session_state.setdefault("pending_google_drafts", {})
    if st.session_state.get("current_user"):
        for _riga_db in _elenca_bozze_email_pendenti_db(st.session_state.current_user):
            _id_bozza_db = _riga_db.get("draft_id")
            if _id_bozza_db and _id_bozza_db not in st.session_state["pending_google_drafts"]:
                st.session_state["pending_google_drafts"][_id_bozza_db] = {
                    "conn_type": _riga_db.get("conn_type"),
                    "conn_user_id": _riga_db.get("conn_user_id"),
                    "to": _riga_db.get("to_addr"),
                    "subject": _riga_db.get("subject"),
                    "body": _riga_db.get("body"),
                }

    _bozze_google_in_sospeso = st.session_state.get("pending_google_drafts") or {}
    if _bozze_google_in_sospeso:
        st.markdown("---")
        st.markdown("##### ✉️ Bozza email in attesa di conferma")
        for _draft_id, _info in list(_bozze_google_in_sospeso.items()):
            with st.container(border=True):
                st.caption(f"A: {_info['to']}  \nOggetto: {_info['subject']}")
                st.write(_info["body"])
                _col_invia, _col_scarta = st.columns(2)
                with _col_invia:
                    if st.button("✅ Invia", key=f"invia_bozza_{_draft_id}", use_container_width=True):
                        _creds_invio = _get_google_credentials(_info["conn_type"], _info["conn_user_id"])
                        if _creds_invio and _send_email_draft(_creds_invio, _draft_id):
                            st.session_state["pending_google_drafts"].pop(_draft_id, None)
                            _aggiorna_stato_bozza_email_db(_draft_id, "sent")
                            st.success("Email inviata.")
                            st.rerun()
                        else:
                            st.error("Invio non riuscito. Riprova.")
                with _col_scarta:
                    if st.button("🗑️ Scarta", key=f"scarta_bozza_{_draft_id}", use_container_width=True):
                        st.session_state["pending_google_drafts"].pop(_draft_id, None)
                        _aggiorna_stato_bozza_email_db(_draft_id, "discarded")
                        st.rerun()

    user_input = st.chat_input(
        "Chiedimi qualcosa, usa il microfono o allega un file...",
        accept_file="multiple",
        file_type=["png", "jpg", "jpeg", "heic", "webp", "mp4", "mov", "avi", "webm", "pdf", "doc", "docx", "txt"],
        accept_audio=True,
        audio_sample_rate=16000,
    )

    if user_input:
        testo_scritto = (user_input.text or "").strip()
        # Tiene traccia se QUESTO messaggio e arrivato tramite microfono: serve
        # dopo per decidere se leggere la risposta ad alta voce in automatico
        # (solo se la domanda e stata fatta a voce) oppure lasciarla solo scritta.
        _input_era_vocale = user_input.audio is not None
        trascrizione_audio = ""
        _audio_non_trascritto = False

        if user_input.audio is not None:
            try:
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio.wav", user_input.audio.getvalue()),
                    language="it",
                )
                trascrizione_audio = (transcription.text or "").strip()
            except Exception:
                _audio_non_trascritto = True

        if testo_scritto and trascrizione_audio:
            testo_completo = (testo_scritto + " " + trascrizione_audio).strip()
        else:
            testo_completo = testo_scritto or trascrizione_audio

        _file_allegati = user_input.files or []
        # Testo dei documenti allegati ORA e letti con successo (round
        # 20ter): lista di tuple (nome, testo), popolata solo nel ramo della
        # chat generica sotto. Inizializzata qui cosi' e' sempre definita,
        # qualunque ramo (email/addestramento/verbale/comando Google) venga
        # preso per questo messaggio.
        _testi_allegati_correnti = []

        # Composizione email guidata a stati (round 19bis): se l'utente ha
        # gia' una composizione in corso, QUALUNQUE messaggio arrivi ora va
        # interpretato solo come risposta al passo corrente - ha la priorita'
        # assoluta su addestramento/verbale/classificatore Google, cosi' il
        # protocollo resta rigido come richiesto (l'IA non decide piu' da
        # sola quando/se instradare la richiesta).
        _stato_composizione_email = _leggi_stato_composizione_email(st.session_state.current_user)
        _composizione_email_attiva = _stato_composizione_email is not None

        _resto_addestramento = _testo_comando_addestramento(testo_completo) if not _composizione_email_attiva else None
        _comando_addestramento_attivo = (not _composizione_email_attiva) and _resto_addestramento is not None
        # Creazione di un nuovo verbale audio: come l'addestramento, ha
        # sempre precedenza sul normale comando Google (calendario/posta/
        # lista spesa), perche' richiede l'audio grezzo appena registrato,
        # non solo il testo trascritto.
        _comando_verbale_nuovo_attivo = (
            (not _composizione_email_attiva) and (not _comando_addestramento_attivo) and _testo_comando_verbale_nuovo(testo_completo)
        )
        # Il comando Google (calendario/posta/lista spesa/verbali) e'
        # controllato solo se non sono gia' attivi i due comandi sopra, per
        # evitare ambiguita' tra loro. Da questo round non e' piu' un
        # controllo a parole chiave: e' Groq stesso (function calling) a
        # capire dal significato del messaggio se si tratta di una di queste
        # azioni, chiedendo un chiarimento se manca un dettaglio invece di
        # indovinare - vedi _classifica_intento_google.
        _argomenti_google = None
        if _composizione_email_attiva or _comando_addestramento_attivo or _comando_verbale_nuovo_attivo:
            _comando_google = None
        else:
            _tipo_intento_google, _valore_intento_google = _classifica_intento_google(
                testo_completo, st.session_state.messages, st.session_state.current_user,
            )
            if _tipo_intento_google == "AZIONE":
                _comando_google = _valore_intento_google["name"]
                _argomenti_google = _valore_intento_google["arguments"]
            elif _tipo_intento_google == "DOMANDA":
                # Sentinella interna (non un vero nome di azione): segnala al
                # ramo di dispatch piu' sotto che la risposta e' gia' pronta
                # (la domanda di chiarimento stessa), senza toccare Google.
                _comando_google = "chiarimento_google"
                _argomenti_google = {"domanda": _valore_intento_google}
            else:
                _comando_google = None

        if _composizione_email_attiva:
            # Passo corrente della macchina a stati: il testo scritto/detto
            # ora e' SOLO la risposta alla domanda in sospeso (indirizzo,
            # oggetto, corpo o conferma) - mai mandato al classificatore.
            prompt = testo_completo if testo_completo else "(nessuna risposta)"
            risposta_composizione_email = _gestisci_step_composizione_email(
                testo_completo, st.session_state.current_user, _stato_composizione_email,
            )
        elif _comando_addestramento_attivo:
            # Il comando "addestramento" salva testo/file nella memoria
            # permanente invece di essere mandato all'AI come domanda normale:
            # gli allegati vanno quindi nello spazio dedicato all'addestramento,
            # non tra gli allegati occasionali della chat.
            prompt = testo_completo if testo_completo else "addestramento"
            risposta_addestramento = _gestisci_addestramento(
                _resto_addestramento,
                _file_allegati,
                st.session_state.current_user.get("name", "Utente"),
                IS_PARENT,
            )
        elif _comando_verbale_nuovo_attivo:
            # Il comando "verbale" (stesso schema di "addestramento": parola
            # all'inizio del messaggio) trascrive, riassume e salva un nuovo
            # verbale audio, invece di essere mandato all'AI come domanda
            # normale. Richiede un vocale registrato nello stesso messaggio.
            prompt = testo_completo if testo_completo else "verbale"
            if user_input.audio is None:
                risposta_verbale_nuovo = (
                    "Per creare un verbale registra un messaggio vocale che inizi con \"verbale\": "
                    "lo trascrivo, salvo l'audio su Google Drive e creo il documento del verbale scritto."
                )
            else:
                risposta_verbale_nuovo = _gestisci_nuovo_verbale(
                    st.session_state.current_user, user_input.audio.getvalue(), trascrizione_audio,
                )
        else:
            notes = []
            if _audio_non_trascritto:
                notes.append("[Audio ricevuto ma non e stato possibile trascriverlo]")
            # Bug segnalato dall'utente (round 20ter): un PDF/Word/testo
            # trascinato nella chat normale veniva solo caricato su R2 e
            # citato con un link nella nota - MAI letto davvero, quindi l'IA
            # rispondeva (correttamente, ma in modo inutile) di non poter
            # leggere il documento. Ora, per le estensioni con estrazione
            # testo disponibile, il contenuto viene estratto qui e passato a
            # build_api_messages perche' l'AI lo legga per davvero in questa
            # stessa risposta (vedi _testi_allegati_correnti sotto).
            _ESTENSIONI_TESTO_ALLEGATI = (".pdf", ".doc", ".docx", ".txt")
            for f in _file_allegati:
                file_bytes = f.getvalue()
                r2_link = r2_upload(file_bytes, f.name, R2_BUCKET_ALLEGATI, R2_PUBLIC_URL_ALLEGATI)
                _estensione_allegato = os.path.splitext(f.name)[1].lower()
                _testo_allegato = ""
                if _estensione_allegato == ".pdf":
                    _testo_allegato = _extract_pdf_text(file_bytes)
                elif _estensione_allegato in (".doc", ".docx"):
                    _testo_allegato = _extract_docx_text(file_bytes)
                elif _estensione_allegato == ".txt":
                    try:
                        _testo_allegato = file_bytes.decode("utf-8", errors="replace").strip()
                    except Exception:
                        _testo_allegato = ""

                if _testo_allegato:
                    # Limite generoso (alcune pagine): la lista dei documenti
                    # correnti va nel prompt di sistema, non nella cronologia,
                    # quindi non e' soggetta al taglio a MAX_MESSAGE_CHARS.
                    _testi_allegati_correnti.append((f.name, _testo_allegato[:15000]))
                    if r2_link is not None:
                        notes.append(f"[Documento allegato e letto: {f.name} ({r2_link})]")
                    else:
                        notes.append(f"[Documento allegato e letto: {f.name}]")
                elif _estensione_allegato in _ESTENSIONI_TESTO_ALLEGATI:
                    if r2_link is not None:
                        notes.append(f"[Allegato salvato: {f.name} ({r2_link}) — non sono riuscito a estrarne il testo, forse e' un PDF scansionato senza testo selezionabile]")
                    else:
                        notes.append(f"[Allegato ricevuto: {f.name} — non salvato in modo permanente perche lo spazio di archiviazione non e ancora configurato o non e raggiungibile, e non sono riuscito a estrarne il testo]")
                elif r2_link is not None:
                    notes.append(f"[Allegato salvato: {f.name} ({r2_link})]")
                else:
                    notes.append(f"[Allegato ricevuto: {f.name} — non salvato in modo permanente perche lo spazio di archiviazione non e ancora configurato o non e raggiungibile]")

            prompt = testo_completo
            if notes:
                prompt = (prompt + "\n\n" + "\n".join(notes)).strip() if prompt else "\n".join(notes)

    else:
        prompt = None
        _input_era_vocale = False
        _composizione_email_attiva = False
        _comando_addestramento_attivo = False
        _comando_verbale_nuovo_attivo = False
        _comando_google = None
        _argomenti_google = None
        _testi_allegati_correnti = []

    # Ora che sappiamo se in questo giro arriva anche una risposta nuova,
    # possiamo riempire (o lasciare vuoto) il segnaposto del pulsante 🔊
    # sull'ultimo messaggio gia' esistente - vedi nota sopra nel ciclo che
    # mostra la cronologia.
    if _segnaposto_pulsante_ultimo is not None and not prompt and st.session_state.messages:
        _b64_msg_ultimo = base64.b64encode(st.session_state.messages[-1]["content"].encode("utf-8")).decode("ascii")
        _segnaposto_pulsante_ultimo.markdown(
            f'<button class="carpanet-tts-btn" data-b64="{_b64_msg_ultimo}" title="Leggi ad alta voce / pausa">🔊</button>',
            unsafe_allow_html=True,
        )

    if prompt:
        # Un nuovo messaggio ha sempre la priorita': se l'assistente sta ancora
        # leggendo ad alta voce la risposta precedente, la interrompe subito
        # (la nuova risposta arrivera' scritta o a voce a seconda di come e
        # arrivato QUESTO messaggio, deciso piu' sotto).
        components.html("""
        <script>
        (function() {
            var topWin = window.parent || window;
            if (topWin.__carpanetStopSpeaking) { topWin.__carpanetStopSpeaking(); }
            else if (topWin.speechSynthesis) { topWin.speechSynthesis.cancel(); }
        })();
        </script>
        """, height=0)

        st.session_state.messages.append({"role": "user", "content": prompt})
        if MEMORIA_PERSISTENTE:
            _era_conversazione_vuota = len(st.session_state.messages) == 1
            _append_message(st.session_state.conversation_id, "user", prompt)
            if _era_conversazione_vuota:
                _righe = prompt.strip().splitlines()
                _titolo_breve = (_righe[0][:60] if _righe else "Nuova conversazione")
                _update_conversation_title(st.session_state.conversation_id, _titolo_breve)
        else:
            save_memory(st.session_state.messages)
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = None

            if _composizione_email_attiva:
                # Macchina a stati per l'email: la risposta al passo corrente
                # e' gia' stata calcolata sopra, nessuna chiamata generica
                # all'AI qui.
                response = risposta_composizione_email
            elif _comando_addestramento_attivo:
                # Comando di addestramento: nessuna chiamata all'AI, si usa
                # direttamente la conferma (o il messaggio d'errore) gia'
                # preparata sopra durante la gestione dell'allegato/testo.
                response = risposta_addestramento
            elif _comando_verbale_nuovo_attivo:
                # Comando "verbale": stesso schema, la risposta e' gia' stata
                # preparata sopra (creazione vera del verbale, o richiesta di
                # registrare un vocale se non ne era presente uno).
                response = risposta_verbale_nuovo
            elif _comando_google == "chiarimento_google":
                # Il classificatore ha riconosciuto che la richiesta riguarda
                # una di queste azioni ma mancano dettagli per eseguirla
                # davvero (es. quale indirizzo, quale articolo, quale
                # verbale): si fa la domanda di chiarimento gia' pronta,
                # invece di indovinare o di cadere nella chat generica (che
                # comunque non saprebbe eseguire l'azione).
                response = _argomenti_google["domanda"]
            elif _comando_google:
                # Comando Google riconosciuto dal significato del messaggio
                # (non piu' da parole chiave fisse): niente chiamata al
                # modello Groq per la risposta principale, si usa Calendar/
                # Gmail/Sheets/Drive direttamente tramite l'account collegato
                # dall'utente (o quello condiviso di famiglia, se genitore).
                response = _handle_google_agent_logic(_comando_google, _argomenti_google, st.session_state.current_user, testo_completo)
            else:
                def is_too_large_error(exc):
                    msg = str(exc).lower()
                    return "413" in str(exc) or "too large" in msg or "request_too_large" in msg or "rate_limit" in msg

                try:
                    api_messages = build_api_messages(
                        st.session_state.messages,
                        st.session_state.get("knowledge_text", ""),
                        location_text=st.session_state.get("user_location"),
                        current_user_name=st.session_state.current_user.get("name"),
                        documenti_correnti=_testi_allegati_correnti,
                    )
                    completion = client.chat.completions.create(
                        model=PRIMARY_MODEL,
                        messages=api_messages,
                        max_tokens=PRIMARY_MAX_TOKENS,
                    )
                    response = completion.choices[0].message.content
                except Exception as e:
                    if is_too_large_error(e):
                        try:
                            fallback_messages = build_api_messages(
                                st.session_state.messages,
                                st.session_state.get("knowledge_text", ""),
                                history_limit=3,
                                char_limit=600,
                                location_text=st.session_state.get("user_location"),
                                current_user_name=st.session_state.current_user.get("name"),
                            )
                            fallback_completion = client.chat.completions.create(
                                model=FALLBACK_MODEL,
                                messages=fallback_messages,
                                max_tokens=FALLBACK_MAX_TOKENS,
                            )
                            response = fallback_completion.choices[0].message.content
                        except Exception as e2:
                            st.error("La richiesta era troppo grande anche per il modello di riserva. Prova a fare una domanda piu breve o dividila in piu messaggi.")
                    else:
                        st.error(f"Errore generazione: {e}")

            if response is not None:
                st.markdown(response)
                _b64_risposta = base64.b64encode(response.encode("utf-8")).decode("ascii")
                st.markdown(
                    f'<button class="carpanet-tts-btn" data-b64="{_b64_risposta}" title="Leggi ad alta voce / pausa">🔊</button>',
                    unsafe_allow_html=True,
                )
                st.session_state.messages.append({"role": "assistant", "content": response})
                if MEMORIA_PERSISTENTE:
                    _append_message(st.session_state.conversation_id, "assistant", response)
                else:
                    save_memory(st.session_state.messages)

                # Lettura automatica SOLO se la domanda e' arrivata a voce:
                # se e' stata scritta, la risposta resta solo testo (si puo'
                # comunque far leggere in ogni momento con il pulsante 🔊 qui sopra).
                if _input_era_vocale and st.session_state.get("tts_enabled", True):
                    components.html(f"""
                    <script>
                    (function() {{
                        var topWin = window.parent || window;
                        if (topWin.__carpanetSpeak) {{ topWin.__carpanetSpeak({json.dumps(response)}); }}
                    }})();
                    </script>
                    """, height=0)
