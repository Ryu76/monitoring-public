from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / "PROGRESS.md"
REPORTS = ROOT / "reports"


def git_status_summary(repository: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "status", "--short"],
        text=True,
        capture_output=True,
        check=False,
    )
    entries = [line for line in result.stdout.splitlines() if line.strip()]
    return "clean" if not entries else f"{len(entries)} changed path(s)"


def worktree_summaries() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "worktree", "list", "--porcelain"],
        text=True,
        capture_output=True,
        check=False,
    )
    worktrees = [Path(line[9:]) for line in result.stdout.splitlines() if line.startswith("worktree ")]
    return [f"- {path}: {git_status_summary(path)}" for path in worktrees]


def latest_progress() -> str:
    if not PROGRESS.exists():
        return "PROGRESS.md 없음"
    lines = [line.rstrip() for line in PROGRESS.read_text(encoding="utf-8").splitlines()]
    selected = [line for line in lines if line.startswith(("- ", "1. ", "2. ", "3. ", "4. "))]
    return "\n".join(selected[-12:]) or "기록된 세부 항목 없음"


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    status = git_status_summary(ROOT)
    worktrees = "\n".join(worktree_summaries())
    details = latest_progress()
    report = (
        f"# 통합 관제 시간별 작업 보고\n\n"
        f"- 시각: {now:%Y-%m-%d %H:%M:%S %Z}\n"
        f"- 기본 worktree Git 상태: {status}\n\n"
        f"## Worktree 상태\n\n{worktrees}\n\n"
        f"## 현재 기록\n\n{details}\n"
    )
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"progress-{now:%Y%m%d-%H00}.md"
    path.write_text(report, encoding="utf-8")
    print(f"[통합 관제 시간별 보고 | {now:%m-%d %H:%M KST}]")
    print(f"기본 worktree Git: {status}")
    print(worktrees)
    print(details)
    print(f"보고서: {path}")


if __name__ == "__main__":
    main()
