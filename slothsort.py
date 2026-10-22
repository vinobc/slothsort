#!/usr/bin/env python3
"""SlothSort — a lazy, local, open-weight PDF tidier.

Point it at a folder of PDFs. A local Gemma model (via Ollama) reads the
first pages of each one, decides what it is, gives it a sensible name and
files it under Sorted/<category>/. Fully offline; nothing leaves the machine.

    python slothsort.py ~/Downloads            # dry run: prints the plan
    python slothsort.py ~/Downloads --apply    # actually rename + move
    python slothsort.py ~/Downloads --undo     # put everything back
"""

import argparse
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

import ollama
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)   # hide fontTools chatter

MODEL = "gemma3:1b"          # swap for any Gemma tag you have pulled
PAGES_TO_READ = 2            # enough to classify; keeps the prompt small
MAX_CHARS = 3000             # cap prompt size so a 1B model stays fast
RETRIES = 2                  # small models occasionally chatter instead of JSON
SORTED_DIR = "Sorted"        # created inside the target folder
UNDO_LOG = "undo.log"        # one JSON line per move, inside Sorted/

CATEGORIES = {
    "papers":          "academic writing: research papers, journal articles, book chapters, conference proceedings, author proofs",
    "syllabi":         "teaching plans: course syllabi, curricula, lesson plans, course outlines",
    "question-papers": "assessments: exam question papers, question banks, answer keys, mark schemes",
    "circulars":       "official institutional communication: notices, circulars, notifications, office orders, holiday lists, academic calendars, schemes and guidelines issued by a university",
    "personal":        "documents about one individual: CV / resume, certificates, ID cards, registrations, bills, receipts",
    "misc":            "only if nothing above fits at all",
}

# Safety net: a 1B model often *describes* a document correctly but fumbles the
# final bucket. If it says "misc", look for category keywords in the filename
# and in the model's own title before accepting that.
KEYWORDS = {
    "circulars":       ["circular", "notice", "notification", "office order", "holiday", "calendar", "scheme", "guidelines"],
    "syllabi":         ["syllabus", "syllabi", "curriculum", "course outline", "lesson plan"],
    "question-papers": ["question paper", "question bank", "exam", "answer key", "mark scheme", "end semester", "mid term"],
    "personal":        ["cv", "resume", "certificate", "registration", "receipt", "invoice", "epan", "pan card", "aadhaar", "passport"],
    "papers":          ["chapter", "journal", "proceedings", "paper", "article", "manuscript", "proof"],
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


# --------------------------------------------------------------------------- reading

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


# --------------------------------------------------------------------------- deciding

def keyword_category(*texts: str) -> str | None:
    """Cheap rule-based fallback: first category whose keyword appears."""
    haystack = " ".join(texts).lower()
    for cat, words in KEYWORDS.items():
        if any(w in haystack for w in words):
            return cat
    return None


def classify(text: str, filename: str) -> dict:
    """Ask the local model; parse JSON; retry a couple of times if it chatters."""
    prompt = PROMPT.format(
        cats=" | ".join(CATEGORIES),
        meanings="\n".join(f"- {k}: {v}" for k, v in CATEGORIES.items()),
        filename=filename,
        text=text[:MAX_CHARS] or "[no extractable text - probably a scanned PDF]",
    )
    verdict = {"category": "misc", "title": "untitled", "year": "unknown"}
    for _ in range(RETRIES + 1):
        reply = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},   # deterministic: same file -> same answer
            format="json",                # Ollama constrains output to valid JSON
        )["message"]["content"]
        match = re.search(r"\{.*\}", reply, re.S)   # tolerate stray text around JSON
        if not match:
            continue
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        cat = str(data.get("category", "misc")).strip().lower()
        verdict = {
            "category": cat if cat in CATEGORIES else "misc",
            "title": str(data.get("title", "untitled")).strip()[:60] or "untitled",
            "year": str(data.get("year", "unknown")).strip(),
        }
        break

    if verdict["category"] == "misc":                       # safety net
        fallback = keyword_category(filename, verdict["title"])
        if fallback:
            verdict["category"] = fallback
            verdict["rescued"] = True
    if not re.fullmatch(r"(19|20)\d\d", verdict["year"]):   # sanitise year
        verdict["year"] = "unknown"
    return verdict


# --------------------------------------------------------------------------- filing

def safe_filename(title: str) -> str:
    """Turn a model title into something every OS accepts."""
    cleaned = re.sub(r"[^\w\s\-&().,]", "", title).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:60] or "untitled"


def plan_destination(folder: Path, pdf: Path, verdict: dict) -> Path:
    year = verdict["year"] if verdict["year"] != "unknown" else "undated"
    dest_dir = folder / SORTED_DIR / verdict["category"]
    dest = dest_dir / f"{year} - {safe_filename(verdict['title'])}.pdf"
    n = 2
    while dest.exists():                                    # never overwrite
        dest = dest_dir / f"{year} - {safe_filename(verdict['title'])} ({n}).pdf"
        n += 1
    return dest


def apply_move(folder: Path, src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dest)
    with (folder / SORTED_DIR / UNDO_LOG).open("a", encoding="utf-8") as log:
        log.write(json.dumps({"from": str(src), "to": str(dest),
                              "at": datetime.now().isoformat(timespec="seconds")}) + "\n")


def undo(folder: Path) -> None:
    log_path = folder / SORTED_DIR / UNDO_LOG
    if not log_path.exists():
        sys.exit("Nothing to undo: no undo.log found.")
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    restored = 0
    for entry in reversed(entries):                         # newest first
        src, dest = Path(entry["to"]), Path(entry["from"])
        if src.exists() and not dest.exists():
            src.rename(dest)
            restored += 1
            print(f"restored  {dest.name}")
    log_path.unlink()
    print(f"\n{restored} file(s) put back.")


# --------------------------------------------------------------------------- main

def main() -> None:
    parser = argparse.ArgumentParser(description="SlothSort: let a local model tidy your PDFs")
    parser.add_argument("folder", type=Path, help="folder containing PDFs")
    parser.add_argument("--apply", action="store_true", help="actually rename and move (default is a dry run)")
    parser.add_argument("--undo", action="store_true", help="reverse the last --apply using undo.log")
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if args.undo:
        undo(folder)
        return

    pdfs = sorted(p for p in folder.iterdir() if p.suffix.lower() == ".pdf" and p.is_file())
    if not pdfs:
        sys.exit(f"No PDFs found in {folder}")

    mode = "APPLYING" if args.apply else "DRY RUN (nothing moved; add --apply to do it)"
    print(f"SlothSort: {len(pdfs)} PDFs, model {MODEL} - {mode}\n")

    for pdf in pdfs:
        verdict = classify(extract_text(pdf), pdf.name)
        dest = plan_destination(folder, pdf, verdict)
        flag = "  (keyword rescue)" if verdict.get("rescued") else ""
        print(f"{pdf.name}\n   -> {dest.relative_to(folder)}{flag}")
        if args.apply:
            apply_move(folder, pdf, dest)

    if args.apply:
        print(f"\nDone. Undo any time with:  python slothsort.py \"{folder}\" --undo")


if __name__ == "__main__":
    main()
