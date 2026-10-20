#!/usr/bin/env python3
"""Series selection in next_lts_canary.sh.

The canary must replay exactly the LibreEcho commits: not upstream commits
brought in by stable merges, and not nothing when our commits arrive through
a merged pull request (their merge commit's first parent is the old main).
"""

from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parent / "next_lts_canary.sh"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@invalid",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@invalid",
            "PATH": "/usr/bin:/bin",
        },
    ).stdout.strip()


def commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name + "\n")
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD")


def set_sublevel(repo: Path, sublevel: int) -> None:
    (repo / "Makefile").write_text(
        f"kernelversion:\n\t@echo 6.1.{sublevel}\n"
    )
    git(repo, "add", "Makefile")


class SeriesSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(self.repo, "init", "-q", "-b", "main")
        set_sublevel(self.repo, 178)
        git(self.repo, "commit", "-q", "-m", "Linux 6.1.178")
        git(self.repo, "tag", "v6.1.178")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def series(self) -> list:
        out = subprocess.run(
            ["bash", str(SCRIPT), "--list-series"],
            cwd=self.repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        return out.split()

    def test_commits_from_a_merged_pull_request_are_selected(self) -> None:
        git(self.repo, "checkout", "-q", "-b", "feature/x")
        ours = [commit(self.repo, "a"), commit(self.repo, "b")]
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "Merge PR", "feature/x")
        self.assertEqual(self.series(), ours)

    def test_upstream_commits_from_a_stable_merge_are_excluded(self) -> None:
        ours = [commit(self.repo, "a")]
        git(self.repo, "checkout", "-q", "-b", "stable", "v6.1.178")
        commit(self.repo, "upstream-fix")
        set_sublevel(self.repo, 179)
        git(self.repo, "commit", "-q", "-m", "Linux 6.1.179")
        git(self.repo, "tag", "v6.1.179")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "-X", "theirs", "-m", "Merge v6.1.179", "v6.1.179")
        ours.append(commit(self.repo, "b"))
        self.assertEqual(self.series(), ours)

    def test_subtree_squash_commits_are_skipped(self) -> None:
        ours = [commit(self.repo, "a")]
        git(self.repo, "checkout", "-q", "--orphan", "squash")
        git(self.repo, "rm", "-q", "-rf", ".")
        commit(self.repo, "Kbuild")
        git(
            self.repo, "commit", "-q", "--amend", "-m",
            "Squashed 'sub/' content\n\ngit-subtree-dir: sub\ngit-subtree-split: 0",
        )
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--allow-unrelated-histories", "-m", "Add sub", "squash")
        ours.append(commit(self.repo, "b"))
        self.assertEqual(self.series(), ours)


if __name__ == "__main__":
    unittest.main()
