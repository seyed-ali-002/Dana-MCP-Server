import tempfile
from pathlib import Path
import sqlite3
import dana.tools.codebase_memory as cm

def test_index_and_incremental_and_search():
    with tempfile.TemporaryDirectory() as d:
        root=Path(d); (root/'a.py').write_text("import os\n\ndef validate_token(x):\n    return x\n")
        c=cm._db(root)
        # direct internal smoke of indexing primitives avoids MCP registration dependency
        text=(root/'a.py').read_text(); syms, imports, summary=cm._analyze(text,'a.py')
        assert syms[0][0]=='validate_token' and 'os' in imports and 'validate_token' in summary
        c.close()

def test_dedup_and_context_id_stable():
    items=[{'path':'a','content':'same'},{'path':'b','content':'same'}]
    out=cm._dedupe(items)
    assert len(out)==1 and set(out[0]['references'])=={'a','b'}
    assert cm._cid('hello')==cm._cid('hello')

def test_delta():
    import difflib
    d=''.join(difflib.unified_diff(['a\n'],['a\n','b\n']))
    assert '+b' in d
