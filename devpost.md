*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

I teach computer science at a university in Bengaluru. My Downloads folder is where institutional PDFs go to die: circulars, academic calendars, holiday lists, a Springer chapter proof, my own CV, a tax document. Ten of them had been sitting there since June. Would I have ever sorted them by hand? Never.

**SlothSort** is a command-line tool that does it for me. Point it at a folder, and a local open-weight model (Gemma 3 1B, running through Ollama on my laptop) reads the first two pages of each PDF, decides what kind of document it is, gives it a sensible name, and files it under `Sorted/<category>/`. Every move is logged, so `--undo` puts everything back.

```
$ python slothsort.py ~/Downloads --apply
SlothSort: 10 PDFs, model gemma3:1b - APPLYING

713158_1_En_6_Chapter_Author.pdf
   -> Sorted/papers/2027 - Service-Oriented Architecture Principles in Indias Digital.pdf
AUB- List of Holidays for the Year 2026.pdf
   -> Sorted/circulars/2026 - Holiday Calendar.pdf  (keyword rescue)
CVDrRVinobChander.pdf
   -> Sorted/personal/2020 - CV.pdf
Notification_Faculty Incentive Scheme and Guidelines.pdf
   -> Sorted/circulars/2023 - Faculty Incentive Scheme and Guidelines.pdf
Print _ Udyam Registration Certificate.pdf
   -> Sorted/personal/2020 - UDYAM Registration Certificate.pdf
...
Done. Undo any time with:  python slothsort.py "/Users/vinob/Downloads" --undo
```

Who gets to be lazier? Me, and anyone whose employer communicates in PDF.

## Demo

Before: ten PDFs with names like `713158_1_En_6_Chapter_Author.pdf` and `UTIITSL_ePAN_Q022008390_20122025_001807.pdf` loose in Downloads.

After one command:

![The Sorted folder after one run: circulars, papers, personal, and undo.log](https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/ibvsiwtosukqvhg8wwpd.png)

Ten for ten on category, on real files, on a laptop, with no internet connection required.

## Code

{% embed https://github.com/vinobc/slothsort %}

About 200 lines of Python. Dependencies: `ollama` and `pypdf`. MIT licensed.

## How I Built It

**Open-source AI at the core:** Gemma 3 1B (Google's open-weight model) served locally by Ollama. The whole pipeline is PDF → `pypdf` text extraction → prompt → local model → JSON → rename and move. There is no API key anywhere in the project.

I built it in three small steps, testing each one on my real Downloads folder before moving on. The interesting part was discovering what a 1-billion-parameter model is and isn't good at.

**Step 1: can it read at all?** The first version just extracted text from one PDF and asked Gemma "what kind of document is this?". It answered in prose: *"This is a calendar or holiday schedule."* Correct, but prose is useless for sorting.

**Step 2: make it answer in a fixed shape.** I switched to Ollama's `format="json"`, which constrains the model's output to valid JSON at the token level, and set `temperature=0` so the same file always gets the same answer. The prompt asks for `{"category", "title", "year"}` with the category drawn from a fixed list. Crucially, the list gives each category a *meaning* ("circulars: notices, holiday lists, academic calendars…"), not just a label. Small models classify far better when told what each bucket is for.

First run: two correct categories out of the eight files it reached, four `misc`, and a crash on the ninth, an encrypted PDF.

**Step 2b: give it the filename.** Adding the original filename to the prompt as "a strong hint" took it from two correct to six out of ten in one go. A lazy human uses the filename too; there was no reason to hide it from the model.

But three files were still `misc`, and here's the thing: the model had *titled* them "Circular Academic Calendar" and "Holiday Calendar". It knew what they were. It just fumbled the last step of picking the bucket. That's a recognisable 1B-model failure mode: good at describing, shaky at committing.

**Step 3: a 10-line safety net.** If the model says `misc`, SlothSort checks the filename and the model's own title for category keywords before accepting that. Four of the ten files were rescued this way, including a truly encrypted tax document that `pypdf` couldn't open at all, which still landed in `personal` because "ePAN" was in its name. The model does the reading; a tiny rule catches the fumble. That hybrid took the score from 6/10 to 10/10 without touching the model.

Then the boring-but-essential parts: never overwrite an existing file, write every move to `undo.log`, dry-run by default, `--apply` to commit, `--undo` to reverse.

What it still gets wrong: the year is a guess (it dated my 2026 chapter proof "2027"), and scanned PDFs have no text to read, so they depend entirely on the filename. Both are honest limits of a 1B model reading two pages. Neither has yet put a file in the wrong folder, and the undo log is there for the day one does.

## Why Does Open Innovation Matter?

Three reasons, in order of how much I care:

**1. These documents should never leave the machine.** University circulars, student-facing calendars, a tax ID document, my CV. Uploading an institution's internal paperwork to a third-party API to save myself ten minutes is a bad trade, and at a university it may not even be permitted. With Gemma running locally through Ollama, the files are read on my laptop and the text never goes anywhere. That's not a feature I added; it's the architecture.

**2. It costs nothing, forever.** No key, no quota, no per-call bill. I can run it on every download for the rest of my career and the marginal cost is a few seconds of CPU. A closed API would have made "run it on everything, always" a budgeting question.

**3. I could see and fix the model's weaknesses.** Because the model is small and local, I could run the same ten files again and again in minutes, watch exactly where it failed, and design around it: structured output, the filename hint, the keyword safety net. That tight loop of *observe the failure, change one thing, re-run* is how I'd teach debugging to students, and it only works when the model is yours to poke at. If I wanted better classification tomorrow, `MODEL = "gemma3:4b"` is a one-line change.

Where the open approach beat a closed one: a frontier API would probably have classified all ten files correctly on the first try, and I'd have learned nothing, paid for every run, and shipped my employer's circulars to someone else's server. The 1B model made me a better engineer of the system around it.

## My Agent Session

Built with Claude as a pair programmer: it drafted the code, I ran every step on my own Downloads folder, and each change came from reading the failures together. The six commits are that loop in code form.

## The Lazy Payoff

The ten PDFs had been in my Downloads since June. I had never sorted them and was never going to. SlothSort did it in well under a minute on an Apple Silicon laptop, and I spent that minute doing nothing, which is the point.

The real payoff is ongoing: every PDF the university sends me now has somewhere to go, and the cost of filing it is one command I don't have to think about.

## Prize Categories

- **Best Use of Gemma**: Gemma 3 1B is the only model in the project, running locally via Ollama.
