"""Exam Prep Mode — curated question bank with animations per question.

Supports STEP (Sixth Term Examination Papers) and ЕГЭ (Russian Unified State Exam).
Each question maps to a Manim animation prompt.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from llm import qwen_client
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

# Local question bank cache
QUESTION_BANK_PATH = Path(__file__).parent / "data" / "question_bank.json"
QUESTION_BANK_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class ExamQuestion:
    """An exam question with its animation prompt."""
    exam: str          # "STEP2", "STEP3", "EGE"
    year: int
    question_num: int
    topic: str
    question_text: str
    animation_prompt: str
    difficulty: int     # 1-10
    key_concepts: list[str] = field(default_factory=list)


@dataclass
class ExamResult:
    """Result of an exam prep session."""
    question: ExamQuestion
    user_answer: str
    is_correct: bool
    explanation: str


# ── Pre-built question bank (curated subset) ────────────────────────────────

STEP_QUESTION_BANK: list[ExamQuestion] = [
    # STEP 2 — 2022
    ExamQuestion(
        exam="STEP2", year=2022, question_num=3,
        topic="Fibonacci numbers",
        question_text="Prove that F_{n-1} * F_{n+1} - F_n^2 = (-1)^n",
        animation_prompt="Animate Cassini's identity for Fibonacci numbers: show the relationship F_{n-1}*F_{n+1} - F_n^2 = (-1)^n with a visual pattern of squares and rectangles",
        difficulty=7,
        key_concepts=["Fibonacci", "Cassini identity", "induction"],
    ),
    ExamQuestion(
        exam="STEP2", year=2022, question_num=5,
        topic="Probability",
        question_text="Find the probability that a random permutation has no fixed points (derangements)",
        animation_prompt="Animate the derangement problem: show permutations of {1,2,3,4} with and without fixed points, counting derangements and showing the inclusion-exclusion principle visually",
        difficulty=8,
        key_concepts=["derangements", "inclusion-exclusion", "probability"],
    ),
    ExamQuestion(
        exam="STEP2", year=2022, question_num=8,
        topic="Calculus",
        question_text="Evaluate the integral of 1/(1+x^4) using partial fractions",
        animation_prompt="Animate the partial fraction decomposition of 1/(1+x^4): show the factorization, decomposition, and integration step by step with color-coded terms",
        difficulty=9,
        key_concepts=["partial fractions", "integration", "polynomial factorization"],
    ),
    # STEP 3 — 2022
    ExamQuestion(
        exam="STEP3", year=2022, question_num=4,
        topic="Number theory",
        question_text="Prove Viète's formula for infinite product of cosines",
        animation_prompt="Animate Viète's formula: show the infinite product π/2 = 2/√2 * 2/√(2+√2) * 2/√(2+√(2+√2)) * ... with each term visualized as a nested geometric construction",
        difficulty=8,
        key_concepts=["Viète's formula", "infinite product", "nested radicals"],
    ),
    ExamQuestion(
        exam="STEP3", year=2022, question_num=5,
        topic="Calculus",
        question_text="Show that the integral of f(x) from 0 to π equals the integral of f(π-x) using symmetry",
        animation_prompt="Animate integral symmetry: show the area under f(x) from 0 to π and how it maps to the area under f(π-x) through reflection across x=π/2",
        difficulty=6,
        key_concepts=["integral symmetry", "substitution", "geometric interpretation"],
    ),
    # STEP 2 — 2021
    ExamQuestion(
        exam="STEP2", year=2021, question_num=8,
        topic="Analysis",
        question_text="Prove that e is irrational",
        animation_prompt="Animate the proof that e is irrational: show the series expansion of e, assume e=p/q, derive a contradiction using the remainder term, with clear step-by-step logic visualization",
        difficulty=9,
        key_concepts=["irrationality", "series expansion", "proof by contradiction", "e"],
    ),
]

EGE_QUESTION_BANK: list[ExamQuestion] = [
    ExamQuestion(
        exam="EGE", year=2024, question_num=12,
        topic="Trigonometric equations",
        question_text="Solve the equation sin(x) + cos(x) = 1",
        animation_prompt="Animate solving sin(x) + cos(x) = 1: show the unit circle, the sum of sine and cosine waves, and the intersection points where they equal 1",
        difficulty=5,
        key_concepts=["trigonometric equations", "unit circle", "graphical solution"],
    ),
    ExamQuestion(
        exam="EGE", year=2024, question_num=14,
        topic="Stereometry",
        question_text="Find the angle between two planes in a cube",
        animation_prompt="Animate finding the angle between two planes in a cube: show the cube, the two planes, the dihedral angle, and the calculation using normal vectors",
        difficulty=7,
        key_concepts=["dihedral angle", "normal vectors", "cube geometry"],
    ),
    ExamQuestion(
        exam="EGE", year=2024, question_num=17,
        topic="Optimization",
        question_text="Find the maximum value of f(x) = x(1-x) on [0,1]",
        animation_prompt="Animate optimization: show f(x) = x(1-x) as a parabola, animate the derivative finding the critical point at x=1/2, highlight the maximum value",
        difficulty=4,
        key_concepts=["optimization", "derivative", "critical points"],
    ),
]


def get_question_bank(exam: str) -> list[ExamQuestion]:
    """Get the question bank for a specific exam."""
    exam = exam.upper()
    if exam.startswith("STEP"):
        return STEP_QUESTION_BANK
    elif exam in ("EGE", "ЕГЭ"):
        return EGE_QUESTION_BANK
    return []


def get_random_question(exam: str) -> ExamQuestion | None:
    """Get a random question from the exam bank."""
    import random
    bank = get_question_bank(exam)
    if not bank:
        return None
    return random.choice(bank)


def get_question_by_topic(topic: str) -> ExamQuestion | None:
    """Find a question by topic keyword match."""
    topic_lower = topic.lower()
    for q in STEP_QUESTION_BANK + EGE_QUESTION_BANK:
        if topic_lower in q.topic.lower() or topic_lower in q.question_text.lower():
            return q
    return None


async def generate_animation_for_question(question_text: str, exam: str) -> ExamQuestion | None:
    """Generate an exam-style question and animation prompt using LLM."""
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": f"""You are an {exam} exam question generator.

Create a challenging but solvable {exam}-style math/physics question and a Manim animation prompt for it.

Return ONLY valid JSON, no markdown fences:
{{"question": "the exam question text", "topic": "topic name", "animation_prompt": "detailed Manim animation prompt", "difficulty": 1-10, "key_concepts": ["concept1", "concept2"]}}
"""},
                {"role": "user", "content": f"Generate a {exam} question about: {question_text}"},
            ],
            temperature=0.6,
            max_tokens=1024,
            timeout=30,
            extra_body={"enable_thinking": False},
        )

        content = (response.choices[0].message.content or "").strip()
        content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)

        result = json.loads(content)
        return ExamQuestion(
            exam=exam,
            year=2024,
            question_num=0,
            topic=result.get("topic", ""),
            question_text=result.get("question", ""),
            animation_prompt=result.get("animation_prompt", ""),
            difficulty=result.get("difficulty", 5),
            key_concepts=result.get("key_concepts", []),
        )

    except Exception as e:
        logger.error(f"Exam question generation failed: {e}")
        return None
