"""Question sharing between teachers (web app, one bank per teacher).

A share belongs to its owner and names a target ('*' = the whole bank, or one question id) and an
audience ('all' approved users, or chosen users). Shared questions are read-only for others: they
appear in their library under a suffixed name (`<name>__p<owner id>`), can be copied into their own
bank, and can be drawn into their exams when they ask for it.
"""
from __future__ import annotations

import dataclasses
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from . import auth
from .library import Library
from .model import Question

SUFFIX = "__p"


def shared_id(qid: str, owner_id: int) -> str:
    return f"{qid}{SUFFIX}{owner_id}"


def split_shared_id(qid: str) -> tuple[str, int] | None:
    head, sep, tail = qid.rpartition(SUFFIX)
    if not sep or not tail.isdigit() or head.count("/") != 2:
        return None
    return head, int(tail)


# ------------------------------------------------------------------ share records
def my_shares(owner: auth.User) -> list[dict[str, Any]]:
    s = auth.store()
    out = []
    for sid, target, audience, created in s.q(
            "SELECT id, target, audience, created_at FROM shares WHERE owner_id = ? ORDER BY target", (owner.id,)):
        members = s.q("SELECT u.id, u.name, u.email FROM share_members m JOIN users u ON u.id = m.user_id "
                      "WHERE m.share_id = ? ORDER BY u.name", (sid,))
        out.append({"id": sid, "target": target, "audience": audience, "created_at": auth._iso(created),
                    "users": [{"id": i, "name": n, "email": e} for i, n, e in members]})
    return out


def set_share(owner: auth.User, target: str, audience: str, user_ids: list[int]) -> dict[str, Any]:
    if audience not in {"all", "users"}:
        raise auth.AuthError(400, "Audience invalide")
    if target != "*" and target.count("/") != 2:
        raise auth.AuthError(400, "Question invalide")
    s = auth.store()
    ids = sorted({int(u) for u in user_ids if int(u) != owner.id})
    if audience == "users":
        if not ids:
            raise auth.AuthError(400, "Choisissez au moins un utilisateur")
        ok = {r[0] for r in s.q(f"SELECT id FROM users WHERE status = 'approved' AND id IN ({','.join('?' * len(ids))})",
                                tuple(ids))}
        if ok != set(ids):
            raise auth.AuthError(400, "Utilisateur inconnu")
    s.x("INSERT INTO shares (owner_id, target, audience, created_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(owner_id, target) DO UPDATE SET audience = excluded.audience", (owner.id, target, audience, time.time()))
    sid = s.q("SELECT id FROM shares WHERE owner_id = ? AND target = ?", (owner.id, target))[0][0]
    s.x("DELETE FROM share_members WHERE share_id = ?", (sid,))
    for uid in ids if audience == "users" else []:
        s.x("INSERT INTO share_members (share_id, user_id) VALUES (?, ?)", (sid, uid))
    return next(x for x in my_shares(owner) if x["id"] == sid)


def delete_share(owner: auth.User, share_id: int) -> None:
    s = auth.store()
    if not s.q("SELECT 1 FROM shares WHERE id = ? AND owner_id = ?", (share_id, owner.id)):
        raise auth.AuthError(404, "Partage introuvable")
    s.x("DELETE FROM shares WHERE id = ?", (share_id,))


def unshare_question(owner: auth.User, qid: str) -> None:
    auth.store().x("DELETE FROM shares WHERE owner_id = ? AND target = ?", (owner.id, qid))


def visible_shares(viewer: auth.User) -> dict[int, set[str]]:
    """owner id -> targets that `viewer` may see ('*' or question ids)."""
    rows = auth.store().q(
        "SELECT s.owner_id, s.target FROM shares s JOIN users o ON o.id = s.owner_id "
        "WHERE o.status = 'approved' AND s.owner_id != ? AND (s.audience = 'all' OR EXISTS "
        "(SELECT 1 FROM share_members m WHERE m.share_id = s.id AND m.user_id = ?))", (viewer.id, viewer.id))
    out: dict[int, set[str]] = {}
    for owner, target in rows:
        out.setdefault(owner, set()).add(target)
    return out


def directory(viewer: auth.User) -> list[dict[str, Any]]:
    """Approved colleagues a teacher can share with."""
    rows = auth.store().q("SELECT id, name, email FROM users WHERE status = 'approved' AND id != ? ORDER BY name",
                          (viewer.id,))
    return [{"id": i, "name": n, "email": e} for i, n, e in rows]


# ------------------------------------------------------------------ libraries with shared questions
@dataclasses.dataclass
class Origin:
    owner_id: int
    owner_name: str
    original_id: str
    library: Library


_owner_libs: dict[Path, Library] = {}
_owner_lock = threading.Lock()


def _owner_lib(root: Path) -> Library:
    with _owner_lock:
        L = _owner_libs.get(root)
        if L is None:
            L = _owner_libs[root] = Library(root)
    L.refresh()
    return L


def _signature(q: Question) -> tuple:
    return (q.course, q.topic, q.body.strip(), q.solution_tex.strip())


class SharedLibrary(Library):
    """The viewer's own library plus the questions colleagues shared with them (read-only, suffixed ids)."""

    def __init__(self, own: Library, viewer: auth.User, include_own: bool = True):
        super().__init__(own.root)
        self.own = own
        self.viewer = viewer
        self.include_own = include_own
        self.origins: dict[str, Origin] = {}

    def _load_all(self) -> dict[str, Question]:
        if self._cache is not None:
            return self._cache
        own = self.own._load_all()
        qs: dict[str, Question] = dict(own) if self.include_own else {}
        seen = {_signature(q) for q in own.values()}  # skip copies identical to one of mine (starter bank)
        s = auth.store()
        origins: dict[str, Origin] = {}
        for owner_id, targets in visible_shares(self.viewer).items():
            owner = s.user_by_id(owner_id)
            if not owner:
                continue
            olib = _owner_lib(auth.library_root(owner))
            for q in olib._load_all().values():
                if "*" not in targets and q.id not in targets:
                    continue
                if q.id not in targets and _signature(q) in seen:
                    continue  # whole-bank share: skip exact copies of my questions (starter bank)
                seen.add(_signature(q))
                nid = shared_id(q.id, owner_id)
                qs[nid] = dataclasses.replace(q, id=nid, name=f"{q.name}{SUFFIX}{owner_id}", history=[])
                origins[nid] = Origin(owner_id, owner.name, q.id, olib)
        self.origins = origins
        self._errors = self.own._errors
        self._cache = qs
        return qs

    def topics(self, course: str) -> list[str]:
        out = set(super().topics(course)) if self.include_own else set()
        sources = set(self.course_sources(course))
        out |= {q.topic for q in self._load_all().values() if q.course in sources}
        return sorted(out)

    def copy_figures(self, names: list[str], dest: Path) -> list[str]:
        missing = super().copy_figures(names, dest)
        if not missing:
            return []
        self._load_all()
        still = []
        libs = {id(o.library): o.library for o in self.origins.values()}.values()
        for n in missing:
            for ol in libs:
                src = ol.figures_dir / Path(n).name
                if src.exists():
                    shutil.copy2(src, dest / "Figures" / src.name)
                    break
            else:
                still.append(n)
        return still

    def save_question(self, q: Question) -> Path:
        if split_shared_id(q.id):
            raise auth.AuthError(403, "Question partagée : copiez-la dans votre banque pour la modifier.")
        return self.own.save_question(q)

    def delete_question(self, qid: str) -> None:
        if qid in self.origins or split_shared_id(qid):
            raise auth.AuthError(403, "Question partagée : seul son auteur peut la supprimer.")
        self.own.delete_question(qid)


def copy_to_own(view: SharedLibrary, qid: str) -> str:
    """Copy a shared question (and its figures) into the viewer's bank. Returns the new id."""
    view._load_all()
    origin = view.origins.get(qid)
    if not origin:
        raise auth.AuthError(404, "Question partagée introuvable")
    src = origin.library.get(origin.original_id)
    own = view.own
    name, n = src.name, 1
    while (own.questions_dir / src.course / src.topic / f"{name}.yaml").exists():
        n += 1
        name = f"{src.name}_{n}"
    src_dir = origin.library.questions_dir / src.course / src.topic
    dst_dir = own.questions_dir / src.course / src.topic
    dst_dir.mkdir(parents=True, exist_ok=True)
    for ext in (".yaml", ".tex"):
        shutil.copy2(src_dir / f"{src.name}{ext}", dst_dir / f"{name}{ext}")
    if src.solution_file and (src_dir / src.solution_file).exists():
        target = src.solution_file.replace(src.name, name, 1) if src.solution_file.startswith(src.name) else src.solution_file
        shutil.copy2(src_dir / src.solution_file, dst_dir / target)
        if target != src.solution_file:
            import yaml
            y = dst_dir / f"{name}.yaml"
            meta = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
            meta.setdefault("solution", {})["file"] = target
            y.write_text(yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8")
    own.figures_dir.mkdir(parents=True, exist_ok=True)
    for f in src.figures:
        sp = origin.library.figures_dir / Path(f).name
        if sp.exists() and not (own.figures_dir / sp.name).exists():
            shutil.copy2(sp, own.figures_dir / sp.name)
    own.reload()
    return f"{src.course}/{src.topic}/{name}"
