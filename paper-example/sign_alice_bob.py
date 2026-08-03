import sys
from pathlib import Path

from pyhanko import stamp
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers
from pyhanko.sign.fields import SigFieldSpec


def sign_pdf(
    input_path, output_path, key_path, cert_path, signer_name, field_name, x, y
):
    print(f"Signing {input_path} as {signer_name} at ({x}, {y})...")
    signer = signers.SimpleSigner.load(key_path, cert_path)

    # Define a box for the signature: (x1, y1, x2, y2)
    # PDF coordinates usually start from bottom-left
    width = 55
    height = 25
    box = (x, y, x + width, y + height)

    with open(input_path, "rb") as inf:
        w = IncrementalPdfFileWriter(inf)
        meta = signers.PdfSignatureMetadata(field_name=field_name, name=signer_name)
        pdf_signer = signers.PdfSigner(
            meta,
            signer,
            new_field_spec=SigFieldSpec(field_name, box=box),
            stamp_style=stamp.TextStampStyle(
                stamp_text=f"Signed By {signer_name}",
                background=stamp.STAMP_ART_CONTENT,
            ),
        )
        with open(output_path, "wb") as outf:
            pdf_signer.sign_pdf(w, output=outf)


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 sign_alice_bob.py <alice_x> <alice_y> <bob_x> <bob_y>")
        print("Example: python3 paper-example/sign_alice_bob.py 100 700 100 600")
        sys.exit(1)

    try:
        ax, ay = int(sys.argv[1]), int(sys.argv[2])
        bx, by = int(sys.argv[3]), int(sys.argv[4])
    except ValueError:
        print("Coordinates must be integers.")
        sys.exit(1)

    base_path = Path("paper-example")
    input_pdf = base_path / "input.pdf"
    alice_signed = base_path / "alice_signed.pdf"
    final_signed = base_path / "final_signed.pdf"

    # Alice signs
    sign_pdf(
        input_pdf,
        alice_signed,
        base_path / "alice_key.pem",
        base_path / "alice_cert.pem",
        "Alice",
        "AliceSig",
        ax,
        ay,
    )

    # Bob signs the file signed by Alice
    sign_pdf(
        alice_signed,
        final_signed,
        base_path / "bob_key.pem",
        base_path / "bob_cert.pem",
        "Bob",
        "BobSig",
        bx,
        by,
    )

    print(f"\nFinal signed PDF saved at {final_signed}")
