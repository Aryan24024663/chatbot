from io import BytesIO
from pathlib import Path
import re
import shutil
import unicodedata

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing
    PdfReader = None

try:
    from docx import Document
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing
    Document = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: no cover - handled at runtime if dependency is missing
    pytesseract = None


BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documents"
TESSERACT_PATH = shutil.which("tesseract")
MIN_TOKEN_LENGTH = 3
DIRECT_ANSWER_SCORE = 4
STOP_WORDS = {
    "a", "an", "and", "are", "can", "for", "from", "how", "in", "is", "it",
    "of", "on", "or", "the", "to", "what", "when", "where", "which", "who",
    "why", "with", "your",
}

model = OllamaLLM(model="gemma:7b")

template = """
You are JAARK Support Chatbot.

Answer the user's question using only the provided reference material.
Do not use outside knowledge or make up information.
Be concise, but include useful details when the reference material provides them.

If the answer is not clearly stated in the reference material, reply exactly:
"I can only answer questions using the provided documents and references."

Reference material:
{doc}

Question:
{question}
"""

prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("“", '"').replace("”", '"')
    normalized = normalized.replace("\u00a0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def tokenize(value: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9']+", normalize_text(value).lower())
    return {
        token
        for token in tokens
        if len(token) >= MIN_TOKEN_LENGTH and token not in STOP_WORDS
    }


def extract_pdf_image_text(page) -> str:
    if not (Image and pytesseract and TESSERACT_PATH):
        return ""

    page_images = getattr(page, "images", None)
    if not page_images:
        return ""

    image_text_parts = []

    for image_file in page_images:
        try:
            image = Image.open(BytesIO(image_file.data))
            ocr_text = pytesseract.image_to_string(image)
        except Exception:
            continue

        cleaned_text = normalize_text(ocr_text)
        if cleaned_text:
            image_text_parts.append(cleaned_text)

    return "\n".join(image_text_parts).strip()


def load_pdf_text(file_path: Path) -> str:
    if PdfReader is None:
        return ""

    reader = PdfReader(str(file_path))
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        page_text = normalize_text(page.extract_text() or "")
        image_text = extract_pdf_image_text(page)

        combined_parts = [part for part in [page_text, image_text] if part]
        if combined_parts:
            pages.append(f"Page {page_number}\n" + "\n".join(combined_parts))

    return "\n\n".join(pages).strip()


def load_docx_text(file_path: Path) -> str:
    if Document is None:
        return ""

    document = Document(str(file_path))
    paragraphs = [normalize_text(paragraph.text) for paragraph in document.paragraphs if normalize_text(paragraph.text)]
    return "\n".join(paragraphs).strip()


def discover_document_paths() -> list[Path]:
    supported_suffixes = {".pdf", ".docx"}
    discovered_paths = []

    if DOCUMENTS_DIR.exists():
        for file_path in sorted(DOCUMENTS_DIR.iterdir()):
            if file_path.is_file() and file_path.suffix.lower() in supported_suffixes:
                discovered_paths.append(file_path)

    for file_path in sorted(BASE_DIR.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in supported_suffixes:
            discovered_paths.append(file_path)

    unique_paths = []
    seen = set()

    for file_path in discovered_paths:
        resolved = file_path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(file_path)

    return unique_paths


def split_into_chunks(source_name: str, text: str, chunk_size: int = 900) -> list[str]:
    cleaned_text = normalize_text(text)
    if not cleaned_text:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if normalize_text(part)]
    if not paragraphs:
        paragraphs = [cleaned_text]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        paragraph = normalize_text(paragraph)
        proposed = f"{current}\n{paragraph}".strip() if current else paragraph

        if len(proposed) <= chunk_size:
            current = proposed
            continue

        if current:
            chunks.append(f"Source: {source_name}\n{current}")

        if len(paragraph) <= chunk_size:
            current = paragraph
            continue

        words = paragraph.split()
        current_words = []

        for word in words:
            proposed_words = " ".join(current_words + [word]).strip()
            if len(proposed_words) > chunk_size and current_words:
                chunks.append(f"Source: {source_name}\n{' '.join(current_words)}")
                current_words = [word]
            else:
                current_words.append(word)

        current = " ".join(current_words).strip()

    if current:
        chunks.append(f"Source: {source_name}\n{current}")

    return chunks


def load_reference_chunks() -> list[str]:
    chunks = []

    for file_path in discover_document_paths():
        if file_path.suffix.lower() == ".pdf":
            file_text = load_pdf_text(file_path)
        elif file_path.suffix.lower() == ".docx":
            file_text = load_docx_text(file_path)
        else:
            file_text = ""

        if file_text:
            chunks.extend(split_into_chunks(file_path.name, file_text))

    return chunks


REFERENCE_CHUNKS = load_reference_chunks()


def score_chunk(question: str, chunk: str) -> tuple[int, int]:
    normalized_question = normalize_text(question).lower()
    normalized_chunk = normalize_text(chunk).lower()
    question_tokens = tokenize(question)
    chunk_tokens = tokenize(chunk)

    overlap_score = len(question_tokens & chunk_tokens)
    phrase_score = 0

    if normalized_question and normalized_question in normalized_chunk:
        phrase_score += 6

    for token in question_tokens:
        if token in normalized_chunk:
            phrase_score += 1

    return (overlap_score + phrase_score, len(chunk))


def select_relevant_chunks(question: str, limit: int = 4) -> str:
    if not REFERENCE_CHUNKS:
        return "No reference documents have been added yet."

    scored_chunks = []
    for chunk in REFERENCE_CHUNKS:
        score, chunk_length = score_chunk(question, chunk)
        if score > 0:
            scored_chunks.append((score, chunk_length, chunk))

    if not scored_chunks:
        return "No relevant reference material was found for this question."

    scored_chunks.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    selected = [chunk for _, _, chunk in scored_chunks[:limit]]
    return "\n\n".join(selected)


def get_ranked_chunks(question: str, limit: int = 4) -> list[tuple[int, str]]:
    if not REFERENCE_CHUNKS:
        return []

    ranked = []
    for chunk in REFERENCE_CHUNKS:
        score, _ = score_chunk(question, chunk)
        if score > 0:
            ranked.append((score, chunk))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[:limit]


def strip_source_prefix(chunk: str) -> str:
    if "\n" not in chunk:
        return chunk.strip()

    _, content = chunk.split("\n", 1)
    return content.strip()


def build_direct_answer(question: str) -> str:
    ranked_chunks = get_ranked_chunks(question, limit=2)
    if not ranked_chunks:
        return ""

    best_score, best_chunk = ranked_chunks[0]
    normalized_question = normalize_text(question).lower()
    allow_low_score_fallback = normalized_question.startswith(("what is ", "who is ", "how do ", "how can "))

    if best_score < DIRECT_ANSWER_SCORE and not allow_low_score_fallback:
        return ""

    question_tokens = tokenize(question)
    candidate_sentences = re.split(r"(?<=[.!?])\s+", strip_source_prefix(best_chunk))
    sentence_scores = []

    for sentence in candidate_sentences:
        cleaned_sentence = normalize_text(sentence)
        if not cleaned_sentence:
            continue

        sentence_tokens = tokenize(cleaned_sentence)
        overlap = len(question_tokens & sentence_tokens)
        contains_all = int(bool(question_tokens) and question_tokens.issubset(sentence_tokens))
        sentence_scores.append((contains_all, overlap, len(cleaned_sentence), cleaned_sentence))

    sentence_scores.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    if sentence_scores and sentence_scores[0][1] > 0:
        top_sentences = [item[3] for item in sentence_scores[:2]]
        return " ".join(top_sentences)

    if allow_low_score_fallback:
        return strip_source_prefix(best_chunk)

    return strip_source_prefix(best_chunk)


def get_response(question: str) -> str:
    direct_answer = build_direct_answer(question)
    if direct_answer:
        return direct_answer

    docs = select_relevant_chunks(question)

    llm_result = chain.invoke({
        "doc": docs,
        "question": question
    })

    return llm_result
