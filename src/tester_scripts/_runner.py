from __future__ import annotations

import os
import sqlite3
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

import modification_pipeline.model
from modification_pipeline.model import (
    ModificationTest,
    ModificationVerifierAssociation,
    Verifier,
    VerifierTest,
)

PAGE_SIZE = 4

# When set (by the Windows VM worker), a consistent snapshot of the working
# database is written here after every committed page so the host can merge
# results incrementally and never loses a run to a dropped/timed-out request.
_SYNC_ENV = "SBSEG_DB_SYNC_PATH"
# Cap how often we pay the (Samba-backed) snapshot cost. Every page still gets
# captured eventually; the host's final merge covers anything skipped here.
_SYNC_MIN_INTERVAL = 5.0


def _snapshot_db(session: Session, dest: Path) -> None:
    """Atomically copy the session's SQLite file to ``dest``.

    Uses SQLite's online backup so the snapshot is transactionally consistent
    even though a verifier may write again immediately, then renames it into
    place so a concurrent reader on the host never sees a half-written file.
    """
    source = session.get_bind().engine.url.database
    if not source:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(str(tmp))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    os.replace(tmp, dest)


def run_paginated(
    name: str,
    process_page: Callable[
        [list[ModificationTest], int],
        list[tuple[ModificationTest, VerifierTest | None]],
    ],
    *,
    already_tested: Callable[[ModificationTest], bool] | None = None,
    on_skip: Callable[[], object] | None = None,
    page_size: int = PAGE_SIZE,
    on_page_committed: Callable[[], object] | None = None,
    where_clause: Any | None = None,
) -> None:
    """Page through ModificationTest rows and persist VerifierTest results.

    Args:
        name: Verifier slug; used for the DB Verifier.id lookup and the
              default already_tested predicate.
        process_page: Called with (unskipped_tests, verifier_id).  Returns
                      (ModificationTest, VerifierTest | None) pairs — pass None
                      to skip persisting a result for that test.
        already_tested: Override for the skip predicate.  Defaults to
                        checking that a VerifierTest with name==`name` exists.
        on_skip: Called for each skipped row (e.g. to advance a progress bar).
        page_size: DB page size.
        on_page_committed: Called after each page commit (e.g. to backup the DB).
    """
    if already_tested is None:
        def already_tested(t: ModificationTest) -> bool:
            return any(a.verifier_test.name == name for a in t.tested_verifiers_assoc)

    with modification_pipeline.model.get_session() as session:
        verifier_id: int = session.execute(
            select(Verifier).where(Verifier.name == name)
        ).scalar_one().id

    sync_path = os.environ.get(_SYNC_ENV)
    sync_dest = Path(sync_path) if sync_path else None
    last_sync = 0.0

    offset = 0
    while True:
        with modification_pipeline.model.get_session() as session:
            stmt = select(ModificationTest).limit(page_size).offset(offset)
            if where_clause is not None:
                stmt = stmt.where(where_clause)
            rows = session.execute(stmt).scalars().all()

            if not rows:
                return

            to_process: list[ModificationTest] = []
            for t in rows:
                if already_tested(t):
                    if on_skip is not None:
                        on_skip()
                else:
                    to_process.append(t)

            for test, vt in process_page(to_process, verifier_id):
                if vt is None:
                    continue
                session.add(vt)
                session.add(
                    ModificationVerifierAssociation(verifier_test=vt, modification_test=test)
                )
            session.commit()

            if sync_dest is not None and (
                time.monotonic() - last_sync >= _SYNC_MIN_INTERVAL
            ):
                _snapshot_db(session, sync_dest)
                last_sync = time.monotonic()

        if on_page_committed is not None:
            on_page_committed()

        offset += page_size
