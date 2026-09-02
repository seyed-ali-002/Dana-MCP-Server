#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / ".dana"
DB = STATE / "memory.db"

# High precision credential gate. The raw secret is never persisted or audited.
_SECRET_PATTERNS = [
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("jwt", re.compile(r"\beyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\b")),
    ("api-key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("credential-assignment", re.compile(r"\b(?:password|passwd|token|secret|api[_-]?key)\s*[:=]\s*\S+", re.I)),
]


def _db() -> sqlite3.Connection:
    STATE.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    c.executescript("""
    CREATE TABLE IF NOT EXISTS memories (
      id TEXT PRIMARY KEY, type TEXT NOT NULL CHECK(type IN ('episodic','semantic','procedural')),
      content TEXT NOT NULL, entity_key TEXT, tags TEXT NOT NULL DEFAULT '[]',
      importance REAL NOT NULL DEFAULT 0.5, confidence REAL NOT NULL DEFAULT 0.7,
      status TEXT NOT NULL DEFAULT 'active', source TEXT NOT NULL DEFAULT 'agent',
      created_at REAL NOT NULL, updated_at REAL NOT NULL, last_accessed_at REAL NOT NULL,
      access_count INTEGER NOT NULL DEFAULT 0, decay REAL NOT NULL DEFAULT 0,
      supersedes TEXT, superseded_by TEXT, disputed INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_mem_entity ON memories(entity_key);
    CREATE INDEX IF NOT EXISTS idx_mem_status ON memories(status);
    CREATE TABLE IF NOT EXISTS links (from_id TEXT NOT NULL, to_id TEXT NOT NULL, kind TEXT NOT NULL, PRIMARY KEY(from_id,to_id,kind));
    CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, action TEXT NOT NULL, memory_id TEXT, detail TEXT NOT NULL DEFAULT '{}');
    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, tags, content='memories', content_rowid='rowid', tokenize='porter unicode61');
    """)
    # Keep FTS synchronized for installations created before triggers existed.
    c.executescript("""
    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
      INSERT INTO memories_fts(rowid,content,tags) VALUES(new.rowid,new.content,new.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts,rowid,content,tags) VALUES('delete',old.rowid,old.content,old.tags);
    END;
    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
      INSERT INTO memories_fts(memories_fts,rowid,content,tags) VALUES('delete',old.rowid,old.content,old.tags);
      INSERT INTO memories_fts(rowid,content,tags) VALUES(new.rowid,new.content,new.tags);
    END;
    """)
    c.commit()
    return c


def _secret_kind(content: str) -> str | None:
    for kind, pattern in _SECRET_PATTERNS:
        if pattern.search(content):
            return kind
    return None


def _tokens(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[\w-]{2,}", text, re.UNICODE) if x.lower() not in {"the", "and", "for", "with", "that", "this"}}


def _similarity(a: str, b: str) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / math.sqrt(len(aa) * len(bb))


def _audit(c: sqlite3.Connection, action: str, memory_id: str | None, detail: dict[str, Any] | None = None) -> None:
    c.execute("INSERT INTO audit(ts,action,memory_id,detail) VALUES(?,?,?,?)", (time.time(), action, memory_id, json.dumps(detail or {}, ensure_ascii=False, default=str)))


def _row(row: sqlite3.Row, score: float | None = None, qualifier: str | None = None) -> dict[str, Any]:
    out = dict(row)
    out["tags"] = json.loads(out.get("tags") or "[]")
    out["disputed"] = bool(out["disputed"])
    if score is not None: out["score"] = round(score, 5)
    if qualifier: out["qualifier"] = qualifier
    return out


def write_memory(content: str, memory_type: str = "semantic", entity_key: str | None = None,
                 tags: list[str] | None = None, importance: float = 0.5,
                 confidence: float = 0.7, source: str = "agent", allow_secret: bool = False) -> dict[str, Any]:
    content = content.strip()
    if not content: raise ValueError("Memory content cannot be empty")
    if memory_type not in {"episodic", "semantic", "procedural"}: raise ValueError("Invalid memory type")
    if not allow_secret and _secret_kind(content): raise ValueError("Content appears to contain a credential; use a password manager")
    importance = min(0.8, max(0.0, float(importance))) if source == "agent" else min(1.0, max(0.0, float(importance)))
    confidence = min(1.0, max(0.0, float(confidence)))
    now = time.time(); c = _db()
    # Entity keys are current-value slots: supersede the previous active value.
    old = None
    if entity_key:
        old = c.execute("SELECT * FROM memories WHERE entity_key=? AND status='active' ORDER BY updated_at DESC LIMIT 1", (entity_key,)).fetchone()
    # Semantic dedup avoids filling retrieval with copies.
    for row in c.execute("SELECT * FROM memories WHERE status='active' ORDER BY updated_at DESC LIMIT 300"):
        if row["entity_key"] == entity_key and entity_key: continue
        if _similarity(content, row["content"]) >= 0.94:
            c.execute("UPDATE memories SET updated_at=?, confidence=MAX(confidence,?), importance=MAX(importance,?) WHERE id=?", (now, confidence, importance, row["id"]))
            _audit(c, "deduplicate", row["id"], {"source": source})
            c.commit(); c.close()
            return {"id": row["id"], "deduplicated": True, "status": "active"}
    mid = uuid.uuid4().hex
    c.execute("INSERT INTO memories(id,type,content,entity_key,tags,importance,confidence,status,source,created_at,updated_at,last_accessed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (mid,memory_type,content,entity_key,json.dumps(tags or [],ensure_ascii=False),importance,confidence,"active",source,now,now,now))
    if old and old["id"] != mid:
        c.execute("UPDATE memories SET status='superseded',superseded_by=?,updated_at=? WHERE id=?", (mid,now,old["id"]))
        c.execute("UPDATE memories SET supersedes=? WHERE id=?", (old["id"],mid))
        _audit(c, "supersede", mid, {"old_id": old["id"], "entity_key": entity_key})
    _audit(c, "write", mid, {"type":memory_type,"entity_key":entity_key,"source":source})
    c.commit(); c.close()
    return {"id":mid,"status":"active","superseded_id":old["id"] if old else None,"importance":importance,"confidence":confidence}


def retrieve_memories(query: str, limit: int = 5, min_score: float = 0.05, include_disputed: bool = False) -> dict[str, Any]:
    query = query.strip(); limit=max(1,min(50,int(limit)))
    if not query: return {"query":query,"memories":[]}
    c=_db(); candidates=[]
    try:
        terms = [re.sub(r'[^\w]', '', x) for x in re.findall(r"[\w-]{2,}", query, re.UNICODE)]
        ftsq = " OR ".join(f'"{x}"*' for x in terms[:12])
        rows = c.execute("SELECT m.*, bm25(memories_fts) AS bm FROM memories_fts JOIN memories m ON m.rowid=memories_fts.rowid WHERE memories_fts MATCH ? AND m.status='active'", (ftsq or '""',)).fetchall() if ftsq else []
        seen={r['id'] for r in rows}
        rows += [r for r in c.execute("SELECT * FROM memories WHERE status='active' ORDER BY importance DESC, updated_at DESC LIMIT 500") if r['id'] not in seen]
    except sqlite3.OperationalError:
        rows=c.execute("SELECT * FROM memories WHERE status='active' LIMIT 500").fetchall()
    now=time.time()
    qtokens=_tokens(query)
    for r in rows:
        if r['disputed'] and not include_disputed: continue
        rt=_tokens(r['content']+' '+' '.join(json.loads(r['tags'] or '[]')))
        keyword=len(qtokens & rt)/max(1,len(qtokens))
        vector=_similarity(query,r['content'])
        age=max(0,now-r['updated_at']); recency=math.exp(-age/(30*86400))
        decay=min(1.0,age/(180*86400))
        score=.40*vector+.20*keyword+.15*r['importance']+.10*r['confidence']+.10*recency-.10*decay-.05*int(r['disputed'])
        if score >= min_score:
            qualifier=[]
            if age>180*86400: qualifier.append("may be outdated")
            if r['disputed']: qualifier.append("disputed")
            if r['confidence']<.5: qualifier.append("low confidence")
            candidates.append((score,r,qualifier))
    candidates.sort(key=lambda x:(-x[0],-x[1]['importance'], -x[1]['updated_at']))
    chosen=candidates[:limit]
    for score,r,_ in chosen:
        c.execute("UPDATE memories SET last_accessed_at=?,access_count=access_count+1 WHERE id=?",(now,r['id']))
    c.commit(); c.close()
    return {"query":query,"memories":[_row(r,s,"; ".join(q) if q else None) for s,r,q in chosen],"count":len(chosen)}


def digest(limit: int=30, max_chars: int=12000) -> dict[str, Any]:
    c=_db(); rows=c.execute("SELECT * FROM memories WHERE status='active' AND disputed=0 ORDER BY importance DESC, confidence DESC, last_accessed_at DESC LIMIT ?",(max(1,min(200,limit)),)).fetchall(); c.close()
    lines=[]; selected=[]
    for r in rows:
        line=f"- [{r['type']}] {r['content']}"
        if r['entity_key']: line += f" (key: {r['entity_key']})"
        if len('\n'.join(lines))+len(line)>max_chars: continue
        lines.append(line); selected.append(r['id'])
    return {"digest":"\n".join(lines),"count":len(selected),"memory_ids":selected,"max_chars":max_chars}


def feedback(memory_id: str, feedback_type: str) -> dict[str, Any]:
    if feedback_type not in {"helpful","stale","wrong"}: raise ValueError("feedback must be helpful, stale, or wrong")
    c=_db(); row=c.execute("SELECT * FROM memories WHERE id=?",(memory_id,)).fetchone()
    if not row: c.close(); raise ValueError("Memory not found")
    if feedback_type=='helpful': c.execute("UPDATE memories SET confidence=MIN(1,confidence+0.08), disputed=0, last_accessed_at=?, access_count=access_count+1 WHERE id=?",(time.time(),memory_id))
    elif feedback_type=='stale': c.execute("UPDATE memories SET confidence=MAX(0,confidence-0.12), disputed=1, decay=MIN(1,decay+0.2) WHERE id=?",(memory_id,))
    else: c.execute("UPDATE memories SET confidence=MAX(0,confidence-0.25), disputed=1 WHERE id=?",(memory_id,))
    _audit(c,"feedback",memory_id,{"feedback":feedback_type}); c.commit(); out=c.execute("SELECT * FROM memories WHERE id=?",(memory_id,)).fetchone(); c.close()
    return _row(out)


def link_memories(from_id: str, to_id: str, kind: str='related_to') -> dict[str, Any]:
    if kind not in {'related_to','part_of','supports','contradicts'}: raise ValueError("Invalid link kind")
    c=_db();
    for mid in (from_id,to_id):
        if not c.execute("SELECT 1 FROM memories WHERE id=?",(mid,)).fetchone(): c.close(); raise ValueError("Memory not found")
    c.execute("INSERT OR IGNORE INTO links VALUES(?,?,?)",(from_id,to_id,kind)); _audit(c,"link",from_id,{"to":to_id,"kind":kind}); c.commit(); c.close(); return {"linked":True,"from_id":from_id,"to_id":to_id,"kind":kind}


def list_links(memory_id: str) -> list[dict[str,Any]]:
    c=_db(); rows=c.execute("SELECT l.*,m.content FROM links l JOIN memories m ON m.id=l.to_id WHERE l.from_id=? UNION ALL SELECT l.from_id,l.to_id,l.kind,m.content FROM links l JOIN memories m ON m.id=l.from_id WHERE l.to_id=?",(memory_id,memory_id)).fetchall(); c.close(); return [dict(r) for r in rows]


def maintenance() -> dict[str,Any]:
    now=time.time(); c=_db()
    cutoff=now-180*86400
    c.execute("UPDATE memories SET decay=MIN(1, MAX(decay, (? - last_accessed_at)/(180*86400))) WHERE status='active'",(now,))
    stale=c.execute("SELECT id FROM memories WHERE status='active' AND importance<0.25 AND confidence<0.35 AND last_accessed_at<?",(cutoff,)).fetchall()
    for r in stale: c.execute("UPDATE memories SET status='quarantined' WHERE id=?",(r['id'],)); _audit(c,'quarantine',r['id'],{})
    c.commit(); result={"decayed":c.execute("SELECT COUNT(*) FROM memories WHERE status='active' AND decay>0").fetchone()[0],"quarantined":len(stale)}; c.close(); return result


def export_memories() -> dict[str,Any]:
    c=_db(); memories=[_row(r) for r in c.execute("SELECT * FROM memories WHERE status!='deleted' ORDER BY created_at")]; links=[dict(r) for r in c.execute("SELECT * FROM links")]; audit=[dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id")]; c.close(); return {"version":1,"exported_at":time.time(),"memories":memories,"links":links,"audit":audit}


def purge_memories(confirm: bool=False) -> dict[str,Any]:
    if not confirm: raise ValueError("Set confirm=true to purge memory data")
    c=_db(); counts={"memories":c.execute("SELECT COUNT(*) FROM memories").fetchone()[0],"links":c.execute("SELECT COUNT(*) FROM links").fetchone()[0]}; c.execute("DELETE FROM links"); c.execute("DELETE FROM memories"); c.execute("DELETE FROM memories_fts"); _audit(c,'purge',None,counts); c.commit(); c.close(); return {"purged":True,**counts}


def stats() -> dict[str,Any]:
    c=_db(); result={"db":str(DB),"total":c.execute("SELECT COUNT(*) FROM memories").fetchone()[0],"active":c.execute("SELECT COUNT(*) FROM memories WHERE status='active'").fetchone()[0],"disputed":c.execute("SELECT COUNT(*) FROM memories WHERE disputed=1").fetchone()[0],"by_type":{r[0]:r[1] for r in c.execute("SELECT type,COUNT(*) FROM memories GROUP BY type")}}; c.close(); return result


def register_memory_tools(mcp: Any) -> None:
    @mcp.tool()
    def memory_write(content:str, memory_type:str='semantic', entity_key:str|None=None, tags:list[str]|None=None, importance:float=.5, confidence:float=.7) -> dict[str,Any]:
        """Store durable typed memory. Entity keys supersede old current values; credentials are rejected."""
        return write_memory(content,memory_type,entity_key,tags,importance,confidence)
    @mcp.tool()
    def memory_retrieve(query:str, limit:int=5, min_score:float=.05, include_disputed:bool=False)->dict[str,Any]:
        """Hybrid local retrieval using SQLite FTS/BM25, lexical similarity, importance, confidence and recency."""
        return retrieve_memories(query,limit,min_score,include_disputed)
    @mcp.tool()
    def memory_digest(limit:int=30,max_chars:int=12000)->dict[str,Any]:
        """Return compact always-on core memory for session start."""
        return digest(limit,max_chars)
    @mcp.tool()
    def memory_feedback(memory_id:str, feedback_type:str)->dict[str,Any]:
        """Mark a memory helpful, stale or wrong and adjust trust."""
        return feedback(memory_id,feedback_type)
    @mcp.tool()
    def memory_link(from_id:str,to_id:str,kind:str='related_to')->dict[str,Any]:
        """Link related memories for one-hop graph expansion."""
        return link_memories(from_id,to_id,kind)
    @mcp.tool()
    def memory_links(memory_id:str)->list[dict[str,Any]]:
        """List links attached to a memory."""
        return list_links(memory_id)
    @mcp.tool()
    def memory_maintain()->dict[str,Any]:
        """Apply decay and quarantine low-confidence stale memories."""
        return maintenance()
    @mcp.tool()
    def memory_export()->dict[str,Any]:
        """Export memories, links and audit records as JSON-safe data."""
        return export_memories()
    @mcp.tool()
    def memory_purge(confirm:bool=False)->dict[str,Any]:
        """Hard-delete all memory data after explicit confirmation."""
        return purge_memories(confirm)
    @mcp.tool()
    def memory_stats()->dict[str,Any]:
        """Show local memory statistics."""
        return stats()
