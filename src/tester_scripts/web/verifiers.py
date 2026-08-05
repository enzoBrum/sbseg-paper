"""Web verifiers are tested manually via the browser.

There is no automation; results are entered with
`main.py db record-web <slug> <test_id> --l1-valid|--no-l1-valid
--l2-valid|--no-l2-valid`.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class WebVerifier:
    name: str          # CLI slug
    display_name: str
    url: str
    version: str | None = None


REGISTRY: dict[str, WebVerifier] = {
    "dss_web_demo": WebVerifier(
        name="dss_web_demo",
        display_name="DSS Web Demo",
        url=(
            "https://ec.europa.eu/digital-building-blocks/DSS/"
            "webapp-demo/validation"
        ),
    ),
    "iti": WebVerifier(
        name="iti",
        display_name="ITI Validador de assinaturas",
        url="https://validar.iti.gov.br/",
    ),
    "certisign": WebVerifier(
        name="certisign",
        display_name="Certisign Verificador",
        url=(
            "https://assinaturas.certisign.com.br/"
            "VerificadorAssinaturas/Verificador"
        ),
    ),
    "digitalsign": WebVerifier(
        name="digitalsign",
        display_name="DigitalSign Validator",
        url=(
            "https://verify.digitalsign.pt/"
            "signaturesValidator/validator/validation"
        ),
    ),
    "dvv": WebVerifier(
        name="dvv",
        display_name="Digital and Population Data Services Agency",
        url="https://dvv.fineid.fi/en/validation",
    ),
    "bry": WebVerifier(
        name="bry",
        display_name="BRY Verifica",
        url="https://verifica.bry.com.br/",
    ),
    "zapsign": WebVerifier(
        name="zapsign",
        display_name="ZapSign Validador",
        url="https://validador.zapsign.com.br/validate-pdf",
    ),
    "clicksign": WebVerifier(
        name="clicksign",
        display_name="Clicksign Validador",
        url="https://www.clicksign.com/validador",
    ),
}


# (slug, display_name, version, url)
SEED_DATA: list[tuple[str, str, str | None, str | None]] = [
    (v.name, v.display_name, v.version, v.url) for v in REGISTRY.values()
]
