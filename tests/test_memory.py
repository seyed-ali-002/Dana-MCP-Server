from dana.tools.memory import DB, STATE, feedback, purge_memories, retrieve_memories, write_memory


def test_memory_write_retrieve_and_supersession(tmp_path, monkeypatch):
    import dana.tools.memory as m
    monkeypatch.setattr(m, "DB", tmp_path / "memory.db")
    monkeypatch.setattr(m, "STATE", tmp_path)
    a = write_memory("User lives in Baku", entity_key="user.location", importance=.8)
    b = write_memory("User lives in Tbilisi", entity_key="user.location", importance=.8)
    assert b["superseded_id"] == a["id"]
    result = retrieve_memories("Where does the user live?", limit=5)
    assert any(x["id"] == b["id"] for x in result["memories"])
    assert all(x["id"] != a["id"] for x in result["memories"])


def test_secret_rejected(tmp_path, monkeypatch):
    import dana.tools.memory as m
    monkeypatch.setattr(m, "DB", tmp_path / "memory.db")
    monkeypatch.setattr(m, "STATE", tmp_path)
    try:
        write_memory("password=super-secret-value")
        assert False, "credential should be rejected"
    except ValueError as exc:
        assert "credential" in str(exc).lower()


def test_feedback_and_purge(tmp_path, monkeypatch):
    import dana.tools.memory as m
    monkeypatch.setattr(m, "DB", tmp_path / "memory.db")
    monkeypatch.setattr(m, "STATE", tmp_path)
    row = write_memory("Dana uses pytest", confidence=.7)
    updated = feedback(row["id"], "stale")
    assert updated["disputed"] is True
    assert purge_memories(True)["memories"] == 1
