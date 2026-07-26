# app/domain/conversations/exceptions.py
from __future__ import annotations


class ConversationNotFoundError(Exception):
    pass


class NamespaceDeletionError(Exception):
    """Raised when Pinecone namespace cleanup fails — deletion is aborted
    rather than proceeding, to avoid orphaning vectors we can no longer find."""
    pass