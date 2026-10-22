#!/usr/bin/env python3
"""SlothSort — a lazy, local, open-weight PDF tidier.

Step 2b scope: structured classification, hardened.
  For every PDF in a folder, ask the local Gemma model for a strict JSON
  verdict (category / title / year) and print a report table.
  Nothing is renamed or moved yet.
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path

import ollama
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)   # hide fontTools chatter

MODEL = "gemma3:1b"          # swap for any Gemma tag you have pulled
PAGES_TO_READ = 2            # enough to classify; keeps the prompt small
MAX_CHARS = 3000             # cap prompt size so a 1B model stays fast
RETRIES = 2                  # small models occasionally chatter instead of JSON

CATEGORIES = {
    "papers":          "academic writing: research papers, journal articles, book chapters, conference proceedings, author proofs",
    "syllabi":         "teaching plans: course syllabi, curricula, lesson plans, course outlines",
    "question-papers": "assessments: exam question papers, question banks, answer keys, mark schemes",
    "circulars":       "official institutional communication: notices, circulars, notifications, office orders, holiday lists, academic calendars, schemes and guidelines issued by a university",
    "personal":        "documents about one individual: CV / resume, certificates, ID cards, registrations, bills, receipts",
    "misc":            "only if nothing above fits at all",
}

PROMPT = """You are a filing assistant. Classify the document below into exactly one category.

Reply with ONLY a JSON object, no markdown, no explanation, exactly this shape:
{{"category": "<one of: {cats}>", "title": "<short descriptive title, max 8 words>", "year": "<4-digit year the document is about, or unknown>"}}

Category meanings (pick the best match; use misc only as a last resort):
{meanings}

Original filename (a strong hint): {filename}

Document text (first pages):
\"\"\"
{text}
\"\"\"
"""


def extract_text(pdf_path: Path, max_pages: int = PAGES_TO_READ) -> str:
    """Return the text of the first few pages of a PDF.

    Empty for scanned PDFs; a short note for encrypted or corrupt ones.
    Never raises - one bad file must not stop the whole folder.
    """
    try:
        reader = PdfReader(str(pdf_path))
        if reader.is_encrypted:
            reader.decrypt("")          # most "encrypted" PDFs only restrict editing
        chunks = [(p.extract_text() or "") for p in reader.pages[:max_pages]]
        return "\n".join(chunks).strip()
    except Exception as exc:            # encrypted with a real password, or corrupt
        return f"[unreadable PDF: {type(exc).__name__}]"


def classify(text: str, filename: str) -> dict:
    """Ask the local model; parse JSON; retry a couple of times if it chatters."""
    prompt = PROMPT.format(
        cats=" | ".join(CATEGORIES),
        meanings="\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items()),
        filename=filename,
        text=text[:MAX_CHARS] or "[no extractable text - probably a scanned PDF]",
    )
    last_reply = ""
    for _ in range(RETRIES + 1):
        reply = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},   # deterministic: same file -> same answer
            format="json",                # Ollama constrains output to valid JSON
        )["message"]["content"]
        last_reply = reply
        match = re.search(r"\{.*\}", reply, re.S)   # tolerate stray text around JSON
        if match:
            try:
                data = json.loads(match.group(0))
                cat = str(data.get("category", "misc")).strip().lower()
                return {
                    "category": cat if cat in CATEGORIES else "misc",
                    "title": str(data.get("title", "untitled")).strip()[:60],
                    "year": str(data.get("year", "unknown")).strip(),
                }
            except json.JSONDecodeError:
                pass
    return {"category": "misc", "title": "untitled", "year": "unknown", "raw": last_reply}


def main() -> None:
    parser = argparse.ArgumentParser(description="SlothSort step 2: classify a folder of PDFs")
    parser.add_argument("folder", type=Path, help="folder containing PDFs")
    args = parser.parse_args()

    pdfs = sorted(p for p in args.folder.iterdir() if p.suffix.lower() == ".pdf")
    if not pdfs:
        sys.exit(f"No PDFs found in {args.folder}")

    print(f"Classifying {len(pdfs)} PDFs with {MODEL} (report only, nothing moved)\n")
    print(f"{'CATEGORY':16} {'YEAR':8} {'TITLE':42} FILE")
    print("-" * 110)
    for pdf in pdfs:
        verdict = classify(extract_text(pdf), pdf.name)
        print(f"{verdict['category']:16} {verdict['year']:8} {verdict['title'][:42]:42} {pdf.name}")
        if "raw" in verdict:
            print(f"    (model did not return usable JSON: {verdict['raw'][:80]!r})")


if __name__ == "__main__":
    main()
