from pathlib import Path

from app.repositories.service import RepositoryChunkService


def test_chunking_service_extracts_logical_chunks(tmp_path: Path) -> None:
    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app").mkdir()
    (repo_dir / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo_dir / "app" / "service.py").write_text(
        """
import os


class Greeter:
    def greet(self, name):
        return f\"Hello {name}\"


def helper(value):
    return value + 1
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = RepositoryChunkService()
    chunks = service.chunk_repository(str(repo_dir))

    assert any(chunk.type == "class" and chunk.name == "Greeter" for chunk in chunks)
    assert any(chunk.type == "function" and chunk.name == "helper" for chunk in chunks)
    assert any(chunk.type == "function" and chunk.name == "greet" for chunk in chunks)
    assert all(chunk.language for chunk in chunks)
    assert all(chunk.path for chunk in chunks)
    assert not any(chunk.type == "module" for chunk in chunks)


def test_chunking_service_tracks_superclasses_and_same_file_where_used(tmp_path: Path) -> None:
    repo_dir = tmp_path / "demo-repo"
    repo_dir.mkdir()
    (repo_dir / "app").mkdir()
    (repo_dir / "app" / "service.py").write_text(
        """
class Base:
    pass


class Child(Base):
    def use_base(self):
        return Base()
""".strip()
        + "\n",
        encoding="utf-8",
    )

    service = RepositoryChunkService()
    chunks = service.chunk_repository(str(repo_dir))

    child_chunk = next(chunk for chunk in chunks if chunk.type == "class" and chunk.name == "Child")
    base_chunk = next(chunk for chunk in chunks if chunk.type == "class" and chunk.name == "Base")

    assert child_chunk.superclasses == ["Base"]
    assert any("Child.use_base" in entry for entry in base_chunk.where_used)
