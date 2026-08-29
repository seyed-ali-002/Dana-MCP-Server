from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
from mcp.server.fastmcp import FastMCP

def register_agent_planning_tools(mcp:FastMCP)->None:
 @mcp.tool()
 def create_task_plan(goal:str, steps:list[str]) -> dict[str,Any]:
    """Create a persistent step-by-step task plan in the workspace."""
    plan={'goal':goal,'created_at':time.time(),'steps':[{'id':i+1,'description':s,'status':'pending'} for i,s in enumerate(steps)]}
    return plan
 @mcp.tool()
 def task_status(plan:dict[str,Any]) -> dict[str,Any]:
    steps=plan.get('steps',[]); done=sum(x.get('status')=='done' for x in steps)
    return {'total':len(steps),'done':done,'pending':len(steps)-done,'complete':done==len(steps)}
 @mcp.tool()
 def change_summary(path:str='.') -> dict[str,Any]:
    import subprocess
    p=Path(path).expanduser().resolve(); r=subprocess.run(['git','status','--short'],cwd=p,text=True,capture_output=True)
    return {'returncode':r.returncode,'changes':r.stdout.splitlines(),'error':r.stderr}
 @mcp.tool()
 def workspace_snapshot(path:str='.') -> dict[str,Any]:
    import subprocess
    p=Path(path).expanduser().resolve(); r=subprocess.run(['git','rev-parse','HEAD'],cwd=p,text=True,capture_output=True)
    return {'path':str(p),'git_head':r.stdout.strip() if r.returncode==0 else None,'error':r.stderr}
 @mcp.tool()
 def rollback_changes(path:str='.', hard:bool=False) -> dict[str,Any]:
    """Discard uncommitted Git changes. hard=true also removes untracked files (dangerous)."""
    import subprocess
    p=Path(path).expanduser().resolve(); cmds=[['git','restore','.']]
    if hard: cmds.append(['git','clean','-fd'])
    results=[]
    for c in cmds:
      r=subprocess.run(c,cwd=p,text=True,capture_output=True);results.append({'command':c,'returncode':r.returncode,'stderr':r.stderr})
    return {'results':results,'ok':all(x['returncode']==0 for x in results)}
