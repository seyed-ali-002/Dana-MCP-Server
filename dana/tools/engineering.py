from __future__ import annotations

import ast
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

IGNORE={".git",".venv","venv","node_modules","__pycache__",".mypy_cache",".ruff_cache"}
MODES={"normal","minimal","strict","ultra"}

def _root(path:str)->Path:
    p=Path(path).expanduser().resolve()
    if not p.exists(): raise ValueError(f"Path not found: {p}")
    return p

def _files(root:Path):
    for p in root.rglob("*"):
        if p.is_file() and not any(x in IGNORE for x in p.parts):
            yield p

def _text(p:Path)->str:
    try:return p.read_text(encoding="utf-8",errors="ignore")
    except OSError:return ""

def _mode()->str:
    return os.getenv("DANA_ENGINEERING_MODE","minimal").strip().lower()

def _set_mode(mode:str)->None:
    if mode not in MODES: raise ValueError(f"mode must be one of {sorted(MODES)}")
    os.environ["DANA_ENGINEERING_MODE"]=mode

def _manifest(root:Path)->dict[str,list[str]]:
    found=defaultdict(list)
    for name in ("pyproject.toml","requirements.txt","package.json","composer.json","go.mod","Cargo.toml"):
        for p in root.rglob(name):
            if not any(x in IGNORE for x in p.parts): found[name].append(str(p.relative_to(root)))
    return dict(found)

def _reuse(root:Path, query:str, limit:int=30)->list[dict[str,Any]]:
    terms=[x.lower() for x in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}",query)][:12]
    out=[]
    for p in _files(root):
        if p.suffix not in {".py",".js",".ts",".tsx",".jsx",".go",".rs",".java",".php",".rb"}: continue
        for i,line in enumerate(_text(p).splitlines(),1):
            score=sum(t in line.lower() for t in terms)
            if score:
                out.append({"path":str(p.relative_to(root)),"line":i,"text":line.strip()[:300],"score":score})
    return sorted(out,key=lambda x:-x["score"])[:limit]

def _python_inventory(root:Path)->dict[str,Any]:
    imports=Counter(); defs=[]
    for p in _files(root):
        if p.suffix!=".py": continue
        try: tree=ast.parse(_text(p))
        except SyntaxError: continue
        for node in ast.walk(tree):
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                names=[a.name.split(".")[0] for a in node.names] if isinstance(node,ast.Import) else [node.module.split(".")[0]] if node.module else []
                imports.update(names)
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                defs.append({"name":node.name,"kind":type(node).__name__.replace("Async","").replace("Def",""),"path":str(p.relative_to(root)),"line":node.lineno})
    return {"imports":dict(imports),"definitions":defs}

def _duplicates(root:Path)->list[dict[str,Any]]:
    groups=defaultdict(list)
    for p in _files(root):
        if p.suffix not in {".py",".js",".ts"}: continue
        for i,line in enumerate(_text(p).splitlines(),1):
            key=re.sub(r"\s+"," ",line.strip())
            if len(key)>=40 and not key.startswith("#"): groups[key].append((p,i))
    return [{"text":k[:220],"locations":[{"path":str(p.relative_to(root)),"line":i} for p,i in v]} for k,v in groups.items() if len(v)>1][:100]

def register_engineering_tools(mcp:FastMCP)->None:
    @mcp.tool()
    def dana_engineering_policy(mode:str|None=None)->dict[str,Any]:
        """Get or set Dana's Ponytail-inspired engineering policy: normal, minimal, strict, ultra."""
        if mode is not None: _set_mode(mode.lower())
        current=_mode()
        return {"mode":current,"pipeline":["need_check","existing_code_check","reuse_check","stdlib_native_check","dependency_check","minimum_change","test_after_change"],"rules":{"security":"never removed for brevity","validation":"never removed for brevity","error_handling":"preserve or improve","default":"prefer existing code and smallest safe change"}}

    @mcp.tool()
    def analyze_implementation_need(path:str=".", request:str="")->dict[str,Any]:
        """Run the pre-implementation checklist before adding code or dependencies."""
        root=_root(path); inventory=_python_inventory(root)
        reuse=_reuse(root,request)
        keywords=set(re.findall(r"[A-Za-z_][A-Za-z0-9_]+",request.lower()))
        stdlib={"json","pathlib","sqlite3","subprocess","asyncio","http","urllib","logging","argparse","dataclasses","typing","re","csv","html","statistics"}
        hints=sorted(stdlib & keywords)
        recommendation="reuse existing implementation" if reuse else ("use standard library/native feature" if hints else "minimal new implementation")
        return {"mode":_mode(),"request":request,"recommendation":recommendation,"existing_matches":reuse[:15],"manifests":_manifest(root),"python_definitions":inventory["definitions"][:100],"stdlib_candidates":hints,"new_dependency_recommended":False,"next_steps":["inspect existing matches","reuse when behavior is compatible","only then implement the smallest safe change"]}

    @mcp.tool()
    def review_implementation(path:str=".", target:str|None=None)->dict[str,Any]:
        """Review a codebase or file for duplication, dead-looking code, unnecessary complexity and dependencies."""
        root=_root(path)
        scan=[root] if root.is_file() else list(_files(root))
        py=[p for p in scan if p.suffix==".py"]
        complexity=[]; unused=[]
        for p in py:
            text=_text(p)
            try: tree=ast.parse(text)
            except SyntaxError as e:
                complexity.append({"path":str(p),"issue":"syntax_error","detail":str(e)});continue
            imports={a.asname or a.name.split(".")[0] for n in tree.body if isinstance(n,(ast.Import,ast.ImportFrom)) for a in n.names}
            names={n.id for n in ast.walk(tree) if isinstance(n,ast.Name)}
            unused.extend({"path":str(p),"issue":"possibly_unused_import","name":x} for x in sorted(imports-names))
            for n in ast.walk(tree):
                if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    branches=sum(isinstance(x,(ast.If,ast.For,ast.While,ast.Try,ast.BoolOp)) for x in ast.walk(n))
                    if branches>12 or len(n.body)>40: complexity.append({"path":str(p),"issue":"high_complexity","function":n.name,"branches":branches,"body_statements":len(n.body)})
        result={"target":target,"mode":_mode(),"duplicate_code":_duplicates(root if root.is_dir() else root.parent),"complexity":complexity[:100],"possible_unused_imports":unused[:100],"manifests":_manifest(root if root.is_dir() else root.parent)}
        result["recommendations"]=["remove duplication by reusing existing helpers","prefer native/stdlib before adding packages","flatten unnecessary abstractions","keep security and validation explicit","run tests after every simplification"]
        return result

    @mcp.tool()
    def simplify_code(path:str, apply:bool=False)->dict[str,Any]:
        """Find safe simplifications. With apply=true, only whitespace/trailing-line cleanup is changed; semantic refactors remain review recommendations."""
        target=_root(path); files=[target] if target.is_file() else [p for p in _files(target) if p.suffix in {".py",".js",".ts",".json",".md"}]
        changes=[]; changed=0
        for p in files:
            original=_text(p); cleaned="\n".join(line.rstrip() for line in original.splitlines())
            if original.endswith("\n"): cleaned+="\n"
            if cleaned!=original:
                changes.append({"path":str(p),"type":"remove_trailing_whitespace","safe":True})
                if apply: p.write_text(cleaned,encoding="utf-8");changed+=1
        return {"mode":_mode(),"applied":apply,"files_changed":changed,"safe_changes":changes[:100],"semantic_simplification":["remove duplication by reusing existing helpers","prefer native/stdlib before adding packages","flatten unnecessary abstractions","keep security and validation explicit","run tests after every simplification"],"duplicate_candidates":len(_duplicates(target.parent if target.is_file() else target)),"note":"Semantic code changes are intentionally review-first to avoid silently removing validation, security, or behavior."}
