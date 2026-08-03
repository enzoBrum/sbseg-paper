import traceback
from concurrent.futures import Future, as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from io import BytesIO

import requests
import tqdm
from sqlalchemy import select
from sqlalchemy.sql.functions import count

import modification_pipeline.model
from modification_pipeline.model import ModificationTest, VerifierTest


def run_test(
    modification_test: ModificationTest, port: int = 8080
) -> tuple[ModificationTest, dict]:
    """POST the PDF to the verifier and return the JSON payload.

    Expected shape:
        {"result": "VALID|INVALID", "warn_modified": bool}
    """
    with BytesIO(modification_test.fileblob) as stream:
        response = requests.post(
            f"http://localhost:{port}/verify",
            files={"file": stream},
            timeout=30,
        )
    assert response.status_code == 200
    return modification_test, response.json()


def test(name: str, where_clause=None):
    from tester_scripts._runner import run_paginated
    from tester_scripts.library.verifiers import REGISTRY

    verifier = REGISTRY[name]()
    print(f"{name} version: {verifier.version or 'unknown'}")

    with modification_pipeline.model.get_session() as session:
        total = session.execute(
            select(count()).select_from(ModificationTest)
        ).scalar_one()

    pbar = tqdm.tqdm(total=total)

    try:
        verifier.start()
        with ThreadPoolExecutor(16) as pool:
            def process_page(
                tests: list[ModificationTest], verifier_id: int
            ) -> list[tuple[ModificationTest, VerifierTest | None]]:
                futs: dict[Future[tuple[ModificationTest, dict]], ModificationTest] = {
                    pool.submit(run_test, t, verifier.port): t for t in tests
                }
                results = []
                for fut in as_completed(futs):
                    pbar.update()
                    try:
                        _, payload = fut.result()
                        t = futs[fut]
                        results.append((t, VerifierTest(
                            name=name,
                            verifier_id=verifier_id,
                            result_layer_1=(payload["result"] == "VALID"),
                            warn_modified_layer_1=(payload["warn_modified"]),
                        )))
                    except Exception:
                        traceback.print_exc()
                return results

            run_paginated(name, process_page, on_skip=pbar.update, where_clause=where_clause)
    finally:
        verifier.stop()
