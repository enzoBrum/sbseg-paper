from pathlib import Path
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate

certs_dir = Path(__file__).parent

for pem_file in certs_dir.glob("*.pem"):
    der_file = pem_file.with_suffix(".der")
    pem_bytes = pem_file.read_bytes()
    if pem_file.stem.startswith("cert"):
        der_bytes = load_pem_x509_certificate(pem_bytes).public_bytes(Encoding.DER)
    else:
        der_bytes = load_pem_private_key(pem_bytes, password=None).private_bytes(
            Encoding.DER,
            format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["PrivateFormat"]).PrivateFormat.PKCS8,
            encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["NoEncryption"]).NoEncryption(),
        )
    der_file.write_bytes(der_bytes)
    print(f"  {pem_file.name} -> {der_file.name}")
