"""
Adds black rectangle to existing PDF page
"""

from io import BytesIO

from pyhanko.pdf_utils.generic import StreamObject
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader

from .chain_item import ChainItem


class AlterPageContent(ChainItem):
    def apply(self, file_content: BytesIO):
        r = PdfFileReader(file_content, False)
        w = IncrementalPdfFileWriter.from_reader(r)

        page_ref = r.root["/Pages"]["/Kids"].raw_get(0)
        page_obj = page_ref.get_object()

        # Paints a black square on the bottom left corner.
        paint_square = b"""
q
0 0 0 rg
0 0 50 50 re f
Q
        """

        new_contents = StreamObject(stream_data=paint_square)
        new_contents_ref = w.add_object(new_contents)

        page_obj["/Contents"] = new_contents_ref

        w.mark_update(page_ref)

        w.write_in_place()
        file_content.seek(0)
