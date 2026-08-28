from pathlib import Path

def test_document_tools_import():
    from dana.tools.documents import register_document_tools
    assert callable(register_document_tools)
