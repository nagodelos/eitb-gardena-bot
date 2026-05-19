import os
from typing import Optional

import anthropic
import streamlit as st

MODEL = "claude-sonnet-4-5"

EITB_LOGO_URL = "https://images14.eitb.eus/multimedia/recursos/img/logo_eitbeus_cabecera3.png"

CUSTOM_CSS = """
<style>
    /* ── Tipografía: Montserrat ─────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;900&display=swap');

    html, body, [class*="css"], .stApp, .stMarkdown, .stText,
    input, textarea, button, select, label, p, span, div {
        font-family: 'Montserrat', sans-serif !important;
    }

    /* ── Layout ─────────────────────────────────────────────────────────── */
    .main .block-container {
        padding-top: 1.5rem;
        max-width: 820px;
    }

    /* ── Headings ───────────────────────────────────────────────────────── */
    h1, h2, h3 {
        color: #000000 !important;
        font-weight: 700 !important;
        font-family: 'Montserrat', sans-serif !important;
    }

    /* ── Subtítulo bilingüe ─────────────────────────────────────────────── */
    .eitb-subtitle {
        color: #595959;
        font-size: 0.95rem;
        font-weight: 400;
        margin-top: -0.5rem;
        margin-bottom: 1.2rem;
        line-height: 1.5;
    }

    /* ── Botones globales (sidebar, genéricos) ──────────────────────────── */
    .stButton > button {
        background-color: #0077CD !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        font-family: 'Montserrat', sans-serif !important;
    }
    .stButton > button:hover {
        background-color: #005ba3 !important;
        color: #FFFFFF !important;
    }

    /* ── Botones de preguntas sugeridas ─────────────────────────────────── */
    div[data-testid="stHorizontalBlock"] .stButton > button {
        background-color: #0077CD !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        font-weight: 600 !important;
        padding: 0.6rem 0.8rem !important;
        text-align: left !important;
        white-space: normal !important;
        height: auto !important;
        line-height: 1.4 !important;
        width: 100% !important;
    }
    div[data-testid="stHorizontalBlock"] .stButton > button:hover {
        background-color: #005ba3 !important;
    }

    /* ── Sidebar ────────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: #fafbfc !important;
    }
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] .sidebar-heading {
        color: #0077CD !important;
        font-weight: 700 !important;
    }
    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] p {
        color: #595959;
        font-size: 0.78rem;
        line-height: 1.6;
    }

    /* ── Acento rojo EITB: borde izquierdo para respuestas fuera de alcance */
    .eitb-out-of-scope {
        border-left: 4px solid #e4001f;
        background-color: #fde8eb;
        padding: 0.75rem 1rem;
        border-radius: 0 6px 6px 0;
        margin: 0.5rem 0;
    }

    /* ── Chat ────────────────────────────────────────────────────────────── */
    .stChatMessage {
        border-radius: 8px;
    }

    /* ── Enlaces ─────────────────────────────────────────────────────────── */
    a, a:visited {
        color: #0077CD !important;
    }
    a:hover {
        color: #005ba3 !important;
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
        page_icon="https://images14.eitb.eus/multimedia/recursos/img/logo_eitbeus_cabecera3.png",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
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
    st.image(EITB_LOGO_URL, width=180)
    st.markdown("## Bot de Transparencia de EITB")
    st.markdown(
        '<p class="eitb-subtitle">'
        "Pregunta sobre financiación, audiencias, organización y más &nbsp;·&nbsp; "
        "EITB-ri buruz galdetu: finantzaketa, audientziak, antolaketa eta gehiago"
        "</p>",
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

    # ── Preguntas sugeridas (solo si la conversación está vacía) ──────────────
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
