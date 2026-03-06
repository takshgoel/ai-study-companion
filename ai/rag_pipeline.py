from typing import Callable, Optional

from ai.embeddings import retrieve_chunks

MODEL_NAME = "gpt-4o-mini"
CHUNK_WORDS = 850
CHUNK_OVERLAP = 150
MERGE_BATCH_SIZE = 8

SECTION_SPECS = [
    ("Overview", "Write a broad but complete orientation to the material. Include learning flow and why each major topic matters.", 350),
    ("Key Concepts", "Create an exhaustive concept checklist. Include every concept and subconcept that appears in the lectures. Use bullets and short explanations.", 1000),
    ("Deep Explanation", "Provide deep, rigorous teaching notes. Explain mechanisms, dependencies, assumptions, equations, and edge cases in detail.", 2200),
    ("Real Examples", "Give multiple concrete examples that map to different concepts. Use step-by-step reasoning and practical scenarios.", 900),
    ("Common Mistakes", "List frequent misunderstandings and explicitly correct each one with a clear explanation.", 700),
    ("Practice Questions", "Generate 8-12 exam-style questions spanning easy to advanced levels.", 350),
    ("Quick Summary", "Write a dense recap that reinforces the full concept map and key exam takeaways.", 350),
]


def _split_into_chunks(text: str, chunk_words: int = CHUNK_WORDS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunks = []
    step = max(1, chunk_words - overlap)

    for start in range(0, len(words), step):
        chunk = words[start : start + chunk_words]
        if not chunk:
            continue
        chunks.append(" ".join(chunk))
        if start + chunk_words >= len(words):
            break

    return chunks


def _llm(client, prompt: str, max_tokens: int = 3500, temperature: float = 0.2) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def _extract_chunk_inventory(client, doc_name: str, chunk_text: str, chunk_index: int, chunk_total: int) -> str:
    prompt = f"""
You are building a zero-omission concept inventory.

Task:
Extract EVERY concept, subconcept, definition, formula, rule, and important detail present in this lecture chunk.
Do not summarize away minor concepts.

Document: {doc_name}
Chunk: {chunk_index}/{chunk_total}

Output format:
- Concept: <name>
  - What it is:
  - Why it matters:
  - Related terms/subconcepts:
  - Any formula/rule/condition:
  - Any caveat/exception:

Also include a final checklist line:
CHECKLIST: comma-separated list of all concept names seen in this chunk.

Lecture chunk:
{chunk_text}
"""
    return _llm(client, prompt, max_tokens=2200, temperature=0.0)


def _merge_inventories_once(client, inventories: list[str], label: str) -> str:
    numbered = "\n\n".join([f"INVENTORY {idx + 1}:\n{item}" for idx, item in enumerate(inventories)])

    prompt = f"""
You are merging lecture concept inventories.

Goal:
Produce one merged inventory that preserves ALL concepts from all inputs with zero omissions.

Rules:
- Keep every unique concept and subconcept.
- Merge duplicates only when they mean the same idea.
- Preserve formulas, conditions, caveats, and terminology.
- If unsure, keep both variants and note relation.

Scope label: {label}

Output format:
1) MASTER CHECKLIST: bullet list of all concepts (exhaustive)
2) DETAILED INVENTORY: grouped concept entries with concise but complete notes

Inputs:
{numbered}
"""

    return _llm(client, prompt, max_tokens=3200, temperature=0.0)


def _count_merge_calls(count: int) -> int:
    calls = 0
    current = count

    while current > 1:
        groups = [len(range(i, min(i + MERGE_BATCH_SIZE, current))) for i in range(0, current, MERGE_BATCH_SIZE)]
        calls += sum(1 for size in groups if size > 1)
        current = len(groups)

    return calls


def _reduce_inventories(client, inventories: list[str], label: str, advance: Callable[[str], None]) -> str:
    if not inventories:
        return ""

    current = inventories
    round_idx = 1

    while len(current) > 1:
        next_round = []
        for i in range(0, len(current), MERGE_BATCH_SIZE):
            batch = current[i : i + MERGE_BATCH_SIZE]
            if len(batch) == 1:
                next_round.append(batch[0])
            else:
                merged = _merge_inventories_once(client, batch, label)
                next_round.append(merged)
                advance(f"Merging concept inventories ({label}, round {round_idx})")
        current = next_round
        round_idx += 1

    return current[0]


def _generate_section(client, section_title: str, section_instruction: str, min_words: int, global_inventory: str, additional_context: str) -> str:
    prompt = f"""
You are writing one section of a final study guide.

Section title: {section_title}

Mandatory requirements:
- Write in depth with strong teaching detail.
- Minimum length: {min_words} words.
- Do not omit relevant concepts from the inventory.
- Use plain text formulas (no LaTeX).
- Keep it clear, structured, and exam-oriented.

Section-specific instruction:
{section_instruction}

Additional context from instructor:
{additional_context}

Global concept inventory (must be covered across the final guide):
{global_inventory}

Return only section body content (no header line).
"""

    return _llm(client, prompt, max_tokens=4200, temperature=0.2)


def generate_study_guide(client, docs: list[dict], additional_context: str, progress_callback: Optional[Callable[[int, int, str], None]] = None) -> str:
    if not docs:
        return "## Overview\n\n_No lecture material available._"

    doc_chunks: list[tuple[dict, list[str]]] = []
    for doc in docs:
        chunks = _split_into_chunks(doc["content"])
        if chunks:
            doc_chunks.append((doc, chunks))

    if not doc_chunks:
        return "## Overview\n\n_No parseable content found in uploaded lectures._"

    chunk_calls = sum(len(chunks) for _, chunks in doc_chunks)
    doc_merge_calls = sum(_count_merge_calls(len(chunks)) for _, chunks in doc_chunks)
    global_merge_calls = _count_merge_calls(len(doc_chunks))
    section_calls = len(SECTION_SPECS)
    total_steps = max(1, chunk_calls + doc_merge_calls + global_merge_calls + section_calls)

    done = 0

    def advance(message: str):
        nonlocal done
        done += 1
        if progress_callback:
            progress_callback(done, total_steps, message)

    doc_level_inventories = []

    for doc, chunks in doc_chunks:
        chunk_inventories = []
        for idx, chunk_text in enumerate(chunks, start=1):
            chunk_inventory = _extract_chunk_inventory(
                client=client,
                doc_name=doc["name"],
                chunk_text=chunk_text,
                chunk_index=idx,
                chunk_total=len(chunks),
            )
            chunk_inventories.append(chunk_inventory)
            advance(f"Reading {doc['name']} chunk {idx}/{len(chunks)}")

        doc_inventory = _reduce_inventories(client, chunk_inventories, f"Document: {doc['name']}", advance)
        doc_level_inventories.append(f"DOCUMENT: {doc['name']}\n{doc_inventory}")

    global_inventory = _reduce_inventories(client, doc_level_inventories, "All documents", advance)

    sections = []
    for section_title, section_instruction, min_words in SECTION_SPECS:
        body = _generate_section(
            client=client,
            section_title=section_title,
            section_instruction=section_instruction,
            min_words=min_words,
            global_inventory=global_inventory,
            additional_context=additional_context,
        )
        sections.append(f"## {section_title}\n\n{body.strip()}")
        advance(f"Writing section: {section_title}")

    return "\n\n---\n\n".join(sections)


def build_context_for_question(question: str, vector_store: dict, k: int = 8) -> str:
    chunks = retrieve_chunks(question, vector_store, k=k)
    if not chunks:
        return ""

    return "\n\n".join([chunk["text"] for chunk in chunks])