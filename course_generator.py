"""Course Generator — creates multi-animation course series from a topic.

Takes a topic and generates a structured course with progressive animations,
each building on the previous one.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from llm import qwen_client
from config import CHAT_MODEL

logger = logging.getLogger(__name__)

COURSE_PROMPT = """You are a Course Designer for math/science education.

Given a topic, design a course series of animations that progressively teach the concept.

Rules:
1. Start with the most basic concept and build to advanced
2. Each animation should be 15-25 seconds
3. Maximum 5 animations in a course
4. Each animation references prerequisites from earlier animations
5. Include difficulty level (beginner/intermediate/advanced)

Return ONLY valid JSON, no markdown fences:
{"topic": "topic name", "course": [{"title": "animation title", "prompt": "animation prompt for the bot", "prerequisites": ["prev animation title"], "level": "beginner|intermediate|advanced", "key_concepts": ["concept1", "concept2"]}]}

Example:
Input: "derivatives"
Output:
{"topic": "Derivatives", "course": [
  {"title": "What is a Derivative?", "prompt": "Show the slope of a tangent line on a curve y=x^2, animated as the point moves along the curve", "prerequisites": [], "level": "beginner", "key_concepts": ["tangent line", "instantaneous rate"]},
  {"title": "Power Rule", "prompt": "Animate the power rule: d/dx(x^n) = n*x^(n-1) with examples for x^2, x^3, x^4 showing the pattern", "prerequisites": ["What is a Derivative?"], "level": "beginner", "key_concepts": ["power rule", "pattern recognition"]},
  {"title": "Product Rule Visualized", "prompt": "Visualize the product rule: d/dx(f*g) = f'*g + f*g' using area of rectangles that grow and shrink", "prerequisites": ["What is a Derivative?", "Power Rule"], "level": "intermediate", "key_concepts": ["product rule", "area visualization"]},
  {"title": "Chain Rule", "prompt": "Animate the chain rule: d/dx(f(g(x))) = f'(g(x))*g'(x) with nested functions shown as composable machines", "prerequisites": ["What is a Derivative?", "Power Rule"], "level": "intermediate", "key_concepts": ["chain rule", "function composition"]},
  {"title": "Optimization Applications", "prompt": "Show how derivatives find maximum/minimum values: animate a parabola with the vertex highlighted, then extend to real-world optimization", "prerequisites": ["What is a Derivative?", "Power Rule", "Product Rule Visualized", "Chain Rule"], "level": "advanced", "key_concepts": ["optimization", "critical points", "second derivative"]}
]}
"""


@dataclass
class CourseLesson:
    """A single lesson in a course."""
    title: str
    prompt: str
    prerequisites: list[str]
    level: str
    key_concepts: list[str]


@dataclass
class Course:
    """A complete course series."""
    topic: str
    lessons: list[CourseLesson]


async def generate_course(topic: str) -> Course:
    """Generate a course series for a topic.

    Returns a Course with 3-5 progressive lessons.
    """
    try:
        response = await qwen_client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": COURSE_PROMPT},
                {"role": "user", "content": f"Design a course for: {topic}"},
            ],
            temperature=0.4,
            max_tokens=2048,
            timeout=60,
            extra_body={"enable_thinking": False},
        )

        content = (response.choices[0].message.content or "").strip()
        content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
        content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)

        result = json.loads(content)
        topic_name = result.get("topic", topic)
        lessons = []
        for lesson in result.get("course", []):
            lessons.append(CourseLesson(
                title=lesson.get("title", ""),
                prompt=lesson.get("prompt", ""),
                prerequisites=lesson.get("prerequisites", []),
                level=lesson.get("level", "beginner"),
                key_concepts=lesson.get("key_concepts", []),
            ))

        logger.info(f"Course generated: {topic_name} — {len(lessons)} lessons")
        return Course(topic=topic_name, lessons=lessons)

    except Exception as e:
        logger.error(f"Course generation failed: {e}")
        raise
