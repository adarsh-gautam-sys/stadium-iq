"""Unit tests for the assessment storage layer (storage.py)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings
from app.storage import save_record


@pytest.mark.asyncio
async def test_save_record_locally(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When firestore_enabled is False, save_record writes to a local JSONL file."""
    # Force local storage mode
    monkeypatch.setattr(settings, "firestore_enabled", False)
    monkeypatch.setattr(settings, "local_data_dir", str(tmp_path))

    payload = {"test_key": "test_value"}
    status = await save_record(payload)

    assert status.startswith("saved_locally:")

    # Verify file was written
    record_file = tmp_path / "records.jsonl"
    assert record_file.exists()

    with record_file.open("r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["test_key"] == "test_value"
        assert "id" in data
        assert "created_at" in data
        assert data["schema_version"] == "1.0"


@pytest.mark.asyncio
async def test_save_record_firestore_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """When firestore_enabled is True, save_record writes to Firestore."""
    monkeypatch.setattr(settings, "firestore_enabled", True)

    mock_doc = MagicMock()
    mock_doc.id = "mock-doc-123"
    mock_doc.set = AsyncMock()

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_doc

    mock_client = MagicMock()
    mock_client.collection.return_value = mock_collection

    with patch("app.storage._FIRESTORE_AVAILABLE", True), \
         patch("app.storage._firestore.AsyncClient", return_value=mock_client):

        payload = {"test_key": "firestore_value"}
        status = await save_record(payload)

        assert status == "saved_to_firestore:mock-doc-123"
        mock_collection.document.assert_called_once()
        mock_doc.set.assert_called_once()

        # Check payload contents in the mock set call
        call_args = mock_doc.set.call_args[0][0]
        assert call_args["test_key"] == "firestore_value"
        assert "created_at" in call_args
        assert call_args["schema_version"] == "1.0"


@pytest.mark.asyncio
async def test_save_record_firestore_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Firestore write fails, it falls back to firestore_unavailable status."""
    monkeypatch.setattr(settings, "firestore_enabled", True)

    with patch("app.storage._FIRESTORE_AVAILABLE", True), \
         patch("app.storage._firestore.AsyncClient", side_effect=ValueError("Connection failed")):

        payload = {"test_key": "failed_value"}
        status = await save_record(payload)

        assert status == "firestore_unavailable:ValueError"
