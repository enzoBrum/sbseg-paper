from pathlib import Path

from modification_pipeline import ASA, SFDA, CreateSignature, Pipeline
from modification_pipeline.add_new_annotation import AddNewAnnotation
from modification_pipeline.alter_page_content import AlterPageContent
from modification_pipeline.model import init
from sys import argv

# unsigned = Path(__file__).parent.parent / "clicksign.pdf"
# unsigned = Path(__file__).parent / "./unsigned-files/example-2-0.pdf"
# unsigned = Path("web-tested-pdfs/clicksign.pdf")
# unsigned = Path(__file__).parent.parent / "belgian_pki_multiple_ocsps_lt.pdf"
unsigned = Path(argv[1])
mod = Path(argv[2])

init("./tmp.db")

pipe = Pipeline(
    [SFDA()],
    unsigned,
    False,
)

pipe.apply(mod)
