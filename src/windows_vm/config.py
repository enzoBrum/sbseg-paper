"""Small, explicit configuration for the Windows verifier VM."""

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = REPO_ROOT / ".vm"
INSTALLER_CACHE = STATE_ROOT / "installers"
API_URL = f"http://127.0.0.1:{os.environ.get('SBSEG_VM_API_PORT', '8765')}"


@dataclass(frozen=True)
class Verifier:
    version: str
    exe: str
    install_args: tuple[str, ...]
    installer_required: bool = True


VERIFIERS = {
    "adobe": Verifier(
        version="26.1.21563.0",
        exe=r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
        install_args=("/sAll", "/rs", "/rps", "/msi", "EULA_ACCEPT=YES"),
    ),
    "foxit": Verifier(
        version="2026.1.1.36485",
        exe=(
            r"C:\Program Files\Foxit Software\Foxit PDF Reader\FoxitPDFReader.exe"
        ),
        install_args=("/quiet",),
    ),
    "master_pdf_editor": Verifier(
        version="5.9.9.8",
        exe=(
            r"C:\Program Files\Code Industry\Master PDF Editor 5\MasterPDFEditor.exe"
        ),
        install_args=("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-"),
    ),
    "edge": Verifier(
        version="148.0.3967.83",
        exe=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        install_args=("/silent", "/install"),
        installer_required=False,
    ),
}
