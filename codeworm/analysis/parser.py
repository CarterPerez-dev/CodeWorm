"""
ⒸAngelaMos | 2026
analysis/parser.py
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

import tree_sitter_go as tsgo
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
import tree_sitter_rust as tsrust
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Node, Parser, Tree

from codeworm.models import Language as CodeLanguage

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass
class ParsedFunction:
    """
    A function or method extracted from parsed source code
    """
    name: str
    start_line: int
    end_line: int
    source: str
    class_name: str | None = None
    decorators: list[str] | None = None
    parameters: list[str] | None = None
    is_async: bool = False
    docstring: str | None = None


@dataclass
class ParsedClass:
    """
    A class extracted from parsed source code
    """
    name: str
    start_line: int
    end_line: int
    source: str
    methods: list[ParsedFunction] | None = None
    decorators: list[str] | None = None
    docstring: str | None = None


class ParserManager:
    """
    Thread-safe tree-sitter parser management
    Parsers are not thread-safe so we use thread-local storage
    """
    _languages: ClassVar[dict[CodeLanguage, Language]] = {}
    _local = threading.local()
    _initialized = False

    @classmethod
    def initialize(cls) -> None:
        """
        Initialize language grammars - call once at startup
        """
        if cls._initialized:
            return

        cls._languages = {
            CodeLanguage.PYTHON: Language(tspython.language()),
            CodeLanguage.TYPESCRIPT: Language(tstypescript.language_typescript()),
            CodeLanguage.TSX: Language(tstypescript.language_tsx()),
            CodeLanguage.JAVASCRIPT: Language(tsjs.language()),
            CodeLanguage.GO: Language(tsgo.language()),
            CodeLanguage.RUST: Language(tsrust.language()),
        }
        cls._initialized = True

    @classmethod
    def get_parser(cls, language: CodeLanguage) -> Parser:
        """
        Get a thread local parser for the specified language
        """
        if not cls._initialized:
            cls.initialize()

        if not hasattr(cls._local, "parsers"):
            cls._local.parsers = {}

        if language not in cls._local.parsers:
            parser = Parser(cls._languages[language])
            cls._local.parsers[language] = parser

        return cls._local.parsers[language]

    @classmethod
    def parse(cls, source: str | bytes, language: CodeLanguage) -> Tree:
        """
        Parse source code and return the syntax tree
        """
        parser = cls.get_parser(language)
        if isinstance(source, str):
            source = source.encode("utf-8")
        return parser.parse(source)


PYTHON_QUERIES = {
    "function":
    """
        (function_definition
            name: (identifier) @name
            parameters: (parameters) @params
            body: (block) @body) @function

        (decorated_definition
            decorator: (decorator) @decorator
            definition: (function_definition
                name: (identifier) @name
                parameters: (parameters) @params)) @decorated_function
    """,
    "class":
    """
        (class_definition
            name: (identifier) @name
            body: (block) @body) @class
    """,
}


class CodeExtractor:
    """
    Extracts functions and classes from parsed syntax trees
    """
    def __init__(self, source: str, language: CodeLanguage) -> None:
        """
        Initialize extractor with source code and language
        """
        self.source = source
        self.source_bytes = source.encode("utf-8")
        self.language = language
        self.tree = ParserManager.parse(source, language)

    def _node_text(self, node: Node) -> str:
        """
        Get the text content of a node
        """
        return self.source_bytes[node.start_byte : node.end_byte].decode("utf-8")

    def _get_docstring(self, node: Node) -> str | None:
        """
        Extract docstring from function or class body
        """
        if self.language != CodeLanguage.PYTHON:
            return None

        body = None
        for child in node.children:
            if child.type == "block":
                body = child
                break

        if not body or not body.children:
            return None

        first_stmt = body.children[0]
        if first_stmt.type == "expression_statement":
            expr = first_stmt.children[0] if first_stmt.children else None
            if expr and expr.type == "string":
                text = self._node_text(expr)
                text = text.strip('"').strip("'")
                return text

        return None

    def extract_functions(self) -> Iterator[ParsedFunction]:
        """
        Extract all functions from the source code
        """
        if self.language == CodeLanguage.PYTHON:
            yield from self._extract_python_functions()
        elif self.language in (CodeLanguage.TYPESCRIPT,
                               CodeLanguage.TSX,
                               CodeLanguage.JAVASCRIPT):
            yield from self._extract_js_functions()
        elif self.language == CodeLanguage.GO:
            yield from self._extract_go_functions()
        elif self.language == CodeLanguage.RUST:
            yield from self._extract_rust_functions()

    def _extract_python_functions(self) -> Iterator[ParsedFunction]:
        """
        Extract functions from Python source
        """
        def visit(node: Node,
                  class_name: str | None = None) -> Iterator[ParsedFunction]:
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    current_class = self._node_text(name_node)
                    for child in node.children:
                        yield from visit(child, current_class)
                return

            if node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                params_node = node.child_by_field_name("parameters")

                if name_node:
                    name = self._node_text(name_node)
                    params = []
                    if params_node:
                        for param in params_node.children:
                            if param.type in ("identifier",
                                              "typed_parameter",
                                              "default_parameter"):
                                params.append(self._node_text(param))

                    yield ParsedFunction(
                        name = name,
                        start_line = node.start_point[0] + 1,
                        end_line = node.end_point[0] + 1,
                        source = self._node_text(node),
                        class_name = class_name,
                        parameters = params,
                        docstring = self._get_docstring(node),
                    )
                return

            if node.type == "decorated_definition":
                decorators = []
                func_node = None
                for child in node.children:
                    if child.type == "decorator":
                        decorators.append(self._node_text(child))
                    elif child.type == "function_definition":
                        func_node = child

                if func_node:
                    for func in visit(func_node, class_name):
                        func.decorators = decorators
                        yield func
                return

            for child in node.children:
                yield from visit(child, class_name)

        yield from visit(self.tree.root_node)

    def _extract_js_functions(self) -> Iterator[ParsedFunction]:
        """
        Extract functions from JavaScript/TypeScript source
        """
        def visit(node: Node,
                  class_name: str | None = None) -> Iterator[ParsedFunction]:
            if node.type in ("class_declaration", "class"):
                name_node = node.child_by_field_name("name")
                current_class = self._node_text(name_node) if name_node else None
                for child in node.children:
                    yield from visit(child, current_class)
                return

            if node.type in ("function_declaration",
                             "method_definition",
                             "arrow_function"):
                name_node = node.child_by_field_name("name")
                name = self._node_text(name_node) if name_node else "<anonymous>"

                is_async = any(c.type == "async" for c in node.children)

                yield ParsedFunction(
                    name = name,
                    start_line = node.start_point[0] + 1,
                    end_line = node.end_point[0] + 1,
                    source = self._node_text(node),
                    class_name = class_name,
                    is_async = is_async,
                )
                return

            for child in node.children:
                yield from visit(child, class_name)

        yield from visit(self.tree.root_node)

    def _extract_go_functions(self) -> Iterator[ParsedFunction]:
        """
        Extract functions from Go source
        """
        def visit(node: Node) -> Iterator[ParsedFunction]:
            if node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    yield ParsedFunction(
                        name = self._node_text(name_node),
                        start_line = node.start_point[0] + 1,
                        end_line = node.end_point[0] + 1,
                        source = self._node_text(node),
                    )
                return

            if node.type == "method_declaration":
                name_node = node.child_by_field_name("name")
                receiver = node.child_by_field_name("receiver")
                class_name = None
                if receiver:
                    for child in receiver.children:
                        if child.type == "type_identifier":
                            class_name = self._node_text(child)
                            break

                if name_node:
                    yield ParsedFunction(
                        name = self._node_text(name_node),
                        start_line = node.start_point[0] + 1,
                        end_line = node.end_point[0] + 1,
                        source = self._node_text(node),
                        class_name = class_name,
                    )
                return

            for child in node.children:
                yield from visit(child)

        yield from visit(self.tree.root_node)

    def _extract_rust_functions(self) -> Iterator[ParsedFunction]:
        """
        Extract functions from Rust source
        """
        def visit(node: Node,
                  impl_name: str | None = None) -> Iterator[ParsedFunction]:
            if node.type == "impl_item":
                type_node = node.child_by_field_name("type")
                current_impl = self._node_text(type_node) if type_node else None
                for child in node.children:
                    yield from visit(child, current_impl)
                return

            if node.type == "function_item":
                name_node = node.child_by_field_name("name")
                if name_node:
                    is_async = any(c.type == "async" for c in node.children)
                    yield ParsedFunction(
                        name = self._node_text(name_node),
                        start_line = node.start_point[0] + 1,
                        end_line = node.end_point[0] + 1,
                        source = self._node_text(node),
                        class_name = impl_name,
                        is_async = is_async,
                    )
                return

            for child in node.children:
                yield from visit(child, impl_name)

        yield from visit(self.tree.root_node)

    def extract_classes(self) -> Iterator[ParsedClass]:
        """
        Extract all classes from the source code
        """
        if self.language == CodeLanguage.PYTHON:
            yield from self._extract_python_classes()

    def _extract_python_classes(self) -> Iterator[ParsedClass]:
        """
        Extract classes from Python source
        """
        def visit(node: Node) -> Iterator[ParsedClass]:
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = self._node_text(name_node)
                    methods = list(self._extract_python_functions())
                    class_methods = [m for m in methods if m.class_name == name]

                    yield ParsedClass(
                        name = name,
                        start_line = node.start_point[0] + 1,
                        end_line = node.end_point[0] + 1,
                        source = self._node_text(node),
                        methods = class_methods,
                        docstring = self._get_docstring(node),
                    )
                return

            for child in node.children:
                yield from visit(child)

        yield from visit(self.tree.root_node)


def parse_file(file_path: Path, language: CodeLanguage) -> CodeExtractor:
    """
    Parse a file and return an extractor for it
    """
    source = file_path.read_text(encoding = "utf-8")
    return CodeExtractor(source, language)
