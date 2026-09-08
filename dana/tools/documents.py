from __future__ import annotations

from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from dana.security.path_policy import require_path


def _set_rtl(paragraph) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    paragraph.alignment = 2
    pPr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    pPr.append(bidi)


def _set_font(run, font: str) -> None:
    run.font.name = font
    run._element.rPr.rFonts.set(
        qn("w:cs"), font
    ) if run._element.rPr is not None else None


def register_document_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def create_docx(
        path: str, title: str = "", content: str = "", font: str = "Tahoma"
    ) -> dict[str, Any]:
        """Create a UTF-8 Persian/RTL-compatible Word document."""
        from docx import Document
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Pt

        doc = Document()
        sections = doc.sections
        for section in sections:
            section.right_margin = section.right_margin
        if title:
            p = doc.add_heading(level=1)
            _set_rtl(p)
            r = p.add_run(title)
            r.font.name = font
            r.font.size = Pt(18)
        for block in content.split("\n"):
            p = doc.add_paragraph()
            _set_rtl(p)
            r = p.add_run(block)
            r.font.name = font
            r.font.size = Pt(11)
            rPr = r._element.get_or_add_rPr()
            rFonts = rPr.rFonts or OxmlElement("w:rFonts")
            rFonts.set(qn("w:ascii"), font)
            rFonts.set(qn("w:hAnsi"), font)
            rFonts.set(qn("w:cs"), font)
            if rPr.rFonts is None:
                rPr.append(rFonts)
        out = Path(path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(out)
        return {"path": str(out), "format": "docx", "rtl": True, "font": font}

    @mcp.tool()
    def create_pdf(
        path: str, title: str = "", content: str = "", font_path: str | None = None
    ) -> dict[str, Any]:
        """Create a Persian-capable PDF using ReportLab with Arabic shaping and bidi."""
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
        except ImportError as exc:
            raise RuntimeError(
                "Install arabic-reshaper and python-bidi for Persian PDF support"
            ) from exc
        out = Path(path).expanduser().resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if not font_path:
            candidates = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            ]
            font_path = next((p for p in candidates if Path(p).exists()), None)
        if not font_path:
            raise RuntimeError("A Unicode TTF font is required; provide font_path")
        font_name = "DanaUnicode"
        pdfmetrics.registerFont(TTFont(font_name, font_path))
        style = ParagraphStyle(
            "DanaRTL",
            fontName=font_name,
            fontSize=11,
            leading=18,
            alignment=TA_RIGHT,
            textColor=colors.black,
        )
        doc = SimpleDocTemplate(
            str(out),
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50,
        )
        story = []
        for text in ([title] if title else []) + content.split("\n"):
            shaped = get_display(arabic_reshaper.reshape(text))
            story.append(Paragraph(shaped.replace("&", "&amp;"), style))
            story.append(Spacer(1, 8))
        doc.build(story)
    @mcp.tool()
    def extract_pdf_text(
        path: str,
        max_pages: int | None = None,
        max_chars: int | None = None,
    ) -> dict[str, Any]:
        """Extract real textual content and metadata from a PDF file.

        Use this before summarizing or creating educational material from PDFs.
        The source file is checked against Dana's filesystem access policy.
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError(
                "PDF extraction requires pypdf. Install Dana dependencies first."
            ) from exc

        source = require_path(path, purpose="extract PDF text")
        if not source.is_file():
            raise ValueError(f"PDF file not found: {source}")
        if source.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a .pdf file: {source}")

        reader = PdfReader(str(source))
        total_pages = len(reader.pages)
        page_limit = total_pages if max_pages is None else max(0, min(int(max_pages), total_pages))
        char_limit = None if max_chars is None else max(0, int(max_chars))
        pages: list[dict[str, Any]] = []
        chunks: list[str] = []
        extracted_chars = 0
        truncated = False

        for index in range(page_limit):
            text = reader.pages[index].extract_text() or ""
            if char_limit is not None and extracted_chars + len(text) > char_limit:
                remaining = max(0, char_limit - extracted_chars)
                text = text[:remaining]
                truncated = True
            pages.append({"page": index + 1, "text": text})
            chunks.append(text)
            extracted_chars += len(text)
            if char_limit is not None and extracted_chars >= char_limit:
                truncated = index + 1 < page_limit or page_limit < total_pages
                break

        metadata = reader.metadata or {}
        return {
            "path": str(source),
            "format": "pdf",
            "page_count": total_pages,
            "pages_extracted": len(pages),
            "text": "\n\n".join(chunks),
            "pages": pages,
            "metadata": {str(k): str(v) for k, v in metadata.items() if v is not None},
            "truncated": truncated or page_limit < total_pages,
        }

    @mcp.tool()
    def extract_pdfs_text(
        directory: str,
        recursive: bool = False,
        max_pages_per_file: int | None = None,
        max_chars_per_file: int | None = None,
    ) -> dict[str, Any]:
        """Extract real text from every PDF in a directory for source-grounded analysis."""
        target = require_path(directory, purpose="extract PDF texts")
        if not target.is_dir():
            raise ValueError(f"Not a directory: {target}")
        pattern = "**/*.pdf" if recursive else "*.pdf"
        files = sorted(path for path in target.glob(pattern) if path.is_file())
        results = []
        total_chars = 0
        for pdf in files:
            item = extract_pdf_text(
                str(pdf),
                max_pages=max_pages_per_file,
                max_chars=max_chars_per_file,
            )
            total_chars += len(item["text"])
            results.append(item)
        return {
            "directory": str(target),
            "files_found": len(files),
            "files_extracted": len(results),
            "total_characters": total_chars,
            "documents": results,
        }


        return {"path": str(out), "format": "pdf", "rtl": True, "font": font_name}

    @mcp.tool()
    def create_document(
        path: str,
        content: str,
        title: str = "",
        format: str = "docx",
        font: str = "Tahoma",
        font_path: str | None = None,
    ) -> dict[str, Any]:
        """Create a Word or PDF document with Unicode/RTL support."""
        if format.lower() == "pdf":
            return create_pdf(path, title, content, font_path)
        return create_docx(path, title, content, font)
