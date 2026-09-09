"""
PDF -> evidence blocks.

Text is extracted with PyMuPDF and grouped into meaningful evidence
blocks. Tables are extracted separately with pdfplumber.

Each block retains:
- a unique ID
- document ID
- page number
- block type
- exact source text

The goal is to reduce unnecessary fragmentation while preserving
the evidence needed for exact quote verification.
"""

import uuid

import fitz
import pdfplumber


MIN_TEXT_LENGTH = 40
MAX_MERGED_BLOCK_LENGTH = 6000
MAX_VERTICAL_GAP = 18


def extract_evidence_blocks(
    pdf_path: str,
    document_id: str,
) -> list[dict]:

    blocks = []

    doc = fitz.open(pdf_path)

    try:

        for page_index in range(len(doc)):

            page = doc[page_index]
            page_num = page_index + 1

            text_blocks = _extract_page_text_blocks(
                page
            )

            merged_blocks = _merge_text_blocks(
                text_blocks
            )

            for text in merged_blocks:

                if len(text) < MIN_TEXT_LENGTH:
                    continue

                blocks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "page": page_num,
                        "block_type": "TEXT",
                        "text": text,
                    }
                )

    finally:
        doc.close()

    # --------------------------------------------------------
    # Tables
    # --------------------------------------------------------

    with pdfplumber.open(pdf_path) as pdf:

        for page_index, page in enumerate(pdf.pages):

            page_num = page_index + 1

            try:
                tables = page.extract_tables()
            except Exception as error:
                print(
                    f"[PDF] Table extraction failed "
                    f"on page {page_num}: {error}"
                )
                continue

            for table in tables:

                rendered = _render_table(
                    table
                )

                if not rendered:
                    continue

                if len(rendered) < MIN_TEXT_LENGTH:
                    continue

                blocks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "document_id": document_id,
                        "page": page_num,
                        "block_type": "TABLE",
                        "text": rendered,
                    }
                )

    print(
        f"[PDF] Extracted {len(blocks)} evidence blocks "
        f"from {pdf_path}"
    )

    return blocks


def _extract_page_text_blocks(
    page,
) -> list[dict]:

    raw_blocks = page.get_text(
        "blocks"
    )

    result = []

    for block in raw_blocks:

        if len(block) < 5:
            continue

        x0, y0, x1, y1, text = block[:5]

        text = text.strip()

        if not text:
            continue

        if len(text) < MIN_TEXT_LENGTH:
            continue

        result.append(
            {
                "x0": x0,
                "y0": y0,
                "x1": x1,
                "y1": y1,
                "text": text,
            }
        )

    result.sort(
        key=lambda item: (
            item["y0"],
            item["x0"],
        )
    )

    return result


def _merge_text_blocks(
    blocks: list[dict],
) -> list[str]:

    if not blocks:
        return []

    merged = []

    current_text = blocks[0]["text"]
    current_y1 = blocks[0]["y1"]

    for block in blocks[1:]:

        text = block["text"]

        vertical_gap = (
            block["y0"] - current_y1
        )

        should_merge = (
            vertical_gap <= MAX_VERTICAL_GAP
            and len(current_text) + len(text) + 1
            <= MAX_MERGED_BLOCK_LENGTH
        )

        if should_merge:

            current_text = (
                current_text
                + "\n"
                + text
            )

            current_y1 = max(
                current_y1,
                block["y1"],
            )

        else:

            merged.append(
                current_text.strip()
            )

            current_text = text
            current_y1 = block["y1"]

    if current_text.strip():
        merged.append(
            current_text.strip()
        )

    return merged


def _render_table(
    table: list[list],
) -> str:

    rows = []

    for row in table:

        if not row:
            continue

        cells = [
            str(cell).strip()
            if cell
            else ""
            for cell in row
        ]

        if any(cells):

            rows.append(
                " | ".join(cells)
            )

    return "\n".join(rows)


def page_raw_text(
    pdf_path: str,
    page_num: int,
) -> str:
    """
    Return raw text for one page.

    Useful for exact evidence verification.
    """

    doc = fitz.open(
        pdf_path
    )

    try:

        if page_num < 1 or page_num > len(doc):
            return ""

        return doc[
            page_num - 1
        ].get_text()

    finally:
        doc.close()

if __name__ == "__main__":
    pdf_path = r"C:\Users\sachi\Downloads\superjoin-starter\superjoin\backend\data\uploads\908d4b1c-90cf-4930-ac42-5787e3d86667.pdf"
    document_id = str(uuid.uuid4())

    blocks = extract_evidence_blocks(
        pdf_path,
        document_id,
    )

    print(len(blocks))