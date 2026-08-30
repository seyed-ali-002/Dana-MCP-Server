from __future__ import annotations
import ast, hashlib, sqlite3, time
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP
from dana.security.path_policy import require_path
IGNORE={'.git','.venv','venv','node_modules','__pycache__','.dana'}
EXT={'.py','.js','.ts','.tsx','.jsx','.php','.go','.rs','.java','.md','.txt','.json','.yaml','.yml'}
def db(root):
 p=root/'.dana'/'codebase_memory.db';p.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(p);c.executescript("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,hash TEXT,summary TEXT,content TEXT,updated REAL);CREATE TABLE IF NOT EXISTS symbols(name TEXT,kind TEXT,path TEXT,line INTEGER,signature TEXT);CREATE INDEX IF NOT EXISTS idx_symbols ON symbols(name);CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(path UNINDEXED,content,summary);");return c
def walk(root):
 for p in root.rglob('*'):
  if any(x in IGNORE for x in p.parts) or not p.is_file() or p.suffix.lower() not in EXT or p.stat().st_size>1000000:continue
  yield p
def sym(t,path):
 out=[]
 if path.endswith('.py'):
  try:
   for n in ast.walk(ast.parse(t)):
    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):out.append((n.name,'class' if isinstance(n,ast.ClassDef) else 'function',n.lineno,n.name))
  except SyntaxError:pass
 return out
def register_codebase_memory_tools(mcp:FastMCP)->None:
 @mcp.tool()
 def index_codebase(path:str='.',force:bool=False)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory');c=db(root);changed=unchanged=0
  for f in walk(root):
   rel=str(f.relative_to(root));t=f.read_text(errors='ignore');h=hashlib.sha256(t.encode()).hexdigest();r=c.execute('SELECT hash FROM files WHERE path=?',(rel,)).fetchone()
   if r and r[0]==h and not force:unchanged+=1;continue
   c.execute('DELETE FROM files WHERE path=?',(rel,));c.execute('DELETE FROM symbols WHERE path=?',(rel,));c.execute('DELETE FROM search WHERE path=?',(rel,));sm=(rel+': '+ ' '.join(x.strip() for x in t.splitlines() if x.strip())[:1100]);c.execute('INSERT INTO files VALUES(?,?,?,?,?)',(rel,h,sm,t,time.time()));c.execute('INSERT INTO search(path,content,summary) VALUES(?,?,?)',(rel,t,sm));c.executemany('INSERT INTO symbols VALUES(?,?,?,?,?)',[(a,b,rel,d,e) for a,b,d,e in sym(t,rel)]);changed+=1
  c.commit();out={'root':str(root),'indexed':changed,'unchanged':unchanged,'files':c.execute('SELECT count(*) FROM files').fetchone()[0],'symbols':c.execute('SELECT count(*) FROM symbols').fetchone()[0]};c.close();return out
 @mcp.tool()
 def update_codebase_memory(path:str='.')->dict[str,Any]:return index_codebase(path,False)
 @mcp.tool()
 def search_codebase_memory(query:str,path:str='.',limit:int=8,context_budget:int=12000)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory');c=db(root)
  try:rows=c.execute('SELECT path,summary,content FROM search WHERE search MATCH ? LIMIT ?',(query,max(1,min(limit,50)))).fetchall()
  except sqlite3.OperationalError:
   q='%'+query+'%';rows=c.execute('SELECT path,summary,content FROM files WHERE content LIKE ? OR summary LIKE ? LIMIT ?',(q,q,max(1,min(limit,50)))).fetchall()
  out=[];used=0
  for p,s,t in rows:
   if used>=context_budget:break
   chunk=t[:context_budget-used];out.append({'path':p,'summary':s,'content':chunk});used+=len(chunk)
  c.close();return {'query':query,'results':out,'context_used':used,'context_budget':context_budget}
 @mcp.tool()
 def get_file_summary(file_path:str,path:str='.')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory');c=db(root);r=c.execute('SELECT summary FROM files WHERE path=?',(file_path,)).fetchone();c.close();return {'path':file_path,'summary':r[0] if r else None,'indexed':bool(r)}
 @mcp.tool()
 def get_symbol_context(symbol:str,path:str='.',limit:int=10)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory');c=db(root);rows=c.execute('SELECT name,kind,path,line,signature FROM symbols WHERE name=? LIMIT ?',(symbol,limit)).fetchall();c.close();return {'symbol':symbol,'matches':[dict(zip(['name','kind','path','line','signature'],r)) for r in rows]}
 @mcp.tool()
 def codebase_memory_status(path:str='.')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory');c=db(root);o={'database':str(root/'.dana'/'codebase_memory.db'),'files':c.execute('SELECT count(*) FROM files').fetchone()[0],'symbols':c.execute('SELECT count(*) FROM symbols').fetchone()[0]};c.close();return o
 @mcp.tool()
 def clear_codebase_memory(path:str='.')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory');p=root/'.dana'/'codebase_memory.db';
  if p.exists():p.unlink()
  return {'cleared':str(p)}
