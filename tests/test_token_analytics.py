from pathlib import Path
from dana.tools.token_analytics import estimate_tokens, _db

def test_estimate_tokens():
    assert estimate_tokens('')==0
    assert estimate_tokens('abcdefgh')==2

def test_session_column_and_storage(tmp_path):
    c=_db(tmp_path)
    c.execute("INSERT INTO events(ts,name,input_tokens,output_tokens,total_tokens,duration,exact,source,session_id) VALUES(1,'a',10,5,15,0.2,1,'test','s1')")
    c.execute("INSERT INTO events(ts,name,input_tokens,output_tokens,total_tokens,duration,exact,source,session_id) VALUES(2,'b',20,10,30,0.4,1,'test','s2')")
    c.commit()
    assert c.execute("SELECT SUM(total_tokens) FROM events WHERE session_id='s1'").fetchone()[0]==15
    assert c.execute('SELECT SUM(total_tokens) FROM events').fetchone()[0]==45
    c.close()
