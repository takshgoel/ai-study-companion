import re

REQUIRED_SECTIONS = [
    "Overview",
    "Key Concepts",
    "Deep Explanation",
    "Real Examples",
    "Common Mistakes",
    "Practice Questions",
    "Quick Summary",
]

SECTION_ALIASES = {
    "overview": "Overview",
    "introduction": "Overview",
    "key concepts": "Key Concepts",
    "core concepts": "Key Concepts",
    "deep explanation": "Deep Explanation",
    "detailed explanations": "Deep Explanation",
    "detailed explanation": "Deep Explanation",
    "real examples": "Real Examples",
    "real world examples": "Real Examples",
    "worked examples": "Real Examples",
    "common mistakes": "Common Mistakes",
    "practice questions": "Practice Questions",
    "quick summary": "Quick Summary",
    "summary": "Quick Summary",
    "key takeaways": "Quick Summary",
}


def slugify(text: str) -> str:
    slug = text.strip().lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug if slug else "section"


def extract_headings(markdown_text: str) -> list[str]:
    return re.findall(r"^##\s+(.+)$", markdown_text, flags=re.MULTILINE)


def normalize_study_guide(raw_markdown: str) -> str:
    chunks = re.split(r"^##\s+", raw_markdown, flags=re.MULTILINE)
    sections = {}

    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        lines = chunk.splitlines()
        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        normalized_key = SECTION_ALIASES.get(title.lower())
        if normalized_key and normalized_key not in sections:
            sections[normalized_key] = body

    output_parts = []
    for idx, section_name in enumerate(REQUIRED_SECTIONS):
        body = sections.get(section_name, "")
        output_parts.append(f"## {section_name}\n\n{body if body else '_No content generated for this section._'}")
        if idx < len(REQUIRED_SECTIONS) - 1:
            output_parts.append("\n---\n")

    return "\n".join(output_parts).strip()


def add_anchor_links(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    out = []

    for line in lines:
        if line.startswith("## "):
            heading = line[3:].strip()
            out.append(f"<a id=\"{slugify(heading)}\"></a>")
        out.append(line)

    return "\n".join(out)
