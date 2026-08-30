from __future__ import annotations
import ast, difflib, hashlib, sqlite3, time
from collections import defaultdict
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP
from dana.security.path_policy import require_path

IGNORE={'.git','.venv','venv','node_modules','__pycache__','.dana'}
EXT={'.py','.js','.ts','.tsx','.jsx','.php','.go','.rs','.java','.md','.txt','.json','.yaml','.yml'}

def _db(root:Path):
 p=root/'.dana'/'codebase_memory.db'; p.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(p)
 c.executescript("""
 CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY,hash TEXT,summary TEXT,content TEXT,updated REAL);
 CREATE TABLE IF NOT EXISTS symbols(name TEXT,kind TEXT,path TEXT,line INTEGER,signature TEXT);
 CREATE TABLE IF NOT EXISTS imports(source TEXT,target TEXT);
 CREATE TABLE IF NOT EXISTS context_cache(id TEXT PRIMARY KEY,hash TEXT,content TEXT,created REAL);
 CREATE INDEX IF NOT EXISTS idx_symbols ON symbols(name); CREATE INDEX IF NOT EXISTS idx_imports_source ON imports(source);
 CREATE VIRTUAL TABLE IF NOT EXISTS search USING fts5(path UNINDEXED,content,summary);
 """); return c

def _walk(root):
 for p in root.rglob('*'):
  if any(x in IGNORE for x in p.parts) or not p.is_file() or p.suffix.lower() not in EXT: continue
  try:
   if p.stat().st_size<=1_000_000: yield p
  except OSError: pass

def _analyze(text:str,rel:str):
 symbols=[]; imports=[]; summary=[]
 if rel.endswith('.py'):
  try:
   tree=ast.parse(text)
   for n in ast.walk(tree):
    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
     kind='class' if isinstance(n,ast.ClassDef) else 'function'; sig=f'{n.name}({", ".join(a.arg for a in getattr(n,"args",ast.arguments()).args)})' if hasattr(n,'args') else n.name
     symbols.append((n.name,kind,n.lineno,sig)); summary.append(f'{kind} {sig} at line {n.lineno}')
    elif isinstance(n,ast.Import): imports += [a.name for a in n.names]
    elif isinstance(n,ast.ImportFrom): imports += [n.module or '']
  except SyntaxError: summary.append('Python syntax currently invalid; indexed as text')
 if not summary: summary=[x.strip() for x in text.splitlines() if x.strip()][:20]
 return symbols,imports,' | '.join(summary)[:4000]

def _cid(content:str)->str: return 'ctx_'+hashlib.sha256(content.encode()).hexdigest()[:20]

def _dedupe(items:list[dict]):
 seen={}; out=[]
 for x in items:
  key=hashlib.sha256(x['content'].encode()).hexdigest()
  if key in seen: seen[key].setdefault('references',[]).append(x['path']); continue
  y=dict(x); y['references']=[x['path']]; seen[key]=y; out.append(y)
 return out

def register_codebase_memory_tools(mcp:FastMCP)->None:
 @mcp.tool()
 def index_codebase(path:str='.',force:bool=False)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); changed=unchanged=0; seen=set()
  for f in _walk(root):
   rel=str(f.relative_to(root)); seen.add(rel)
   try:t=f.read_text(errors='ignore')
   except OSError: continue
   h=hashlib.sha256(t.encode()).hexdigest(); old=c.execute('SELECT hash FROM files WHERE path=?',(rel,)).fetchone()
   if old and old[0]==h and not force: unchanged+=1; continue
   syms,imports,summary=_analyze(t,rel)
   for table in ('files','symbols','imports','search'): c.execute(f'DELETE FROM {table} WHERE path=?' if table in ('files','symbols') else ('DELETE FROM imports WHERE source=?' if table=='imports' else 'DELETE FROM search WHERE path=?'),(rel,))
   c.execute('INSERT INTO files VALUES(?,?,?,?,?)',(rel,h,summary,t,time.time())); c.execute('INSERT INTO search(path,content,summary) VALUES(?,?,?)',(rel,t,summary))
   c.executemany('INSERT INTO symbols VALUES(?,?,?,?,?)',[(a,b,rel,d,e) for a,b,d,e in syms]); c.executemany('INSERT INTO imports VALUES(?,?)',[(rel,x) for x in imports]); changed+=1
  for (rel,) in c.execute('SELECT path FROM files').fetchall():
   if rel not in seen:
    c.execute('DELETE FROM files WHERE path=?',(rel,)); c.execute('DELETE FROM symbols WHERE path=?',(rel,)); c.execute('DELETE FROM imports WHERE source=?',(rel,)); c.execute('DELETE FROM search WHERE path=?',(rel,))
  c.commit(); out={'root':str(root),'indexed':changed,'unchanged':unchanged,'files':c.execute('SELECT count(*) FROM files').fetchone()[0],'symbols':c.execute('SELECT count(*) FROM symbols').fetchone()[0]}; c.close(); return out

 @mcp.tool()
 def update_codebase_memory(path:str='.')->dict[str,Any]: return index_codebase(path,False)

 @mcp.tool()
 def search_codebase_memory(query:str,path:str='.',limit:int=8,context_budget:int|None=None)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); n=max(1,min(limit,100))
  try: rows=c.execute('SELECT path,summary,content FROM search WHERE search MATCH ? LIMIT ?',(query,n)).fetchall()
  except sqlite3.OperationalError:
   q='%'+query+'%'; rows=c.execute('SELECT path,summary,content FROM files WHERE content LIKE ? OR summary LIKE ? LIMIT ?',(q,q,n)).fetchall()
  results=_dedupe([{'path':p,'summary':s,'content':t} for p,s,t in rows])
  # Compatibility only: budget is optional and never used as a default limit.
  if context_budget and context_budget>0:
   used=0; clipped=[]
   for r in results:
    if used>=context_budget: break
    x=dict(r); x['content']=x['content'][:context_budget-used]; used+=len(x['content']); clipped.append(x)
   results=clipped
  content='\n\n'.join(f"# {r['path']}\n{r['content']}" for r in results); cid=_cid(content)
  c.execute('INSERT OR REPLACE INTO context_cache VALUES(?,?,?,?)',(cid,hashlib.sha256(content.encode()).hexdigest(),content,time.time())); c.commit(); c.close()
  return {'query':query,'results':results,'context_id':cid,'complete':True,'limited':bool(context_budget)}

 @mcp.tool()
 def get_context(context_id:str,path:str='.')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); r=c.execute('SELECT content,hash,created FROM context_cache WHERE id=?',(context_id,)).fetchone(); c.close(); return {'context_id':context_id,'found':bool(r),'content':r[0] if r else None,'hash':r[1] if r else None,'created':r[2] if r else None}

 @mcp.tool()
 def get_context_delta(context_id:str,path:str='.',new_content:str='')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); r=c.execute('SELECT content FROM context_cache WHERE id=?',(context_id,)).fetchone(); c.close()
  if not r:return {'found':False,'context_id':context_id}
  diff=''.join(difflib.unified_diff(r[0].splitlines(True),new_content.splitlines(True),fromfile=context_id,tofile='new'))
  return {'found':True,'context_id':context_id,'changed':bool(diff),'delta':diff}

 @mcp.tool()
 def get_file_delta(file_path:str,path:str='.',previous_content:str='')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); f=require_path(root/file_path,purpose='file delta'); current=f.read_text(errors='ignore'); diff=''.join(difflib.unified_diff(previous_content.splitlines(True),current.splitlines(True),fromfile='previous',tofile=file_path)); return {'path':file_path,'changed':bool(diff),'delta':diff,'hash':hashlib.sha256(current.encode()).hexdigest()}

 @mcp.tool()
 def get_file_summary(file_path:str,path:str='.')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); r=c.execute('SELECT summary,hash FROM files WHERE path=?',(file_path,)).fetchone(); c.close(); return {'path':file_path,'summary':r[0] if r else None,'hash':r[1] if r else None,'indexed':bool(r)}

 @mcp.tool()
 def get_symbol_context(symbol:str,path:str='.',limit:int=10,include_source:bool=False)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); rows=c.execute('SELECT name,kind,path,line,signature FROM symbols WHERE name=? LIMIT ?',(symbol,max(1,min(limit,100)))).fetchall(); out=[]
  for r in rows:
   item=dict(zip(['name','kind','path','line','signature'],r))
   if include_source:
    text=c.execute('SELECT content FROM files WHERE path=?',(r[2],)).fetchone(); lines=(text[0].splitlines() if text else []); start=max(0,r[3]-1); item['source']='\n'.join(lines[start:start+120])
   out.append(item)
  c.close(); return {'symbol':symbol,'matches':out}

 @mcp.tool()
 def get_dependency_context(file_path:str,path:str='.',depth:int=1)->dict[str,Any]:
  root=require_path(path,purpose='dependency context'); c=_db(root); frontier={file_path}; seen=set(); graph=defaultdict(list)
  for _ in range(max(1,min(depth,10))):
   nxt=set()
   for src in frontier:
    if src in seen: continue
    seen.add(src); deps=[x[0] for x in c.execute('SELECT target FROM imports WHERE source=?',(src,)).fetchall()]; graph[src]=deps
    for d in deps:
     candidates=[x[0] for x in c.execute('SELECT path FROM files WHERE path LIKE ? LIMIT 5',('%'+d.replace('.','/')+'%',)).fetchall()]; nxt.update(candidates)
   frontier=nxt
  c.close(); return {'file':file_path,'depth':depth,'graph':dict(graph),'related_files':sorted(seen)}

 @mcp.tool()
 def get_project_map(path:str='.',include_symbols:bool=True)->dict[str,Any]:
  root=require_path(path,purpose='project map'); c=_db(root); files=[dict(zip(['path','summary','hash'],r)) for r in c.execute('SELECT path,summary,hash FROM files ORDER BY path').fetchall()]; out={'files':files}
  if include_symbols: out['symbols']=[dict(zip(['name','kind','path','line','signature'],r)) for r in c.execute('SELECT name,kind,path,line,signature FROM symbols ORDER BY path,line').fetchall()]
  c.close(); return out

 @mcp.tool()
 def context_compress(contexts:list[str],structural:bool=True)->dict[str,Any]:
  unique=[]; seen=set()
  for x in contexts:
   h=hashlib.sha256(x.encode()).hexdigest()
   if h not in seen: seen.add(h); unique.append(x)
  if structural:
   # Lossless-ish optimization: preserve text while removing only repeated blank lines.
   unique=['\n'.join(line for i,line in enumerate(x.splitlines()) if line.strip() or (i and x.splitlines()[i-1].strip())) for x in unique]
  content='\n\n'.join(unique); return {'content':content,'items_before':len(contexts),'items_after':len(unique),'deduplicated':len(contexts)-len(unique),'context_id':_cid(content)}

 @mcp.tool()
 def codebase_memory_status(path:str='.')->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); c=_db(root); o={'database':str(root/'.dana'/'codebase_memory.db'),'files':c.execute('SELECT count(*) FROM files').fetchone()[0],'symbols':c.execute('SELECT count(*) FROM symbols').fetchone()[0],'cached_contexts':c.execute('SELECT count(*) FROM context_cache').fetchone()[0],'token_limit':None}; c.close(); return o

 @mcp.tool()
 def clear_codebase_memory(path:str='.',clear_context_cache:bool=True)->dict[str,Any]:
  root=require_path(path,purpose='codebase memory'); p=root/'.dana'/'codebase_memory.db'
  if p.exists(): p.unlink()
  return {'cleared':str(p),'context_cache_cleared':clear_context_cache}
