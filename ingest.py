"""
ingest.py — Genera data/index.pkl a partir de los PDFs en data/pdfs/
            y los Markdown en data/html/.

Uso:
    python3 ingest.py

Requisitos:
    pip install pypdf sentence-transformers numpy
"""

import os
import pickle
import re
import time
from pathlib import Path
from typing import List, Dict, Any

import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

# ── Configuración ──────────────────────────────────────────────────────────────
PDFS_DIR = Path(__file__).parent / "data" / "pdfs"
HTML_DIR = Path(__file__).parent / "data" / "html"
INDEX_PATH = Path(__file__).parent / "data" / "index.pkl"
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_TOKENS = 800      # tamaño objetivo en tokens (~4 chars/token → ~3200 chars)
CHUNK_OVERLAP = 100     # solape en tokens (~400 chars)

CHARS_PER_TOKEN = 4
CHUNK_SIZE = CHUNK_TOKENS * CHARS_PER_TOKEN      # ~3200 chars
OVERLAP_SIZE = CHUNK_OVERLAP * CHARS_PER_TOKEN   # ~400 chars


def extract_text_by_page(pdf_path: Path) -> List[Dict[str, Any]]:
    """Devuelve lista de {page, text} por cada página del PDF."""
    pages = []
    try:
        reader = PdfReader(str(pdf_path))
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({"page": i, "text": text})
    except Exception as e:
        print(f"  [AVISO] No se pudo leer {pdf_path.name}: {e}")
    return pages


def chunk_text(text: str, source: str, page: int) -> List[Dict[str, Any]]:
    """Trocea texto en chunks con solape, preservando metadatos."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({
                "text": chunk,
                "source": source,
                "page": page,
            })
        start += CHUNK_SIZE - OVERLAP_SIZE
    return chunks


def parse_front_matter(md_text: str) -> tuple[dict, str]:
    """Extrae el front matter YAML simple del Markdown. Devuelve (meta, body)."""
    if not md_text.startswith("---"):
        return {}, md_text
    end = md_text.find("\n---", 3)
    if end == -1:
        return {}, md_text
    fm = md_text[3:end].strip()
    body = md_text[end + 4:].lstrip()
    meta = {}
    for line in fm.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def chunks_from_html(md_path: Path) -> List[Dict[str, Any]]:
    """Lee un .md (HTML extraído) y lo trocea. Conserva título y URL en metadata."""
    text = md_path.read_text(encoding="utf-8")
    meta, body = parse_front_matter(text)
    if not body.strip():
        return []
    title = meta.get("title", md_path.stem)
    url = meta.get("url", "")
    # Limpieza ligera: quita líneas vacías repetidas y espacios redundantes
    body = re.sub(r"\n{3,}", "\n\n", body)
    raw_chunks = chunk_text(body, md_path.name, 1)
    for c in raw_chunks:
        c["title"] = title
        c["url"] = url
        c["source_type"] = "html"
    return raw_chunks


def main() -> None:
    pdf_files = sorted(PDFS_DIR.glob("*.pdf")) if PDFS_DIR.exists() else []
    html_files = sorted(HTML_DIR.glob("*.md")) if HTML_DIR.exists() else []

    if not pdf_files and not html_files:
        print(f"No se encontraron fuentes en {PDFS_DIR} ni {HTML_DIR}.")
        print("Ejecuta `python3 download_sources.py` primero.")
        return

    print(f"PDFs en {PDFS_DIR}: {len(pdf_files)}")
    print(f"HTML en {HTML_DIR}: {len(html_files)}\n")

    # ── 1. Extraer texto y generar chunks ───────────────────────────────────
    all_chunks: List[Dict[str, Any]] = []
    t0 = time.time()

    total = len(pdf_files) + len(html_files)
    pos = 0

    for pdf_path in pdf_files:
        pos += 1
        print(f"[{pos:02d}/{total}] {pdf_path.name}", end=" ... ")
        pages = extract_text_by_page(pdf_path)
        doc_chunks = []
        for page_data in pages:
            doc_chunks.extend(
                chunk_text(page_data["text"], pdf_path.name, page_data["page"])
            )
        # Marca el tipo para que la app pueda renderizar las citas con criterio
        for c in doc_chunks:
            c["source_type"] = "pdf"
        print(f"{len(pages)} páginas, {len(doc_chunks)} chunks")
        all_chunks.extend(doc_chunks)

    for md_path in html_files:
        pos += 1
        print(f"[{pos:02d}/{total}] {md_path.name}", end=" ... ")
        doc_chunks = chunks_from_html(md_path)
        print(f"HTML, {len(doc_chunks)} chunks")
        all_chunks.extend(doc_chunks)

    print(f"\nTotal chunks: {len(all_chunks)}")

    # ── 2. Generar embeddings ───────────────────────────────────────────────
    print(f"\nCargando modelo de embeddings '{EMBED_MODEL}'...")
    model = SentenceTransformer(EMBED_MODEL)

    texts = [c["text"] for c in all_chunks]
    print(f"Generando embeddings para {len(texts)} chunks...")
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    # ── 3. Serializar índice ────────────────────────────────────────────────
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "chunks": all_chunks,
        "embeddings": embeddings,          # np.ndarray float32 (N, dim)
        "model": EMBED_MODEL,
    }

    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)

    elapsed = time.time() - t0
    size_mb = INDEX_PATH.stat().st_size / 1_048_576

    print(f"\n{'─'*50}")
    print(f"PDFs procesados : {len(pdf_files)}")
    print(f"HTML procesados : {len(html_files)}")
    print(f"Chunks generados: {len(all_chunks)}")
    print(f"Índice guardado : {INDEX_PATH}  ({size_mb:.1f} MB)")
    print(f"Tiempo total    : {elapsed:.1f} s")
    print(f"{'─'*50}")


if __name__ == "__main__":
    main()
