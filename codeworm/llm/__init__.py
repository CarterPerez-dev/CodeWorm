"""
ⒸAngelaMos | 2026
llm/__init__.py
"""
from codeworm.llm.client import (
    GenerationResult,
    OllamaClient,
    OllamaConnectionError,
    OllamaError,
    OllamaModelError,
    OllamaTimeoutError,
    create_client,
)
from codeworm.llm.generator import DocumentationGenerator, GeneratedDocumentation, generate_documentation
from codeworm.llm.prompts import PromptBuilder, PromptContext, build_commit_prompt, build_documentation_prompt


__all__ = [
    "DocumentationGenerator",
    "GeneratedDocumentation",
    "GenerationResult",
    "OllamaClient",
    "OllamaConnectionError",
    "OllamaError",
    "OllamaModelError",
    "OllamaTimeoutError",
    "PromptBuilder",
    "PromptContext",
    "build_commit_prompt",
    "build_documentation_prompt",
    "create_client",
    "generate_documentation",
]
