import json
import subprocess

import pytest

from lab import going_feed as G
from lab import publish_going as P


def _feed(**kw):
    f = {"schema": G.SCHEMA, "schema_version": G.SCHEMA_VERSION, "generated_at": "2026-10-18T10:00:00+00:00", "source": {},
         "freshness": {}, "notices": G.NOTICES,
         "games": [{"game_id": "2026_06_ARI_LA", "home_team": "LA", "away_team": "ARI", "kickoff_utc": "2026-10-18T20:05:00+00:00",
                    "forecast": {"archived_at": "2026-10-17T20:05:35+00:00", "champion": {"p_home": 0.79},
                                 "models": [{"key": "logreg", "p_home": 0.8}]}}]}
    f.update(kw)
    return f


def test_validate_accepts_a_clean_feed_and_rejects_leaks():
    assert G.validate(_feed()) == []
    bad = _feed()
    bad["games"][0]["forecast"]["archived_at"] = "2026-10-18T21:00:00+00:00"          # after kickoff
    assert any("after kickoff" in e for e in G.validate(bad))
    bad = _feed()
    bad["games"][0]["forecast"]["champion"]["p_home"] = 1.3
    assert any("out of range" in e for e in G.validate(bad))
    for leak in ("C:\\Users\\travi\\OneDrive\\x.json", "feature_snapshot", "my api_key"):
        assert any("forbidden" in e for e in G.validate(_feed(source={"x": leak}))), leak
    assert "schema_version must be 1.x" in G.validate(_feed(schema_version="2.0.0"))


def _git(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], capture_output=True, text=True, check=True).stdout.strip()


def test_push_feed_uses_a_separate_branch_and_never_touches_the_checkout(tmp_path):
    remote, work = tmp_path / "remote.git", tmp_path / "work"
    subprocess.run(["git", "init", "--bare", "-q", str(remote)], check=True)
    subprocess.run(["git", "init", "-q", str(work)], check=True)
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    (work / "a.txt").write_text("hello")
    _git(work, "add", "a.txt")
    _git(work, "commit", "-qm", "init")
    _git(work, "remote", "add", "origin", str(remote))
    head, status = _git(work, "rev-parse", "HEAD"), _git(work, "status", "--porcelain")
    f = tmp_path / "feed.json"
    f.write_text(json.dumps(_feed()))
    c1 = P.push_feed(f, repo=work)
    c2 = P.push_feed(f, repo=work)                                  # identical content -> no new commit
    assert c1 == c2
    f.write_text(json.dumps(_feed(generated_at="2026-10-18T11:00:00+00:00")))
    c3 = P.push_feed(f, repo=work)
    assert c3 != c1 and _git(remote, "rev-parse", f"{c3}^") == c1   # history kept
    assert json.loads(_git(remote, "show", f"{P.BRANCH}:{P.REMOTE_PATH}"))["generated_at"] == "2026-10-18T11:00:00+00:00"
    assert _git(remote, "ls-tree", "--name-only", P.BRANCH) == P.REMOTE_PATH   # only the feed file is published
    assert _git(work, "rev-parse", "HEAD") == head and _git(work, "status", "--porcelain") == status


def test_publish_never_raises_and_logs_failures(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "PUB_DIR", tmp_path)
    monkeypatch.setattr(P, "HISTORY", tmp_path / "history.jsonl")
    monkeypatch.setattr(P, "FEED_FILE", tmp_path / "feed.json")
    monkeypatch.setattr("lab.going_feed.build", lambda now=None: (_ for _ in ()).throw(RuntimeError("no snapshots")))
    r = P.publish(push=True)
    assert r["ok"] is False and r["stage"] == "build"
    monkeypatch.setattr("lab.going_feed.build", lambda now=None: _feed())
    r = P.publish(push=False)
    assert r["ok"] and not r["pushed"] and json.loads((tmp_path / "feed.json").read_text())["schema"] == G.SCHEMA
    h = P.health()
    assert h["attempts"] == 2 and h["last_local_write"]["ok"] and h["last_published"] is None and h["automatic"] is False
