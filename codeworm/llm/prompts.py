"""
ⒸAngelaMos | 2026
llm/prompts.py
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from codeworm.models import DocType, Language

if TYPE_CHECKING:
    from codeworm.analysis import AnalysisCandidate
    from codeworm.analysis.targets import DocumentationTarget
    from codeworm.core.config import PromptSettings


DEFAULT_SYSTEM_PROMPT = """You are a technical documentation writer analyzing code snippets.

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

DEFAULT_DOCUMENTATION_TEMPLATE = """Analyze and document this {language} code:

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

DEFAULT_COMMIT_MESSAGE_TEMPLATE = """Based on this documentation snippet, generate a natural-sounding git commit message.

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

SECURITY_REVIEW_SYSTEM_PROMPT = """You are a security analyst reviewing code for vulnerabilities.

Analyze the code for:
- Injection vulnerabilities (SQL, command, XSS)
- Authentication and authorization issues
- Hardcoded secrets or credentials
- Race conditions and TOCTOU bugs
- Input validation gaps
- Insecure deserialization
- Error handling that leaks information

Rules:
1. Only reference code in the provided snippet
2. Be specific about line numbers and variable names
3. Rate severity: Critical, High, Medium, Low, Info
4. Suggest concrete fixes
5. Keep under 200 words
6. Use markdown formatting"""

SECURITY_REVIEW_TEMPLATE = """Review this {language} code for security issues:

```{language}
{source}
```

Context:
- Function/Class: {name}
- File: {file_path}
- Repository: {repo}

Write a security review (100-200 words) covering:
1. Any vulnerabilities found (with severity)
2. Attack vectors if applicable
3. Recommended fixes
4. Overall security posture"""

PERFORMANCE_ANALYSIS_SYSTEM_PROMPT = """You are a performance engineer analyzing code efficiency.

Analyze the code for:
- Time complexity (Big O notation)
- Space complexity and memory allocation
- Unnecessary iterations or redundant operations
- Blocking calls in async contexts
- N+1 query patterns
- Missing caching opportunities
- Resource leaks (unclosed connections, file handles)

Rules:
1. Only reference code in the provided snippet
2. Be specific about which operations are costly
3. Suggest concrete optimizations
4. Keep under 200 words
5. Use markdown formatting"""

PERFORMANCE_ANALYSIS_TEMPLATE = """Analyze this {language} code for performance:

```{language}
{source}
```

Context:
- Function/Class: {name}
- File: {file_path}
- Complexity: {complexity} (cyclomatic)
- Lines: {line_count}

Write a performance analysis (100-200 words) covering:
1. Time and space complexity
2. Bottlenecks or inefficiencies
3. Optimization opportunities
4. Resource usage concerns"""

TIL_SYSTEM_PROMPT = """You write short, focused "Today I Learned" entries about interesting code techniques.

Style:
- Casual and conversational
- Focus on ONE interesting thing
- Explain why it's clever or useful
- Make it memorable and shareable

Rules:
1. Only reference code in the provided snippet
2. Pick the single most interesting aspect
3. Keep it under 100 words
4. Use markdown formatting
5. Start with "TIL:" or a similar hook"""

TIL_TEMPLATE = """Write a TIL (Today I Learned) entry about this {language} code:

```{language}
{source}
```

Context:
- Function/Class: {name}
- Repository: {repo}

Write a short TIL entry (50-100 words) about the most interesting technique or pattern in this code."""

FILE_DOC_SYSTEM_PROMPT = """You document source files at a high level, explaining their purpose and architecture.

Focus on:
- What this file is responsible for
- Key exports and public API
- How it fits into the larger project
- Design decisions and patterns used
- Dependencies and relationships

Rules:
1. Only reference code in the provided content
2. Focus on the "big picture" not individual functions
3. Keep under 200 words
4. Use markdown formatting"""

FILE_DOC_TEMPLATE = """Document this {language} source file:

{source}

Context:
- File: {file_path}
- Repository: {repo}
- Lines: {line_count}

Write file-level documentation (100-200 words) covering:
1. File purpose and responsibility
2. Key exports or public interface
3. How it fits in the project
4. Notable design decisions"""

CLASS_DOC_SYSTEM_PROMPT = """You document classes, explaining their design, responsibility, and interface.

Focus on:
- Single Responsibility: what this class owns
- Public interface and method signatures
- Design patterns used (factory, observer, strategy, etc.)
- Relationship to other classes
- State management approach

Rules:
1. Only reference code in the provided snippet
2. Focus on the class as a whole, not individual methods
3. Keep under 200 words
4. Use markdown formatting"""

CLASS_DOC_TEMPLATE = """Document this {language} class:

```{language}
{source}
```

Context:
- Class: {name}
- File: {file_path}
- Repository: {repo}

Write class documentation (100-200 words) covering:
1. Class responsibility and purpose
2. Public interface (key methods)
3. Design patterns used
4. How it fits in the architecture"""

MODULE_DOC_SYSTEM_PROMPT = """You document packages/modules, explaining how they organize code.

Focus on:
- Package purpose and scope
- How files within relate to each other
- Public API surface
- Dependency direction
- When a developer would interact with this package

Rules:
1. Only reference content in the provided listing
2. Explain the organizational structure
3. Keep under 200 words
4. Use markdown formatting"""

MODULE_DOC_TEMPLATE = """Document this package/module structure:

{source}

Context:
- Repository: {repo}

Write module-level documentation (100-200 words) covering:
1. Package purpose and scope
2. How the files relate to each other
3. Public API surface
4. When a developer would use this module"""

CODE_EVOLUTION_SYSTEM_PROMPT = """You analyze code changes, explaining what changed and why.

Focus on:
- What was changed (added, modified, removed)
- Why this change was likely made
- Impact on behavior or API
- Whether this is a bug fix, feature, or refactor
- Any risks introduced by the change

Rules:
1. Only reference the diff provided
2. Be specific about what lines changed
3. Keep under 200 words
4. Use markdown formatting"""

CODE_EVOLUTION_TEMPLATE = """Analyze this code change:

{source}

Context:
- Repository: {repo}

Write a change analysis (100-200 words) covering:
1. What was changed
2. Why it was likely changed
3. Impact on behavior
4. Any risks or concerns"""

PATTERN_ANALYSIS_SYSTEM_PROMPT = """You identify and explain design patterns found in code.

Focus on:
- Which design pattern is being used
- How it's implemented in this specific code
- Benefits of using this pattern here
- Any deviations from the canonical pattern
- When this pattern is and isn't appropriate

Rules:
1. Only reference code in the provided snippet
2. Be specific about the pattern implementation
3. Keep under 200 words
4. Use markdown formatting"""

PATTERN_ANALYSIS_TEMPLATE = """Analyze the design pattern in this {language} code:

```{language}
{source}
```

Context:
- File: {file_path}
- Repository: {repo}
- Detected pattern: {name}

Write a pattern analysis (100-200 words) covering:
1. Which pattern is used and how
2. Benefits of this pattern here
3. Any deviations from the standard pattern
4. When this pattern is appropriate"""

DOC_TYPE_PROMPTS: dict[
    DocType,
    tuple[str,
          str]] = {
              DocType.FUNCTION_DOC:
              (DEFAULT_SYSTEM_PROMPT,
               DEFAULT_DOCUMENTATION_TEMPLATE),
              DocType.SECURITY_REVIEW:
              (SECURITY_REVIEW_SYSTEM_PROMPT,
               SECURITY_REVIEW_TEMPLATE),
              DocType.PERFORMANCE_ANALYSIS:
              (PERFORMANCE_ANALYSIS_SYSTEM_PROMPT,
               PERFORMANCE_ANALYSIS_TEMPLATE),
              DocType.TIL: (TIL_SYSTEM_PROMPT,
                            TIL_TEMPLATE),
              DocType.FILE_DOC: (FILE_DOC_SYSTEM_PROMPT,
                                 FILE_DOC_TEMPLATE),
              DocType.CLASS_DOC: (CLASS_DOC_SYSTEM_PROMPT,
                                  CLASS_DOC_TEMPLATE),
              DocType.MODULE_DOC: (MODULE_DOC_SYSTEM_PROMPT,
                                   MODULE_DOC_TEMPLATE),
              DocType.CODE_EVOLUTION:
              (CODE_EVOLUTION_SYSTEM_PROMPT,
               CODE_EVOLUTION_TEMPLATE),
              DocType.PATTERN_ANALYSIS:
              (PATTERN_ANALYSIS_SYSTEM_PROMPT,
               PATTERN_ANALYSIS_TEMPLATE),
          }

DEFAULT_LANGUAGE_HINTS: dict[
    str,
    str
] = {
    "python":
    "Focus on Pythonic patterns, type hints, decorators, and context managers",
    "typescript": "Note TypeScript-specific types, generics, and async patterns",
    "tsx": "Cover React component patterns, hooks usage, and prop types",
    "javascript": "Highlight async/await patterns, closures, and module patterns",
    "go": "Emphasize Go idioms like error handling, goroutines, and interfaces",
    "rust":
    "Focus on ownership, borrowing, lifetimes, and Result/Option patterns",
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
    Loads templates from config or uses defaults
    """
    def __init__(
        self,
        settings: PromptSettings | None = None,
        style: str = "technical",
    ) -> None:
        """
        Initialize with optional settings from config
        """
        self.style = style
        self._settings = settings

        if settings and settings.system_prompt:
            self._system_prompt = settings.system_prompt
        else:
            self._system_prompt = DEFAULT_SYSTEM_PROMPT

        if settings and settings.documentation_template:
            self._doc_template = settings.documentation_template
        else:
            self._doc_template = DEFAULT_DOCUMENTATION_TEMPLATE

        if settings and settings.commit_message_template:
            self._commit_template = settings.commit_message_template
        else:
            self._commit_template = DEFAULT_COMMIT_MESSAGE_TEMPLATE

        if settings and settings.language_hints:
            self._language_hints = settings.language_hints
        else:
            self._language_hints = DEFAULT_LANGUAGE_HINTS

    def _get_language_hint(self, language: Language) -> str:
        """
        Get language-specific hint from config or defaults
        """
        return self._language_hints.get(language.value, "")

    def build_documentation_prompt(
        self,
        context: PromptContext,
    ) -> tuple[str,
               str]:
        """
        Build system and user prompts for documentation
        Returns (system_prompt, user_prompt)
        """
        system = self._system_prompt

        lang_hint = self._get_language_hint(context.language)
        if lang_hint:
            system += f"\n\nLanguage-specific guidance: {lang_hint}"

        display_name = context.name
        if context.class_name:
            display_name = f"{context.class_name}.{context.name}"

        user = self._doc_template.format(
            language = context.language.value,
            source = context.source,
            name = display_name,
            file_path = context.file_path,
            repo = context.repo,
            complexity = context.complexity,
            line_count = context.line_count,
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
    ) -> tuple[str,
               str]:
        """
        Build prompt for generating commit message
        """
        system = "You generate natural, human sounding git commit messages. Be concise and specific."

        display_name = context.name
        if context.class_name:
            display_name = f"{context.class_name}.{context.name}"

        user = self._commit_template.format(
            documentation = documentation[: 500],
            name = display_name,
            language = context.language.value,
            repo = context.repo,
        )

        return system, user

    def build_target_prompt(
        self,
        target: DocumentationTarget,
    ) -> tuple[str,
               str]:
        """
        Build prompts for any DocumentationTarget based on its doc_type
        """
        prompts = DOC_TYPE_PROMPTS.get(target.doc_type)
        if not prompts:
            prompts = (DEFAULT_SYSTEM_PROMPT, DEFAULT_DOCUMENTATION_TEMPLATE)

        system_prompt, user_template = prompts

        lang_hint = self._get_language_hint(target.snippet.language)
        if lang_hint:
            system_prompt += f"\n\nLanguage-specific guidance: {lang_hint}"

        user = user_template.format(
            language = target.snippet.language.value,
            source = target.source_context[: 5000],
            name = target.display_name,
            file_path = str(target.snippet.file_path),
            repo = target.snippet.repo,
            complexity = target.snippet.complexity,
            line_count = target.snippet.line_count,
        )

        return system_prompt, user

    @classmethod
    def from_candidate(cls, candidate: AnalysisCandidate) -> PromptContext:
        """
        Create prompt context from analysis candidate
        """
        return PromptContext(
            source = candidate.snippet.source,
            name = candidate.snippet.function_name or candidate.snippet.class_name
            or "unknown",
            language = candidate.snippet.language,
            repo = candidate.snippet.repo,
            file_path = str(candidate.scanned_file.relative_path),
            complexity = candidate.snippet.complexity,
            line_count = candidate.snippet.line_count,
            class_name = candidate.snippet.class_name,
            decorators = candidate.parsed_function.decorators,
            is_async = candidate.parsed_function.is_async,
        )


def get_prompt_builder(settings: PromptSettings | None = None) -> PromptBuilder:
    """
    Get a prompt builder, optionally configured from settings
    """
    return PromptBuilder(settings = settings)


def build_documentation_prompt(
    candidate: AnalysisCandidate,
    settings: PromptSettings | None = None,
) -> tuple[str,
           str]:
    """
    Convenience function to build documentation prompt from candidate
    """
    builder = PromptBuilder(settings = settings)
    context = PromptBuilder.from_candidate(candidate)
    return builder.build_documentation_prompt(context)


def build_commit_prompt(
    documentation: str,
    candidate: AnalysisCandidate,
    settings: PromptSettings | None = None,
) -> tuple[str,
           str]:
    """
    Convenience function to build commit message prompt
    """
    builder = PromptBuilder(settings = settings)
    context = PromptBuilder.from_candidate(candidate)
    return builder.build_commit_message_prompt(documentation, context)
