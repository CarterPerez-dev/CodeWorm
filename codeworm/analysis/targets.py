"""
ⒸAngelaMos | 2026
analysis/targets.py
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from git import InvalidGitRepositoryError, Repo

from codeworm.analysis.parser import CodeExtractor
from codeworm.analysis.scanner import RepoScanner
from codeworm.models import LANGUAGE_EXTENSIONS, CodeSnippet, DocType, Language

if TYPE_CHECKING:
    from codeworm.core.config import RepoEntry


@dataclass
class DocumentationTarget:
    """
    A generalized documentation target that supports any doc type
    """
    doc_type: DocType
    snippet: CodeSnippet
    source_context: str
    metadata: dict = field(default_factory = dict)

    @property
    def score(self) -> float:
        return self.snippet.interest_score

    @property
    def display_name(self) -> str:
        return self.snippet.display_name


class FileTargetFinder:
    """
    Finds files worth documenting at the file level
    """
    def __init__(self, scanner: RepoScanner) -> None:
        self.scanner = scanner

    def find(
        self,
        repo: RepoEntry,
        limit: int = 20,
    ) -> list[DocumentationTarget]:
        targets: list[DocumentationTarget] = []

        for scanned_file in self.scanner.scan_repo(repo.path, repo.name):
            try:
                source = scanned_file.path.read_text(encoding = "utf-8")
            except Exception:  # noqa: S112
                continue

            line_count = source.count("\n") + 1
            if line_count < 20:
                continue

            extractor = CodeExtractor(source, scanned_file.language)
            func_count = sum(1 for _ in extractor.extract_functions())

            score = min(
                100.0,
                (
                    min(line_count / 200,
                        1.0) * 30 + min(func_count / 8,
                                        1.0) * 30 +
                    min(scanned_file.size_bytes / 5000,
                        1.0) * 20 + min(source.count("import ") / 10,
                                        1.0) * 20
                )
            )

            if score < 20:
                continue

            snippet = CodeSnippet(
                repo = repo.name,
                file_path = scanned_file.path,
                function_name = None,
                class_name = None,
                language = scanned_file.language,
                source = source[: 4000],
                start_line = 1,
                end_line = line_count,
                interest_score = score,
                doc_type = DocType.FILE_DOC,
            )

            targets.append(
                DocumentationTarget(
                    doc_type = DocType.FILE_DOC,
                    snippet = snippet,
                    source_context = source[: 6000],
                    metadata = {
                        "line_count": line_count,
                        "function_count": func_count,
                        "relative_path": str(scanned_file.relative_path),
                    },
                )
            )

            if len(targets) >= limit * 2:
                break

        targets.sort(key = lambda t: t.score, reverse = True)
        return targets[: limit]


class ClassTargetFinder:
    """
    Finds classes worth documenting
    """
    def __init__(self, scanner: RepoScanner) -> None:
        self.scanner = scanner

    def find(
        self,
        repo: RepoEntry,
        limit: int = 20,
    ) -> list[DocumentationTarget]:
        targets: list[DocumentationTarget] = []

        for scanned_file in self.scanner.scan_repo(repo.path, repo.name):
            try:
                source = scanned_file.path.read_text(encoding = "utf-8")
            except Exception:  # noqa: S112
                continue

            extractor = CodeExtractor(source, scanned_file.language)

            for parsed_class in extractor.extract_classes():
                method_count = len(parsed_class.methods or [])
                line_count = parsed_class.end_line - parsed_class.start_line + 1

                if line_count < 15:
                    continue

                score = min(
                    100.0,
                    (
                        min(method_count / 6,
                            1.0) * 35 + min(line_count / 100,
                                            1.0) * 25 +
                        (10 if parsed_class.docstring else 0) +
                        min(len(parsed_class.decorators or []) * 5,
                            15) + 15
                    )
                )

                snippet = CodeSnippet(
                    repo = repo.name,
                    file_path = scanned_file.path,
                    function_name = None,
                    class_name = parsed_class.name,
                    language = scanned_file.language,
                    source = parsed_class.source[: 4000],
                    start_line = parsed_class.start_line,
                    end_line = parsed_class.end_line,
                    interest_score = score,
                    doc_type = DocType.CLASS_DOC,
                )

                targets.append(
                    DocumentationTarget(
                        doc_type = DocType.CLASS_DOC,
                        snippet = snippet,
                        source_context = parsed_class.source[: 6000],
                        metadata = {
                            "method_count":
                            method_count,
                            "method_names":
                            [m.name for m in (parsed_class.methods or [])],
                            "has_docstring":
                            bool(parsed_class.docstring),
                            "relative_path":
                            str(scanned_file.relative_path),
                        },
                    )
                )

                if len(targets) >= limit * 2:
                    break

            if len(targets) >= limit * 2:
                break

        targets.sort(key = lambda t: t.score, reverse = True)
        return targets[: limit]


class ModuleTargetFinder:
    """
    Finds Python packages or directory-level modules to document
    """
    def find(
        self,
        repo: RepoEntry,
        limit: int = 10,
    ) -> list[DocumentationTarget]:
        targets: list[DocumentationTarget] = []

        if not repo.path.exists():
            return targets

        for dirpath in repo.path.rglob("__init__.py"):
            pkg_dir = dirpath.parent
            rel_dir = pkg_dir.relative_to(repo.path)

            skip_dirs = {
                "node_modules",
                ".git",
                "venv",
                ".venv",
                "__pycache__",
                "dist",
                "build",
                "vendor",
                "target",
                ".tox",
                ".mypy_cache"
            }
            if any(part in skip_dirs for part in rel_dir.parts):
                continue

            py_files = list(pkg_dir.glob("*.py"))
            file_count = len(py_files)

            if file_count < 2:
                continue

            init_content = ""
            try:  # noqa: SIM105
                init_content = dirpath.read_text(encoding = "utf-8")
            except Exception:  # noqa: S110
                pass

            file_listing = "\n".join(f"  - {f.name}" for f in sorted(py_files))
            context = f"Package: {rel_dir}\nFiles ({file_count}):\n{file_listing}"

            if init_content.strip():
                context += f"\n\n__init__.py:\n{init_content[:2000]}"

            score = min(
                100.0,
                (
                    min(file_count / 8,
                        1.0) * 40 + min(len(init_content) / 500,
                                        1.0) * 30 + 30
                )
            )

            snippet = CodeSnippet(
                repo = repo.name,
                file_path = pkg_dir,
                function_name = None,
                class_name = None,
                language = Language.PYTHON,
                source = context[: 4000],
                start_line = 1,
                end_line = 1,
                interest_score = score,
                doc_type = DocType.MODULE_DOC,
            )

            targets.append(
                DocumentationTarget(
                    doc_type = DocType.MODULE_DOC,
                    snippet = snippet,
                    source_context = context[: 6000],
                    metadata = {
                        "package_path": str(rel_dir),
                        "file_count": file_count,
                        "file_names": [f.name for f in py_files],
                        "has_init_content": bool(init_content.strip()),
                    },
                )
            )

            if len(targets) >= limit:
                break

        for dirpath in repo.path.rglob("index.ts"):
            pkg_dir = dirpath.parent
            rel_dir = pkg_dir.relative_to(repo.path)

            skip_dirs = {"node_modules", ".git", "dist", "build"}
            if any(part in skip_dirs for part in rel_dir.parts):
                continue

            ts_files = list(pkg_dir.glob("*.ts")) + list(pkg_dir.glob("*.tsx"))
            file_count = len(ts_files)

            if file_count < 2:
                continue

            index_content = ""
            try:  # noqa: SIM105
                index_content = dirpath.read_text(encoding = "utf-8")
            except Exception:  # noqa: S110
                pass

            file_listing = "\n".join(f"  - {f.name}" for f in sorted(ts_files))
            context = f"Module: {rel_dir}\nFiles ({file_count}):\n{file_listing}"
            if index_content.strip():
                context += f"\n\nindex.ts:\n{index_content[:2000]}"

            score = min(
                100.0,
                (
                    min(file_count / 8,
                        1.0) * 40 + min(len(index_content) / 500,
                                        1.0) * 30 + 30
                )
            )

            snippet = CodeSnippet(
                repo = repo.name,
                file_path = pkg_dir,
                function_name = None,
                class_name = None,
                language = Language.TYPESCRIPT,
                source = context[: 4000],
                start_line = 1,
                end_line = 1,
                interest_score = score,
                doc_type = DocType.MODULE_DOC,
            )

            targets.append(
                DocumentationTarget(
                    doc_type = DocType.MODULE_DOC,
                    snippet = snippet,
                    source_context = context[: 6000],
                    metadata = {
                        "package_path": str(rel_dir),
                        "file_count": file_count,
                        "file_names": [f.name for f in ts_files],
                    },
                )
            )

            if len(targets) >= limit:
                break

        targets.sort(key = lambda t: t.score, reverse = True)
        return targets[: limit]


class EvolutionTargetFinder:
    """
    Finds recently changed files and generates git diff context
    """
    def find(
        self,
        repo: RepoEntry,
        limit: int = 10,
    ) -> list[DocumentationTarget]:
        targets: list[DocumentationTarget] = []

        try:
            git_repo = Repo(repo.path)
        except InvalidGitRepositoryError:
            return targets

        try:
            commits = list(git_repo.iter_commits(max_count = 20))
        except Exception:
            return targets

        seen_files: set[str] = set()

        for i, commit in enumerate(commits[:-1]):
            parent = commits[i + 1]
            try:
                diffs = parent.diff(commit, create_patch = True)
            except Exception:  # noqa: S112
                continue

            for diff in diffs:
                file_path = diff.b_path or diff.a_path
                if not file_path or file_path in seen_files:
                    continue

                ext = Path(file_path).suffix.lower()
                language = LANGUAGE_EXTENSIONS.get(ext)
                if not language:
                    continue

                seen_files.add(file_path)

                try:
                    diff_text = diff.diff.decode("utf-8", errors = "replace")
                except Exception:  # noqa: S112
                    continue

                if len(diff_text) < 20:
                    continue

                full_path = repo.path / file_path
                score = min(
                    100.0,
                    (
                        min(len(diff_text) / 1000,
                            1.0) * 40 + 30 + (10 if diff.new_file else 0) +
                        min(diff_text.count("\n+") / 20,
                            1.0) * 20
                    )
                )

                snippet = CodeSnippet(
                    repo = repo.name,
                    file_path = full_path,
                    function_name = None,
                    class_name = None,
                    language = language,
                    source = diff_text[: 4000],
                    start_line = 1,
                    end_line = 1,
                    interest_score = score,
                    doc_type = DocType.CODE_EVOLUTION,
                )

                context = (
                    f"Commit: {commit.hexsha[:8]}\n"
                    f"Message: {commit.message.strip()}\n"
                    f"Author: {commit.author}\n"
                    f"File: {file_path}\n"
                    f"Change type: {'new file' if diff.new_file else 'modified'}\n\n"
                    f"Diff:\n{diff_text[:5000]}"
                )

                targets.append(
                    DocumentationTarget(
                        doc_type = DocType.CODE_EVOLUTION,
                        snippet = snippet,
                        source_context = context[: 6000],
                        metadata = {
                            "commit_hash": commit.hexsha[: 8],
                            "commit_message": commit.message.strip()[: 100],
                            "is_new_file": diff.new_file,
                            "relative_path": file_path,
                        },
                    )
                )

                if len(targets) >= limit:
                    break

            if len(targets) >= limit:
                break

        targets.sort(key = lambda t: t.score, reverse = True)
        return targets[: limit]


class PatternTargetFinder:
    """
    Finds design patterns across a repository
    """
    PATTERN_SIGNATURES: ClassVar[dict] = {
        "singleton": {
            "indicators": ["_instance",
                           "__new__",
                           "getInstance"],
            "description": "Singleton pattern",
        },
        "factory": {
            "indicators": ["create_",
                           "make_",
                           "build_",
                           "factory"],
            "description": "Factory pattern",
        },
        "observer": {
            "indicators": [
                "subscribe",
                "notify",
                "on_event",
                "emit",
                "listener",
                "addEventListener"
            ],
            "description":
            "Observer/Event pattern",
        },
        "decorator_pattern": {
            "indicators": ["wrapper",
                           "wraps",
                           "functools.wraps",
                           "@wraps"],
            "description": "Decorator pattern",
        },
        "strategy": {
            "indicators": ["Strategy",
                           "execute",
                           "set_strategy",
                           "algorithm"],
            "description": "Strategy pattern",
        },
        "middleware": {
            "indicators": ["middleware",
                           "next()",
                           "dispatch",
                           "use("],
            "description": "Middleware/Pipeline pattern",
        },
        "repository_pattern": {
            "indicators":
            ["Repository",
             "get_by_id",
             "find_all",
             "save(",
             "delete("],
            "description": "Repository pattern",
        },
    }

    def __init__(self, scanner: RepoScanner) -> None:
        self.scanner = scanner

    def find(
        self,
        repo: RepoEntry,
        limit: int = 10,
    ) -> list[DocumentationTarget]:
        targets: list[DocumentationTarget] = []

        for scanned_file in self.scanner.scan_repo(repo.path, repo.name):
            try:
                source = scanned_file.path.read_text(encoding = "utf-8")
            except Exception:  # noqa: S112
                continue

            for pattern_name, pattern_info in self.PATTERN_SIGNATURES.items():
                matches = sum(
                    1 for indicator in pattern_info["indicators"]
                    if indicator in source
                )
                if matches < 2:
                    continue

                score = min(100.0, matches * 15 + 30)

                snippet = CodeSnippet(
                    repo = repo.name,
                    file_path = scanned_file.path,
                    function_name = pattern_name,
                    class_name = None,
                    language = scanned_file.language,
                    source = source[: 4000],
                    start_line = 1,
                    end_line = source.count("\n") + 1,
                    interest_score = score,
                    doc_type = DocType.PATTERN_ANALYSIS,
                )

                targets.append(
                    DocumentationTarget(
                        doc_type = DocType.PATTERN_ANALYSIS,
                        snippet = snippet,
                        source_context = source[: 6000],
                        metadata = {
                            "pattern": pattern_name,
                            "pattern_description": pattern_info["description"],
                            "indicator_matches": matches,
                            "relative_path": str(scanned_file.relative_path),
                        },
                    )
                )

            if len(targets) >= limit * 2:
                break

        targets.sort(key = lambda t: t.score, reverse = True)
        return targets[: limit]


class FunctionPerspectiveFinder:
    """
    Reuses existing function candidates but assigns a different doc_type
    for alternative perspectives (security review, performance, TIL)
    """
    def __init__(self, analyzer: object) -> None:
        self.analyzer = analyzer

    def find(
        self,
        repo: RepoEntry,
        doc_type: DocType,
        limit: int = 20,
    ) -> list[DocumentationTarget]:
        candidates = self.analyzer.find_candidates(repo = repo, limit = limit)
        targets = []

        for candidate in candidates:
            snippet = candidate.snippet.model_copy()
            snippet.doc_type = doc_type

            targets.append(
                DocumentationTarget(
                    doc_type = doc_type,
                    snippet = snippet,
                    source_context = candidate.snippet.source,
                    metadata = {
                        "complexity": candidate.snippet.complexity,
                        "nesting_depth": candidate.snippet.nesting_depth,
                        "parameter_count": candidate.snippet.parameter_count,
                        "relative_path":
                        str(candidate.scanned_file.relative_path),
                    },
                )
            )

        return targets


class TargetRouter:
    """
    Routes doc_type requests to the appropriate target finder
    """
    def __init__(
        self,
        analyzer: object,
        scanner: RepoScanner,
    ) -> None:
        self.file_finder = FileTargetFinder(scanner)
        self.class_finder = ClassTargetFinder(scanner)
        self.module_finder = ModuleTargetFinder()
        self.evolution_finder = EvolutionTargetFinder()
        self.pattern_finder = PatternTargetFinder(scanner)
        self.perspective_finder = FunctionPerspectiveFinder(analyzer)

    def find_targets(
        self,
        doc_type: DocType,
        repo: RepoEntry,
        limit: int = 20,
    ) -> list[DocumentationTarget]:
        if doc_type == DocType.FUNCTION_DOC:
            candidates = self.perspective_finder.analyzer.find_candidates(
                repo = repo,
                limit = limit,
            )
            return [
                DocumentationTarget(
                    doc_type = DocType.FUNCTION_DOC,
                    snippet = c.snippet,
                    source_context = c.snippet.source,
                    metadata = {
                        "relative_path": str(c.scanned_file.relative_path)
                    },
                ) for c in candidates
            ]

        if doc_type == DocType.FILE_DOC:
            return self.file_finder.find(repo, limit)

        if doc_type == DocType.CLASS_DOC:
            return self.class_finder.find(repo, limit)

        if doc_type == DocType.MODULE_DOC:
            return self.module_finder.find(repo, limit)

        if doc_type == DocType.CODE_EVOLUTION:
            return self.evolution_finder.find(repo, limit)

        if doc_type == DocType.PATTERN_ANALYSIS:
            return self.pattern_finder.find(repo, limit)

        if doc_type in (
                DocType.SECURITY_REVIEW,
                DocType.PERFORMANCE_ANALYSIS,
                DocType.TIL,
        ):
            return self.perspective_finder.find(repo, doc_type, limit)

        return []


def select_doc_type(weights: dict[str, int]) -> DocType:
    """
    Weighted random selection of a documentation type
    """
    types = []
    type_weights = []

    for type_str, weight in weights.items():
        try:
            types.append(DocType(type_str))
            type_weights.append(weight)
        except ValueError:
            continue

    if not types:
        return DocType.FUNCTION_DOC

    return random.choices(types, weights = type_weights, k = 1)[0]
