import os
import json
import streamlit as st
from groq import Groq

MEMORY_FILE = "chat_memory.json"


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


st.set_page_config(page_title="Carpanet AI", page_icon="🐟", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&display=swap');

.stApp, [data-testid="stAppViewContainer"], body {
    background: linear-gradient(135deg, #0a0e17 0%, #10162a 100%);
        color: #e6f1ff;
        }

        .carpanet-title {
            font-family: 'Orbitron', sans-serif;
                font-weight: 900;
                    font-size: 2.6rem;
                        text-align: center;
                            background: linear-gradient(90deg, #00e5ff, #7b5cff, #ff2d95);
                                -webkit-background-clip: text;
                                    -webkit-text-fill-color: transparent;
                                        text-shadow: 0 0 25px rgba(0,229,255,0.35);
                                            letter-spacing: 2px;
                                                margin-bottom: 0;
                                                }

                                                .carpanet-subtitle {
                                                    font-family: 'Orbitron', sans-serif;
                                                        text-align: center;
                                                            color: #7b8bab;
                                                                font-size: 0.85rem;
                                                                    letter-spacing: 3px;
                                                                        margin-top: 0;
                                                                            margin-bottom: 1.5rem;
                                                                            }
                                                                            </style>
                                                                            """, unsafe_allow_html=True)

st.markdown('<div class="carpanet-title">🐟 CARPANET AI</div>', unsafe_allow_html=True)
st.markdown('<div class="carpanet-subtitle">AGENTE VOCALE & AGENTICO</div>', unsafe_allow_html=True)

with st.sidebar:
        st.markdown("### 🐟 Carpanet AI")
        st.caption("La memoria resta finché il server è attivo. Se Render riavvia il servizio (es. dopo inattività prolungata), la cronologia si azzera.")
        if st.button("🗑️ Nuova conversazione"):
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

    voice_html = f"""
        <div style="text-align:center; font-family:'Orbitron', sans-serif;">
                <button id="voiceBtn" style="
            background: linear-gradient(135deg, #00e5ff, #7b5cff);
                        color: #0a0e17;
                                    border: none;
                                                border-radius: 50px;
                                                            padding: 14px 32px;
                                                                        font-family: 'Orbitron', sans-serif;
                                                                                    font-weight: 700;
                                                                                                font-size: 1rem;
                                                                                                            letter-spacing: 1px;
                                                                                                                        cursor: pointer;
                                                                                                                                    box-shadow: 0 0 20px rgba(0,229,255,0.5);
                                                                                                                                            ">🐟 PARLA CON CARPANET</button>
                                                                                                                                                    <p id="status" style="color:#7b8bab; font-family:'Orbitron', sans-serif; font-size:0.85rem; margin-top:12px;">Premi e parla</p>
                                                                                                                                                        </div>
                                                                                                                                                            <script>
                                                                                                                                                                    const btn = document.getElementById('voiceBtn');
                                                                                                                                                                            const status = document.getElementById('status');
                                                                                                                                                                                    btn.onclick = function() {{
                                                                                                                                                                                                if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                                                                                                                                                                                                                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                                                                                                                                                                                                                                const recognition = new SpeechRecognition();
                                                                                                                                                                                                                                                recognition.lang = 'it-IT';
                                                                                                                                                                                                                                                                recognition.continuous = false;
                                                                                                                                                                                                                                                                                recognition.interimResults = false;
                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                status.innerText = "Ascolto in corso... parla ora!";
                                                                                                                                                                                                                                                                                                                recognition.start();
                                                                                                                                                                                                                                                                                                                
                                                                                                                                                                                                                                                                                                                                recognition.onresult = function(e) {{
                                                                                                                                                                                                                                                                                                                                                    var text = e.results[0][0].transcript;
                                                                                                                                                                                                                                                                                                                                                                        status.innerText = "Hai detto: " + text;
                                                                                                                                                                                                                                                                                                                                                                                            btn.style.boxShadow = "0 0 20px rgba(255,45,149,0.6)";
                                                                                                                                                                                                                                                                                                                                                                                            
                                                                                                                                                                                                                                                                                                                                                                                                                const chatInput = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                                                                                                                                                                                                                                                                                                                                                                                                                                    if (chatInput) {{
                                                                                                                                                                                                                                                                                                                                                                                                                                                            const nativeSetter = Object.getOwnPropertyDescriptor(window.parent.HTMLTextAreaElement.prototype, 'value').set;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    nativeSetter.call(chatInput, text);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            chatInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    chatInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        }}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        }};
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        recognition.onerror = function(e) {{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            recognition.stop();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                btn.style.boxShadow = "0 0 20px rgba(255,45,149,0.6)";
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    status.innerText = "Errore microfono o permesso negato.";
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    }};
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                }} else {{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                alert("Il tuo browser non supporta il riconoscimento vocale. Usa Google Chrome o Microsoft Edge.");
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            }}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    }}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        </script>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            """
    st.components.v1.html(voice_html, height=160)

    for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                                st.markdown(message["content"])

            # Input dell'utente
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

                                            # Sintesi vocale automatica
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
                                            
