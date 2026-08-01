import os
import io
import streamlit as st
from groq import Groq
from audio_recorder_streamlit import audio_recorder
from gtts import gTTS
import base64

st.set_page_config(page_title="Agente AI Vocale", page_icon="🎙️")
st.title("🎙️ Il tuo Agente AI Vocale")

groq_api_key = os.environ.get("GROQ_API_KEY")

if not groq_api_key:
    st.warning("Inserisci la tua GROQ_API_KEY su Render.")
else:
    client = Groq(api_key=groq_api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Sezione registrazione audio
    st.write("### 🗣️ Parla con l'Agente")
    audio_bytes = audio_recorder(text="Clicca per registrare", recording_color="#e84c3d", neutral_color="#6aa84f")

    user_text = None

    if audio_bytes:
        with st.spinner("Trascrizione voce in corso..."):
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice.wav"
            try:
                # Speech-To-Text con Whisper via Groq
                transcription = client.audio.transcriptions.create(
                    file=(audio_file.name, audio_file.read()),
                    model="whisper-large-v3-turbo",
                    language="it"
                )
                user_text = transcription.text
            except Exception as e:
                st.error(f"Errore trascrizione audio: {e}")

    # Fallback per input di testo
    text_input = st.chat_input("Oppure scrivi qui...")
    if text_input:
        user_text = text_input

    # Mostra cronologia
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Elaborazione risposta
    if user_text:
        st.session_state.messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)

        with st.chat_message("assistant"):
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
                )
                response = completion.choices[0].message.content
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

                # Generazione Audio Risposta (Text-To-Speech)
                tts = gTTS(text=response, lang='it')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                audio_base64 = base64.b64encode(fp.read()).decode('utf-8')
                audio_html = f'<audio autoplay src="data:audio/mp3;base64,{audio_base64}">'
                st.components.v1.html(audio_html, height=0)

            except Exception as e:
                st.error(f"Errore: {e}")
