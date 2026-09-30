from __future__ import annotations
import json, os, platform, shutil, socket, sqlite3, subprocess, time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
import logging
from mcp.server.fastmcp import FastMCP
from dana.config import settings
from dana.security.path_policy import require_path

_BROWSER = None
_PAGE = None
_YDOTOOLD = None
_YDOTOOL_VARIANT = None
_DESKTOP_LOG = logging.getLogger("dana.desktop")

def _run(cmd:list[str], timeout:int=30, dangerous:bool=False, cwd:str|None=None, input_text:str|None=None)->dict[str,Any]:
    if dangerous and not settings.allow_dangerous_tools: raise PermissionError("Dangerous operations require DANA_ALLOW_DANGEROUS_TOOLS.")
    try: p=subprocess.run(cmd,input=input_text,text=True,capture_output=True,cwd=cwd,timeout=max(1,min(timeout,300)),check=False)
    except FileNotFoundError as exc: raise RuntimeError(f"Command not found: {cmd[0]}") from exc
    except subprocess.TimeoutExpired as exc: raise TimeoutError(f"Command timed out after {timeout}s") from exc
    return {"command":cmd,"returncode":p.returncode,"stdout":p.stdout[-50000:],"stderr":p.stderr[-20000:],"ok":p.returncode==0}

def _path(value:str,purpose:str)->Path: return require_path(value,purpose=purpose)
def _store(name:str)->Path:
    root=Path.home()/".config"/"dana"; root.mkdir(parents=True,exist_ok=True); return root/name


def _desktop_backend() -> str:

    """Select a desktop-control backend from the active graphical session."""
    session = os.getenv("XDG_SESSION_TYPE", "").strip().lower()
    if session == "wayland" or os.getenv("WAYLAND_DISPLAY"):
        if shutil.which("ydotool"):
            _DESKTOP_LOG.info("Desktop backend selected: ydotool (Wayland)")
            return "ydotool"
        raise RuntimeError(
            "Wayland desktop control requires ydotool. Install Dana's native desktop dependencies "
            "or install the ydotool package; xdotool only controls the XWayland compatibility layer."
        )
    if shutil.which("xdotool"):
        _DESKTOP_LOG.info("Desktop backend selected: xdotool (X11)")
        return "xdotool"
    if shutil.which("ydotool"):
        _DESKTOP_LOG.info("Desktop backend selected: ydotool (non-X11 Linux session)")
        return "ydotool"
    raise RuntimeError("No supported desktop-control backend is installed (xdotool or ydotool).")


def _ydotool_variant() -> str:
    """Detect the pre-1.0 Ubuntu/Debian CLI versus the current 1.x CLI."""
    global _YDOTOOL_VARIANT
    if _YDOTOOL_VARIANT is not None:
        return _YDOTOOL_VARIANT
    if not shutil.which("ydotool"):
        raise RuntimeError("ydotool is not installed.")
    probe = subprocess.run(["ydotool", "help"], capture_output=True, text=True, timeout=5, check=False)
    help_text = (probe.stdout + "\\n" + probe.stderr).lower()
    if "recorder" in help_text and "debug" not in help_text:
        _YDOTOOL_VARIANT = "legacy"
    elif "debug" in help_text or "bakers" in help_text or "stdin" in help_text:
        _YDOTOOL_VARIANT = "modern"
    else:
        _YDOTOOL_VARIANT = "unknown"
    _DESKTOP_LOG.info("Detected ydotool CLI variant: %s", _YDOTOOL_VARIANT)
    return _YDOTOOL_VARIANT


def _ydotool_socket_available() -> bool:
    candidates=[
        Path(os.getenv("YDOTOOL_SOCKET","")) if os.getenv("YDOTOOL_SOCKET") else None,
        Path(os.getenv("XDG_RUNTIME_DIR",""))/".ydotool_socket" if os.getenv("XDG_RUNTIME_DIR") else None,
        Path(f"/run/dana-ydotool-{os.getuid()}/.ydotool_socket") if hasattr(os,"getuid") else None,
        Path("/tmp/.ydotool_socket"),
    ]
    for path in candidates:
        if not path or not path.exists():
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.settimeout(1)
                sock.connect(str(path))
            return True
        except OSError:
            continue
    return False



def _ydotool_socket_path() -> Path | None:
    configured = os.getenv("YDOTOOL_SOCKET", "").strip()
    candidates = [Path(configured)] if configured else []
    runtime = os.getenv("XDG_RUNTIME_DIR", "").strip()
    if runtime:
        candidates.append(Path(runtime) / ".ydotool_socket")
    candidates.append(Path("/run") / f"dana-ydotool-{os.getuid()}" / ".ydotool_socket")
    candidates.append(Path("/tmp/.ydotool_socket"))
    for path in candidates:
        if path.exists():
            if not configured:
                os.environ["YDOTOOL_SOCKET"] = str(path)
            return path
    return None


def _ydotool_uinput_error() -> str | None:
    """Return an actionable uinput permission/state error, if one exists."""
    device = Path("/dev/uinput")
    if not device.exists():
        return "Wayland input requires /dev/uinput, but the device does not exist. Load the kernel uinput module (modprobe uinput) and configure it to load at boot."
    if not os.access(device, os.W_OK):
        if not _ydotool_socket_available():
            return "Wayland input cannot write /dev/uinput and ydotoold is not reachable. Configure a uinput rule and start ydotoold as the desktop user (or install a supported ydotool package)."
    return None


def _desktop_diagnostics() -> dict[str,Any]:
    """Report the actual Linux desktop input backend readiness."""
    session=os.getenv("XDG_SESSION_TYPE","").strip().lower() or "unknown"
    wayland=bool(session=="wayland" or os.getenv("WAYLAND_DISPLAY"))
    uinput=Path("/dev/uinput")
    sockets=[
        str(p) for p in (
            Path(os.getenv("XDG_RUNTIME_DIR",""))/".ydotool_socket" if os.getenv("XDG_RUNTIME_DIR") else None,
            Path(f"/run/dana-ydotool-{os.getuid()}/.ydotool_socket") if hasattr(os,"getuid") else None,
            Path("/tmp/.ydotool_socket"),
        ) if p and p.exists()
    ]
    result={
        "ok":True,
        "os":platform.system(),
        "session":session,
        "wayland_display":os.getenv("WAYLAND_DISPLAY",""),
        "backend":None,
        "ydotool":shutil.which("ydotool"),
        "ydotoold":shutil.which("ydotoold"),
        "ydotool_socket":os.getenv("YDOTOOL_SOCKET") or (sockets[0] if sockets else ""),
        "uinput":{"exists":uinput.exists(),"writable":os.access(uinput,os.W_OK)},
        "sockets":sockets,
    }
    if wayland:
        result["backend"]="ydotool"
        if not result["ydotool"]:
            result["ok"]=False
            result["error"]="ydotool is not installed."
        else:
            try:
                result["ydotool_variant"]=_ydotool_variant()
            except Exception as exc:
                result["ok"]=False
                result["error"]=str(exc)
            uinput_error=_ydotool_uinput_error()
            if uinput_error:
                result["ok"]=False
                result["error"]=uinput_error
            if result.get("ydotool_variant") in {"legacy","modern"} and not result["sockets"]:
                result["ok"]=False
                result["error"]="ydotoold is not running or its socket is unavailable."
    else:
        result["backend"]="xdotool" if shutil.which("xdotool") else None
        if result["backend"] is None:
            result["ok"]=False
            result["error"]="xdotool is not installed for the active X11 session."
    return result


def _desktop_ydo(action:str,x:int=0,y:int=0,button:str="left",clicks:int=1,scroll:int=0,text:str="",key:str="")->dict[str,Any]:
    """Execute Wayland-safe input through ydotool/uinput with CLI-version compatibility."""
    global _YDOTOOLD
    variant = _ydotool_variant()
    uinput_error = _ydotool_uinput_error()
    if uinput_error:
        raise RuntimeError(uinput_error)

    socket_candidates=[Path(os.getenv("YDOTOOL_SOCKET","")) if os.getenv("YDOTOOL_SOCKET") else None, Path(os.getenv("XDG_RUNTIME_DIR",""))/".ydotool_socket" if os.getenv("XDG_RUNTIME_DIR") else None, Path("/run")/f"dana-ydotool-{os.getuid()}/.ydotool_socket", Path("/tmp/.ydotool_socket")]
    if not os.getenv("YDOTOOL_SOCKET"):
        for socket_path in socket_candidates:
            if socket_path and socket_path.exists():
                os.environ["YDOTOOL_SOCKET"]=str(socket_path)
                break
    if _YDOTOOLD is None and shutil.which("ydotoold") and not any(p and p.exists() for p in socket_candidates):
        try:
            _YDOTOOLD = subprocess.Popen(["ydotoold"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.35)
            if Path("/tmp/.ydotool_socket").exists() and not os.getenv("YDOTOOL_SOCKET"):
                os.environ["YDOTOOL_SOCKET"]="/tmp/.ydotool_socket"
        except OSError as exc:
            _DESKTOP_LOG.warning("Could not start ydotoold: %s", exc)

    def run_checked(command:list[str], timeout:int=5)->dict[str,Any]:
        result=_run(command,timeout)
        stderr=(result.get("stderr") or "").strip()
        stdout=(result.get("stdout") or "").strip()
        fatal_markers=("error", "failed", "fatal", "terminate", "aborted", "unrecognised option", "backend unavailable", "cannot")
        if result["returncode"] != 0 or any(marker in stderr.lower() for marker in fatal_markers):
            detail=stderr or stdout or f"exit code {result['returncode']}"
            result["ok"]=False
            result["error"]=detail
            return result
        return result

    if variant == "legacy":
        # Ubuntu/Debian 0.1.x uses the old CLI. It does not understand the
        # current --absolute/-x/-y/hex-button syntax.
        if action == "move":
            return run_checked(["ydotool","mousemove",str(max(0,x)),str(max(0,y))])
        if action == "move_relative":
            return run_checked(["ydotool","mousemove_relative","--",str(x),str(y)])
        if action == "click":
            buttons={"left":"1","middle":"2","right":"3"}
            if button not in buttons: raise ValueError("button must be left, middle or right")
            moved=run_checked(["ydotool","mousemove",str(max(0,x)),str(max(0,y))])
            if not moved["ok"]: return moved
            return run_checked(["ydotool","click","--repeat",str(max(1,min(clicks,20))),buttons[button]])
        if action == "scroll":
            if scroll == 0: raise ValueError("scroll must be non-zero")
            amount=max(1,min(abs(scroll),50))
            wheel="4" if scroll > 0 else "5"
            return run_checked(["ydotool","click","--repeat",str(amount),wheel])

        if action == "type": return run_checked(["ydotool","type",text],10)
        if action == "key": return run_checked(["ydotool","key",key])
        if action == "hotkey":
            parts=[p.strip() for p in key.replace("+"," ").split() if p.strip()]
            if len(parts)<2: raise ValueError("hotkey requires at least two keys, e.g. ctrl+c")
            return run_checked(["ydotool","key","+".join(parts)])
    else:
        if action == "move":
            return run_checked(["ydotool","mousemove","--absolute","-x",str(max(0,x)),"-y",str(max(0,y))])
        if action == "click":
            buttons={"left":"0xC0","right":"0xC1","middle":"0xC2"}
            if button not in buttons: raise ValueError("button must be left, middle or right")
            moved=run_checked(["ydotool","mousemove","--absolute","-x",str(max(0,x)),"-y",str(max(0,y))])
            if not moved["ok"]: return moved
            return run_checked(["ydotool","click","--repeat",str(max(1,min(clicks,20))),buttons[button]])
        if action == "type": return run_checked(["ydotool","type","--delay","1",text],10)
        if action == "key": return run_checked(["ydotool","key",key])
        if action == "hotkey":
            parts=[p.strip() for p in key.replace("+"," ").split() if p.strip()]
            if len(parts)<2: raise ValueError("hotkey requires at least two keys, e.g. ctrl+c")
            return run_checked(["ydotool","key","+".join(parts)])
        if action == "move_relative":
            return run_checked(["ydotool","mousemove","-x",str(x),"-y",str(y)])
        if action == "scroll":
            if scroll == 0: raise ValueError("scroll must be non-zero")
            amount=max(1,min(abs(scroll),50))
            direction=amount if scroll > 0 else -amount
            return run_checked(["ydotool","mousemove","--wheel","--","0",str(direction)])
    raise ValueError(f"Wayland backend does not support action: {action}")


def register_local_agent_tools(mcp:FastMCP)->None:
    @mcp.tool()
    def system_resources()->dict[str,Any]:
        """Return CPU, memory, disk and host runtime information."""
        out={"os":platform.system(),"release":platform.release(),"architecture":platform.machine(),"python":platform.python_version(),"hostname":socket.gethostname(),"cpu_count":os.cpu_count()}
        try:
            import psutil
            out.update({"cpu_percent":psutil.cpu_percent(interval=.1),"memory":dict(psutil.virtual_memory()._asdict()),"swap":dict(psutil.swap_memory()._asdict()),
                        "disks":[{"mountpoint":p.mountpoint,"usage":dict(psutil.disk_usage(p.mountpoint)._asdict())} for p in psutil.disk_partitions(all=False)]})
        except ImportError: out["psutil"]="not installed"
        return out

    @mcp.tool()
    def list_processes(limit:int=50)->list[dict[str,Any]]:
        """List running processes."""
        try: import psutil
        except ImportError as exc: raise RuntimeError("Install psutil for process inspection.") from exc
        rows=[]
        for p in psutil.process_iter(["pid","name","username","status","cpu_percent","memory_percent","cmdline"]):
            try: rows.append(p.info)
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
        rows.sort(key=lambda x:float(x.get("cpu_percent") or 0),reverse=True); return rows[:max(1,min(limit,500))]

    @mcp.tool()
    def service_control(action:str,service:str)->dict[str,Any]:
        """Inspect or control a Linux systemd service."""
        if platform.system()!="Linux": raise RuntimeError("systemd control currently requires Linux.")
        if not service or any(c in service for c in " ;|&$()<>"): raise ValueError("Invalid service name.")
        if action=="status": return _run(["systemctl","status","--no-pager",service],20)
        if action in {"start","stop","restart"}: return _run(["systemctl",action,service],30,True)
        raise ValueError("action must be status, start, stop or restart")

    @mcp.tool()
    def process_control(action:str,pid:int,signal:int=15)->dict[str,Any]:
        """Send a signal to a process. Termination is protected."""
        if action!="kill" or pid<=0 or signal not in {1,2,9,15}: raise ValueError("Invalid kill arguments.")
        if not settings.allow_dangerous_tools: raise PermissionError("Process termination is disabled.")
        os.kill(pid,signal); return {"ok":True,"pid":pid,"signal":signal}

    @mcp.tool()
    def clipboard(action:str,text:str="")->dict[str,Any]:
        """Read or write the desktop clipboard."""
        if action not in {"get","set"}: raise ValueError("action must be get or set")
        system=platform.system()
        if system=="Linux":
            wayland=bool(os.getenv("XDG_SESSION_TYPE","").strip().lower()=="wayland" or os.getenv("WAYLAND_DISPLAY"))
            if action=="get":
                if wayland and shutil.which("wl-paste"): cmd=["wl-paste","--no-newline"]
                elif shutil.which("xclip"): cmd=["xclip","-selection","clipboard","-o"]
                elif shutil.which("xsel"): cmd=["xsel","--clipboard","--output"]
                else: raise RuntimeError("No clipboard backend available. Install wl-clipboard for Wayland or xclip/xsel for X11.")
            else:
                if wayland and shutil.which("wl-copy"): cmd=["wl-copy"]
                elif shutil.which("xclip"): cmd=["xclip","-selection","clipboard"]
                elif shutil.which("xsel"): cmd=["xsel","--clipboard","--input"]
                else: raise RuntimeError("No clipboard backend available. Install wl-clipboard for Wayland or xclip/xsel for X11.")
        elif system=="Darwin": cmd=["pbpaste"] if action=="get" else ["pbcopy"]
        elif system=="Windows": cmd=["powershell","-NoProfile","-Command","Get-Clipboard"] if action=="get" else ["clip"]
        else: raise RuntimeError("Unsupported operating system.")
        r=_run(cmd,10,input_text=None if action=="get" else text); return {"action":action,"text":r["stdout"] if action=="get" else text,"ok":r["ok"],"stderr":r["stderr"]}

    @mcp.tool()
    def desktop_notify(title:str,message:str)->dict[str,Any]:
        """Show a native desktop notification when supported."""
        if platform.system()=="Linux" and shutil.which("notify-send"): return _run(["notify-send",title[:200],message[:2000]],10)
        if platform.system()=="Darwin" and shutil.which("osascript"): return _run(["osascript","-e",f'display notification {json.dumps(message[:2000])} with title {json.dumps(title[:200])}'],10)
        if platform.system()=="Windows": return _run(["powershell","-NoProfile","-Command","[console]::beep(700,250)"],10)
        return {"ok":False,"message":"No supported notification utility found."}

    @mcp.tool()
    def network_diagnostics(action:str,target:str="",port:int=0,timeout:int=5)->dict[str,Any]:
        """Run DNS, ping, TCP, HTTP and interface diagnostics."""
        if action=="dns":
            if not target: raise ValueError("target is required")
            return {"target":target,"addresses":sorted({x[4][0] for x in socket.getaddrinfo(target,None)})}
        if action=="ping": return _run(["ping","-n" if platform.system()=="Windows" else "-c","1",target],timeout)
        if action=="tcp":
            started=time.perf_counter()
            with socket.create_connection((target,port),timeout=timeout): pass
            return {"ok":True,"target":target,"port":port,"latency_ms":round((time.perf_counter()-started)*1000,2)}
        if action=="http":
            if urlparse(target).scheme not in {"http","https"}: raise ValueError("Only http/https URLs are supported.")
            import urllib.request
            started=time.perf_counter()
            with urllib.request.urlopen(urllib.request.Request(target,headers={"User-Agent":"Dana/1.0"}),timeout=timeout) as r:
                return {"ok":True,"status":r.status,"url":r.geturl(),"latency_ms":round((time.perf_counter()-started)*1000,2),"body_preview":r.read(10000).decode("utf-8","replace")}
        if action=="interfaces": return _run(["ip","-brief","addr"],10) if shutil.which("ip") else _run(["ipconfig"] if platform.system()=="Windows" else ["ifconfig"],10)
        raise ValueError("action must be dns, ping, tcp, http or interfaces")

    @mcp.tool()
    def docker_control(action:str,target:str="",command:list[str]|None=None,tail:int=200)->dict[str,Any]:
        """Inspect and control Docker containers and images."""
        if not shutil.which("docker"): raise RuntimeError("Docker is not installed.")
        if action=="ps": return _run(["docker","ps","--all"])
        if action=="images": return _run(["docker","images"])
        if action=="logs": return _run(["docker","logs","--tail",str(max(1,min(tail,5000))),target])
        if action=="inspect": return _run(["docker","inspect",target])
        if action=="stats": return _run(["docker","stats","--no-stream",target] if target else ["docker","stats","--no-stream"])
        if action in {"start","stop","restart"}: return _run(["docker",action,target],60,action!="start")
        if action=="exec":
            if not command: raise ValueError("command is required")
            return _run(["docker","exec",target,*command],120,True)
        raise ValueError("Unsupported Docker action.")

    @mcp.tool()
    def ssh_remote(action:str,host:str,username:str="",command:list[str]|None=None,local_path:str="",remote_path:str="",port:int=22)->dict[str,Any]:
        """Execute SSH commands or transfer files through OpenSSH."""
        if not shutil.which("ssh"): raise RuntimeError("OpenSSH client is not installed.")
        if not host or any(c in host for c in " ;|&$()<>"): raise ValueError("Invalid host.")
        dest=f"{username}@{host}" if username else host
        if action=="exec":
            if not command: raise ValueError("command is required")
            return _run(["ssh","-o","BatchMode=yes","-o","ConnectTimeout=10","-p",str(port),dest,"--",*command],120,True)
        if action in {"download","upload"}:
            local=_path(local_path,"SSH file transfer")
            src,dst=(f"{dest}:{remote_path}",str(local)) if action=="download" else (str(local),f"{dest}:{remote_path}")
            return _run(["scp","-P",str(port),src,dst],180,True)
        raise ValueError("action must be exec, download or upload")

    @mcp.tool()
    def database(action:str,database_path:str,sql:str="",parameters:list[Any]|None=None,allow_write:bool=False)->dict[str,Any]:
        """Inspect and query SQLite databases. Writes are protected."""
        path=_path(database_path,"database access")
        if not path.is_file(): raise ValueError(f"Database not found: {path}")
        if action=="connect": return {"ok":True,"path":str(path),"type":"sqlite"}
        with sqlite3.connect(path) as conn:
            conn.row_factory=sqlite3.Row
            if action=="tables": return {"tables":[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]}
            if action=="schema": return {"schema":[dict(r) for r in conn.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('table','index','view') ORDER BY type,name")]}
            if action=="query":
                if not sql.strip(): raise ValueError("sql is required")
                write=sql.lstrip().split(None,1)[0].lower() in {"insert","update","delete","replace","create","drop","alter","vacuum","reindex"}
                if write and (not allow_write or not settings.allow_dangerous_tools): raise PermissionError("Database writes require allow_write and DANA_ALLOW_DANGEROUS_TOOLS.")
                cur=conn.execute(sql,parameters or [])
                if cur.description: return {"columns":[d[0] for d in cur.description],"rows":[dict(r) for r in cur.fetchall()]}
                conn.commit(); return {"affected_rows":cur.rowcount}
        raise ValueError("action must be connect, query, tables or schema")

    @mcp.tool()
    def scheduler(action:str,job_id:str="",schedule:str="",command:list[str]|None=None)->dict[str,Any]:
        """Persist auditable local scheduled-task definitions."""
        store=_store("schedules.json"); data=json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
        if action=="list": return {"jobs":data}
        if action=="add":
            if not job_id or not schedule or not command: raise ValueError("job_id, schedule and command are required")
            data[job_id]={"schedule":schedule,"command":command,"created_at":time.time()}; store.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); return {"ok":True,"job":data[job_id]}
        if action=="remove":
            if not settings.allow_dangerous_tools: raise PermissionError("Removing schedules is protected.")
            removed=data.pop(job_id,None); store.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8"); return {"ok":removed is not None,"removed":removed}
        raise ValueError("action must be list, add or remove")

    @mcp.tool()
    def secrets(action:str,key:str="",value:str="",reveal:bool=False)->dict[str,Any]:
        """Manage local secrets in a chmod 0600 store; values are masked by default."""
        store=_store("secrets.json"); data=json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
        if action=="list": return {"keys":sorted(data)}
        if not key: raise ValueError("key is required")
        if action=="get":
            if key not in data: raise KeyError(key)
            secret=str(data[key]); return {"key":key,"value":secret if reveal else "*"*min(8,len(secret)),"masked":not reveal}
        if action in {"set","delete"} and not settings.allow_dangerous_tools: raise PermissionError("Secret mutation is protected.")
        if action=="set": data[key]=value
        elif action=="delete": data.pop(key,None)
        else: raise ValueError("action must be list, get, set or delete")
        store.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding="utf-8")
        try: os.chmod(store,0o600)
        except OSError: pass
        return {"ok":True,"key":key}

    @mcp.tool()
    def mcp_manager(action:str="list",path:str="config/mcp-clients")->dict[str,Any]:
        """Discover and read local MCP configuration files."""
        root=_path(path,"MCP configuration discovery")
        if not root.exists(): return {"files":[]}
        files=[p for p in sorted(root.rglob("*")) if p.is_file()]
        if action=="list": return {"files":[str(p.relative_to(root)) for p in files]}
        if action=="read": return {"files":[{"path":str(p.relative_to(root)),"content":p.read_text(encoding="utf-8",errors="replace")[:50000]} for p in files]}
        raise ValueError("action must be list or read")

    @mcp.tool()
    def desktop_control(action:str,target:str="",text:str="",key:str="",x:int=0,y:int=0,button:str="left",clicks:int=1,scroll:int=0)->dict[str,Any]:
        """Control the local Linux desktop: mouse, keyboard, windows and screenshots.

        Actions: windows, activate, close, minimize, maximize, move, move_relative, click, scroll,
        type, key, hotkey, position, screenshot. Automatically selects xdotool on X11
        and ydotool/uinput on Wayland where supported.
        """
        if platform.system()!="Linux": raise RuntimeError("desktop_control currently targets Linux.")
        read_only={"windows","position","screenshot","diagnostics"}
        if action=="diagnostics":
            return _desktop_diagnostics()
        if action=="windows":
            if not shutil.which("wmctrl"): raise RuntimeError("wmctrl is not installed. Install the system package 'wmctrl'.")
            return _run(["wmctrl","-lG"])
        if action=="activate":
            if not target: raise ValueError("target window id or title is required")
            if not shutil.which("wmctrl"): raise RuntimeError("wmctrl is not installed.")
            return _run(["wmctrl","-ia",target] if target.startswith("0x") else ["wmctrl","-a",target])
        if action in {"close","minimize","maximize"}:
            if not target: raise ValueError("target window id or title is required")
            if not shutil.which("wmctrl"): raise RuntimeError("wmctrl is not installed.")
            if action=="close": return _run(["wmctrl","-ic",target] if target.startswith("0x") else ["wmctrl","-c",target])
            if action=="minimize": return _run(["wmctrl","-ir",target,"-b","add,hidden"])
            return _run(["wmctrl","-ir",target,"-b","add,maximized_vert,maximized_horz"])
        if action=="screenshot":
            out=_path(target,"desktop screenshot") if target else _store("screenshots/dana-screenshot.png")
            out.parent.mkdir(parents=True,exist_ok=True)
            if shutil.which("gnome-screenshot"): return _run(["gnome-screenshot","-f",str(out)]) | {"path":str(out)}
            if shutil.which("import"): return _run(["import","-window","root",str(out)]) | {"path":str(out)}
            try:
                import pyautogui
                pyautogui.screenshot(str(out)); return {"ok":True,"path":str(out),"backend":"pyautogui"}
            except ImportError as exc:
                raise RuntimeError("Install gnome-screenshot, ImageMagick (import), or Dana's optional desktop dependency.") from exc
        if action=="position":
            if shutil.which("xdotool") and os.getenv("XDG_SESSION_TYPE","").strip().lower() != "wayland":
                return _run(["xdotool","getmouselocation","--shell"],5)
            return {"ok":True,"backend":_desktop_backend(),"note":"Pointer position is not queryable portably on Wayland."}
        backend=_desktop_backend()
        if backend=="ydotool" and action in {"move","move_relative","click","scroll","type","key","hotkey"}:
            return _desktop_ydo(action,x,y,button,clicks,scroll,text,key)
        if backend=="xdotool":
            if action=="move": return _run(["xdotool","mousemove",str(max(0,x)),str(max(0,y))],5)
            if action=="move_relative": return _run(["xdotool","mousemove_relative",str(x),str(y)],5)
            if action=="click":
                buttons={"left":"1","middle":"2","right":"3"}
                if button not in buttons: raise ValueError("button must be left, middle or right")
                return _run(["xdotool","mousemove",str(max(0,x)),str(max(0,y)),"click","--repeat",str(max(1,min(clicks,20))),buttons[button]],5)
            if action=="scroll":
                if scroll==0: raise ValueError("scroll must be non-zero")
                amount=max(1,min(abs(scroll),50)); direction="4" if scroll>0 else "5"
                return _run(["xdotool","click","--repeat",str(amount),direction])
            if action=="type": return _run(["xdotool","type","--clearmodifiers","--delay","1",text])
            if action=="key": return _run(["xdotool","key","--clearmodifiers",key])
            if action=="hotkey":
                parts=[p.strip() for p in key.replace("+"," ").split() if p.strip()]
                if len(parts)<2: raise ValueError("hotkey requires at least two keys, e.g. ctrl+c")
                return _run(["xdotool","key","--clearmodifiers","+".join(parts)])
        try:
            import pyautogui
        except ImportError as exc:
            raise RuntimeError("Install xdotool or Dana's optional desktop dependency (pip install dana-mcp-server[desktop]).") from exc
        if action=="move": pyautogui.moveTo(max(0,x),max(0,y),duration=0.05); return {"ok":True,"x":x,"y":y,"backend":"pyautogui"}
        if action=="move_relative": pyautogui.moveRel(x,y,duration=0.05); return {"ok":True,"dx":x,"dy":y,"backend":"pyautogui"}
        if action=="click":
            if button not in {"left","middle","right"}: raise ValueError("button must be left, middle or right")
            pyautogui.click(x=max(0,x),y=max(0,y),clicks=max(1,min(clicks,20)),button=button); return {"ok":True,"backend":"pyautogui"}
        if action=="scroll":
            if scroll==0: raise ValueError("scroll must be non-zero")
            pyautogui.scroll(max(-50,min(scroll,50))); return {"ok":True,"backend":"pyautogui"}
        if action=="type": pyautogui.write(text,interval=0.001); return {"ok":True,"backend":"pyautogui"}
        if action=="key": pyautogui.press(key); return {"ok":True,"backend":"pyautogui"}
        if action=="hotkey":
            parts=[p.strip().lower() for p in key.replace("+"," ").split() if p.strip()]
            if len(parts)<2: raise ValueError("hotkey requires at least two keys, e.g. ctrl+c")
            pyautogui.hotkey(*parts); return {"ok":True,"backend":"pyautogui"}
        raise ValueError("action must be windows, activate, close, minimize, maximize, move, move_relative, click, scroll, type, key, hotkey, position or screenshot")

    @mcp.tool()
    def media(action:str,source:str,output:str="",width:int=0,height:int=0,fps:int=1)->dict[str,Any]:
        """Inspect and transform media with FFmpeg/ImageMagick."""
        src=_path(source,"media input")
        if not src.exists(): raise ValueError(f"Source not found: {src}")
        if action=="info":
            if not shutil.which("ffprobe"): raise RuntimeError("ffprobe is not installed.")
            return _run(["ffprobe","-v","error","-show_format","-show_streams",str(src)],60)
        if not output: raise ValueError("output is required")
        dst=_path(output,"media output"); dst.parent.mkdir(parents=True,exist_ok=True)
        if action=="convert":
            if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg is not installed.")
            return _run(["ffmpeg","-y","-i",str(src),str(dst)],300,True)
        if action=="extract_audio":
            if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg is not installed.")
            return _run(["ffmpeg","-y","-i",str(src),"-vn",str(dst)],300,True)
        if action=="frames":
            if not shutil.which("ffmpeg"): raise RuntimeError("ffmpeg is not installed.")
            return _run(["ffmpeg","-y","-i",str(src),"-vf",f"fps={max(1,min(fps,60))}",str(dst)],300,True)
        if action=="resize":
            image_tool = shutil.which("magick") or shutil.which("convert")
            if not image_tool: raise RuntimeError("ImageMagick is not installed.")
            if width<=0 or height<=0: raise ValueError("width and height must be positive")
            return _run([image_tool,str(src),"-resize",f"{width}x{height}",str(dst)],180,True)
        raise ValueError("action must be info, convert, resize, extract_audio or frames")

    @mcp.tool()
    def browser(action:str,url:str="",selector:str="",text:str="",key:str="",path:str="")->dict[str,Any]:
        """Automate Chromium/Chrome using Dana's optional Playwright dependency."""
        global _BROWSER,_PAGE
        try: from playwright.sync_api import sync_playwright
        except ImportError as exc: raise RuntimeError("Install Dana's browser/full optional dependency first.") from exc
        if action=="open":
            if not url: raise ValueError("url is required")
            if _BROWSER is None:
                _BROWSER=sync_playwright().start(); _PAGE=_BROWSER.chromium.launch(headless=True).new_page()
            _PAGE.goto(url,wait_until="domcontentloaded",timeout=30000); return {"url":_PAGE.url,"title":_PAGE.title()}
        if _PAGE is None: raise RuntimeError("Open a browser page first.")
        if action=="click": _PAGE.locator(selector).click(timeout=15000); return {"ok":True,"url":_PAGE.url}
        if action=="type": _PAGE.locator(selector).fill(text); return {"ok":True}
        if action=="press": _PAGE.locator(selector).press(key); return {"ok":True}
        if action=="text": return {"url":_PAGE.url,"title":_PAGE.title(),"text":_PAGE.locator("body").inner_text()[:50000]}
        if action=="screenshot":
            out=_path(path or "dana-browser.png","browser screenshot"); _PAGE.screenshot(path=str(out),full_page=True); return {"ok":True,"path":str(out)}
        raise ValueError("action must be open, click, type, press, text or screenshot")
