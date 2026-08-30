from __future__ import annotations
import hashlib, re, sqlite3, time
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP
from dana.security.path_policy import require_path

# Provider-independent estimate. Exact model usage can be recorded when a client/API supplies it.
_WORD_RE=re.compile(r"\w+|[^\w\s]", re.UNICODE)

def estimate_tokens(text:str)->int:
    # Conservative multilingual heuristic; avoids pretending to know provider tokenizer counts.
    return max(0, (len(text)+3)//4) if text else 0

def _db(root:Path):
    p=root/'.dana'/'analytics.db'; p.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(p)
    c.execute('CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, name TEXT, input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER, duration REAL, exact INTEGER, source TEXT, session_id TEXT)')
    cols={row[1] for row in c.execute('PRAGMA table_info(events)')}
    if 'session_id' not in cols: c.execute("ALTER TABLE events ADD COLUMN session_id TEXT DEFAULT 'default'")
    c.execute('CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, started REAL, ended REAL)')
    return c

def _session(root:Path,session_id:str):
    c=_db(root); now=time.time(); c.execute('INSERT OR IGNORE INTO sessions VALUES(?,?,NULL)',(session_id,now)); c.commit(); c.close()

def register_token_analytics_tools(mcp:FastMCP)->None:
 @mcp.tool()
 def estimate_tokens_for_context(text:str)->dict[str,Any]:
    tokens=estimate_tokens(text); return {'estimated_tokens':tokens,'characters':len(text),'exact':False,'method':'provider-independent character estimate'}

 @mcp.tool()
 def record_token_usage(name:str,input_tokens:int=0,output_tokens:int=0,duration_seconds:float=0.0,path:str='.',session_id:str='default',exact:bool=True,source:str='client_reported')->dict[str,Any]:
    root=require_path(path,purpose='token analytics'); _session(root,session_id); total=max(0,input_tokens)+max(0,output_tokens); c=_db(root); c.execute('INSERT INTO events(ts,name,input_tokens,output_tokens,total_tokens,duration,exact,source) VALUES(?,?,?,?,?,?,?,?,?)',(time.time(),name,max(0,input_tokens),max(0,output_tokens),total,max(0.0,duration_seconds),int(exact),source,session_id)); c.commit(); c.close(); return {'recorded':True,'total_tokens':total,'exact':exact,'duration_seconds':max(0.0,duration_seconds)}

 @mcp.tool()
 def start_work_session(path:str='.',session_id:str='default')->dict[str,Any]:
    root=require_path(path,purpose='token analytics'); c=_db(root); now=time.time(); c.execute('INSERT OR REPLACE INTO sessions(id,started,ended) VALUES(?,?,NULL)',(session_id,now)); c.commit(); c.close(); return {'session_id':session_id,'started_at':now}

 @mcp.tool()
 def end_work_session(path:str='.',session_id:str='default')->dict[str,Any]:
    root=require_path(path,purpose='token analytics'); c=_db(root); now=time.time(); row=c.execute('SELECT started FROM sessions WHERE id=?',(session_id,)).fetchone(); c.execute('UPDATE sessions SET ended=? WHERE id=?',(now,session_id)); c.commit(); c.close(); return {'session_id':session_id,'duration_seconds':max(0.0,now-row[0]) if row else None}

 @mcp.tool()
 def get_token_analytics(path:str='.',session_id:str='',include_operations:bool=True,operation_limit:int=50)->dict[str,Any]:
    """Return per-session or all-time token and timing analytics."""
    root=require_path(path,purpose='token analytics'); c=_db(root)
    where=''; params=()
    if session_id:
        where=' WHERE session_id=?'; params=(session_id,)
    totals=c.execute('SELECT COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0),COALESCE(SUM(total_tokens),0),COALESCE(SUM(duration),0),COUNT(*) FROM events'+where,params).fetchone()
    all_totals=c.execute('SELECT COALESCE(SUM(input_tokens),0),COALESCE(SUM(output_tokens),0),COALESCE(SUM(total_tokens),0),COALESCE(SUM(duration),0),COUNT(*) FROM events').fetchone()
    wall=0.0
    if session_id:
        row=c.execute('SELECT started,ended FROM sessions WHERE id=?',(session_id,)).fetchone(); now=time.time()
        wall=max(0.0,(row[1] or now)-row[0]) if row else 0.0
    ops=[]
    if include_operations:
        rows=c.execute('SELECT id,ts,name,input_tokens,output_tokens,total_tokens,duration,exact,source,session_id FROM events'+where+' ORDER BY id DESC LIMIT ?',params+(max(1,min(operation_limit,500)),)).fetchall()
        keys=['id','timestamp','name','input_tokens','output_tokens','total_tokens','duration_seconds','exact','source','session_id']
        ops=[dict(zip(keys,r)) for r in rows]
    c.close()
    current={'input_tokens':totals[0],'output_tokens':totals[1],'total_tokens':totals[2],'operation_time_seconds':totals[3],'operations':totals[4],'wall_time_seconds':wall}
    lifetime={'input_tokens':all_totals[0],'output_tokens':all_totals[1],'total_tokens':all_totals[2],'operation_time_seconds':all_totals[3],'operations':all_totals[4]}
    return {'scope':'session' if session_id else 'all_time','session_id':session_id or None,'current':current,'all_time':lifetime,'recent_operations':ops}

 @mcp.tool()
 def get_operation_analytics(path:str='.',session_id:str='',limit:int=100)->dict[str,Any]:
    """Return timing and token usage for every recorded operation, without an aggregate-only view."""
    return get_token_analytics(path,session_id,True,limit)

 @mcp.tool()
 def reset_token_analytics(path:str='.',session_id:str='')->dict[str,Any]:
    root=require_path(path,purpose='token analytics'); c=_db(root)
    if session_id: c.execute('DELETE FROM sessions WHERE id=?',(session_id,))
    else: c.execute('DELETE FROM events'); c.execute('DELETE FROM sessions')
    c.commit(); c.close(); return {'reset':True,'session_id':session_id or 'all'}
