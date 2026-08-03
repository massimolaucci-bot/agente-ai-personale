import os
import json
import hashlib
import requests
import streamlit as st
from groq import Groq

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


# --- pCloud (allegati: foto, video, documenti) --------------------------------
# Configurazione via variabili d'ambiente, non ancora impostate su Render:
# preferito: PCLOUD_ACCESS_TOKEN (token OAuth generato dalla dashboard sviluppatori
# pCloud, non la password dell'account) + PCLOUD_API_HOST (eapi.pcloud.com per
# account europei, api.pcloud.com per account US).
PCLOUD_API_HOST = os.environ.get("PCLOUD_API_HOST", "eapi.pcloud.com")
PCLOUD_ACCESS_TOKEN = os.environ.get("PCLOUD_ACCESS_TOKEN")
PCLOUD_FOLDER_ID = os.environ.get("PCLOUD_FOLDER_ID", "0")  # 0 = cartella radice
PCLOUD_TIMEOUT = 15


def _pcloud_enabled():
    return bool(PCLOUD_ACCESS_TOKEN)


def pcloud_upload(file_bytes, filename):
    """Carica un file su pCloud. Ritorna il fileid se riuscito, altrimenti None.
    Non solleva mai eccezioni: se pCloud non e configurato o la chiamata fallisce,
    l'app deve continuare a funzionare comunque (allegato semplicemente non salvato)."""
    if not _pcloud_enabled():
        return None
    try:
        r = requests.post(
            f"https://{PCLOUD_API_HOST}/uploadfile",
            params={
                "auth": PCLOUD_ACCESS_TOKEN,
                "folderid": PCLOUD_FOLDER_ID,
                "filename": filename,
                "nopartial": "1",
            },
            files={"file": (filename, file_bytes)},
            timeout=PCLOUD_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("result") == 0:
            metadata = data.get("metadata") or []
            if metadata:
                return metadata[0].get("fileid")
        return None
    except Exception:
        return None


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


# --- Login familiare e ruoli (genitore = accesso completo, figlio = limitato) --
# Richiede la memoria persistente su Supabase: senza database esterno non c'e
# un posto sicuro dove conservare gli account, quindi in quel caso il login
# viene saltato e tutti vengono trattati come "genitore" (comportamento identico
# a prima di questa modifica).
def _hash_pin(pin):
    return hashlib.sha256((str(pin) + "carpanet_family_salt_v1").encode("utf-8")).hexdigest()


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


def build_api_messages(history, knowledge_text, history_limit=None, char_limit=None):
    history_limit = history_limit or MAX_HISTORY_MESSAGES
    char_limit = char_limit or MAX_MESSAGE_CHARS

    system_prompt = (
        "Sei Carpanet AI, l'assistente personale di Massimo (Carpanet). "
        "Rispondi sempre in italiano, in modo chiaro, utile e diretto. "
        "Per default sii conciso: vai dritto al punto e approfondisci solo se l'utente lo chiede esplicitamente "
        "(es. 'spiegami meglio', 'in dettaglio', 'più lungo')."
    )
    if knowledge_text and knowledge_text.strip():
        system_prompt += (
            "\n\nInformazioni e istruzioni permanenti fornite dall'utente: seguile sempre.\n"
            + knowledge_text.strip()
        )

    api_messages = [{"role": "system", "content": system_prompt}]
    recent = history[-history_limit:]
    for m in recent:
        content = m["content"]
        if len(content) > char_limit:
            content = content[:char_limit] + "\n[...contenuto troncato...]"
        api_messages.append({"role": m["role"], "content": content})
    return api_messages


st.set_page_config(page_title="Carpanet AI", page_icon=":fish:", layout="centered")

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
    font-size: 1rem !important;
}}
[data-testid="stChatInputTextArea"]::placeholder {{
    color: #a9b8d6 !important;
    opacity: 1 !important;
}}
[data-testid="stChatInput"] button svg {{
    color: #e6f1ff !important;
}}
/* Il pulsante "Start recording" non riceve uno sfondo/border-radius forzato:
   Streamlit sostituisce il suo contenuto con una visualizzazione audio (wavesurfer)
   durante la registrazione, e un contenitore troppo vincolato dal nostro CSS
   puo' interferire con quella libreria. Ci limitiamo a rendere l'icona ben visibile. */
[data-testid="stChatInput"] button[aria-label="Start recording"] svg {{
    color: #7b5cff !important;
}}
[data-testid="stChatInput"] button[aria-label="Upload files"] {{
    background: linear-gradient(135deg, #00e5ff, #7b5cff) !important;
    border-radius: 50% !important;
    opacity: 1 !important;
}}
[data-testid="stChatInput"] button[aria-label="Upload files"] svg {{
    color: #0a0e17 !important;
}}
[data-testid="stChatInput"] button[aria-label="Upload files"] svg * {{
    fill: #0a0e17 !important;
    stroke: #0a0e17 !important;
}}
[data-testid="stChatInput"] button[aria-label="Send message"] {{
    background: linear-gradient(135deg, #00e5ff, #7b5cff) !important;
    border-radius: 50% !important;
}}
[data-testid="stChatInput"] button[aria-label="Send message"] svg {{
    color: #0a0e17 !important;
}}
[data-testid="stChatInput"] button[aria-label="Send message"] svg * {{
    fill: #0a0e17 !important;
    stroke: #0a0e17 !important;
}}
.stApp, [data-testid="stAppViewContainer"] {{
    color: #f2f6ff !important;
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
</style>
<img class="carpanet-logo" src="data:image/jpeg;base64,{LOGO_B64}">
""", unsafe_allow_html=True)

MEMORIA_PERSISTENTE = _supabase_enabled()

# --- Login familiare ------------------------------------------------------
# Attivo solo se la memoria persistente (Supabase) e configurata: senza un
# database esterno non c'e un posto sicuro dove tenere gli account, quindi
# in quel caso si salta il login e si trattano tutti come "genitore" (nessun
# cambiamento di comportamento rispetto a prima).
if "current_user" not in st.session_state:
    st.session_state.current_user = None

if MEMORIA_PERSISTENTE and st.session_state.current_user is None:
    st.markdown("## 👨‍👩‍👧‍👦 Accesso famiglia")
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

    if IS_PARENT and st.button("Nuova conversazione"):
        st.session_state.messages = []
        save_memory([])
        st.rerun()

    st.markdown("---")
    st.markdown("#### Risposte vocali")
    if "tts_enabled" not in st.session_state:
        st.session_state.tts_enabled = True
    st.session_state.tts_enabled = st.toggle(
        "Leggi le risposte ad alta voce",
        value=st.session_state.tts_enabled,
        help="Se disattivato, le risposte vengono mostrate solo come testo, senza sintesi vocale.",
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
    st.markdown("#### 📎 Allegati (pCloud)")
    ALLEGATI_ATTIVI = _pcloud_enabled()
    if ALLEGATI_ATTIVI:
        st.caption("Gli allegati inviati dalla chat vengono salvati su pCloud.")
    else:
        st.caption("Il salvataggio su pCloud non e ancora configurato: gli allegati verranno comunque accettati ma non salvati in modo permanente, finche non vengono aggiunte le credenziali pCloud.")

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

    if "messages" not in st.session_state:
        st.session_state.messages = load_memory()
    if "knowledge_text" not in st.session_state:
        st.session_state.knowledge_text = load_knowledge()

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

    user_input = st.chat_input(
        "Chiedimi qualcosa, usa il microfono o allega un file...",
        accept_file="multiple",
        file_type=["png", "jpg", "jpeg", "heic", "webp", "mp4", "mov", "avi", "webm", "pdf", "doc", "docx", "txt"],
        accept_audio=True,
        audio_sample_rate=16000,
    )

    if user_input:
        prompt = (user_input.text or "").strip()
        notes = []

        if user_input.audio is not None:
            try:
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=("audio.wav", user_input.audio.getvalue()),
                    language="it",
                )
                transcribed = (transcription.text or "").strip()
                if transcribed:
                    prompt = (prompt + " " + transcribed).strip() if prompt else transcribed
            except Exception:
                notes.append("[Audio ricevuto ma non e stato possibile trascriverlo]")

        for f in (user_input.files or []):
            file_bytes = f.getvalue()
            fileid = pcloud_upload(file_bytes, f.name)
            if fileid is not None:
                notes.append(f"[Allegato salvato su pCloud: {f.name}]")
            else:
                notes.append(f"[Allegato ricevuto: {f.name} — non salvato in modo permanente perche pCloud non e ancora configurato o non e raggiungibile]")

        if notes:
            prompt = (prompt + "\n\n" + "\n".join(notes)).strip() if prompt else "\n".join(notes)

    else:
        prompt = None

    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_memory(st.session_state.messages)
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            def is_too_large_error(exc):
                msg = str(exc).lower()
                return "413" in str(exc) or "too large" in msg or "request_too_large" in msg or "rate_limit" in msg

            response = None
            try:
                api_messages = build_api_messages(st.session_state.messages, st.session_state.get("knowledge_text", ""))
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
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_memory(st.session_state.messages)

                if st.session_state.get("tts_enabled", True):
                    tts_script = f"""
                    <script>
                        var msg = new SpeechSynthesisUtterance({repr(response)});
                        msg.lang = 'it-IT';
                        window.speechSynthesis.speak(msg);
                    </script>
                    """
                    st.components.v1.html(tts_script, height=0)
