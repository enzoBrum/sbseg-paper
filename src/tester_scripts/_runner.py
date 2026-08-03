from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import select

import modification_pipeline.model
from modification_pipeline.model import (
    ModificationTest,
    ModificationVerifierAssociation,
    Verifier,
    VerifierTest,
)

PAGE_SIZE = 32


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

        if on_page_committed is not None:
            on_page_committed()

        offset += page_size
