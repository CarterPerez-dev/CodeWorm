"""
ⒸAngelaMos | 2026
llm/prompts.py
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from codeworm.models import Language

if TYPE_CHECKING:
    from codeworm.analysis import AnalysisCandidate


SYSTEM_PROMPT = """You are a technical documentation writer analyzing code snippets.

Your task is to write clear, concise documentation that explains:
- What the code does (the "what")
- Why it matters or when to use it (the "why")
- Any notable patterns, trade-offs, or gotchas

Rules:
1. Only reference code that exists in the provided snippet
2. Do not invent or assume external functionality
3. Be specific - mention actual variable/function names
4. Keep explanations under 200 words
5. Use markdown formatting
6. Focus on practical understanding, not line-by-line description"""


DOCUMENTATION_TEMPLATE = """Analyze and document this {language} code:

```{language}
{source}
```

Context:
- Function/Class: {name}
- File: {file_path}
- Repository: {repo}
- Complexity: {complexity} (cyclomatic)
- Lines: {line_count}

Write technical documentation (100-200 words) covering:
1. Purpose and behavior
2. Key implementation details
3. When/why to use this code
4. Any patterns or gotchas worth noting"""


COMMIT_MESSAGE_TEMPLATE = """Based on this documentation snippet, generate a natural-sounding git commit message.

Documentation:
{documentation}

Code context:
- Function: {name}
- Language: {language}
- Repository: {repo}

Generate a commit message that:
- Starts with a verb (Document, Add, Analyze, etc)
- Is under 72 characters
- Sounds natural, not robotic
- Mentions the function/concept name

Return ONLY the commit message, nothing else."""


LANGUAGE_HINTS: dict[Language, str] = {
    Language.PYTHON: "Focus on Pythonic patterns, type hints, decorators, and context managers",
    Language.TYPESCRIPT: "Note TypeScript-specific types, generics, and async patterns",
    Language.TSX: "Cover React component patterns, hooks usage, and prop types",
    Language.JAVASCRIPT: "Highlight async/await patterns, closures, and module patterns",
    Language.GO: "Emphasize Go idioms like error handling, goroutines, and interfaces",
    Language.RUST: "Focus on ownership, borrowing, lifetimes, and Result/Option patterns",
}


@dataclass
class PromptContext:
    """
    Context for generating prompts
    """
    source: str
    name: str
    language: Language
    repo: str
    file_path: str
    complexity: float
    line_count: int
    class_name: str | None = None
    decorators: list[str] | None = None
    is_async: bool = False


class PromptBuilder:
    """
    Builds prompts for documentation generation
    """
    def __init__(self, style: str = "technical") -> None:
        """
        Initialize with documentation style
        """
        self.style = style

    def build_documentation_prompt(self, context: PromptContext) -> tuple[str, str]:
        """
        Build system and user prompts for documentation
        Returns (system_prompt, user_prompt)
        """
        system = SYSTEM_PROMPT

        lang_hint = LANGUAGE_HINTS.get(context.language, "")
        if lang_hint:
            system += f"\n\nLanguage-specific guidance: {lang_hint}"

        display_name = context.name
        if context.class_name:
            display_name = f"{context.class_name}.{context.name}"

        user = DOCUMENTATION_TEMPLATE.format(
            language=context.language.value,
            source=context.source,
            name=display_name,
            file_path=context.file_path,
            repo=context.repo,
            complexity=context.complexity,
            line_count=context.line_count,
        )

        if context.decorators:
            user += f"\n\nDecorators present: {', '.join(context.decorators)}"
        if context.is_async:
            user += "\n\nThis is an async function."

        return system, user

    def build_commit_message_prompt(
        self,
        documentation: str,
        context: PromptContext,
    ) -> tuple[str, str]:
        """
        Build prompt for generating commit message
        """
        system = "You generate natural, human sounding git commit messages. Be concise and specific."

        display_name = context.name
        if context.class_name:
            display_name = f"{context.class_name}.{context.name}"

        user = COMMIT_MESSAGE_TEMPLATE.format(
            documentation=documentation[:500],
            name=display_name,
            language=context.language.value,
            repo=context.repo,
        )

        return system, user

    @classmethod
    def from_candidate(cls, candidate: AnalysisCandidate) -> PromptContext:
        """
        Create prompt context from analysis candidate
        """
        return PromptContext(
            source=candidate.snippet.source,
            name=candidate.snippet.function_name or candidate.snippet.class_name or "unknown",
            language=candidate.snippet.language,
            repo=candidate.snippet.repo,
            file_path=str(candidate.scanned_file.relative_path),
            complexity=candidate.snippet.complexity,
            line_count=candidate.snippet.line_count,
            class_name=candidate.snippet.class_name,
            decorators=candidate.parsed_function.decorators,
            is_async=candidate.parsed_function.is_async,
        )


def build_documentation_prompt(candidate: AnalysisCandidate) -> tuple[str, str]:
    """
    Convenience function to build documentation prompt from candidate
    """
    builder = PromptBuilder()
    context = PromptBuilder.from_candidate(candidate)
    return builder.build_documentation_prompt(context)


def build_commit_prompt(documentation: str, candidate: AnalysisCandidate) -> tuple[str, str]:
    """
    Convenience function to build commit message prompt
    """
    builder = PromptBuilder()
    context = PromptBuilder.from_candidate(candidate)
    return builder.build_commit_message_prompt(documentation, context)
