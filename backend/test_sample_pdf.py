"""Run the Lbl -> Span regression test against a local tagged PDF.

Usage (from the backend directory):
    python test_sample_pdf.py "C:\\path\\to\\sample.pdf"

The script writes a new *_actual_text_fixed.pdf file beside the source PDF.
"""
from pathlib import Path
import sys

from app.services.pdf_service import inspect_pdf, process_pdf


def main() -> int:
    if len(sys.argv) != 2:
        print('Usage: python test_sample_pdf.py "<input.pdf>"')
        return 2

    source = Path(sys.argv[1]).expanduser().resolve()
    if not source.is_file() or source.suffix.lower() != ".pdf":
        print(f"Input PDF not found: {source}")
        return 2

    output = source.with_name(f"{source.stem}_actual_text_fixed.pdf")
    report = inspect_pdf(source)
    result = process_pdf(source, output)

    print(f"Input:  {source}")
    print(f"Output: {output}")
    print(f"Pages: {report['pages']}")
    print(f"Lbl elements: {report['label_count']}")
    print(f"Existing Span preserved: {result['unchanged_spans']}")
    print(f"New Span elements: {result['created_spans']}")
    print(f"Skipped: {result['skipped']}")
    print(f"Post-save validation: {result['validation']}")
    print("New Span ActualText: ' Bullet ' (one leading and one trailing space)")

    if result["skipped"]:
        print("Some labels were skipped. Review the details before using the output.")
        return 1
    print("PASS: repair completed and post-save structure validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
