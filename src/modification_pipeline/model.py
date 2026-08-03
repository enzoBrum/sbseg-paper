from enum import Enum
from pathlib import Path
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, create_engine, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
    Session,
)


class VerifierCategory(str, Enum):
    GUI = "gui"
    LIBRARY = "library"
    WEB = "web"

FILE_PATH = Path(__file__).parent.parent / "signed_files.db"
ENGINE_URL = f"sqlite:///{FILE_PATH}"


class Base(DeclarativeBase): ...


class ModificationTest(Base):
    __tablename__: str = "modification_test"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255))
    fileblob: Mapped[bytes] = mapped_column(LargeBinary, default=None)
    expected_result: Mapped[bool] = mapped_column(Boolean)

    attack_name: Mapped[Optional[str]] = mapped_column(String(64), default=None)

    associations: Mapped[List["ModificationChainAssociation"]] = relationship(
        back_populates="modification_test"
    )

    tested_verifiers_assoc: Mapped[List["ModificationVerifierAssociation"]] = (
        relationship(back_populates="modification_test")
    )


class ChainItemSpec(Base):
    __tablename__: str = "chain_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_name: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    field_mdp_action: Mapped[Optional[str]] = mapped_column(String(10), default=None)
    field_mdp_include_sigfield: Mapped[Optional[bool]] = mapped_column(default=None)
    mdp_perms: Mapped[Optional[int]] = mapped_column(default=None)
    certify: Mapped[Optional[bool]] = mapped_column(default=None)
    include_adobe_p: Mapped[Optional[bool]] = mapped_column(default=None)
    stamp_enable: Mapped[Optional[bool]] = mapped_column(default=None)
    signer_idx: Mapped[Optional[int]] = mapped_column(default=None)
    sig_field_name: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    target_page_index: Mapped[Optional[int]] = mapped_column(default=None)
    place_on_different_page: Mapped[Optional[bool]] = mapped_column(default=None)

    idx: Mapped[int] = mapped_column(default=None)

    associations: Mapped[List["ModificationChainAssociation"]] = relationship(
        back_populates="chain_item"
    )


class ModificationChainAssociation(Base):
    __tablename__: str = "modification_chain_association"

    idA: Mapped[int] = mapped_column(
        ForeignKey("modification_test.id"), primary_key=True
    )
    idB: Mapped[int] = mapped_column(ForeignKey("chain_item.id"), primary_key=True)

    # Relationships
    modification_test: Mapped["ModificationTest"] = relationship(
        back_populates="associations"
    )
    chain_item: Mapped["ChainItemSpec"] = relationship(back_populates="associations")


class Verifier(Base):
    __tablename__: str = "verifier"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(16))
    version: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    url: Mapped[Optional[str]] = mapped_column(String(512), default=None)


class VerifierTest(Base):
    __tablename__: str = "verifier_test"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(255))
    verifier_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("verifier.id"), default=None
    )
    verifier: Mapped[Optional["Verifier"]] = relationship()

    result_layer_1:        Mapped[Optional[bool]]  = mapped_column(Boolean, default=None)
    warn_modified_layer_1: Mapped[Optional[bool]]  = mapped_column(Boolean, default=None)
    screenshot_layer_1:    Mapped[Optional[bytes]] = mapped_column(LargeBinary, default=None)

    result_layer_2:        Mapped[Optional[bool]]  = mapped_column(Boolean, default=None)
    warn_modified_layer_2: Mapped[Optional[bool]]  = mapped_column(Boolean, default=None)
    screenshot_layer_2:    Mapped[Optional[bytes]] = mapped_column(LargeBinary, default=None)

    modification_test_assoc: Mapped[List["ModificationVerifierAssociation"]] = (
        relationship(back_populates="verifier_test")
    )


class ModificationVerifierAssociation(Base):
    __tablename__: str = "modification_verifier_association"

    idA: Mapped[int] = mapped_column(
        ForeignKey("modification_test.id"), primary_key=True
    )
    idB: Mapped[int] = mapped_column(ForeignKey("verifier_test.id"), primary_key=True)

    # Relationships
    verifier_test: Mapped["VerifierTest"] = relationship(
        back_populates="modification_test_assoc"
    )
    modification_test: Mapped["ModificationTest"] = relationship(
        back_populates="tested_verifiers_assoc"
    )


SESSION: sessionmaker[Session] | None = None

FILE_PATH = Path(__file__).parent.parent / "signed_files.db"
ENGINE_URL = f"sqlite:///{FILE_PATH}"


def _seed_verifiers(session: Session) -> None:
    """Idempotently populate the `verifier` table from in-code registries."""
    from tester_scripts.gui.verifiers import SEED_DATA as _GUI_SEED
    from tester_scripts.library.verifiers import SEED_DATA as _LIB_SEED
    from tester_scripts.web.verifiers import SEED_DATA as _WEB_SEED

    existing = {
        row.name: row
        for row in session.execute(select(Verifier)).scalars().all()
    }

    def _upsert(
        slug: str,
        display: str,
        version: str | None,
        category: VerifierCategory,
        url: str | None = None,
    ) -> None:
        row = existing.get(slug)
        if row is None:
            session.add(
                Verifier(
                    name=slug,
                    display_name=display,
                    category=category.value,
                    version=version,
                    url=url,
                )
            )
            return
        row.display_name = display
        row.category = category.value
        if version is not None:
            row.version = version
        row.url = url

    for slug, display, version in _GUI_SEED:
        _upsert(slug, display, version, VerifierCategory.GUI)
    for slug, display, version in _LIB_SEED:
        _upsert(slug, display, version, VerifierCategory.LIBRARY)
    for slug, display, version, url in _WEB_SEED:
        _upsert(slug, display, version, VerifierCategory.WEB, url=url)

    session.commit()


def init(filepath: Path | None = None):
    if filepath is not None:
        engine_url = f"sqlite:///{filepath}"
    else:
        engine_url = ENGINE_URL

    global SESSION
    print(engine_url)
    engine = create_engine(engine_url, echo=False)
    Base.metadata.create_all(engine)
    SESSION = sessionmaker(bind=engine)

    with SESSION() as session:
        _seed_verifiers(session)


def get_sessionmaker() -> sessionmaker:
    assert SESSION is not None
    return SESSION


def get_session() -> Session:
    assert SESSION is not None
    return SESSION()
