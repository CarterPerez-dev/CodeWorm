"""
ⒸAngelaMos | 2026
analysis/complexity.py
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import lizard

from codeworm.models import Language

if TYPE_CHECKING:
    from collections.abc import Iterator


LANGUAGE_MAP: dict[Language, str] = {
    Language.PYTHON: "python",
    Language.TYPESCRIPT: "javascript",
    Language.TSX: "javascript",
    Language.JAVASCRIPT: "javascript",
    Language.GO: "go",
    Language.RUST: "rust",
}


@dataclass
class ComplexityMetrics:
    """
    Complexity metrics for a function or method
    """
    name: str
    cyclomatic_complexity: int
    nloc: int
    token_count: int
    parameter_count: int
    start_line: int
    end_line: int
    max_nesting_depth: int = 0
    fan_in: int = 0
    fan_out: int = 0

    @property
    def line_count(self) -> int:
        """
        Total lines including whitespace and comments
        """
        return self.end_line - self.start_line + 1

    @property
    def is_complex(self) -> bool:
        """
        Check if function exceeds complexity thresholds
        """
        return self.cyclomatic_complexity > 10 or self.nloc > 50

    @property
    def complexity_rating(self) -> str:
        """
        Human readable complexity rating
        """
        cc = self.cyclomatic_complexity
        if cc <= 5:
            return "simple"
        if cc <= 10:
            return "moderate"
        if cc <= 20:
            return "complex"
        return "very_complex"


@dataclass
class FileComplexity:
    """
    Aggregated complexity metrics for a file
    """
    file_path: Path
    functions: list[ComplexityMetrics]
    average_complexity: float
    total_nloc: int
    max_complexity: int
    num_functions: int

    @property
    def has_complex_functions(self) -> bool:
        """
        Check if file contains any complex functions
        """
        return any(f.is_complex for f in self.functions)


class ComplexityAnalyzer:
    """
    Analyzes code complexity using Lizard
    """
    def __init__(self, language: Language | None = None) -> None:
        """
        Initialize analyzer optionally filtered to a language
        """
        self.language = language
        self._extensions = self._get_extensions()

    def _get_extensions(self) -> list[str]:
        """
        Get file extensions for the configured language
        """
        ext_map = {
            Language.PYTHON: [".py"],
            Language.TYPESCRIPT: [".ts"],
            Language.TSX: [".tsx"],
            Language.JAVASCRIPT: [".js", ".jsx"],
            Language.GO: [".go"],
            Language.RUST: [".rs"],
        }
        if self.language:
            return ext_map.get(self.language, [])
        return [ext for exts in ext_map.values() for ext in exts]

    def analyze_source(self, source: str, filename: str = "source.py") -> list[ComplexityMetrics]:
        """
        Analyze complexity of source code string
        """
        analysis = lizard.analyze_file.analyze_source_code(filename, source)
        return self._convert_functions(analysis.function_list)

    def analyze_file(self, file_path: Path) -> FileComplexity:
        """
        Analyze complexity of a single file
        """
        analysis = lizard.analyze_file(str(file_path))
        functions = self._convert_functions(analysis.function_list)

        if not functions:
            return FileComplexity(
                file_path=file_path,
                functions=[],
                average_complexity=0.0,
                total_nloc=analysis.nloc,
                max_complexity=0,
                num_functions=0,
            )

        total_cc = sum(f.cyclomatic_complexity for f in functions)
        max_cc = max(f.cyclomatic_complexity for f in functions)

        return FileComplexity(
            file_path=file_path,
            functions=functions,
            average_complexity=total_cc / len(functions),
            total_nloc=analysis.nloc,
            max_complexity=max_cc,
            num_functions=len(functions),
        )

    def analyze_directory(self, directory: Path, recursive: bool = True) -> Iterator[FileComplexity]:
        """
        Analyze all supported files in a directory
        """
        pattern = "**/*" if recursive else "*"
        for ext in self._extensions:
            for file_path in directory.glob(f"{pattern}{ext}"):
                if file_path.is_file():
                    try:
                        yield self.analyze_file(file_path)
                    except Exception:
                        continue

    def _convert_functions(self, function_list: list) -> list[ComplexityMetrics]:
        """
        Convert lizard function info to our ComplexityMetrics
        """
        results = []
        for func in function_list:
            metrics = ComplexityMetrics(
                name=func.name,
                cyclomatic_complexity=func.cyclomatic_complexity,
                nloc=func.nloc,
                token_count=func.token_count,
                parameter_count=func.parameter_count,
                start_line=func.start_line,
                end_line=func.end_line,
                max_nesting_depth=getattr(func, "max_nesting_depth", 0),
                fan_in=getattr(func, "fan_in", 0),
                fan_out=getattr(func, "fan_out", 0),
            )
            results.append(metrics)
        return results

    def get_hotspots(
        self,
        directory: Path,
        min_complexity: int = 10,
        top_n: int = 20,
    ) -> list[tuple[Path, ComplexityMetrics]]:
        """
        Find the most complex functions in a directory
        """
        hotspots: list[tuple[Path, ComplexityMetrics]] = []

        for file_complexity in self.analyze_directory(directory):
            for func in file_complexity.functions:
                if func.cyclomatic_complexity >= min_complexity:
                    hotspots.append((file_complexity.file_path, func))

        hotspots.sort(key=lambda x: x[1].cyclomatic_complexity, reverse=True)
        return hotspots[:top_n]


def get_function_complexity(source: str, function_name: str, filename: str = "source.py") -> ComplexityMetrics | None:
    """
    Get complexity metrics for a specific function in source code
    """
    analyzer = ComplexityAnalyzer()
    metrics = analyzer.analyze_source(source, filename)

    for m in metrics:
        if m.name == function_name or m.name.endswith(f".{function_name}"):
            return m

    return None
