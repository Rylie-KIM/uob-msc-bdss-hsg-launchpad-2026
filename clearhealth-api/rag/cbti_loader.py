"""
Load CBT-i documents into the ChromaDB vector store.

Usage:
    python rag/cbti_loader.py

Place CBT-i PDF or .txt files in rag/cbti_docs/ before running.
If no files exist, a built-in CBT-i knowledge base is loaded as fallback.
"""
import os
import uuid
from pathlib import Path
from vector_store import add_documents, is_empty

DOCS_DIR = Path(__file__).parent / "cbti_docs"

# Fallback built-in CBT-i knowledge (used when no PDF files are present)
BUILTIN_CBTI = [
    ("stimulus_control", """Stimulus Control Therapy for Insomnia:
Go to bed only when sleepy. Use the bed only for sleep (and sex) — not for reading, watching TV, or using your phone.
If you cannot sleep within 20 minutes, get out of bed and do something calm until you feel sleepy again.
Set a consistent wake time every day, including weekends.
Avoid napping during the day."""),

    ("sleep_restriction", """Sleep Restriction Therapy:
Limit time in bed to match your actual sleep time to build up sleep pressure.
If you sleep 5 hours but spend 8 hours in bed, start with a sleep window of 5.5 hours.
Gradually extend the window by 15-30 minutes when sleep efficiency exceeds 85%.
This therapy temporarily increases daytime sleepiness — it is normal and expected."""),

    ("sleep_hygiene", """Sleep Hygiene Guidelines:
Keep a regular sleep schedule — same bedtime and wake time every day.
Avoid caffeine after 2pm. Avoid alcohol close to bedtime (it disrupts sleep architecture).
Keep the bedroom cool (16-18°C), dark, and quiet.
Avoid screens for 1 hour before bed; blue light suppresses melatonin.
Regular exercise improves sleep quality but avoid intense exercise within 2 hours of bedtime.
Avoid large meals within 2 hours of bedtime."""),

    ("relaxation", """Relaxation Techniques for Sleep:
Progressive Muscle Relaxation: Tense and release each muscle group from feet to face, 5 seconds each.
4-7-8 Breathing: Inhale for 4 counts, hold for 7, exhale for 8. Repeat 4 times.
Body Scan: Lie still and mentally scan from feet to head, noticing and releasing tension.
These techniques activate the parasympathetic nervous system to counteract the stress response."""),

    ("cognitive_restructuring", """Cognitive Restructuring for Sleep Anxiety:
Challenge unhelpful thoughts like 'I must get 8 hours or I will fail'.
Reality check: Most adults function adequately on 6-7 hours occasionally. One bad night is not catastrophic.
Reframe: 'Lying in bed resting is still beneficial even if I am not asleep.'
Avoid clock-watching — it increases sleep anxiety. Turn the clock away.
Replace: 'I need to sleep now' with 'I will let sleep come naturally.'"""),

    ("sleep_diary", """Sleep Diary Instructions:
Record daily: time you got into bed, time you fell asleep, number of awakenings, final wake time, total sleep time, sleep quality (1-5).
Use this data to identify patterns — what helps and what hinders your sleep.
Complete the diary in the morning while memory is fresh.
The diary is a core CBT-i tool — it helps personalise your treatment."""),

    ("jet_lag", """Jet Lag and Sleep for International Students:
Jet lag occurs when your body clock is misaligned with local time.
Recovery tip: Expose yourself to morning daylight to reset your circadian rhythm.
Avoid sleeping at the wrong local time — stay awake until local bedtime even if tired.
Light meals, regular exercise, and consistent wake times speed adjustment.
Full adaptation typically takes 1 day per hour of time zone difference.
NHS advice: melatonin can help but is prescription-only in the UK — speak to a GP."""),

    ("when_to_seek_help", """When to Seek Professional Help for Sleep:
See your GP if: insomnia has lasted more than 3 months, is severely affecting daily life, or is accompanied by symptoms of depression or anxiety.
Your university health centre can refer you to counselling or sleep clinics.
NHS talking therapies (IAPT) offer free CBT-i for mild-to-moderate insomnia.
Student Minds (0300 102 1234) offers peer support for student mental health.
Samaritans (116 123) are available 24/7 if you are in crisis."""),
]


def load_pdfs() -> list[tuple[str, str]]:
    """Load text from PDF files in cbti_docs/. Returns (doc_id, text) pairs."""
    chunks = []
    try:
        from pypdf import PdfReader
    except ImportError:
        print("pypdf not installed — skipping PDF loading")
        return chunks

    for pdf_path in DOCS_DIR.glob("*.pdf"):
        reader = PdfReader(pdf_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if len(text.strip()) > 100:
                doc_id = f"{pdf_path.stem}_p{i}"
                chunks.append((doc_id, text.strip()))
        print(f"Loaded {len(reader.pages)} pages from {pdf_path.name}")
    return chunks


def load_txts() -> list[tuple[str, str]]:
    """Load .txt files from cbti_docs/."""
    chunks = []
    for txt_path in DOCS_DIR.glob("*.txt"):
        text = txt_path.read_text(encoding="utf-8")
        # Simple chunking by paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 100]
        for i, para in enumerate(paragraphs):
            chunks.append((f"{txt_path.stem}_{i}", para))
        print(f"Loaded {len(paragraphs)} chunks from {txt_path.name}")
    return chunks


def seed():
    """Load all CBT-i documents into the vector store."""
    if not is_empty():
        print("Vector store already populated — skipping")
        return

    chunks = load_pdfs() + load_txts()

    if not chunks:
        print("No PDF/txt files found in cbti_docs/ — using built-in knowledge base")
        chunks = BUILTIN_CBTI

    ids = [c[0] for c in chunks]
    texts = [c[1] for c in chunks]
    add_documents(texts, ids)
    print(f"Loaded {len(texts)} chunks into vector store")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    seed()
