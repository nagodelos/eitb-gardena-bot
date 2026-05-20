"""
download_sources.py — Descarga las fuentes listadas en data/sources.json.

- Los PDFs van a data/pdfs/ (con el filename del JSON).
- Las páginas HTML se capturan, se extraen a texto principal con trafilatura
  y se guardan como Markdown en data/html/ con cabecera (front matter)
  que incluye título y URL original (para que las citas las puedan referenciar).

Uso:
    python3 download_sources.py             # descarga lo que falte
    python3 download_sources.py --refresh   # vuelve a bajar todo
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

import requests

try:
    import trafilatura
except ImportError:  # pragma: no cover
    trafilatura = None

ROOT = Path(__file__).parent
SOURCES_JSON = ROOT / "data" / "sources.json"
PDFS_DIR = ROOT / "data" / "pdfs"
HTML_DIR = ROOT / "data" / "html"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
REFERER = "https://www.eitbtaldea.eus/es/transparencia/"
HEADERS = {"User-Agent": USER_AGENT, "Referer": REFERER}
TIMEOUT = 120


def load_sources() -> list[Dict[str, Any]]:
    with open(SOURCES_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data["sources"]


def download_pdf(src: Dict[str, Any], refresh: bool) -> str:
    out = PDFS_DIR / src["filename"]
    if out.exists() and out.stat().st_size > 0 and not refresh:
        return f"skip   {src['filename']} (ya existe)"
    try:
        r = requests.get(src["url"], headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            return f"ERR    {src['filename']}: respuesta no es PDF ({len(r.content)} bytes)"
        out.write_bytes(r.content)
        return f"ok     {src['filename']} ({len(r.content):,} bytes)"
    except Exception as e:  # noqa: BLE001
        return f"ERR    {src['filename']}: {e}"


def build_front_matter(src: Dict[str, Any]) -> str:
    captured = time.strftime("%Y-%m-%d")
    return (
        f"---\n"
        f"id: {src['id']}\n"
        f"title: {src['title']}\n"
        f"url: {src['url']}\n"
        f"category: {src['category']}\n"
        f"captured_at: {captured}\n"
        f"---\n\n"
        f"# {src['title']}\n\n"
    )


def fetch_html(src: Dict[str, Any], refresh: bool) -> str:
    if trafilatura is None:
        return f"ERR    {src['filename']}: instala trafilatura (pip install trafilatura)"
    out = HTML_DIR / src["filename"]
    if out.exists() and out.stat().st_size > 0 and not refresh:
        return f"skip   {src['filename']} (ya existe)"
    try:
        downloaded = trafilatura.fetch_url(src["url"])
        if not downloaded:
            return f"ERR    {src['filename']}: no se pudo descargar la página"
        text = trafilatura.extract(
            downloaded,
            output_format="markdown",
            include_links=False,
            include_tables=True,
            favor_recall=True,
        )
        if not text or len(text) < 200:
            return f"ERR    {src['filename']}: contenido extraído insuficiente"
        out.write_text(build_front_matter(src) + text, encoding="utf-8")
        return f"ok     {src['filename']} ({len(text):,} chars)"
    except Exception as e:  # noqa: BLE001
        return f"ERR    {src['filename']}: {e}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="Redescarga incluso si el archivo ya existe.")
    args = parser.parse_args()

    PDFS_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    sources = load_sources()
    pdfs = [s for s in sources if s["type"] == "pdf"]
    htmls = [s for s in sources if s["type"] == "html"]

    print(f"Fuentes en sources.json: {len(sources)} ({len(pdfs)} PDFs, {len(htmls)} HTML)")
    print(f"PDFs   → {PDFS_DIR}")
    print(f"HTML   → {HTML_DIR}")
    print()

    print("== PDFs ==")
    ok = err = skip = 0
    for src in pdfs:
        line = download_pdf(src, args.refresh)
        print(f"  {line}")
        if line.startswith("ok"):
            ok += 1
        elif line.startswith("skip"):
            skip += 1
        else:
            err += 1
    print(f"\n  Resumen PDFs: {ok} descargados, {skip} ya existían, {err} fallos.\n")

    print("== HTML ==")
    ok = err = skip = 0
    for src in htmls:
        line = fetch_html(src, args.refresh)
        print(f"  {line}")
        if line.startswith("ok"):
            ok += 1
        elif line.startswith("skip"):
            skip += 1
        else:
            err += 1
    print(f"\n  Resumen HTML: {ok} capturados, {skip} ya existían, {err} fallos.")


if __name__ == "__main__":
    main()
