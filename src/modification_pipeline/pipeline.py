from io import BytesIO
from pathlib import Path

from .chain_item import ChainItem
from .model import ModificationChainAssociation, ModificationTest, get_sessionmaker


class Pipeline:

    # All modification applied to a file.
    # Each modification corresponds to a PDF revision.
    chain: list[ChainItem]
    modification_test: ModificationTest
    stream: BytesIO

    def __init__(
        self,
        chain: list[ChainItem],
        infile: Path,
        expected_result: bool,
        attack_name: str | None = None,
    ) -> None:
        self.chain = chain
        self.modification_test = ModificationTest(
            filename=infile.name,
            expected_result=expected_result,
            attack_name=attack_name,
        )
        self.stream = BytesIO(infile.read_bytes())

    def apply(self, outfile: Path | None):
        for item in self.chain:
            try:
                item.apply(self.stream)
            except Exception as e:
                raise Exception(
                    f"Exception on run -> {self.chain}, {self.modification_test}, {vars(self.chain[0].spec)}"
                ) from e
            self.stream.seek(0)

        self.modification_test.fileblob = self.stream.read()

        with get_sessionmaker()() as session:
            session.add(self.modification_test)
            for i, item in enumerate(self.chain):
                item.spec.idx = i
                session.add(item.spec)

                assoc = ModificationChainAssociation(
                    modification_test=self.modification_test, chain_item=item.spec
                )

                session.add(assoc)

            session.commit()

        if outfile is not None:
            self.stream.seek(0)
            outfile.write_bytes(self.stream.read())

        self.stream.close()
