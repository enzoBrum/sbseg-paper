from abc import ABC, abstractmethod
from io import BytesIO
from typing import cast

from pyhanko.pdf_utils.generic import ArrayObject, DictionaryObject, IndirectObject
from pyhanko.pdf_utils.reader import PdfFileReader

from .model import ChainItemSpec


class ChainItem(ABC):
    spec: ChainItemSpec

    def __init__(self, **kwargs) -> None:
        self.spec = ChainItemSpec(**kwargs, item_name=self.__class__.__name__)

    @abstractmethod
    def apply(self, file_content: BytesIO): ...

    def find_sig_field_ref(
        self, field_name: str | None, r: PdfFileReader
    ) -> IndirectObject:
        if field_name is None:
            sig_field_indirect: IndirectObject = r.root["/AcroForm"]["/Fields"].raw_get(
                -1
            )
        else:
            fields = cast(ArrayObject, r.root["/AcroForm"]["/Fields"])
            for i in range(len(fields)):
                cur = cast(DictionaryObject, fields[i])
                print(cur)
                if cur["/T"] != field_name:
                    continue
                sig_field_indirect = cast(IndirectObject, fields.raw_get(i))
                break
            else:
                raise Exception(f"{field_name} not found")

        return sig_field_indirect
