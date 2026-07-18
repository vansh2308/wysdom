import re
import subprocess
import tempfile
from pathlib import Path

from tree_sitter import Node
from tree_sitter_language_pack import get_language, get_parser

from app.repositories.models import CodeChunk

ChunkContext = tuple[str, str, int, int, str | None, str | None]


class RepositoryChunkService:
    def __init__(self) -> None:
        self._ignored_dirs = {
            ".git",
            ".venv",
            "node_modules",
            "dist",
            "build",
            "__pycache__",
            ".pytest_cache",
            "vendor",
            "target",
            "thirdparty"
        }
        self._supported_extensions = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rb": "ruby",
            ".cs": "csharp",
        }

    def chunk_repository(self, repo_input: str, include_tests: bool = True) -> list[CodeChunk]:
        repo_path = self._resolve_repository_path(repo_input)
        source_files = self._collect_source_files(repo_path, include_tests=include_tests)

        chunk_index: dict[Path, list[ChunkContext]] = {
            file_path: self._collect_chunk_contexts(file_path, repo_path)
            for file_path in source_files
        }

        chunks: list[CodeChunk] = []
        for file_path in source_files:
            parsed_chunks = self._parse_file(file_path, repo_path, chunk_index=chunk_index)
            chunks.extend(parsed_chunks)

        return chunks

    def _resolve_repository_path(self, repo_input: str) -> Path:
        candidate = Path(repo_input).expanduser()
        if candidate.exists():
            return candidate.resolve()

        if re.match(r"^https?://", repo_input):
            temp_dir = Path(tempfile.mkdtemp(prefix="repo-ingest-"))
            clone_result = subprocess.run(
                ["git", "clone", "--depth", "1", repo_input, str(temp_dir / "repo")],
                capture_output=True,
                text=True,
                check=False,
            )
            if clone_result.returncode != 0:
                raise RuntimeError(f"Unable to clone repository: {clone_result.stderr or clone_result.stdout}")
            return (temp_dir / "repo").resolve()

        raise FileNotFoundError(f"Repository path does not exist: {repo_input}")

    def _collect_source_files(self, repo_path: Path, include_tests: bool = True) -> list[Path]:
        source_files: list[Path] = []
        for file_path in repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in self._ignored_dirs for part in file_path.parts):
                continue
            if not include_tests and "test" in file_path.parts:
                continue
            if file_path.suffix.lower() in self._supported_extensions:
                source_files.append(file_path)
        return sorted(source_files)

    def _parse_file(
        self,
        file_path: Path,
        repo_root: Path,
        chunk_index: dict[Path, list[ChunkContext]] | None = None,
    ) -> list[CodeChunk]:
        language_name = self._supported_extensions.get(file_path.suffix.lower())
        if not language_name:
            return []

        try:
            parser = get_parser(language_name)
            language = get_language(language_name)
        except Exception:
            return []

        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = parser.parse(source.encode("utf-8"))
        root = tree.root_node

        chunks: list[CodeChunk] = []
        self._collect_chunks_from_node(
            node=root,
            file_path=file_path,
            repo_root=repo_root,
            source=source,
            language=language_name,
            chunks=chunks,
            parent_scope=None,
            chunk_index=chunk_index,
        )

        return chunks

    def _collect_chunks_from_node(
        self,
        *,
        node: Node,
        file_path: Path,
        repo_root: Path,
        source: str,
        language: str,
        chunks: list[CodeChunk],
        parent_scope: tuple[str, str] | None,
        chunk_index: dict[Path, list[ChunkContext]] | None = None,
    ) -> None:
        if not node.is_named:
            for child in node.children:
                self._collect_chunks_from_node(
                    node=child,
                    file_path=file_path,
                    repo_root=repo_root,
                    source=source,
                    language=language,
                    chunks=chunks,
                    parent_scope=parent_scope,
                    chunk_index=chunk_index,
                )
            return

        if self._should_capture(node, language):
            scope = self._scope_for_node(node, language)
            parent_name = parent_scope[1] if parent_scope else None
            parent_type = parent_scope[0] if parent_scope else None
            chunk = self._build_chunk_from_node(
                node=node,
                file_path=file_path,
                repo_root=repo_root,
                source=source,
                language=language,
                parent_name=parent_name,
                parent_type=parent_type,
                chunk_index=chunk_index,
            )
            if chunk is not None:
                chunks.append(chunk)
            child_parent_scope = scope if scope else parent_scope
        else:
            child_parent_scope = parent_scope

        for child in node.children:
            self._collect_chunks_from_node(
                node=child,
                file_path=file_path,
                repo_root=repo_root,
                source=source,
                language=language,
                chunks=chunks,
                parent_scope=child_parent_scope,
                chunk_index=chunk_index,
            )

    def _scope_for_node(self, node: Node, language: str) -> tuple[str, str] | None:
        chunk_type = self._infer_chunk_type(node, language)
        if chunk_type is None:
            return None
        name = self._extract_name(node, language)
        if not name:
            return None
        return chunk_type, name

    def _collect_chunk_contexts(self, file_path: Path, repo_root: Path) -> list[ChunkContext]:
        language_name = self._supported_extensions.get(file_path.suffix.lower())
        if not language_name:
            return []

        try:
            parser = get_parser(language_name)
            language = get_language(language_name)
        except Exception:
            return []

        source = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = parser.parse(source.encode("utf-8"))
        contexts: list[ChunkContext] = []
        self._collect_chunk_contexts_from_node(
            node=tree.root_node,
            language=language_name,
            contexts=contexts,
            parent_scope=None,
        )
        return contexts

    def _collect_chunk_contexts_from_node(
        self,
        *,
        node: Node,
        language: str,
        contexts: list[ChunkContext],
        parent_scope: tuple[str, str] | None,
    ) -> None:
        if not node.is_named:
            for child in node.children:
                self._collect_chunk_contexts_from_node(
                    node=child,
                    language=language,
                    contexts=contexts,
                    parent_scope=parent_scope,
                )
            return

        if self._should_capture(node, language):
            scope = self._scope_for_node(node, language)
            if scope is None:
                child_parent_scope = parent_scope
            else:
                chunk_type, chunk_name = scope
                start_line = node.start_point[0] + 1
                end_line = node.end_point[0] + 1
                parent_name = parent_scope[1] if parent_scope else None
                parent_type = parent_scope[0] if parent_scope else None
                contexts.append((chunk_type, chunk_name, start_line, end_line, parent_name, parent_type))
                child_parent_scope = scope
            for child in node.children:
                self._collect_chunk_contexts_from_node(
                    node=child,
                    language=language,
                    contexts=contexts,
                    parent_scope=child_parent_scope,
                )
            return

        for child in node.children:
            self._collect_chunk_contexts_from_node(
                node=child,
                language=language,
                contexts=contexts,
                parent_scope=parent_scope,
            )

    def _should_capture(self, node: Node, language_name: str) -> bool:
        if language_name == "python":
            return node.type in {"function_definition", "async_function_definition", "class_definition"}
        if language_name in {"javascript", "typescript"}:
            return node.type in {"function_declaration", "method_definition", "class_declaration", "arrow_function"}
        if language_name == "java":
            return node.type in {"class_declaration", "method_declaration"}
        if language_name == "go":
            return node.type in {"function_declaration", "method_declaration", "type_declaration"}
        if language_name == "ruby":
            return node.type in {"class", "method", "singleton_method"}
        return False

    def _build_chunk_from_node(
        self,
        *,
        node: Node,
        file_path: Path,
        repo_root: Path,
        source: str,
        language: str,
        parent_name: str | None,
        parent_type: str | None,
        chunk_index: dict[Path, list[ChunkContext]] | None = None,
    ) -> CodeChunk | None:
        chunk_type = self._infer_chunk_type(node, language)
        if chunk_type is None:
            return None

        name = self._extract_name(node, language)
        if not name:
            return None

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        content = self._extract_source_segment(source, node)
        related_comments = self._extract_related_comments(source, start_line)
        superclasses = self._extract_superclasses(node, language)
        where_used = self._collect_where_used(
            name,
            repo_root,
            current_file=file_path,
            chunk_index=chunk_index,
            current_chunk_start_line=start_line,
            current_chunk_end_line=end_line,
        )

        return self._build_chunk(
            chunk_type=chunk_type,
            name=name,
            path=file_path.relative_to(repo_root).as_posix(),
            language=language,
            start_line=start_line,
            end_line=end_line,
            content=content,
            repo_root=repo_root,
            file_path=file_path,
            source=source,
            file_paths=[file_path],
            parent_name=parent_name,
            parent_type=parent_type,
            superclasses=superclasses,
            related_comments=related_comments,
            where_used=where_used,
        )

    def _build_chunk(
        self,
        *,
        chunk_type: str,
        name: str,
        path: str,
        language: str,
        start_line: int,
        end_line: int,
        content: str,
        repo_root: Path,
        file_path: Path,
        source: str,
        file_paths: list[Path],
        parent_name: str | None,
        parent_type: str | None,
        superclasses: list[str] | None = None,
        related_comments: list[str] | None = None,
        where_used: list[str] | None = None,
    ) -> CodeChunk:
        return CodeChunk(
            id=self._make_chunk_id(path, name, start_line),
            type=chunk_type,
            name=name,
            language=language,
            path=path,
            start_line=start_line,
            end_line=end_line,
            content=content,
            parent_name=parent_name,
            parent_type=parent_type,
            superclasses=superclasses or [],
            related_comments=related_comments or [],
            where_used=where_used or [],
        )

    def _infer_chunk_type(self, node: Node, language: str) -> str | None:
        if language == "python":
            if node.type == "class_definition":
                return "class"
            if node.type in {"function_definition", "async_function_definition"}:
                return "function"
        elif language in {"javascript", "typescript"}:
            if node.type == "class_declaration":
                return "class"
            if node.type in {"function_declaration", "method_definition", "arrow_function"}:
                return "function"
        elif language == "java":
            if node.type == "class_declaration":
                return "class"
            if node.type == "method_declaration":
                return "function"
        elif language == "go":
            if node.type in {"type_declaration", "function_declaration", "method_declaration"}:
                return "function"
        elif language == "ruby":
            if node.type == "class":
                return "class"
            if node.type in {"method", "singleton_method"}:
                return "function"
        return None

    def _extract_name(self, node: Node, language: str) -> str | None:
        if language == "python":
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8")
        if language in {"javascript", "typescript"}:
            for child in node.children:
                if child.type in {"identifier", "property_identifier"}:
                    return child.text.decode("utf-8")
            if node.type == "method_definition":
                return node.child_by_field_name("name").text.decode("utf-8") if node.child_by_field_name("name") else None
        if language == "java":
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8")
        if language == "go":
            for child in node.children:
                if child.type == "identifier":
                    return child.text.decode("utf-8")
        if language == "ruby":
            for child in node.children:
                if child.type in {"identifier", "constant"}:
                    return child.text.decode("utf-8")
        return None

    def _extract_superclasses(self, node: Node, language: str) -> list[str]:
        if language != "python" or node.type != "class_definition":
            return []

        for child in node.children:
            if child.type != "argument_list":
                continue
            names: list[str] = []
            for grandchild in child.children:
                if grandchild.type in {"identifier", "attribute"}:
                    names.append(grandchild.text.decode("utf-8"))
            if names:
                return names

        return []

    def _extract_source_segment(self, source: str, node: Node) -> str:
        lines = source.splitlines()
        start_line = node.start_point[0]
        end_line = node.end_point[0]
        return "\n".join(lines[start_line:end_line + 1])

    def _extract_related_comments(self, source: str, start_line: int) -> list[str]:
        lines = source.splitlines()
        comments: list[str] = []
        for index in range(max(0, start_line - 2), -1, -1):
            stripped = lines[index].strip()
            if not stripped:
                continue
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*"):
                comments.append(stripped)
                continue
            break
        return list(reversed(comments))

    def _collect_where_used(
        self,
        name: str,
        repo_root: Path,
        current_file: Path,
        chunk_index: dict[Path, list[ChunkContext]] | None = None,
        current_chunk_start_line: int | None = None,
        current_chunk_end_line: int | None = None,
    ) -> list[str]:
        if chunk_index is None:
            chunk_index = {}

        matches: list[str] = []
        seen: set[str] = set()
        for file_path, contexts in chunk_index.items():
            if not file_path.is_file():
                continue
            if any(part in self._ignored_dirs for part in file_path.parts):
                continue
            if file_path.suffix.lower() not in self._supported_extensions:
                continue

            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for match in re.finditer(rf"\b{re.escape(name)}\b", content):
                line_number = content.count("\n", 0, match.start()) + 1
                if (
                    file_path == current_file
                    and current_chunk_start_line is not None
                    and current_chunk_end_line is not None
                    and current_chunk_start_line <= line_number <= current_chunk_end_line
                ):
                    continue

                relative_path = file_path.relative_to(repo_root).as_posix()
                scope_name = self._find_enclosing_scope_name(contexts, line_number)
                entry = f"{relative_path}::{scope_name}" if scope_name else relative_path
                if entry not in seen:
                    seen.add(entry)
                    matches.append(entry)

        return matches

    def _find_enclosing_scope_name(self, contexts: list[ChunkContext], line_number: int) -> str | None:
        for context in reversed(contexts):
            chunk_type, chunk_name, start_line, end_line, parent_name, parent_type = context
            if start_line <= line_number <= end_line:
                if parent_name and parent_type:
                    return f"{parent_name}.{chunk_name}"
                return chunk_name
        return None

    def _make_chunk_id(self, path: str, name: str, start_line: int) -> str:
        return f"{path}:{name}:{start_line}"
