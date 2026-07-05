from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


THIS_DIR = Path(__file__).resolve().parent
PYTHON_DIR = THIS_DIR.parents[1]
CASES_DIR = THIS_DIR / "cases"
RESULTS_PATH = THIS_DIR / "code_task_results.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run code-task evals for Mini Claude Code.")
    parser.add_argument("--mode", choices=["agent", "oracle"], default="agent")
    parser.add_argument("--case", default=None, help="Run only one case id.")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--keep-workdirs", action="store_true")
    return parser.parse_args()


def run_command(command: str, cwd: Path, env: dict[str, str] | None = None, timeout: int = 120) -> dict:
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
    )
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def copy_tree(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    for path in src.rglob("*"):
        rel = path.relative_to(src)
        target = dst / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def snapshot_files(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if "__pycache__" in rel or rel.endswith(".pyc"):
            continue
        files[rel] = path.read_text(encoding="utf-8", errors="replace")
    return files


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    names = sorted(set(before) | set(after))
    return [name for name in names if before.get(name) != after.get(name)]


def load_case(case_dir: Path) -> dict:
    test_command = (case_dir / "test_command.txt").read_text(encoding="utf-8").strip()
    prompt = (case_dir / "prompt.txt").read_text(encoding="utf-8").strip()
    expected = (case_dir / "expected.md").read_text(encoding="utf-8").strip()
    return {
        "id": case_dir.name,
        "test_command": test_command.replace("{python}", sys.executable),
        "prompt": prompt,
        "expected": expected,
    }


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def run_agent(case: dict, workdir: Path, max_turns: int) -> dict:
    prompt = (
        "You are running inside a small benchmark repository.\n"
        "Fix the implementation so the tests pass.\n"
        "Rules:\n"
        "- Make the smallest source-code change that satisfies the tests.\n"
        "- Do not modify test files.\n"
        "- Run the test command before finishing.\n\n"
        f"Task:\n{case['prompt']}\n\n"
        f"Test command:\n{case['test_command']}\n"
    )
    command = [
        sys.executable,
        "-m",
        "mini_claude",
        "--accept-edits",
        "--max-turns",
        str(max_turns),
        prompt,
    ]
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PYTHON_DIR) + (os.pathsep + existing if existing else "")
    started = time.time()
    proc = subprocess.run(
        command,
        cwd=str(workdir),
        text=True,
        capture_output=True,
        timeout=600,
        env=env,
    )
    return {
        "returncode": proc.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-6000:],
    }


def run_case(case_dir: Path, mode: str, max_turns: int, keep_workdirs: bool) -> dict:
    case = load_case(case_dir)
    temp_root = Path(tempfile.mkdtemp(prefix=f"{case['id']}-"))
    workdir = temp_root / "repo"
    shutil.copytree(case_dir / "repo", workdir)

    before = snapshot_files(workdir)
    baseline = run_command(case["test_command"], workdir)

    agent_result = None
    if mode == "oracle":
        copy_tree(case_dir / "solution", workdir)
    else:
        if not has_api_key():
            raise RuntimeError("agent mode requires ANTHROPIC_API_KEY or OPENAI_API_KEY")
        agent_result = run_agent(case, workdir, max_turns)

    final = run_command(case["test_command"], workdir)
    after = snapshot_files(workdir)
    changes = changed_files(before, after)
    tests_modified = [name for name in changes if name.startswith("test_") or "/test_" in name]

    payload = {
        "case_id": case["id"],
        "mode": mode,
        "baseline_passed": baseline["passed"],
        "final_passed": final["passed"],
        "baseline": baseline,
        "final": final,
        "agent": agent_result,
        "changed_files": changes,
        "tests_modified": tests_modified,
        "workdir": str(workdir) if keep_workdirs else None,
    }

    if not keep_workdirs:
        shutil.rmtree(temp_root, ignore_errors=True)

    return payload


def main() -> int:
    args = parse_args()
    case_dirs = sorted(p for p in CASES_DIR.iterdir() if p.is_dir())
    if args.case:
        case_dirs = [p for p in case_dirs if p.name == args.case]
    if not case_dirs:
        raise SystemExit("No matching code-task cases found.")

    started = time.time()
    results = []
    for case_dir in case_dirs:
        print(f"Running {case_dir.name} ({args.mode})...")
        result = run_case(case_dir, args.mode, args.max_turns, args.keep_workdirs)
        status = "PASS" if result["final_passed"] else "FAIL"
        print(f"  baseline_passed={result['baseline_passed']} final={status} changed={result['changed_files']}")
        results.append(result)

    passed = sum(1 for r in results if r["final_passed"])
    baseline_failed = sum(1 for r in results if not r["baseline_passed"])
    payload = {
        "mode": args.mode,
        "tasks_run": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4),
        "baseline_failed": baseline_failed,
        "duration_seconds": round(time.time() - started, 3),
        "results": results,
    }
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote code-task eval summary to {RESULTS_PATH}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

