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
)
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader

from .chain_item import ChainItem


class ASA(ChainItem):
    def __init__(self, change_page: bool = False, target_page_index: int = 1) -> None:
        super().__init__(
            place_on_different_page=change_page,
            target_page_index=target_page_index,
        )

    def apply(self, file_content: BytesIO):
        r = PdfFileReader(file_content, False)
        w = IncrementalPdfFileWriter.from_reader(r)

        sig_field_ref = self.find_sig_field_ref(None, r)
        sig_field_obj = cast(DictionaryObject, sig_field_ref.get_object())

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
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
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
                                NumberObject(100),
                                NumberObject(100),
                                NumberObject(300),
                                NumberObject(200),
                            ]
                        ),
                        NameObject("/Resources"): resources_ref,
                    }
                ),
                b"\nq\n1 0 0 1 0 0 cm\nBT\n0 g\n0 Tc /F1 12 Tf\n150 150 Td (SOME_TEXT-NEW AP) Tj\nET\nQ\n",
            )
        )
        sig_field_obj[NameObject("/AP")] = DictionaryObject(
            {NameObject("/N"): form_ref}
        )
        sig_field_obj[NameObject("/Rect")] = ArrayObject(
            [
                NumberObject(100),
                NumberObject(100),
                NumberObject(400),
                NumberObject(400),
            ]
        )

        # Optionally move widget to a different page
        if self.spec.place_on_different_page:
            kids = cast(ArrayObject, r.root["/Pages"]["/Kids"])
            old_page_ref = cast(IndirectObject, sig_field_obj.raw_get("/P"))
            new_page_ref = cast(
                IndirectObject, kids.raw_get(self.spec.target_page_index)
            )

            old_page_obj = cast(DictionaryObject, old_page_ref.get_object())
            new_page_obj = cast(DictionaryObject, new_page_ref.get_object())

            old_annots = cast(ArrayObject, old_page_obj["/Annots"])
            for i, entry in enumerate(old_annots):
                if (
                    isinstance(entry, IndirectObject)
                    and entry.idnum == sig_field_ref.idnum
                ):
                    old_annots.pop(i)
                    break
            else:
                raise Exception("Could not find sigfield reference in old page /Annots")

            if "/Annots" in new_page_obj:
                cast(ArrayObject, new_page_obj["/Annots"]).append(sig_field_ref)
            else:
                new_page_obj[NameObject("/Annots")] = ArrayObject([sig_field_ref])

            sig_field_obj[NameObject("/P")] = new_page_ref

            w.mark_update(old_page_ref)
            w.mark_update(new_page_ref)

        w.mark_update(sig_field_ref)
        w.write_in_place()
        file_content.seek(0)
