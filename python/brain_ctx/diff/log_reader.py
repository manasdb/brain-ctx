"""
brain-ctx diff
==============
Human-readable summary of what AI agents have done to this codebase.
Reads the observability log and produces:

  - Files written (by whom, when)
  - Files that were blocked (violation attempts)
  - Proposals made vs accepted vs rejected
  - Invariant violations
  - Timeline: what changed and when

Supports:
  - diff since last commit
  - diff since a timestamp
  - diff for a specific session
  - diff for a specific agent role
  - --rotate: archive old log entries

Usage:
    from brain_ctx.diff.log_reader import DiffReader
    report = DiffReader(log_path, project_root).since_last_commit()
    report.print()
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ── Data model ─────────────────────────────────────────────────

@dataclass
class LogEntry:
    ts:         datetime
    session_id: str
    model:      str
    role:       str
    action:     str
    path:       Optional[str]
    allowed:    Optional[bool]
    summary:    Optional[str]
    raw:        dict

    @classmethod
    def from_dict(cls, d: dict) -> "LogEntry":
        ts_str = d.get("ts") or d.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        except Exception:
            ts = datetime.now(timezone.utc)
        return cls(
            ts=ts,
            session_id=d.get("session_id", ""),
            model=d.get("model", "unknown"),
            role=d.get("role", "unknown"),
            action=d.get("action", ""),
            path=d.get("path"),
            allowed=d.get("allowed"),
            summary=d.get("summary"),
            raw=d,
        )


@dataclass
class DiffReport:
    since:       Optional[datetime]
    entries:     list[LogEntry]  = field(default_factory=list)
    project_root: Optional[Path] = None

    # ── Aggregated views ───────────────────────────────────────

    @property
    def writes(self) -> list[LogEntry]:
        return [e for e in self.entries if e.action == "write" and e.allowed]

    @property
    def blocked(self) -> list[LogEntry]:
        return [e for e in self.entries if e.allowed is False]

    @property
    def violations(self) -> list[LogEntry]:
        return [e for e in self.entries
                if e.action in ("write","delete") and e.allowed is False]

    @property
    def proposals(self) -> list[LogEntry]:
        return [e for e in self.entries if e.action == "propose"]

    @property
    def sessions(self) -> dict[str, list[LogEntry]]:
        result: dict[str, list[LogEntry]] = defaultdict(list)
        for e in self.entries:
            result[e.session_id].append(e)
        return dict(result)

    @property
    def by_role(self) -> dict[str, list[LogEntry]]:
        result: dict[str, list[LogEntry]] = defaultdict(list)
        for e in self.entries:
            result[e.role].append(e)
        return dict(result)

    @property
    def files_touched(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for e in self.writes:
            if e.path and e.path not in seen:
                seen.add(e.path)
                result.append(e.path)
        return result

    def print(self, verbose: bool = False) -> None:
        since_str = self.since.strftime("%Y-%m-%d %H:%M") if self.since else "all time"
        print(f"\n{'─'*60}")
        print(f"  brain.ctx diff — since {since_str}")
        print(f"{'─'*60}")

        if not self.entries:
            print("  No AI activity recorded in this period.\n")
            return

        # Sessions
        print(f"\n  📋 Sessions: {len(self.sessions)}")
        for sid, ses_entries in list(self.sessions.items())[:5]:
            first = ses_entries[0]
            last  = ses_entries[-1]
            print(f"     {sid[:8]}... | {first.model}/{first.role} | "
                  f"{first.ts.strftime('%m-%d %H:%M')} → {last.ts.strftime('%H:%M')} "
                  f"| {len(ses_entries)} actions")

        # Writes
        print(f"\n  ✏️  Files written: {len(self.files_touched)}")
        for fpath in self.files_touched[:10]:
            writers = [e for e in self.writes if e.path == fpath]
            roles   = list({e.role for e in writers})
            print(f"     {fpath}  [{', '.join(roles)}]")
        if len(self.files_touched) > 10:
            print(f"     ... and {len(self.files_touched)-10} more")

        # Blocked
        if self.blocked:
            print(f"\n  🚫 Blocked actions: {len(self.blocked)}")
            for e in self.blocked[:5]:
                print(f"     [{e.role}] tried to {e.action} {e.path or '(unknown)'}")
                reason = e.raw.get("reason", "")
                if reason:
                    print(f"     → {reason[:80]}")
            if len(self.blocked) > 5:
                print(f"     ... and {len(self.blocked)-5} more blocked actions")

        # Violations
        if self.violations:
            print(f"\n  ❌ Violations: {len(self.violations)}")
            for e in self.violations[:5]:
                print(f"     [{e.role}] {e.action} on {e.path or '?'} — BLOCKED")

        # Proposals
        if self.proposals:
            print(f"\n  💡 Proposals: {len(self.proposals)}")
            for e in self.proposals[:5]:
                summary = e.summary or e.raw.get("summary", "")
                if summary:
                    print(f"     [{e.role}] {summary[:80]}")

        # By role summary
        print(f"\n  👥 Activity by role:")
        for role, role_entries in sorted(self.by_role.items()):
            writes_  = sum(1 for e in role_entries if e.action == "write" and e.allowed)
            blocked_ = sum(1 for e in role_entries if e.allowed is False)
            print(f"     {role:15s} {len(role_entries):3d} actions  "
                  f"{writes_:3d} writes  {blocked_:3d} blocked")

        print(f"\n{'─'*60}\n")


# ── Reader ─────────────────────────────────────────────────────

class DiffReader:
    """
    Reads the brain-ctx observability log and produces DiffReports.

    Example:
        reader = DiffReader(Path(".brain-ctx.log"))
        report = reader.since_commit()
        report.print()

        # Or by time window
        from datetime import datetime, timedelta
        since = datetime.now() - timedelta(days=7)
        report = reader.since(since)
        report.print(verbose=True)
    """

    def __init__(
        self,
        log_path: Path = Path(".brain-ctx.log"),
        project_root: Path = Path("."),
    ):
        self.log_path     = log_path
        self.project_root = project_root.resolve()

    def _load_entries(self) -> list[LogEntry]:
        if not self.log_path.exists():
            return []
        entries: list[LogEntry] = []
        for line in self.log_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                entries.append(LogEntry.from_dict(d))
            except json.JSONDecodeError:
                continue
        return sorted(entries, key=lambda e: e.ts)

    def all(self) -> DiffReport:
        """Return diff for all recorded history."""
        entries = self._load_entries()
        return DiffReport(since=None, entries=entries,
                          project_root=self.project_root)

    def since(self, when: datetime) -> DiffReport:
        """Return diff since a specific datetime."""
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        entries = [e for e in self._load_entries() if e.ts >= when]
        return DiffReport(since=when, entries=entries,
                          project_root=self.project_root)

    def since_commit(self) -> DiffReport:
        """
        Return diff since the last git commit.
        Falls back to last 24 hours if git unavailable.
        """
        try:
            import git
            repo        = git.Repo(self.project_root)
            last_commit = list(repo.iter_commits(max_count=1))[0]
            when        = datetime.fromtimestamp(
                last_commit.committed_date, tz=timezone.utc
            )
            return self.since(when)
        except Exception:
            # Fallback: last 24 hours
            from datetime import timedelta
            return self.since(datetime.now(timezone.utc) - timedelta(hours=24))

    def since_hours(self, hours: int) -> DiffReport:
        """Return diff for the last N hours."""
        from datetime import timedelta
        return self.since(datetime.now(timezone.utc) - timedelta(hours=hours))

    def for_session(self, session_id: str) -> DiffReport:
        """Return diff for a specific session ID."""
        entries = [e for e in self._load_entries()
                   if e.session_id.startswith(session_id)]
        return DiffReport(since=None, entries=entries,
                          project_root=self.project_root)

    def for_role(self, role: str) -> DiffReport:
        """Return diff for a specific agent role."""
        entries = [e for e in self._load_entries() if e.role == role]
        return DiffReport(since=None, entries=entries,
                          project_root=self.project_root)

    def violations_only(self) -> DiffReport:
        """Return only blocked/violation entries."""
        entries = [e for e in self._load_entries() if e.allowed is False]
        return DiffReport(since=None, entries=entries,
                          project_root=self.project_root)

    def rotate(self, keep_days: int = 30) -> tuple[int, Path]:
        """
        Archive log entries older than keep_days to .brain-ctx.log.archive.
        Returns (archived_count, archive_path).
        """
        from datetime import timedelta
        cutoff  = datetime.now(timezone.utc) - timedelta(days=keep_days)
        entries = self._load_entries()

        to_keep    = [e for e in entries if e.ts >= cutoff]
        to_archive = [e for e in entries if e.ts <  cutoff]

        if not to_archive:
            return 0, Path(".brain-ctx.log.archive")

        archive_path = self.log_path.parent / ".brain-ctx.log.archive"

        # Append to archive
        with open(archive_path, "a", encoding="utf-8") as f:
            for e in to_archive:
                f.write(json.dumps(e.raw) + "\n")

        # Rewrite current log with only recent entries
        with open(self.log_path, "w", encoding="utf-8") as f:
            for e in to_keep:
                f.write(json.dumps(e.raw) + "\n")

        return len(to_archive), archive_path

    def stats(self) -> dict:
        """Return summary statistics for the entire log."""
        entries = self._load_entries()
        if not entries:
            return {"total": 0}
        return {
            "total":      len(entries),
            "writes":     sum(1 for e in entries if e.action == "write" and e.allowed),
            "blocked":    sum(1 for e in entries if e.allowed is False),
            "proposals":  sum(1 for e in entries if e.action == "propose"),
            "sessions":   len({e.session_id for e in entries}),
            "models":     list({e.model for e in entries}),
            "roles":      list({e.role  for e in entries}),
            "date_range": {
                "from": entries[0].ts.isoformat(),
                "to":   entries[-1].ts.isoformat(),
            },
        }
