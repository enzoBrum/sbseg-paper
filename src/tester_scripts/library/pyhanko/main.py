from flask import Flask, jsonify, request
from pyhanko_certvalidator import ValidationContext

from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.diff_analysis.policy_api import ModificationLevel
from pyhanko.sign.validation import validate_pdf_signature

application = Flask(__name__)


@application.post("/verify")
def verify():
    vc = ValidationContext(
        [load_cert_from_pemder(f"cert-{i}.pem") for i in range(1, 7)]
    )

    file_stream = request.files["file"].stream
    r = PdfFileReader(file_stream)

    statuses = [validate_pdf_signature(sig, vc) for sig in r.embedded_signatures]

    if not statuses:
        return jsonify({"result": "INVALID", "warn_modified": False}), 200

    valid = all(s.bottom_line for s in statuses)
    warn_modified = any(
        s.modification_level == ModificationLevel.OTHER for s in statuses
    )

    return (
        jsonify(
            {"result": "VALID" if valid else "INVALID", "warn_modified": warn_modified}
        ),
        200,
    )


if __name__ == "__main__":
    application.run()
