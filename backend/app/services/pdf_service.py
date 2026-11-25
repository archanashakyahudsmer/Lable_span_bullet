"""PDF list-label Span repair.

The repair is deliberately conservative:
- Existing Span children are not edited.
- A missing Span is inserted only when the Lbl points to one direct MCID,
  the MCID's ParentTree slot points back to that Lbl, and page content confirms
  the known bullet glyph used by the source PDF.
- Both the structure-tree /K and the matching ParentTree array entry are updated.
- The source file is never overwritten.

This implementation uses PyMuPDF's low-level xref API. It avoids an additional
pikepdf dependency and is covered by checks against the supplied sample PDF.
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import fitz

BULLET_ACTUAL_TEXT = " Bullet "

_REF_RE = re.compile(r"(\d+)\s+\d+\s+R")
_PARENT_ARRAY_TOKEN_RE = re.compile(r"null|\d+\s+\d+\s+R")
_PARENT_TREE_TOKEN_RE = re.compile(r"\d+\s+\d+\s+R|\d+")


def _xref_value(doc: fitz.Document, xref: int, key: str) -> int | None:
    """Return the object number for a PDF indirect-reference key."""
    kind, value = doc.xref_get_key(xref, key)
    if kind != "xref":
        return None
    try:
        return int(value.split()[0])
    except (ValueError, IndexError):
        return None


def _walk_structure(doc: fitz.Document, elem_xref: int, seen: set[int] | None = None):
    """Walk StructElem children only; do not follow /P parent references."""
    if seen is None:
        seen = set()
    if elem_xref in seen:
        return
    seen.add(elem_xref)

    kind, tag = doc.xref_get_key(elem_xref, "S")
    if kind == "name" and tag == "/Lbl":
        yield elem_xref

    kid_kind, kids = doc.xref_get_key(elem_xref, "K")
    child_refs: list[int] = []
    if kid_kind == "xref":
        child_refs.append(int(kids.split()[0]))
    elif kid_kind == "array":
        child_refs.extend(int(ref) for ref in _REF_RE.findall(kids))

    for child_xref in child_refs:
        child_kind, child_tag = doc.xref_get_key(child_xref, "S")
        if child_kind == "name":
            yield from _walk_structure(doc, child_xref, seen)


def _parent_tree_arrays(
    doc: fitz.Document,
    node_xref: int,
    found: dict[int, int] | None = None,
    seen: set[int] | None = None,
) -> dict[int, int]:
    """Return {StructParents key: indirect MCID parent-array xref}."""
    if found is None:
        found = {}
    if seen is None:
        seen = set()
    if node_xref in seen:
        return found
    seen.add(node_xref)

    kind, nums = doc.xref_get_key(node_xref, "Nums")
    if kind == "array":
        tokens = _PARENT_TREE_TOKEN_RE.findall(nums)
        # A number tree /Nums array is [key value key value ...]. In this
        # document each value is an indirect reference to an MCID parent array.
        if len(tokens) % 2:
            raise ValueError("Malformed ParentTree /Nums array.")
        for index in range(0, len(tokens), 2):
            try:
                key = int(tokens[index])
            except ValueError as exc:
                raise ValueError("ParentTree key is not an integer.") from exc
            ref_match = re.fullmatch(r"(\d+)\s+\d+\s+R", tokens[index + 1])
            if ref_match:
                found[key] = int(ref_match.group(1))

    kids_kind, kids = doc.xref_get_key(node_xref, "Kids")
    if kids_kind == "array":
        for child in _REF_RE.findall(kids):
            _parent_tree_arrays(doc, int(child), found, seen)
    return found


def _read_parent_array(doc: fitz.Document, array_xref: int) -> list[str]:
    """Read a ParentTree MCID array as ref/null tokens without losing entries."""
    raw = doc.xref_object(array_xref, compressed=False).strip()
    if not (raw.startswith("[") and raw.endswith("]")):
        raise ValueError(f"ParentTree object {array_xref} is not an array.")
    inside = raw[1:-1]
    items = _PARENT_ARRAY_TOKEN_RE.findall(inside)
    residue = _PARENT_ARRAY_TOKEN_RE.sub("", inside)
    if residue.strip():
        raise ValueError(f"ParentTree array {array_xref} contains unsupported values.")
    return items


def _struct_root_xref(doc: fitz.Document) -> int:
    catalog = doc.pdf_catalog()
    root = _xref_value(doc, catalog, "StructTreeRoot")
    if root is None:
        raise ValueError("This PDF has no tagged structure tree (StructTreeRoot).")
    return root


def _labels(doc: fitz.Document) -> list[int]:
    root = _struct_root_xref(doc)
    document_elem = _xref_value(doc, root, "K")
    if document_elem is None:
        return []
    return list(_walk_structure(doc, document_elem))


def _span_children(doc: fitz.Document, label_xref: int) -> list[int]:
    kind, value = doc.xref_get_key(label_xref, "K")
    refs: list[int] = []
    if kind == "xref":
        refs = [int(value.split()[0])]
    elif kind == "array":
        refs = [int(ref) for ref in _REF_RE.findall(value)]
    result = []
    for ref in refs:
        child_kind, child_tag = doc.xref_get_key(ref, "S")
        if child_kind == "name" and child_tag == "/Span":
            result.append(ref)
    return result


def _resolve_page(doc: fitz.Document, label_xref: int) -> int | None:
    """Use /Pg on Lbl or walk /P ancestors if /Pg is inherited."""
    current = label_xref
    seen: set[int] = set()
    while current and current not in seen:
        seen.add(current)
        page = _xref_value(doc, current, "Pg")
        if page is not None:
            return page
        current = _xref_value(doc, current, "P") or 0
    return None


def _page_for_xref(doc: fitz.Document, page_xref: int) -> fitz.Page | None:
    for page in doc:
        if page.xref == page_xref:
            return page
    return None


def _mcid_content(page: fitz.Page, mcid: int) -> str | None:
    streams = []
    for stream_xref in page.get_contents():
        stream = page.parent.xref_stream(stream_xref)
        if stream:
            streams.append(stream.decode("latin-1", errors="replace"))
    content = "\n".join(streams)
    pattern = re.compile(
        rf"/Lbl\s*<<?\s*/MCID\s+{mcid}\s*>>\s*BDC(.*?)EMC",
        re.DOTALL,
    )
    match = pattern.search(content)
    return match.group(1) if match else None


def _is_known_bullet_content(marked_content: str | None) -> bool:
    """Confirm the sample's bullet glyph rather than wrapping arbitrary text.

    In the supplied InDesign PDF, the Lbl marked-content stream uses glyph code
    octal 225 in a Tj text-show operator; PyMuPDF decodes that glyph as U+2022.
    Other/unknown glyph encodings are reported for review, never guessed.
    """
    if not marked_content:
        return False
    return bool(re.search(r"\(\\225\)\s*Tj", marked_content))


def _locate_parent_array(
    doc: fitz.Document,
    label_xref: int,
    mcid: int,
    parent_arrays: dict[int, int],
) -> tuple[int, int, list[str]] | None:
    page_xref = _resolve_page(doc, label_xref)
    if page_xref is None:
        return None
    struct_parents_kind, struct_parents_value = doc.xref_get_key(page_xref, "StructParents")
    if struct_parents_kind != "int":
        return None
    parent_array_xref = parent_arrays.get(int(struct_parents_value))
    if parent_array_xref is None:
        return None
    items = _read_parent_array(doc, parent_array_xref)
    if mcid < 0 or mcid >= len(items):
        return None
    if items[mcid] != f"{label_xref} 0 R":
        return None
    return page_xref, parent_array_xref, items


def inspect_pdf(path: Path) -> dict[str, Any]:
    """Read-only inspection report for every Lbl structure element."""
    with fitz.open(path) as doc:
        root = _struct_root_xref(doc)
        parent_tree_xref = _xref_value(doc, root, "ParentTree")
        if parent_tree_xref is None:
            raise ValueError("Tagged PDF is missing the StructTreeRoot ParentTree.")
        parent_arrays = _parent_tree_arrays(doc, parent_tree_xref)
        labels = _labels(doc)
        rows = []

        for index, label_xref in enumerate(labels, start=1):
            spans = _span_children(doc, label_xref)
            if spans:
                actual_text = []
                for span_xref in spans:
                    kind, val = doc.xref_get_key(span_xref, "ActualText")
                    actual_text.append(val if kind == "string" else "")
                rows.append({
                    "index": index,
                    "label_xref": label_xref,
                    "status": "existing_span_preserved",
                    "span_count": len(spans),
                    "actual_text": actual_text,
                    "detail": "A Span child already exists. It will be preserved without modification.",
                })
                continue

            kid_kind, kid_value = doc.xref_get_key(label_xref, "K")
            if kid_kind != "int":
                rows.append({
                    "index": index,
                    "label_xref": label_xref,
                    "status": "skipped_ambiguous_kid",
                    "detail": "Lbl does not have one direct MCID integer; structure was left unchanged.",
                })
                continue

            mcid = int(kid_value)
            linkage = _locate_parent_array(doc, label_xref, mcid, parent_arrays)
            if linkage is None:
                rows.append({
                    "index": index,
                    "label_xref": label_xref,
                    "mcid": mcid,
                    "status": "skipped_parent_tree_mismatch",
                    "detail": "ParentTree does not point to this Lbl at the MCID slot; structure was left unchanged.",
                })
                continue

            page_xref = linkage[0]
            page = _page_for_xref(doc, page_xref)
            marked_content = _mcid_content(page, mcid) if page else None
            if not _is_known_bullet_content(marked_content):
                rows.append({
                    "index": index,
                    "label_xref": label_xref,
                    "mcid": mcid,
                    "status": "skipped_bullet_not_confirmed",
                    "detail": "The marked content was not recognized as the bullet glyph; structure was left unchanged.",
                })
                continue

            rows.append({
                "index": index,
                "label_xref": label_xref,
                "mcid": mcid,
                "status": "ready_to_create_span",
                "detail": "Bullet glyph and ParentTree linkage are confirmed. A Span with ActualText ' Bullet ' can be created.",
            })

        summary = {
            "existing_span": sum(r["status"] == "existing_span_preserved" for r in rows),
            "ready_to_create_span": sum(r["status"] == "ready_to_create_span" for r in rows),
            "skipped": sum(r["status"].startswith("skipped_") for r in rows),
        }
        return {
            "filename": path.name,
            "pages": len(doc),
            "is_tagged": True,
            "label_count": len(labels),
            "labels": rows,
            "summary": summary,
        }


def process_pdf(input_path: Path, output_path: Path) -> dict[str, Any]:
    """Insert nested Span tags where safe, updating both K and ParentTree."""
    created = unchanged = skipped = 0
    details: list[dict[str, Any]] = []

    with fitz.open(input_path) as doc:
        root = _struct_root_xref(doc)
        parent_tree_xref = _xref_value(doc, root, "ParentTree")
        if parent_tree_xref is None:
            raise ValueError("Tagged PDF is missing the StructTreeRoot ParentTree.")
        parent_arrays = _parent_tree_arrays(doc, parent_tree_xref)
        labels = _labels(doc)

        for index, label_xref in enumerate(labels, start=1):
            # User rule: any existing direct Span child is preserved as-is.
            if _span_children(doc, label_xref):
                unchanged += 1
                details.append({"index": index, "result": "unchanged_existing_span"})
                continue

            kid_kind, kid_value = doc.xref_get_key(label_xref, "K")
            if kid_kind != "int":
                skipped += 1
                details.append({"index": index, "result": "skipped_ambiguous_kid"})
                continue

            mcid = int(kid_value)
            linkage = _locate_parent_array(doc, label_xref, mcid, parent_arrays)
            if linkage is None:
                skipped += 1
                details.append({"index": index, "result": "skipped_parent_tree_mismatch", "mcid": mcid})
                continue

            page_xref, parent_array_xref, parent_items = linkage
            page = _page_for_xref(doc, page_xref)
            marked_content = _mcid_content(page, mcid) if page else None
            if not _is_known_bullet_content(marked_content):
                skipped += 1
                details.append({"index": index, "result": "skipped_bullet_not_confirmed", "mcid": mcid})
                continue

            span_xref = doc.get_new_xref()
            span_object = (
                "<<\n"
                "/Type /StructElem\n"
                "/S /Span\n"
                f"/P {label_xref} 0 R\n"
                f"/Pg {page_xref} 0 R\n"
                f"/K {mcid}\n"
                f"/ActualText ({BULLET_ACTUAL_TEXT})\n"
                ">>"
            )
            doc.update_object(span_xref, span_object)

            # 1) Make Span the child of Lbl.
            doc.xref_set_key(label_xref, "K", f"{span_xref} 0 R")

            # 2) The ParentTree MCID slot must point to the new Span, not Lbl.
            parent_items[mcid] = f"{span_xref} 0 R"
            doc.update_object(parent_array_xref, "[ " + " ".join(parent_items) + " ]")

            created += 1
            details.append({
                "index": index,
                "result": "created_span",
                "label_xref": label_xref,
                "span_xref": span_xref,
                "mcid": mcid,
                "page_xref": page_xref,
            })

        # Save to a separate output path; never overwrite the source PDF.
        doc.save(output_path, garbage=0, deflate=True)

    # Re-open and validate the saved file before telling the caller it succeeded.
    validation = validate_processed_pdf(output_path)
    expected = created + unchanged
    if validation["span_children"] < expected or validation["parent_tree_links"] < expected:
        raise ValueError(
            "Post-save validation failed: the nested Span count or ParentTree links are incomplete."
        )

    # Check the exact spaced ActualText value on every Span created in this run.
    # Existing Span elements are preserved and are not rewritten.
    with fitz.open(output_path) as saved_doc:
        for detail in details:
            if detail.get("result") != "created_span":
                continue
            actual_kind, actual_value = saved_doc.xref_get_key(
                detail["span_xref"], "ActualText"
            )
            if actual_kind != "string" or actual_value != BULLET_ACTUAL_TEXT:
                raise ValueError(
                    f"Post-save validation failed for newly created Span {detail['span_xref']}: "
                    "ActualText must contain one leading and one trailing space."
                )

    return {
        "created_spans": created,
        "unchanged_spans": unchanged,
        "skipped": skipped,
        "details": details,
        "validation": validation,
        "output": str(output_path),
    }


def validate_processed_pdf(path: Path) -> dict[str, int]:
    """Validate nested Span children, ActualText and ParentTree back-links."""
    with fitz.open(path) as doc:
        root = _struct_root_xref(doc)
        parent_tree_xref = _xref_value(doc, root, "ParentTree")
        if parent_tree_xref is None:
            raise ValueError("Processed PDF is missing ParentTree.")
        parent_arrays = _parent_tree_arrays(doc, parent_tree_xref)
        labels = _labels(doc)
        span_count = 0
        parent_tree_links = 0
        actual_text_bullet = 0

        for label_xref in labels:
            spans = _span_children(doc, label_xref)
            for span_xref in spans:
                span_count += 1
                actual_kind, actual_value = doc.xref_get_key(span_xref, "ActualText")
                if actual_kind == "string" and actual_value == BULLET_ACTUAL_TEXT:
                    actual_text_bullet += 1

                mcid_kind, mcid_value = doc.xref_get_key(span_xref, "K")
                page_xref = _resolve_page(doc, span_xref)
                if mcid_kind != "int" or page_xref is None:
                    continue
                struct_parents_kind, struct_parents_value = doc.xref_get_key(page_xref, "StructParents")
                if struct_parents_kind != "int":
                    continue
                array_xref = parent_arrays.get(int(struct_parents_value))
                if array_xref is None:
                    continue
                items = _read_parent_array(doc, array_xref)
                mcid = int(mcid_value)
                if 0 <= mcid < len(items) and items[mcid] == f"{span_xref} 0 R":
                    parent_tree_links += 1

        return {
            "pages": len(doc),
            "label_count": len(labels),
            "span_children": span_count,
            "actual_text_bullet_with_spaces": actual_text_bullet,
            "parent_tree_links": parent_tree_links,
        }
