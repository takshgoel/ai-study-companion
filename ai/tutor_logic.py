def generate_tutor_reply(client, question: str, selected_text: str, context_text: str, chat_history: list[dict]) -> str:
    prompt = f"""
You are an AI tutor helping a student learn from lecture slides.

Use this response format exactly:
### Explanation
### Example
### Simplified Version

Rules:
- Base the answer on lecture context when available
- Be clear and concise
- If context is missing, say so briefly and still teach the concept

Highlighted Section:
{selected_text}

Retrieved Lecture Context:
{context_text}

Conversation History:
{chat_history}

Student Question:
{question}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1400,
        temperature=0.3,
    )

    return response.choices[0].message.content
