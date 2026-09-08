from pathlib import Path

def test_document_tools_import():
    from dana.tools.documents import register_document_tools
    assert callable(register_document_tools)



def test_pdf_text_extraction(tmp_path: Path):
    from reportlab.pdfgen import canvas
    from pypdf import PdfReader

    source = tmp_path / "sample.pdf"
    pdf = canvas.Canvas(str(source))
    pdf.drawString(72, 720, "Dana PDF source content")
    pdf.save()

    reader = PdfReader(str(source))
    assert "Dana PDF source content" in (reader.pages[0].extract_text() or "")
