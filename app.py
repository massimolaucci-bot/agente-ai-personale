import os
import json
import base64
import hashlib
import requests
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
from datetime import datetime
from zoneinfo import ZoneInfo

MEMORY_FILE = "chat_memory.json"
KNOWLEDGE_FILE = "knowledge.json"

MAX_HISTORY_MESSAGES = 6    # quante battute recenti mandare al modello ad ogni richiesta
MAX_MESSAGE_CHARS = 1500    # lunghezza massima di un singolo messaggio inviato al modello
MAX_SAVED_MESSAGES = 200    # quante battute tenere salvate su disco per la visualizzazione

PRIMARY_MODEL = "groq/compound"
FALLBACK_MODEL = "llama-3.3-70b-versatile"
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
    if not _supabase_enabled():
        return False
    try:
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/family_users",
            headers=SUPABASE_HEADERS,
            json={"name": name, "pin_hash": _hash_pin(pin), "role": role},
            timeout=SUPABASE_TIMEOUT,
        )
        r.raise_for_status()
        return True
    except Exception:
        return False


def build_api_messages(history, knowledge_text, history_limit=None, char_limit=None, location_text=None, current_user_name=None):
    history_limit = history_limit or MAX_HISTORY_MESSAGES
    char_limit = char_limit or MAX_MESSAGE_CHARS

    system_prompt = (
        "Sei Carpanet AI, l'assistente personale di Massimo (Carpanet). "
        "Rispondi sempre in italiano, in modo chiaro, utile e diretto. "
        "Per default sii conciso: vai dritto al punto e approfondisci solo se l'utente lo chiede esplicitamente "
        "(es. 'spiegami meglio', 'in dettaglio', 'più lungo').\n\n"
        f"{_contesto_temporale()}"
    )
    if location_text:
        system_prompt += f"\nPosizione approssimativa dell'utente: {location_text}."
    if knowledge_text and knowledge_text.strip():
        system_prompt += (
            "\n\nInformazioni e istruzioni permanenti fornite dall'utente: seguile sempre.\n"
            + knowledge_text.strip()
        )

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
    if (!doc.body || doc.body.dataset.carpanetTtsBound) { return; }
    doc.body.dataset.carpanetTtsBound = '1';

    if (!('speechSynthesis' in topWin)) { return; }
    var synth = topWin.speechSynthesis;
    var corrente = { bottone: null };

    function decodificaB64Utf8(b64) {
        var raw = atob(b64);
        var bytes = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) { bytes[i] = raw.charCodeAt(i); }
        return new TextDecoder('utf-8').decode(bytes);
    }

    // Chrome (desktop e Android) ha un bug noto e molto diffuso: se si chiama
    // speak() troppo a ridosso di un cancel() (nello stesso istante), oppure
    // se il motore di sintesi vocale e' rimasto "fermo" per qualche secondo
    // dopo l'ultima lettura, le chiamate successive a speak() possono fallire
    // in silenzio (nessun audio, nessun evento onstart/onend: il pulsante
    // resta come "bloccato"). Questo e' esattamente il comportamento
    // descritto: la prima lettura funziona, quelle dopo no. Il rimedio
    // raccomandato e' annullare sempre prima, aspettare un istante brevissimo
    // e SOLO DOPO avviare la nuova lettura (mai speak() subito dopo cancel()
    // nello stesso istante).
    function avvia(bottone, testo) {
        var utterance = new topWin.SpeechSynthesisUtterance(testo);
        utterance.lang = 'it-IT';
        utterance.onend = function() {
            if (corrente.bottone === bottone) { bottone.textContent = '🔊'; corrente.bottone = null; }
        };
        utterance.onerror = function() {
            if (corrente.bottone === bottone) { bottone.textContent = '🔊'; corrente.bottone = null; }
        };
        corrente.bottone = bottone;
        corrente.utterance = utterance;
        bottone.textContent = '⏸️';
        synth.speak(utterance);
    }

    function leggi(bottone) {
        var testo = decodificaB64Utf8(bottone.getAttribute('data-b64'));
        synth.cancel();
        setTimeout(function() { avvia(bottone, testo); }, 80);
    }

    doc.addEventListener('click', function(ev) {
        var bottone = ev.target && ev.target.closest ? ev.target.closest('.carpanet-tts-btn') : null;
        if (!bottone) { return; }
        ev.preventDefault();

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
        // nuova, sempre passando dal cancel() + piccola attesa di leggi().
        if (corrente.bottone && corrente.bottone !== bottone) {
            corrente.bottone.textContent = '🔊';
        }
        leggi(bottone);
    });

    // "Sblocco" del motore vocale al primissimo tocco/click sulla pagina:
    // su alcuni browser (soprattutto mobile) la sintesi vocale resta
    // silenziosa finche' non viene "attivata" da un gesto dell'utente.
    // IMPORTANTE: un'utterance con testo VUOTO ('') puo' restare bloccata per
    // sempre nella coda su alcuni browser (Chrome in particolare), perche' non
    // arriva mai a generare l'evento di fine lettura: il risultato e' che
    // TUTTE le letture successive restano mute, anche quella dal pulsante
    // 🔊 (bug scoperto dopo il rilascio). Per questo qui usiamo un testo non
    // vuoto ma silenzioso (volume 0) e velocissimo, e in piu' lo cancelliamo
    // comunque poco dopo come rete di sicurezza, cosi' non puo' mai bloccare
    // le letture vere.
    var sbloccato = false;
    function sbloccaMotoreVocale() {
        if (sbloccato) { return; }
        sbloccato = true;
        try {
            var muto = new topWin.SpeechSynthesisUtterance('.');
            muto.volume = 0;
            muto.rate = 10;
            synth.speak(muto);
            setTimeout(function() { synth.cancel(); }, 300);
        } catch (e) { /* ignorato: non e' critico */ }
    }
    doc.addEventListener('click', sbloccaMotoreVocale, { once: true, capture: true });
    doc.addEventListener('touchstart', sbloccaMotoreVocale, { once: true, capture: true });

    // Lettura automatica (dopo una domanda fatta a voce): interrompe quella in
    // corso, se c'e', e legge la nuova risposta.
    topWin.__carpanetSpeak = function(testo) {
        if (corrente.bottone) { corrente.bottone.textContent = '🔊'; corrente.bottone = null; }
        synth.cancel();
        setTimeout(function() {
            var utterance = new topWin.SpeechSynthesisUtterance(testo);
            utterance.lang = 'it-IT';
            synth.speak(utterance);
        }, 80);
    };
    // Interrompe qualunque lettura in corso senza avviarne una nuova: usato
    // quando arriva un nuovo messaggio (scritto o vocale) mentre l'assistente
    // sta ancora leggendo la risposta precedente.
    topWin.__carpanetStopSpeaking = function() {
        synth.cancel();
        if (corrente.bottone) { corrente.bottone.textContent = '🔊'; corrente.bottone = null; }
    };
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
            var here = new URLSearchParams(window.top.location.search);
            if (here.has('geo_lat') || here.has('geo_denied')) { return; }
            if (!navigator.geolocation) { return; }
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    var p = new URLSearchParams(window.top.location.search);
                    p.set('geo_lat', pos.coords.latitude);
                    p.set('geo_lon', pos.coords.longitude);
                    window.top.location.search = p.toString();
                },
                function () {
                    var p = new URLSearchParams(window.top.location.search);
                    p.set('geo_denied', '1');
                    window.top.location.search = p.toString();
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

if MEMORIA_PERSISTENTE and st.session_state.current_user is None:
    st.markdown("## AI privata")
    existing_users = _load_family_users()
    if not existing_users:
        st.info("Nessun account ancora creato. Crea il primo account (genitore) per iniziare.")
        with st.form("bootstrap_parent_form"):
            new_name = st.text_input("Il tuo nome")
            new_pin = st.text_input("Scegli un PIN (4-6 cifre)", type="password")
            submitted = st.form_submit_button("Crea account genitore")
            if submitted:
                if new_name.strip() and new_pin.strip():
                    if _create_family_user(new_name.strip(), new_pin.strip(), "genitore"):
                        st.session_state.current_user = {"name": new_name.strip(), "role": "genitore"}
                        st.session_state.just_logged_in = True
                        st.rerun()
                    else:
                        st.error("Errore nella creazione dell'account. Riprova.")
                else:
                    st.warning("Inserisci nome e PIN.")
    else:
        names = [u["name"] for u in existing_users]
        with st.form("login_form"):
            selected_name = st.selectbox("Chi sei?", names)
            pin_input = st.text_input("PIN", type="password")
            submitted = st.form_submit_button("Accedi")
            if submitted:
                user = _verify_family_login(selected_name, pin_input)
                if user:
                    st.session_state.current_user = user
                    st.session_state.just_logged_in = True
                    st.rerun()
                else:
                    st.error("PIN errato.")
    st.stop()
elif st.session_state.current_user is None:
    # Memoria persistente non configurata: nessun posto sicuro per gli account,
    # quindi si procede senza login, con accesso completo (comportamento invariato).
    st.session_state.current_user = {"name": "Utente", "role": "genitore"}

CURRENT_ROLE = st.session_state.current_user.get("role", "genitore")
IS_PARENT = CURRENT_ROLE == "genitore"

# --- Pagina di benvenuto (a ogni login, prima della chat) -----------------
if st.session_state.get("just_logged_in"):
    _nome_utente = st.session_state.current_user.get("name", "")
    st.markdown(f"""
    <div class="carpanet-welcome">
        <img class="carpanet-welcome-logo" src="data:image/jpeg;base64,{LOGO_B64}">
        <h1>Ciao {_nome_utente} 👋</h1>
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

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                _b64_msg = base64.b64encode(message["content"].encode("utf-8")).decode("ascii")
                st.markdown(
                    f'<button class="carpanet-tts-btn" data-b64="{_b64_msg}" title="Leggi ad alta voce / pausa">🔊</button>',
                    unsafe_allow_html=True,
                )

    if not st.session_state.messages:
        st.caption(
            "🎙️ Se il microfono mostra \"Recording failed\" o non registra, il browser ha "
            "probabilmente bloccato il permesso in passato: tocca l'icona del lucchetto/informazioni "
            "accanto all'indirizzo del sito, apri i permessi e consenti il Microfono, poi ricarica la pagina."
        )

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
        _resto_addestramento = _testo_comando_addestramento(testo_completo)
        _comando_addestramento_attivo = _resto_addestramento is not None

        if _comando_addestramento_attivo:
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
        else:
            notes = []
            if _audio_non_trascritto:
                notes.append("[Audio ricevuto ma non e stato possibile trascriverlo]")
            for f in _file_allegati:
                file_bytes = f.getvalue()
                r2_link = r2_upload(file_bytes, f.name, R2_BUCKET_ALLEGATI, R2_PUBLIC_URL_ALLEGATI)
                if r2_link is not None:
                    notes.append(f"[Allegato salvato: {f.name} ({r2_link})]")
                else:
                    notes.append(f"[Allegato ricevuto: {f.name} — non salvato in modo permanente perche lo spazio di archiviazione non e ancora configurato o non e raggiungibile]")

            prompt = testo_completo
            if notes:
                prompt = (prompt + "\n\n" + "\n".join(notes)).strip() if prompt else "\n".join(notes)

    else:
        prompt = None
        _input_era_vocale = False
        _comando_addestramento_attivo = False

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

            if _comando_addestramento_attivo:
                # Comando di addestramento: nessuna chiamata all'AI, si usa
                # direttamente la conferma (o il messaggio d'errore) gia'
                # preparata sopra durante la gestione dell'allegato/testo.
                response = risposta_addestramento
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
