# app/infrastructure/artifacts/repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge.models import ArtifactStatus, ChunkRecord, DocumentArtifact, IngestionJob, IngestionJobStatus, RepositoryArtifact, Chunk
from app.knowledge.orm_models import ArtifactStatusDB, ChunkORM, DocumentORM, IngestionJobORM, IngestionJobStatusDB, RepositoryORM


def _to_document(row: DocumentORM) -> DocumentArtifact:
    return DocumentArtifact(
        id=row.id, conversation_id=row.conversation_id, filename=row.filename, content_type=row.content_type,
        status=ArtifactStatus(row.status.value), page_count=row.page_count,
        extraction_metadata=row.extraction_metadata, error=row.error, created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_repository(row: RepositoryORM) -> RepositoryArtifact:
    return RepositoryArtifact(
        id=row.id, conversation_id=row.conversation_id, repo_url=row.repo_url, default_branch=row.default_branch,
        indexed_commit_sha=row.indexed_commit_sha, languages_detected=row.languages_detected,
        status=ArtifactStatus(row.status.value), error=row.error, created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_chunk_record(row: ChunkORM) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=row.chunk_id, conversation_id=row.conversation_id, parent_type=row.parent_type,
        parent_id=row.parent_id, text=row.text, metadata=row.chunk_metadata, token_count=row.token_count,
        created_at=row.created_at,
    )


def _to_ingestion_job(row: IngestionJobORM) -> IngestionJob:
    return IngestionJob(
        id=row.id, conversation_id=row.conversation_id, source_type=row.source_type, source_ref=row.source_ref,
        status=IngestionJobStatus(row.status.value), error=row.error, started_at=row.started_at, completed_at=row.completed_at,
    )


class SqlAlchemyDocumentArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation_id: UUID, filename: str, content_type: str) -> DocumentArtifact:
        row = DocumentORM(conversation_id=conversation_id, filename=filename, content_type=content_type)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_document(row)

    async def update_status(
        self, document_id: UUID, status: ArtifactStatus, page_count: int | None = None,
        extraction_metadata: dict[str, Any] | None = None, error: str | None = None,
    ) -> DocumentArtifact:
        row = await self._session.get(DocumentORM, document_id)
        if row is None:
            raise LookupError(f"document {document_id} not found")
        row.status = ArtifactStatusDB(status.value)
        if page_count is not None:
            row.page_count = page_count
        if extraction_metadata is not None:
            row.extraction_metadata = extraction_metadata
        if error is not None:
            row.error = error
        await self._session.flush()
        await self._session.refresh(row)
        return _to_document(row)

    async def get(self, document_id: UUID) -> DocumentArtifact | None:
        row = await self._session.get(DocumentORM, document_id)
        return _to_document(row) if row else None

    async def list_by_conversation(self, conversation_id: UUID) -> list[DocumentArtifact]:
        result = await self._session.execute(select(DocumentORM).where(DocumentORM.conversation_id == conversation_id))
        return [_to_document(r) for r in result.scalars().all()]


class SqlAlchemyRepositoryArtifactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation_id: UUID, repo_url: str, default_branch: str | None) -> RepositoryArtifact:
        row = RepositoryORM(conversation_id=conversation_id, repo_url=repo_url, default_branch=default_branch)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_repository(row)

    async def update_status(
        self, repository_id: UUID, status: ArtifactStatus, indexed_commit_sha: str | None = None,
        languages_detected: list[str] | None = None, error: str | None = None,
    ) -> RepositoryArtifact:
        row = await self._session.get(RepositoryORM, repository_id)
        if row is None:
            raise LookupError(f"repository {repository_id} not found")
        row.status = ArtifactStatusDB(status.value)
        if indexed_commit_sha is not None:
            row.indexed_commit_sha = indexed_commit_sha
        if languages_detected is not None:
            row.languages_detected = languages_detected
        if error is not None:
            row.error = error
        await self._session.flush()
        await self._session.refresh(row)
        return _to_repository(row)

    async def get(self, repository_id: UUID) -> RepositoryArtifact | None:
        row = await self._session.get(RepositoryORM, repository_id)
        return _to_repository(row) if row else None

    async def list_by_conversation(self, conversation_id: UUID) -> list[RepositoryArtifact]:
        result = await self._session.execute(select(RepositoryORM).where(RepositoryORM.conversation_id == conversation_id))
        return [_to_repository(r) for r in result.scalars().all()]


class SqlAlchemyChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(self, conversation_id: UUID, parent_type: str, parent_id: str, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        rows = [
            ChunkORM(
                chunk_id=c.chunk_id, conversation_id=conversation_id, parent_type=parent_type, parent_id=parent_id,
                text=c.text, chunk_metadata=c.metadata, token_count=None,
            )
            for c in chunks
        ]
        self._session.add_all(rows)
        await self._session.flush()
        return len(rows)

    async def list_by_parent(self, parent_id: str) -> list[ChunkRecord]:
        result = await self._session.execute(select(ChunkORM).where(ChunkORM.parent_id == parent_id))
        return [_to_chunk_record(r) for r in result.scalars().all()]

    async def list_by_conversation(self, conversation_id: UUID) -> list[ChunkRecord]:
        result = await self._session.execute(select(ChunkORM).where(ChunkORM.conversation_id == conversation_id))
        return [_to_chunk_record(r) for r in result.scalars().all()]


class SqlAlchemyIngestionJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation_id: UUID, source_type: str, source_ref: str) -> IngestionJob:
        row = IngestionJobORM(conversation_id=conversation_id, source_type=source_type, source_ref=source_ref, status=IngestionJobStatusDB.RUNNING)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_ingestion_job(row)

    async def complete(self, job_id: UUID, status: IngestionJobStatus, error: str | None = None) -> IngestionJob:
        row = await self._session.get(IngestionJobORM, job_id)
        if row is None:
            raise LookupError(f"ingestion job {job_id} not found")
        row.status = IngestionJobStatusDB(status.value)
        row.error = error
        row.completed_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_ingestion_job(row)