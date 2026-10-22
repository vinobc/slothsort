# SlothSort

A lazy academic's file tidier. Point it at a folder full of downloaded PDFs — papers, syllabi, question papers, circulars — and it reads each one with a local open-weight model (Gemma via Ollama), gives it a sensible name, and files it into the right folder. Fully offline. Nothing leaves your laptop.

Built for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

## Why open-source AI

Institutional documents — exam papers, student lists, internal circulars — should never be uploaded to a third-party API. Running Gemma locally through Ollama means the tidier works with no internet, costs nothing per run, and the model can be swapped with a one-line config change.

## Quick start

```bash
# 1. Install Ollama (https://ollama.com) and pull a Gemma model
ollama pull gemma3:1b

# 2. Install Python deps
pip install -r requirements.txt

# 3. Dry run on a folder (shows what it would do, moves nothing)
python slothsort.py ~/Downloads --dry-run

# 4. Do it for real
python slothsort.py ~/Downloads
```

## How it works

1. Extracts the first ~2 pages of text from each PDF (`pypdf`).
2. Asks the local model for a JSON verdict: category, short title, year.
3. Renames to `YYYY - short-title.pdf` and moves it into `Sorted/<category>/`.
4. Writes an `undo.log` so every move can be reversed.

## Categories

`papers`, `syllabi`, `question-papers`, `circulars`, `books`, `misc` — edit `CATEGORIES` in `slothsort.py` to suit your own clutter.

## License

MIT
