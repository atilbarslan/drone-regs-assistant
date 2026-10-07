"""Local debugging record of one answer: the passages given to the model and its raw reply.

Off unless DEBUG_RAW=1. Files go to data/debug/ (outside git) and are the only place where the
question text is kept; request_log never stores it. Not meant for the deployed demo.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


async def write_raw(directory: Path, record: dict) -> Path | None:
    """Write one record as JSON, in a thread so the event loop is not blocked. A failure is
    logged and never fails the request."""

    def write() -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid4().hex[:6]}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    try:
        return await asyncio.to_thread(write)
    except OSError as exc:
        logger.warning("debug record not written (%s)", type(exc).__name__)
        return None
