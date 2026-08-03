from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pyhanko import stamp
from pyhanko.pdf_utils import generic
from pyhanko.pdf_utils.generic import pdf_name
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import SimpleSigner, signers
from pyhanko.sign.fields import FieldMDPAction, FieldMDPSpec, MDPPerm, SigFieldSpec
from pyhanko.sign.signers.cms_embedder import (
    SigMDPSetup,
    docmdp_reference_dictionary,
    fieldmdp_reference_dictionary,
)

from .chain_item import ChainItem

CMS_SIGNERS: list[SimpleSigner] | None = None

old_sig_mdp_setup_apply = SigMDPSetup.apply


def new_sig_mdp_setup_apply(self: SigMDPSetup, sig_obj_ref, writer):
    certify = self.certify
    docmdp_perms = self.docmdp_perms

    lock = self.field_lock

    reference_array = generic.ArrayObject()

    if certify:
        assert docmdp_perms is not None
        root = writer.root
        try:
            perms = root["/Perms"]
        except KeyError:
            root["/Perms"] = perms = generic.DictionaryObject()
        perms[generic.pdf_name("/DocMDP")] = sig_obj_ref
        writer.update_container(perms)
        reference_array.append(docmdp_reference_dictionary(docmdp_perms))

    if lock is not None:
        fieldmdp_ref = fieldmdp_reference_dictionary(lock, data_ref=writer.root_ref)
        reference_array.append(fieldmdp_ref)

        if docmdp_perms is not None and SigMDPSetup.include_adobe_p:  # type: ignore
            fieldmdp_ref["/TransformParams"]["/P"] = generic.NumberObject(
                docmdp_perms.value
            )

    if reference_array:
        sig_obj_ref.get_object()["/Reference"] = reference_array


SigMDPSetup.apply = new_sig_mdp_setup_apply
signers.PdfSigner._enforce_certification_constraints = lambda *_args, **_kwargs: None


class CreateSignature(ChainItem):

    def __init__(
        self,
        field_mdp_action: Literal["/All", "/Include", "/Exclude"] | None = None,
        field_mdp_include_sigfield: bool = False,
        include_adobe_p: bool = False,
        mdp_perms: Literal[1, 2, 3] | None = None,
        certify: bool = False,
        stamp_enable: bool = False,
        signer_idx: int = 0,
        sig_field_name: str | None = None,
    ) -> None:
        super().__init__(
            field_mdp_action=field_mdp_action,
            field_mdp_include_sigfield=field_mdp_include_sigfield,
            include_adobe_p=include_adobe_p,
            mdp_perms=mdp_perms,
            certify=certify,
            stamp_enable=stamp_enable,
            signer_idx=signer_idx,
            sig_field_name=sig_field_name,
        )

    def apply(self, file_content: BytesIO):
        global CMS_SIGNERS

        if CMS_SIGNERS is None:
            certspath = Path(__file__).parent.parent / "certs"

            CMS_SIGNERS = []
            for i in range(1, 6):
                signer = SimpleSigner.load(
                    str(certspath / f"key-{i}.pem"), str(certspath / f"cert-{i}.pem")
                )
                assert signer is not None
                CMS_SIGNERS.append(signer)

        cms_signer = CMS_SIGNERS[self.spec.signer_idx]  # type: ignore
        SigMDPSetup.include_adobe_p = self.spec.include_adobe_p  # type: ignore

        if self.spec.sig_field_name is not None:
            w = IncrementalPdfFileWriter(file_content, strict=False)
            pdf_signer = signers.PdfSigner(
                signers.PdfSignatureMetadata(
                    self.spec.sig_field_name,
                    "sha256",
                    name="FOO",
                    docmdp_permissions=(
                        MDPPerm(self.spec.mdp_perms)
                        if self.spec.mdp_perms is not None
                        else MDPPerm.FILL_FORMS
                    ),
                    certify=self.spec.certify or False,
                ),
                cms_signer,
                stamp_style=(
                    stamp.TextStampStyle(stamp_text="Signed By FOO")
                    if self.spec.stamp_enable
                    else None
                ),
            )
            pdf_signer.sign_pdf(w, in_place=True)
            file_content.seek(0)
            return

        field_name = uuid4().hex
        if self.spec.stamp_enable:
            box = (100, 100, 300, 300)
            stamp_style = stamp.TextStampStyle(stamp_text="Signed by FOO")
        else:
            box = stamp_style = None

        locked_fields = [field_name] if self.spec.field_mdp_include_sigfield else []
        if self.spec.field_mdp_action is None:
            field_mdp = None
        elif self.spec.field_mdp_action == "/All":
            field_mdp = FieldMDPSpec(
                FieldMDPAction(pdf_name(self.spec.field_mdp_action))
            )
        else:
            field_mdp = FieldMDPSpec(
                FieldMDPAction(pdf_name(self.spec.field_mdp_action)), locked_fields
            )

        w = IncrementalPdfFileWriter(file_content, strict=False)

        pdf_signer = signers.PdfSigner(
            signers.PdfSignatureMetadata(
                field_name,
                "sha256",
                name="FOO",
                docmdp_permissions=(
                    MDPPerm(self.spec.mdp_perms)
                    if self.spec.mdp_perms is not None
                    else MDPPerm.FILL_FORMS
                ),
                certify=self.spec.certify or False,
            ),
            cms_signer,
            new_field_spec=SigFieldSpec(
                field_name,
                box=box,
                field_mdp_spec=field_mdp,
                doc_mdp_update_value=(
                    MDPPerm(self.spec.mdp_perms)
                    if self.spec.mdp_perms is not None
                    else None
                ),
            ),
            stamp_style=stamp_style,
        )

        pdf_signer.sign_pdf(w, in_place=True)
        file_content.seek(0)
