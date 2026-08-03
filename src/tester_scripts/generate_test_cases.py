"""
Test-case generation following Algorithm 1 of the paper.

Each (mdp_level, is_cert_sig, is_field_protected, is_stamp, change_page) tuple
emits one ASA Pipeline and one SFDA Pipeline.

How (is_cert_sig, mdp_level) maps to PDF:

  - is_cert_sig=True,  mdp_level=P  -> certification signature with DocMDP /P
  - is_cert_sig=False, mdp_level=P  -> approval signature with SigFieldLock /P
  - is_cert_sig=False, mdp_level=None -> approval signature, no permission control
  - is_cert_sig=True,  mdp_level=None -> invalid (skipped)

``is_field_protected`` controls whether the signed field appears in the
FieldMDP/SigFieldLock /Fields list (i.e., whether the field itself is locked).
``change_page`` drives the two novel variants: ASA rewrites /P of the signed
widget; SFDA places the duplicated widget on a different page.
"""

from itertools import product
from pathlib import Path
from typing import Literal

from modification_pipeline import AddNewAnnotation, AlterPageContent, ChainItem, CreateSignature, Pipeline, SFDA, ASA

MdpLevel = Literal[1, 2, 3] | None


def create_asa_test_case(
    infile: Path,
    mdp_level: MdpLevel,
    is_cert_sig: bool,
    is_field_protected: bool,
    is_stamp: bool,
    change_page: bool,
) -> Pipeline:
    needs_sigfieldlock = (not is_cert_sig) and mdp_level is not None
    field_mdp_action = (
        "/Include" if (is_field_protected or needs_sigfieldlock) else None
    )

    chain = [
        CreateSignature(
            mdp_perms=mdp_level,
            certify=is_cert_sig,
            field_mdp_action=field_mdp_action,
            field_mdp_include_sigfield=is_field_protected,
            stamp_enable=is_stamp,
        ),
        ASA(change_page=change_page),
    ]

    return Pipeline(chain, infile, False, attack_name="ASA")


def create_sfda_test_case(
    infile: Path,
    mdp_level: MdpLevel,
    is_cert_sig: bool,
    is_field_protected: bool,
    is_stamp: bool,
    change_page: bool,
) -> Pipeline:
    needs_sigfieldlock = (not is_cert_sig) and mdp_level is not None
    field_mdp_action = (
        "/Include" if (is_field_protected or needs_sigfieldlock) else None
    )

    chain = [
        CreateSignature(
            mdp_perms=mdp_level,
            certify=is_cert_sig,
            field_mdp_action=field_mdp_action,
            field_mdp_include_sigfield=is_field_protected,
            stamp_enable=is_stamp,
        ),
        SFDA(change_page=change_page),
    ]

    return Pipeline(chain, infile, False, attack_name="SFDA")


def create_extra_p1_test_case(infile: Path) -> Pipeline:
    chain: list[ChainItem] = [
        CreateSignature(mdp_perms=1, certify=True),
        CreateSignature(mdp_perms=None, certify=False),
    ]
    return Pipeline(chain, infile, False, attack_name="EXTRA_P1")


def create_extra_p2_test_case(infile: Path) -> Pipeline:
    chain: list[ChainItem] = [
        CreateSignature(mdp_perms=2, certify=True),
        CreateSignature(mdp_perms=None, certify=False),
    ]
    return Pipeline(chain, infile, True, attack_name="EXTRA_P2")


def create_extra_p3_test_case(infile: Path) -> Pipeline:
    chain: list[ChainItem] = [
        CreateSignature(mdp_perms=3, certify=True),
        AddNewAnnotation(),
    ]
    return Pipeline(chain, infile, True, attack_name="EXTRA_P3")


def create_smoke_test_1_valid(infile: Path) -> Pipeline:
    return Pipeline([CreateSignature()], infile, True, attack_name="SMOKE_TEST_1")


def create_smoke_test_2_alter_page(infile: Path) -> Pipeline:
    return Pipeline(
        [CreateSignature(), AlterPageContent()], infile, False, attack_name="SMOKE_TEST_2"
    )


def create_smoke_test_3_mdp3_annot(infile: Path) -> Pipeline:
    return Pipeline(
        [CreateSignature(certify=True, mdp_perms=3), AddNewAnnotation()],
        infile, True, attack_name="SMOKE_TEST_3",
    )


def gen_test_cases() -> list[Pipeline]:
    unsigned_files = list((Path(__file__).parent.parent / "unsigned-files").iterdir())

    ret = []

    for (
        infile,
        mdp_level,
        is_cert_sig,
        is_field_protected,
        is_stamp,
        change_page,
    ) in product(
        unsigned_files,
        (None, 1, 2, 3),
        (True, False),
        (True, False),
        (True, False),
        (True, False),
    ):
        if is_cert_sig and mdp_level is None:
            continue

        ret.append(
            create_asa_test_case(
                infile,
                mdp_level,
                is_cert_sig,
                is_field_protected,
                is_stamp,
                change_page,
            )
        )
        ret.append(
            create_sfda_test_case(
                infile,
                mdp_level,
                is_cert_sig,
                is_field_protected,
                is_stamp,
                change_page,
            )
        )

    for infile in unsigned_files:
        ret.append(create_extra_p1_test_case(infile))
        ret.append(create_extra_p2_test_case(infile))
        ret.append(create_extra_p3_test_case(infile))

    for infile in unsigned_files:
        ret.append(create_smoke_test_1_valid(infile))
        ret.append(create_smoke_test_2_alter_page(infile))
        ret.append(create_smoke_test_3_mdp3_annot(infile))

    return ret
