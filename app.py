import os
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Agente AI Vocale", page_icon="🎙️", layout="centered")

st.title("🎙️ Agente AI Vocale & Agentico")

groq_api_key = os.environ.get("GROQ_API_KEY")

if not groq_api_key:
    st.error("GROQ_API_KEY non trovata nelle impostazioni di Render.")
else:
    client = Groq(api_key=groq_api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Pulsante Vocale Nativo Browser
    st.write("### 🗣️ Interazione Vocale")
    
    components_code = """
    <div style="text-align: center; margin-bottom: 20px;">
        <button id="speech-btn" onclick="startDictation()" style="background-color: #ff4b4b; color: white; border: none; padding: 12px 24px; font-size: 16px; border-radius: 8px; cursor: pointer; font-weight: bold;">
            🎤 Clicca qui per Parlare
        </button>
        <p id="status" style="margin-top: 10px; font-size: 14px; color: #666;"></p>
    </div>

    <script>
        function startDictation() {
            if (window.hasOwnProperty('webkitSpeechRecognition') || window.hasOwnProperty('SpeechRecognition')) {
                var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
                var recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.lang = "it-IT";
                
                var btn = document.getElementById('speech-btn');
                var status = document.getElementById('status');
                
                btn.style.backgroundColor = "#d32f2f";
                status.innerText = "Ascolto in corso... parla ora!";

                recognition.start();

                recognition.onresult = function(e) {
                    var text = e.results[0][0].transcript;
                    status.innerText = "Hai detto: " + text;
                    btn.style.backgroundColor = "#ff4b4b";
                    
                    const chatInput = window.parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                    if (chatInput) {
                        chatInput.value = text;
                        chatInput.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                };

                recognition.onerror = function(e) {
                    recognition.stop();
                    btn.style.backgroundColor = "#ff4b4b";
                    status.innerText = "Errore microfono o permesso negato.";
                };
            } else {
                alert("Il tuo browser non supporta il riconoscimento vocale. Usa Google Chrome o Microsoft Edge.");
            }
        }
    </script>
    """
    st.components.v1.html(components_code, height=100)

    # Mostra la cronologia
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input dell'utente
    if prompt := st.chat_input("Chiedimi qualcosa o usa il pulsante sopra..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
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
