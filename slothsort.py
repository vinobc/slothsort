#!/usr/bin/env python3
"""SlothSort — a lazy, local, open-weight PDF tidier.

Step 1 scope: prove the two foundations work on your machine.
  (a) we can pull text out of a PDF
  (b) we can talk to a local Gemma model through Ollama

Nothing is renamed or moved yet. Later steps add classification,
renaming, moving and undo.
"""

import argparse
import sys
from pathlib import Path

import ollama
from pypdf import PdfReader

MODEL = "gemma3:4b"          # swap for any Gemma tag you have pulled
PAGES_TO_READ = 2            # enough to classify; keeps the prompt small


def extract_text(pdf_path: Path, max_pages: int = PAGES_TO_READ) -> str:
    """Return the text of the first few pages of a PDF."""
    reader = PdfReader(str(pdf_path))
    chunks = []
    for page in reader.pages[:max_pages]:
        chunks.append(page.extract_text() or "")
    return "\n".join(chunks).strip()


def ask_model(prompt: str) -> str:
    """Send a prompt to the local Ollama model and return its reply."""
    response = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


def main() -> None:
    parser = argparse.ArgumentParser(description="SlothSort step 1: smoke test")
    parser.add_argument("pdf", type=Path, help="one PDF to test with")
    args = parser.parse_args()

    if not args.pdf.is_file():
        sys.exit(f"Not a file: {args.pdf}")

    text = extract_text(args.pdf)
    print(f"--- extracted {len(text)} characters from {args.pdf.name} ---")
    print(text[:500], "...\n")

    reply = ask_model(
        "In one sentence, what kind of document is this?\n\n" + text[:3000]
    )
    print(f"--- {MODEL} says ---")
    print(reply)


if __name__ == "__main__":
    main()
