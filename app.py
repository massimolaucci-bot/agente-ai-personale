import os
import streamlit as str
from groq import Groq

# Titolo dell'applicazione
str.set_page_config(page_title="Agente AI Personale", page_icon="🤖")
str.title("🤖 Il tuo Agente AI Personale")

# Recupera la chiave API dalle variabili d'ambiente di Render
groq_api_key = os.environ.get("GROQ_API_KEY")

if not groq_api_key:
    str.warning("Inserisci la tua GROQ_API_KEY nelle impostazioni di Render per iniziare.")
else:
    client = Groq(api_key=groq_api_key)

    # Inizializza la cronologia della chat
    if "messages" not in str.session_state:
        str.session_state.messages = []

    # Mostra i messaggi precedenti
    for message in str.session_state.messages:
        with str.chat_message(message["role"]):
            str.markdown(message["content"])

    # Input dell'utente
    if prompt := str.chat_input("Chiedimi qualcosa..."):
        str.session_state.messages.append({"role": "user", "content": prompt})
        with str.chat_message("user"):
            str.markdown(prompt)

        # Risposta del modello via Groq
        with str.chat_message("assistant"):
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": m["role"], "content": m["content"]}
                        for m in str.session_state.messages
                    ],
                )
                response = completion.choices[0].message.content
                str.markdown(response)
                str.session_state.messages.append({"role": "assistant", "content": response})
            except Exception as e:
                str.error(f"Errore durante la generazione della risposta: {e}")
