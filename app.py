import os
from typing import Optional

import anthropic
import streamlit as st

MODEL = "claude-sonnet-4-5"

CUSTOM_CSS = """
<style>
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 800px;
    }
    h1 {
        color: #1a1a2e;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    .stChatMessage {
        border-radius: 8px;
    }
    /* Suggested-question buttons */
    div[data-testid="stHorizontalBlock"] .stButton > button {
        background-color: #f4f6f8;
        border: 1px solid #d0d7de;
        border-radius: 8px;
        color: #24292f;
        font-size: 0.83rem;
        padding: 0.55rem 0.75rem;
        text-align: left;
        white-space: normal;
        height: auto;
        line-height: 1.4;
        width: 100%;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        background-color: #e8ecf0;
        border-color: #8c959f;
    }
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    section[data-testid="stSidebar"] .stCaption {
        color: #6c757d;
        font-size: 0.78rem;
        line-height: 1.5;
    }
</style>
"""

_RAG_DISCLAIMER = (
    "Esta respuesta se basa en conocimiento general y no en los documentos "
    "oficiales de EITB. Una próxima versión conectará la documentación de transparencia."
)

SUGGESTED_QUESTIONS = [
    "¿Cómo está organizada EITB?",
    "¿Qué derechos tengo como ciudadano frente a EITB?",
    "¿Cuáles son las normas editoriales de EITB?",
    "¿Qué políticas públicas tiene EITB?",
]


def build_system_prompt(language: str) -> str:
    lang_rule = (
        "Responde siempre en castellano, independientemente del idioma de la pregunta."
        if language == "Castellano"
        else "Erantzun beti euskaraz, galderaren hizkuntzaz gain."
    )
    return f"""Eres el Bot de Transparencia de EITB (Euskal Irrati Telebista), un agente conversacional de transparencia institucional al servicio de la ciudadanía vasca.

Reglas que debes seguir estrictamente:

1. Eres exclusivamente un agente de transparencia institucional de EITB. Tu único ámbito es el ente público EITB: su funcionamiento, financiación, organización interna, normativa aplicable, programación, audiencias y servicio público.

2. Solo respondes sobre EITB. Si te preguntan algo fuera de ese ámbito, lo declaras claramente ("Esa pregunta está fuera del alcance de este bot de transparencia de EITB") y no inventas ni extrapolas información.

3. Termina cada respuesta con la siguiente nota, separada por una línea en blanco:

---
{_RAG_DISCLAIMER}

4. {lang_rule}

5. Sé conciso, riguroso y honesto. Cita datos concretos cuando los tengas. Si no dispones de información suficiente para responder con precisión, indícalo claramente."""


def get_api_key() -> Optional[str]:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except (KeyError, FileNotFoundError):
        return os.environ.get("ANTHROPIC_API_KEY")


def main() -> None:
    st.set_page_config(
        page_title="EITB Gardena Bot",
        page_icon="📺",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### Configuración")
        language: str = st.radio(
            "Idioma / Hizkuntza",
            options=["Castellano", "Euskera"],
            index=0,
        )
        st.markdown("---")
        st.caption(f"Modelo: `{MODEL}`")
        st.markdown("---")
        st.caption(
            "Este bot no solicita datos personales y no almacena "
            "la conversación más allá de la sesión."
        )

    # ── Cabecera ──────────────────────────────────────────────────────────────
    st.title("📺 Bot de Transparencia de EITB")
    st.markdown(
        "Pregunta sobre financiación, audiencias, organización y más &nbsp;·&nbsp; "
        "*EITB-ri buruz galdetu: finantzaketa, audientziak, antolaketa eta gehiago*",
        unsafe_allow_html=True,
    )

    # ── Clave API ─────────────────────────────────────────────────────────────
    api_key = get_api_key()
    if not api_key:
        st.error(
            "No se ha configurado la clave de API de Anthropic. "
            "Añade `ANTHROPIC_API_KEY` en `.streamlit/secrets.toml` "
            "o como variable de entorno."
        )
        st.stop()

    client = anthropic.Anthropic(api_key=api_key)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # ── Preguntas sugeridas (solo si la conversación está vacía) ───────────────
    if not st.session_state.messages:
        st.markdown("**Preguntas sugeridas · Galdera gomendatuak**")
        col_a, col_b = st.columns(2)
        cols = [col_a, col_b, col_a, col_b]
        for i, question in enumerate(SUGGESTED_QUESTIONS):
            if cols[i].button(question, key=f"sugg_{i}", use_container_width=True):
                st.session_state.messages.append({"role": "user", "content": question})
                st.rerun()

    # ── Historial de mensajes ─────────────────────────────────────────────────
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Generar respuesta si el último turno es del usuario ───────────────────
    if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with client.messages.stream(
                model=MODEL,
                max_tokens=800,
                temperature=0.2,
                system=build_system_prompt(language),
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages
                ],
            ) as stream:
                response_text = st.write_stream(stream.text_stream)
        st.session_state.messages.append(
            {"role": "assistant", "content": response_text}
        )

    # ── Input del usuario ─────────────────────────────────────────────────────
    if user_input := st.chat_input(
        "Escribe tu pregunta sobre EITB… / Idatzi zure galdera EITB-ri buruz…"
    ):
        st.session_state.messages.append({"role": "user", "content": user_input})
        st.rerun()


if __name__ == "__main__":
    main()
