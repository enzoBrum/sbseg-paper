"""Detect ASA and SFDA signature-field attacks in a signed PDF.

Reports affected fields and offending objects for each attack found.

- ASA: a field's /AP or /Rect differs between its signing revision and the
  latest one.
- SFDA: two fields share a /V signature dict, one introduced in a later
  revision than the dict.

Usage: uv run python src/detect_attacks.py <file.pdf> [<file.pdf> ...]

Also runnable as: uv run python src/main.py detect <file.pdf> [<file.pdf> ...]
"""

import sys
from dataclasses import dataclass, field

from pyhanko.pdf_utils.generic import DictionaryObject, IndirectObject
from pyhanko.pdf_utils.reader import PdfFileReader


def _resolve(obj):
    """Follow an indirect reference to its target; pass direct objects through."""
    return obj.get_object() if isinstance(obj, IndirectObject) else obj


def _get(d, key):
    """Dict lookup that always resolves indirect references (unlike .get)."""
    return _resolve(d.get(key)) if key in d else None


def _ref_str(ref) -> str:
    """Render an indirect reference as 'idnum gen R' for the report."""
    if isinstance(ref, IndirectObject):
        ref = ref.reference
    return f"{ref.idnum} {ref.generation} R"


def _appearance_fingerprint(field_obj: DictionaryObject):
    """Content fingerprint of a field's /AP normal appearance.

    Compares resolved stream bytes + /BBox rather than indirect-reference
    identity, so an unmodified field reads identically across revisions.
    """
    ap = _get(field_obj, "/AP")
    if ap is None:
        return None
    normal = _get(ap, "/N")
    if normal is None:
        return None
    bbox = list(normal["/BBox"]) if "/BBox" in normal else None
    try:
        data = normal.data  # decoded stream content
    except Exception:
        data = None
    return (bbox, data)


def _rect(field_obj: DictionaryObject):
    return list(field_obj["/Rect"]) if "/Rect" in field_obj else None


def _iter_acroform_fields(fields_arr):
    """Yield (IndirectObject, DictionaryObject) over the full field tree."""
    for i in range(len(fields_arr)):
        ref = fields_arr.raw_get(i)
        obj = ref.get_object()
        yield ref, obj
        kids = _get(obj, "/Kids")
        if kids is not None:
            yield from _iter_acroform_fields(kids)


def _field_ref_by_name(reader: PdfFileReader, name: str):
    af = _get(reader.root, "/AcroForm")
    if af is None:
        return None
    for ref, obj in _iter_acroform_fields(af["/Fields"]):
        if obj.get("/T") == name:
            return ref
    return None


def _all_signature_fields(reader: PdfFileReader):
    """All signature fields/widgets in the latest revision, deduped by object.

    Scans both the AcroForm field tree and every page's /Annots, because an
    SFDA duplicate widget is sometimes added straight to a page's /Annots
    without being registered in /AcroForm/Fields.
    """
    seen: dict[int, tuple] = {}

    def consider(ref):
        if not isinstance(ref, IndirectObject):
            return
        obj = ref.get_object()
        if not isinstance(obj, DictionaryObject):
            return
        is_sig = obj.get("/FT") == "/Sig" or "/V" in obj
        if is_sig:
            seen.setdefault(ref.reference.idnum, (ref, obj))

    af = _get(reader.root, "/AcroForm")
    if af is not None and "/Fields" in af:
        for ref, _ in _iter_acroform_fields(af["/Fields"]):
            consider(ref)

    pages = _get(reader.root, "/Pages")
    if pages is not None and "/Kids" in pages:
        for page in pages["/Kids"]:
            page = _resolve(page)
            annots = _get(page, "/Annots")
            if annots is None:
                continue
            for j in range(len(annots)):
                consider(annots.raw_get(j))

    return list(seen.values())


@dataclass
class Finding:
    attack: str
    field_name: str
    detail: str
    objects: list = field(default_factory=list)


def detect_asa(reader: PdfFileReader) -> list[Finding]:
    findings: list[Finding] = []
    xrefs = reader.xrefs

    for emb in reader.embedded_signatures:
        signed_rev = emb.signed_revision
        field_ref = _field_ref_by_name(reader, emb.field_name)
        if field_ref is None:
            continue

        # Skip fields introduced *after* the revision we'd compare against
        # (e.g. an SFDA duplicate that shares another field's /V): they did not
        # exist in `signed_rev`, so the comparison is meaningless. SFDA handles
        # those instead.
        if xrefs.get_introducing_revision(field_ref.reference) > signed_rev:
            continue

        latest_obj = field_ref.get_object()
        historical = reader.get_historical_resolver(signed_rev)
        signed_obj = historical.get_object(field_ref.reference)
        if not isinstance(signed_obj, DictionaryObject):
            continue

        diffs = []
        objects = [_ref_str(field_ref)]

        if _rect(signed_obj) != _rect(latest_obj):
            diffs.append(f"/Rect {_rect(signed_obj)} -> {_rect(latest_obj)}")

        if _appearance_fingerprint(signed_obj) != _appearance_fingerprint(latest_obj):
            diffs.append("/AP (appearance stream) was replaced")
            ap = _get(latest_obj, "/AP")
            if ap is not None and "/N" in ap:
                objects.append(_ref_str(ap.raw_get("/N")))

        if diffs:
            findings.append(
                Finding(
                    attack="ASA",
                    field_name=emb.field_name,
                    detail="; ".join(diffs),
                    objects=objects,
                )
            )
    return findings


def detect_sfda(reader: PdfFileReader) -> list[Finding]:
    findings: list[Finding] = []
    xrefs = reader.xrefs

    # Group signature fields by the signature dictionary (/V) they reference.
    by_sig_dict: dict[int, list] = {}
    for field_ref, obj in _all_signature_fields(reader):
        if "/V" not in obj:
            continue
        v_ref = obj.raw_get("/V")
        if not isinstance(v_ref, IndirectObject):
            continue
        by_sig_dict.setdefault(v_ref.reference.idnum, []).append((field_ref, obj, v_ref))

    for entries in by_sig_dict.values():
        if len(entries) < 2:
            continue  # not shared -> not a duplication

        v_ref = entries[0][2]
        v_intro = xrefs.get_introducing_revision(v_ref.reference)

        for field_ref, obj, _ in entries:
            field_intro = xrefs.get_introducing_revision(field_ref.reference)
            if field_intro > v_intro:
                findings.append(
                    Finding(
                        attack="SFDA",
                        field_name=str(obj.get("/T")),
                        detail=(
                            f"field introduced in revision {field_intro} references "
                            f"signature dictionary {_ref_str(v_ref)} from revision "
                            f"{v_intro}"
                        ),
                        objects=[_ref_str(field_ref), _ref_str(v_ref)],
                    )
                )
    return findings


def report(path: str) -> bool:
    """Print a report for one PDF. Returns True if any attack was detected."""
    print(f"=== {path}")
    with open(path, "rb") as f:
        reader = PdfFileReader(f, strict=False)
        print(f"revisions: {reader.xrefs.total_revisions}")
        findings = detect_asa(reader) + detect_sfda(reader)

        if not findings:
            print("RESULT: clean (no ASA or SFDA detected)")
            return False

        print(f"RESULT: ATTACK DETECTED ({len(findings)} finding(s))")
        for fnd in findings:
            print(f"  [{fnd.attack}] field {fnd.field_name!r}: {fnd.detail}")
            print(f"           offending objects: {', '.join(fnd.objects)}")
        return True


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    detected_any = False
    for path in argv:
        detected_any |= report(path)
        print()
    return 1 if detected_any else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
