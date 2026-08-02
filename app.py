import os
import json
import streamlit as st
from groq import Groq

MEMORY_FILE = "chat_memory.json"

LOGO_B64 = "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"


def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_memory(messages):
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(messages, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


st.set_page_config(page_title="Carpanet AI", page_icon=":fish:", layout="centered")

st.markdown(f"""
<style>
.stApp, [data-testid="stAppViewContainer"], body {{
    background: linear-gradient(135deg, #0a0e17 0%, #10162a 100%);
    color: #e6f1ff;
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

with st.sidebar:
    st.markdown("### Carpanet AI")
    st.caption("La memoria resta finche il server e attivo. Se Render riavvia il servizio, la cronologia si azzera.")
    if st.button("Nuova conversazione"):
        st.session_state.messages = []
        save_memory([])
        st.rerun()

groq_api_key = os.environ.get("GROQ_API_KEY")

if not groq_api_key:
    st.error("GROQ_API_KEY non trovata nelle impostazioni di Render.")
else:
    client = Groq(api_key=groq_api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = load_memory()

    voice_html = """
    <div style="text-align:center;">
        <button id="voiceBtn" style="
            background: linear-gradient(135deg, #00e5ff, #7b5cff);
            color: #0a0e17;
            border: none;
            border-radius: 50px;
            padding: 14px 32px;
            font-weight: 700;
            font-size: 1rem;
            letter-spacing: 1px;
            cursor: pointer;
            box-shadow: 0 0 20px rgba(0,229,255,0.5);
        ">Parla con Carpanet</button>
        <p id="status" style="color:#7b8bab; font-size:0.85rem; margin-top:12px;">Premi e parla</p>
    </div>
    <script>
        const btn = document.getElementById('voiceBtn');
        const status = document.getElementById('status');
        btn.onclick = function() {
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                const recognition = new SpeechRecognition();
                recognition.lang = 'it-IT';
                recognition.continuous = false;
                recognition.interimResults = false;

                status.innerText = "Ascolto in corso... parla ora!";
                recognition.start();

                recognition.onresult = function(e) {
                    var text = e.results[0][0].transcript;
                    status.innerText = "Hai detto: " + text;
                    btn.style.boxShadow = "0 0 20px rgba(255,45,149,0.6)";

                    const chatInput = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                    if (chatInput) {
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value').set;
                        nativeSetter.call(chatInput, text);
                        chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                        chatInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
                    }
                };

                recognition.onerror = function(e) {
                    recognition.stop();
                    btn.style.boxShadow = "0 0 20px rgba(255,45,149,0.6)";
                    status.innerText = "Errore microfono o permesso negato.";
                };
            } else {
                alert("Il tuo browser non supporta il riconoscimento vocale. Usa Google Chrome o Microsoft Edge.");
            }
        }
    </script>
    """
    st.components.v1.html(voice_html, height=160)

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Chiedimi qualcosa o usa il pulsante sopra..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_memory(st.session_state.messages)
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                completion = client.chat.completions.create(
                    model="groq/compound",
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                )
                response = completion.choices[0].message.content
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
                save_memory(st.session_state.messages)

                tts_script = f"""
                <script>
                    var msg = new SpeechSynthesisUtterance({repr(response)});
                    msg.lang = 'it-IT';
                    window.speechSynthesis.speak(msg);
                </script>
                """
                st.components.v1.html(tts_script, height=0)

            except Exception as e:
                st.error(f"Errore generazione: {e}")
