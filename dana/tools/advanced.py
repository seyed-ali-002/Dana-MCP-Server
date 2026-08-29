from __future__ import annotations
import ast, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP

IGNORE={'.git','.venv','venv','node_modules','__pycache__','.mypy_cache','.ruff_cache'}
def files(root: Path, suffixes: set[str]|None=None):
    for p in root.rglob('*'):
        if any(x in IGNORE for x in p.parts) or not p.is_file(): continue
        if suffixes is None or p.suffix in suffixes: yield p
def run(cmd:list[str], cwd:str|None=None, timeout:int=120):
    try:
        p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
        return {'returncode':p.returncode,'stdout':p.stdout[-30000:],'stderr':p.stderr[-30000:],'command':cmd}
    except Exception as e:return {'returncode':-1,'stdout':'','stderr':str(e),'command':cmd}
def safe_rel(p,root):
    try:return str(p.relative_to(root))
    except:return str(p)

def register_advanced_tools(mcp: FastMCP)->None:
 @mcp.tool()
 def browser_open(url:str, screenshot_path:str|None=None) -> dict[str,Any]:
    """Open a public URL with Playwright and optionally save a screenshot."""
    try:
      from playwright.sync_api import sync_playwright
    except ImportError:
      return {"skipped":True,"reason":"Install Dana browser extras: pip install -e .[browser] and playwright install chromium"}
    with sync_playwright() as pw:
      b=pw.chromium.launch(headless=True); page=b.new_page(); page.goto(url,wait_until='domcontentloaded',timeout=30000)
      title=page.title(); text=page.locator('body').inner_text()[:10000]
      if screenshot_path: page.screenshot(path=str(Path(screenshot_path).expanduser().resolve()),full_page=True)
      b.close()
    return {"url":url,"title":title,"text":text,"screenshot":screenshot_path}
 @mcp.tool()
 def database_schema(database:str) -> dict[str,Any]:
    """Inspect SQLite database tables and columns."""
    import sqlite3
    db=Path(database).expanduser().resolve(); con=sqlite3.connect(db)
    tables=[x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    schema={t:[{'name':r[1],'type':r[2],'notnull':bool(r[3]),'pk':bool(r[5])} for r in con.execute(f'PRAGMA table_info("{t}")')] for t in tables}; con.close()
    return {"database":str(db),"tables":schema}
 @mcp.tool()
 def database_health_check(database:str) -> dict[str,Any]:
    import sqlite3
    db=Path(database).expanduser().resolve(); con=sqlite3.connect(db); rows=list(con.execute('PRAGMA integrity_check')); con.close()
    return {"database":str(db),"integrity":rows,"ok":all(r[0]=='ok' for r in rows)}
 @mcp.tool()
 def docker_status() -> dict[str,Any]:
    if not shutil.which('docker'): return {"available":False,"reason":"docker not installed"}
    return {"available":True,"result":run(['docker','ps','--format','{{json .}}'])}
 @mcp.tool()
 def container_logs(container:str, tail:int=200) -> dict[str,Any]:
    if not shutil.which('docker'): return {"available":False,"reason":"docker not installed"}
    return run(['docker','logs','--tail',str(max(1,min(tail,5000))),container])
 @mcp.tool()
 def docker_build(path:str='.', tag:str='dana-build:latest') -> dict[str,Any]:
    if not shutil.which('docker'): return {"available":False,"reason":"docker not installed"}
    return run(['docker','build','-t',tag,str(Path(path).expanduser().resolve())],timeout=300)
 @mcp.tool()
 def analyze_project(path:str='.') -> dict[str,Any]:
    """Analyze project structure, languages, manifests and likely framework."""
    root=Path(path).expanduser().resolve(); counts={}; manifests=[]
    for p in files(root):
      counts[p.suffix or '[no extension]']=counts.get(p.suffix or '[no extension]',0)+1
      if p.name in {'pyproject.toml','package.json','requirements.txt','Dockerfile','docker-compose.yml','composer.json','Cargo.toml','go.mod'}: manifests.append(safe_rel(p,root))
    hints=[]
    names={p.name for p in root.iterdir()} if root.exists() else set()
    if 'pyproject.toml' in names: hints.append('Python project')
    if 'package.json' in names: hints.append('Node.js project')
    if 'Dockerfile' in names: hints.append('Dockerized')
    return {'root':str(root),'file_types':counts,'manifests':manifests,'hints':hints}
 @mcp.tool()
 def find_entry_points(path:str='.') -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); out=[]
    for p in files(root,{'.py','.js','.ts','.sh'}):
      try:t=p.read_text(errors='ignore')
      except:continue
      if '__main__' in t or 'FastAPI(' in t or 'if __name__' in t or p.name in {'main.py','app.py','index.js','server.js'}: out.append(safe_rel(p,root))
    return {'entry_points':out}
 @mcp.tool()
 def project_health_check(path:str='.') -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); analysis=analyze_project(str(root)); issues=[]
    if not (root/'.git').exists(): issues.append('Git repository not detected')
    if not (root/'README.md').exists(): issues.append('README.md missing')
    if not any(p.name in {'pyproject.toml','package.json','requirements.txt','composer.json'} for p in root.iterdir()): issues.append('Dependency manifest not detected')
    return {'ok':not issues,'issues':issues,'analysis':analysis}
 @mcp.tool()
 def find_duplicate_code(path:str='.', min_lines:int=6) -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); seen={}; dup=[]
    for p in files(root,{'.py','.js','.ts','.php'}):
      lines=p.read_text(errors='ignore').splitlines()
      for i in range(max(0,len(lines)-min_lines+1)):
       block='\n'.join(x.strip() for x in lines[i:i+min_lines] if x.strip())
       if len(block)<40: continue
       if block in seen: dup.append({'first':seen[block],'duplicate':safe_rel(p,root)+f':{i+1}'})
       else: seen[block]=safe_rel(p,root)+f':{i+1}'
    return {'duplicates':dup[:200],'count':len(dup)}
 @mcp.tool()
 def analyze_stacktrace(text:str) -> dict[str,Any]:
    lines=text.splitlines(); frames=[x.strip() for x in lines if 'File ' in x or re.search(r'\bat\s+',x)]
    errors=[x.strip() for x in lines if re.search(r'(Error|Exception|Traceback|FAILED)',x)]
    return {'frames':frames,'errors':errors[-10:],'raw_tail':lines[-30:]}
 @mcp.tool()
 def tail_logs(path:str, lines:int=100) -> dict[str,Any]:
    p=Path(path).expanduser().resolve(); data=p.read_text(errors='ignore').splitlines()[-max(1,min(lines,5000)):]
    return {'path':str(p),'lines':data}
 @mcp.tool()
 def search_logs(path:str, pattern:str, limit:int=200) -> dict[str,Any]:
    rx=re.compile(pattern,re.I); p=Path(path).expanduser().resolve(); matches=[{'line':i+1,'text':x} for i,x in enumerate(p.read_text(errors='ignore').splitlines()) if rx.search(x)]
    return {'matches':matches[:limit],'count':len(matches)}
 @mcp.tool()
 def secret_scan(path:str='.') -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); patterns={'aws_key':r'AKIA[0-9A-Z]{16}','private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','generic_secret':r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[^\s"\']{8,}'}; hits=[]
    for p in files(root):
      if p.stat().st_size>2_000_000: continue
      try:t=p.read_text(errors='ignore')
      except:continue
      for name,pat in patterns.items():
       for m in re.finditer(pat,t): hits.append({'file':safe_rel(p,root),'type':name,'line':t.count('\n',0,m.start())+1})
    return {'hits':hits[:500],'count':len(hits)}
 @mcp.tool()
 def dependency_security_scan(path:str='.') -> dict[str,Any]:
    """Audit Python and Node.js dependencies when the corresponding audit tool is available."""
    root=Path(path).expanduser().resolve(); results={}
    if (root/'package.json').exists() and shutil.which('npm'):
      results['npm']=run(['npm','audit','--json'],str(root))
    if (root/'pyproject.toml').exists() or (root/'requirements.txt').exists():
      audit=shutil.which('pip-audit')
      if audit: results['python']=run([audit],str(root))
      else: results['python']={'skipped':True,'reason':'pip-audit not installed; install Dana security extra'}
    if not results:return {'skipped':True,'reason':'No supported dependency manifest detected'}
    return {'results':results}
 @mcp.tool()
 def dependency_outdated(path:str='.') -> dict[str,Any]:
    root=Path(path).expanduser().resolve()
    if (root/'package.json').exists() and shutil.which('npm'): return run(['npm','outdated','--json'],str(root))
    if (root/'pyproject.toml').exists(): return run([sys.executable,'-m','pip','list','--outdated','--format=json'],str(root))
    return {'skipped':True,'reason':'No supported dependency manifest detected'}
 @mcp.tool()
 def system_metrics() -> dict[str,Any]:
    import shutil as sh
    total,used,free=sh.disk_usage('/')
    return {'cpu_count':os.cpu_count(),'disk':{'total':total,'used':used,'free':free}}
 @mcp.tool()
 def port_check(host:str='127.0.0.1', port:int=80) -> dict[str,Any]:
    import socket
    s=socket.socket(); s.settimeout(3)
    try:s.connect((host,port)); ok=True; err=''
    except Exception as e:ok=False;err=str(e)
    finally:s.close()
    return {'host':host,'port':port,'open':ok,'error':err}
 @mcp.tool()
 def find_symbol(path:str, symbol:str) -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); found=[]; rx=re.compile(r'\b(?:def|class|function|const|let|var)\s+'+re.escape(symbol)+r'\b')
    for p in files(root,{'.py','.js','.ts','.tsx','.jsx'}):
      for i,l in enumerate(p.read_text(errors='ignore').splitlines(),1):
       if rx.search(l): found.append({'file':safe_rel(p,root),'line':i,'text':l.strip()})
    return {'matches':found}
 @mcp.tool()
 def find_references(path:str, symbol:str, limit:int=500) -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); rx=re.compile(r'\b'+re.escape(symbol)+r'\b'); out=[]
    for p in files(root,{'.py','.js','.ts','.tsx','.jsx'}):
      for i,l in enumerate(p.read_text(errors='ignore').splitlines(),1):
       if rx.search(l): out.append({'file':safe_rel(p,root),'line':i,'text':l.strip()})
    return {'references':out[:limit],'count':len(out)}
 @mcp.tool()
 def code_complexity(path:str='.') -> dict[str,Any]:
    root=Path(path).expanduser().resolve(); out=[]
    for p in files(root,{'.py'}):
      try:tree=ast.parse(p.read_text(errors='ignore'))
      except:continue
      for n in ast.walk(tree):
       if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
        complexity=1+sum(isinstance(x,(ast.If,ast.For,ast.While,ast.Try,ast.BoolOp,ast.Match)) for x in ast.walk(n))
        out.append({'file':safe_rel(p,root),'function':n.name,'line':n.lineno,'complexity':complexity})
    return {'functions':sorted(out,key=lambda x:x['complexity'],reverse=True)}
