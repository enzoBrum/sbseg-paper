from copy import deepcopy
from io import BytesIO
from typing import cast

from pyhanko.pdf_utils.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader

from .chain_item import ChainItem


class SFDA(ChainItem):
    def __init__(
        self,
        sig_field_name: str = "duplicate",
        change_page: bool = False,
        target_page_index: int = 1,
    ) -> None:
        super().__init__(
            sig_field_name=sig_field_name,
            place_on_different_page=change_page,
            target_page_index=target_page_index,
        )

    def apply(self, file_content: BytesIO):
        r = PdfFileReader(file_content, False)
        w = IncrementalPdfFileWriter.from_reader(r)

        src_ref: IndirectObject = self.find_sig_field_ref(None, r)
        src_obj = cast(DictionaryObject, src_ref.get_object())

        # Duplicate field, sharing the original /V (signature dict)
        new_field = deepcopy(src_obj)
        new_field[NameObject("/T")] = TextStringObject(self.spec.sig_field_name)

        # Add AP to the duplicate
        font_ref = w.add_object(
            DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                    NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
                }
            )
        )
        resources_ref = w.add_object(
            DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): font_ref}
                    ),
                    #NameObject("/XObject"): DictionaryObject(
                    #    {
                    #        NameObject("/Im1"): src_obj["/AP"]["/N"]["/Resources"][
                    #            "/XObject"
                    #        ].raw_get("/Im1")
                    #    }
                    #),
                },
            )
        )
        form_ref = w.add_object(
            StreamObject(
                DictionaryObject(
                    {
                        NameObject("/Type"): NameObject("/XObject"),
                        NameObject("/Subtype"): NameObject("/Form"),
                        NameObject("/BBox"): ArrayObject(
                            [
                                NumberObject(0),
                                NumberObject(0),
                                NumberObject(900),
                                NumberObject(900),
                            ]
                        ),
                        NameObject("/Resources"): resources_ref,
                    }
                ),
                b"""
q
1 1 1 rg
460 415 90 19 re f
Q
BT /F2 12 Tf 460 420 Td (200.000,00) Tj ET
                """,
            )
        )
        new_field[NameObject("/AP")] = DictionaryObject({NameObject("/N"): form_ref})

        # Set Rect on the duplicate
        new_field[NameObject("/Rect")] = ArrayObject(
            [
                NumberObject(0),
                NumberObject(0),
                NumberObject(900),
                NumberObject(900),
            ]
        )

        # Determine host page
        kids = cast(ArrayObject, r.root["/Pages"]["/Kids"])
        host_page_index = (
            self.spec.target_page_index if self.spec.place_on_different_page else 0
        )
        page_ref = cast(IndirectObject, kids.raw_get(host_page_index))
        page_obj = cast(DictionaryObject, page_ref.get_object())

        if self.spec.place_on_different_page:
            new_field[NameObject("/P")] = page_ref

        new_field_ref = w.add_object(new_field)

        if "/Annots" in page_obj:
            cast(ArrayObject, page_obj["/Annots"]).append(new_field_ref)
        else:
            page_obj[NameObject("/Annots")] = ArrayObject([new_field_ref])

        acroform_ref = cast(IndirectObject, r.root.raw_get("/AcroForm"))
        acroform_obj = cast(DictionaryObject, acroform_ref.get_object())
        acroform_obj["/Fields"].append(new_field_ref)

        w.mark_update(page_ref)

        if isinstance(acroform_ref, IndirectObject):
            w.mark_update(acroform_ref)
        w.write_in_place()
        file_content.seek(0)
