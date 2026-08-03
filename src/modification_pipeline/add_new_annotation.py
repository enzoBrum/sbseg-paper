from copy import deepcopy
from io import BytesIO

from pyhanko.pdf_utils.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    NumberObject,
    StreamObject,
    TextStringObject,
)
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader

from .chain_item import ChainItem


class AddNewAnnotation(ChainItem):
    def __init__(self) -> None:
        super().__init__()

    def apply(self, file_content: BytesIO):
        r = PdfFileReader(file_content, False)
        w = IncrementalPdfFileWriter.from_reader(r)

        font_obj = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )

        font_ref = w.add_object(font_obj)

        resources_obj = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )

        resources_ref = w.add_object(resources_obj)

        form_obj = DictionaryObject(
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
        )

        xobject_stream = b"""
q
1 0 0 1 0 0 cm
BT
0 g
0 Tc /F1 12 Tf
150 150 Td (SOME_TEXT) Tj
ET
Q
        """

        form_obj = StreamObject(form_obj, xobject_stream)
        form_ref = w.add_object(form_obj)

        annot_obj = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/FreeText"),
                NameObject("/Rect"): deepcopy(form_obj["/BBox"]),
                NameObject("/DA"): TextStringObject("/F1 12  Tf 0 g"),
                NameObject("/Contents"): TextStringObject("SOME_TEXT"),
                NameObject("/F"): NumberObject(4),
                NameObject("/Border"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(0)]
                ),
                NameObject("/Rotate"): NumberObject(0),
                NameObject("/AP"): DictionaryObject({NameObject("/N"): form_ref}),
            }
        )

        annot_ref = w.add_object(annot_obj)

        page_ref = r.root["/Pages"]["/Kids"].raw_get(0)
        page_obj = page_ref.get_object()

        if "/Annots" in page_obj:
            page_obj["/Annots"].append(annot_ref)
        else:
            page_obj["/Annots"] = ArrayObject([annot_ref])

        w.mark_update(page_ref)

        w.write_in_place()
        file_content.seek(0)
