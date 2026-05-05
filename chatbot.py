from io import BytesIO
from pathlib import Path
import re
import shutil
import unicodedata

from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM

# Optional imports. If one of these packages is not installed, the chatbot
# skips that feature instead of crashing immediately.
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


# Project paths and tuning values used throughout the chatbot.
BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documents"
TESSERACT_PATH = shutil.which("tesseract")
MIN_TOKEN_LENGTH = 3
DIRECT_ANSWER_SCORE = 4

# Common words that are ignored when comparing a question with document text.
STOP_WORDS = {
    "a", "an", "and", "are", "can", "for", "from", "how", "in", "is", "it",
    "of", "on", "or", "the", "to", "what", "when", "where", "which", "who",
    "why", "with", "your",
}

# Simple responses for greetings and short messages that do not need the LLM.
SMALL_TALK_RESPONSES = {
    "thanks": "You're welcome. If you need anything else from the provided documents, just ask.",
    "thank you": "You're welcome. If you need anything else from the provided documents, just ask.",
    "ok": "No problem. Feel free to ask another question about the provided documents.",
    "okay": "No problem. Feel free to ask another question about the provided documents.",
    "hi": "Hello. Ask me a question and I'll answer using the provided documents and references.",
    "hello": "Hello. Ask me a question and I'll answer using the provided documents and references.",
    "hey": "Hello. Ask me a question and I'll answer using the provided documents and references.",
    "bye": "Goodbye. If you need more help from the provided documents later, just come back and ask.",
    "goodbye": "Goodbye. If you need more help from the provided documents later, just come back and ask.",
}

# Configure the local Ollama model used to generate answers.
model = OllamaLLM(model="gemma:7b")

# Prompt template that tells the model to answer only from the supplied
# reference material.
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
    # Standardize spacing, quotes, and unicode characters before processing text.
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = normalized.replace("“", '"').replace("”", '"')
    normalized = normalized.replace("\u00a0", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_filename(value: str) -> str:
    # Turn filenames into searchable words by removing extensions and dashes.
    return normalize_text(value.replace(".pdf", "").replace(".docx", "").replace("-", " "))


def tokenize(value: str) -> set[str]:
    # Split text into important lowercase tokens for matching questions to chunks.
    tokens = re.findall(r"[a-z0-9']+", normalize_text(value).lower())
    return {
        token
        for token in tokens
        if len(token) >= MIN_TOKEN_LENGTH and token not in STOP_WORDS
    }


def get_small_talk_response(question: str) -> str:
    # Handle greetings and short polite messages before looking at documents.
    normalized_question = normalize_text(question).lower().strip(" .!?")

    if normalized_question in SMALL_TALK_RESPONSES:
        return SMALL_TALK_RESPONSES[normalized_question]

    if normalized_question.startswith("thanks") or normalized_question.startswith("thank you"):
        return SMALL_TALK_RESPONSES["thanks"]

    return ""


def extract_pdf_image_text(page) -> str:
    # Use OCR to extract text from images inside a PDF page when possible.
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
    # Read normal PDF text and any OCR text from images, grouped by page number.
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
    # Read all non-empty paragraphs from a Word document.
    if Document is None:
        return ""

    document = Document(str(file_path))
    paragraphs = [normalize_text(paragraph.text) for paragraph in document.paragraphs if normalize_text(paragraph.text)]
    return "\n".join(paragraphs).strip()


def discover_document_paths() -> list[Path]:
    # Find supported reference documents in the documents folder and app folder.
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

    # Remove duplicates in case the same file is discovered more than once.
    for file_path in discovered_paths:
        resolved = file_path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(file_path)

    return unique_paths


def split_into_chunks(source_name: str, text: str, chunk_size: int = 900) -> list[str]:
    # Break long document text into smaller chunks so the model receives only
    # the most relevant reference material for a question.
    cleaned_text = normalize_text(text)
    if not cleaned_text:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if normalize_text(part)]
    if not paragraphs:
        paragraphs = [cleaned_text]

    chunks = []
    current = ""
    current_page = ""

    for paragraph in paragraphs:
        paragraph = normalize_text(paragraph)

        # Keep track of page markers so each chunk can cite its source page.
        page_match = re.match(r"^Page\s+(\d+)\b", paragraph)
        if page_match:
            current_page = f"Page {page_match.group(1)}"

        proposed = f"{current}\n{paragraph}".strip() if current else paragraph

        if len(proposed) <= chunk_size:
            current = proposed
            continue

        if current:
            header = f"Source: {source_name}"
            if current_page:
                header += f" | {current_page}"
            chunks.append(f"{header}\n{current}")

        if len(paragraph) <= chunk_size:
            current = paragraph
            continue

        # If one paragraph is still too long, split it further by words.
        words = paragraph.split()
        current_words = []

        for word in words:
            proposed_words = " ".join(current_words + [word]).strip()
            if len(proposed_words) > chunk_size and current_words:
                header = f"Source: {source_name}"
                if current_page:
                    header += f" | {current_page}"
                chunks.append(f"{header}\n{' '.join(current_words)}")
                current_words = [word]
            else:
                current_words.append(word)

        current = " ".join(current_words).strip()

    if current:
        header = f"Source: {source_name}"
        if current_page:
            header += f" | {current_page}"
        chunks.append(f"{header}\n{current}")

    return chunks


def load_reference_chunks() -> list[str]:
    # Load every discovered document and convert its text into searchable chunks.
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


# Reference chunks are loaded once when the module starts.
REFERENCE_CHUNKS = load_reference_chunks()


def score_chunk(question: str, chunk: str) -> tuple[int, int]:
    # Give each chunk a relevance score based on token overlap, phrase matches,
    # and whether the question mentions the source filename.
    normalized_question = normalize_text(question).lower()
    normalized_chunk = normalize_text(chunk).lower()
    question_tokens = tokenize(question)
    chunk_tokens = tokenize(chunk)
    source_name = extract_source_name(chunk)
    source_tokens = tokenize(normalize_filename(source_name))

    overlap_score = len(question_tokens & chunk_tokens)
    phrase_score = 0
    source_score = len(question_tokens & source_tokens) * 3

    if normalized_question and normalized_question in normalized_chunk:
        phrase_score += 6

    for token in question_tokens:
        if token in normalized_chunk:
            phrase_score += 1

    source_phrase = normalize_filename(source_name).lower()
    if source_phrase and source_phrase in normalized_question:
        source_score += 6

    return (overlap_score + phrase_score + source_score, len(chunk))


def select_relevant_chunks(question: str, limit: int = 4) -> str:
    # Choose the best matching chunks and join them into the context sent to the LLM.
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
    # Return scored chunks so other functions can use the best source directly.
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
    # Remove the generated source header so only document content remains.
    if "\n" not in chunk:
        content = chunk.strip()
    else:
        _, content = chunk.split("\n", 1)
        content = content.strip()

    content = re.sub(r"^Page\s+\d+(?:\s+Page\s+\d+\s+of\s+\d+)?\s*", "", content).strip()
    return content


def extract_source_name(chunk: str) -> str:
    # Pull the document filename out of the first line of a chunk.
    first_line = chunk.split("\n", 1)[0].strip()
    source_match = re.match(r"^Source:\s*(.+?)(?:\s+\|\s+Page\s+\d+)?$", first_line)
    if source_match:
        return source_match.group(1).strip()
    return "Provided documents"


def extract_page_reference(chunk: str) -> str:
    # Pull the page label out of the first line of a chunk, if one exists.
    first_line = chunk.split("\n", 1)[0].strip()
    page_match = re.search(r"\b(Page\s+\d+)\b", first_line)
    if page_match:
        return page_match.group(1)
    return ""


def format_source_reference(chunk: str) -> str:
    # Build a readable source citation for the answer.
    source_name = extract_source_name(chunk)
    page_reference = extract_page_reference(chunk)
    if page_reference:
        return f"Source: {source_name} | {page_reference}"
    return f"Source: {source_name}"


def split_answer_units(text: str) -> list[str]:
    # Split model output into bullets or sentences so it can be formatted neatly.
    if "•" in text:
        units = []
        for part in text.split("•"):
            cleaned_part = normalize_text(part)
            if cleaned_part:
                units.append(f"• {cleaned_part}")
        return units

    units = re.split(r"(?<=[.!?])\s+", normalize_text(text))
    return [unit.strip() for unit in units if unit.strip()]


def is_heading_like(unit: str) -> bool:
    # Detect short labels such as "Requirements:" so formatting can split there.
    plain_unit = unit.removeprefix("• ").strip()
    return plain_unit.endswith(":") and len(plain_unit.split()) <= 10


def format_answer_body(text: str) -> str:
    # Clean up the final answer into readable paragraphs without changing meaning.
    text = text.strip()
    if not text:
        return text

    if "\n\n" in text:
        paragraphs = [normalize_text(paragraph) for paragraph in text.split("\n\n") if normalize_text(paragraph)]
        return "\n\n".join(paragraphs)

    units = split_answer_units(text)
    if len(units) <= 2 and len(text) < 280:
        return normalize_text(text)

    paragraphs = []
    current_units = []
    current_tokens = set()

    for unit in units:
        unit_tokens = tokenize(unit)
        current_text = " ".join(current_units).strip()
        current_length = len(current_text)
        topic_overlap = len(current_tokens & unit_tokens)
        should_split = False
        current_unit_count = len(current_units)

        # Start a new paragraph when the current one is getting long or the
        # next unit appears to be a new topic.
        if current_units and is_heading_like(unit):
            should_split = True
        elif current_units and current_length > 180 and topic_overlap == 0:
            should_split = True
        elif current_units and current_length > 260:
            should_split = True
        elif current_units and unit.startswith("•") and current_unit_count >= 2:
            should_split = True
        elif current_units and current_unit_count >= 3 and current_length > 150:
            should_split = True

        if should_split:
            paragraphs.append(" ".join(current_units).strip())
            current_units = [unit]
            current_tokens = set(unit_tokens)
            continue

        current_units.append(unit)
        current_tokens |= unit_tokens

    if current_units:
        paragraphs.append(" ".join(current_units).strip())

    return "\n\n".join(paragraphs)


def format_answer_response(answer_text: str, source_reference: str = "") -> str:
    # Combine the formatted answer with its source citation.
    formatted_answer = format_answer_body(answer_text)
    if source_reference:
        return f"{formatted_answer}\n\n{source_reference}"
    return formatted_answer


def build_direct_answer(question: str) -> str:
    # Try to answer directly from the best matching chunk before asking the LLM.
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

    # Score individual sentences so the answer can be short when a clear match exists.
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
        answer_text = " ".join(top_sentences)
        return format_answer_response(answer_text, format_source_reference(best_chunk))

    if allow_low_score_fallback:
        return format_answer_response(strip_source_prefix(best_chunk), format_source_reference(best_chunk))

    return format_answer_response(strip_source_prefix(best_chunk), format_source_reference(best_chunk))


def get_response(question: str) -> str:
    # Main chatbot entry point used by the Flask app.
    small_talk_response = get_small_talk_response(question)
    if small_talk_response:
        return small_talk_response

    # Prefer a direct extract from the documents when the match is strong enough.
    direct_answer = build_direct_answer(question)
    if direct_answer:
        return direct_answer

    # Otherwise send the most relevant document chunks to the local LLM.
    docs = select_relevant_chunks(question)

    llm_result = chain.invoke({
        "doc": docs,
        "question": question
    })

    # Add the best available source citation to the generated answer.
    ranked_chunks = get_ranked_chunks(question, limit=1)
    if ranked_chunks:
        return format_answer_response(llm_result, format_source_reference(ranked_chunks[0][1]))

    return format_answer_response(llm_result)
