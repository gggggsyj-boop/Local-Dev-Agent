from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


PYTHON_DIR = Path(__file__).resolve().parents[1]
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from mini_claude import agent, frontmatter, memory, tools  # noqa: E402


class TempWorkspace:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.home.mkdir()
        self.project.mkdir()
        self.old_cwd = Path.cwd()

    def __enter__(self):
        os.chdir(self.project)
        return self

    def __exit__(self, exc_type, exc, tb):
        os.chdir(self.old_cwd)
        self.tmp.cleanup()


class ToolSafetyEval(unittest.TestCase):
    def setUp(self) -> None:
        tools.reset_activated_tools()
        tools.reset_permission_cache()

    def test_deferred_tools_are_hidden_until_tool_search(self):
        active_names = {t["name"] for t in tools.get_active_tool_definitions()}
        self.assertNotIn("enter_plan_mode", active_names)
        self.assertNotIn("exit_plan_mode", active_names)
        self.assertIn("enter_plan_mode", tools.get_deferred_tool_names())

        result = asyncio.run(tools.execute_tool("tool_search", {"query": "plan"}, {}))
        self.assertIn("enter_plan_mode", result)

        active_names = {t["name"] for t in tools.get_active_tool_definitions()}
        self.assertIn("enter_plan_mode", active_names)
        self.assertIn("exit_plan_mode", active_names)

    def test_permission_modes_block_or_allow_risky_actions(self):
        with TempWorkspace() as ws, patch.object(tools.Path, "home", return_value=ws.home):
            dangerous = tools.check_permission("run_shell", {"command": "rm -rf build"}, "default")
            self.assertEqual(dangerous["action"], "confirm")

            dont_ask = tools.check_permission("run_shell", {"command": "rm -rf build"}, "dontAsk")
            self.assertEqual(dont_ask["action"], "deny")

            plan_shell = tools.check_permission("run_shell", {"command": "pytest"}, "plan")
            self.assertEqual(plan_shell["action"], "deny")

            read_file = tools.check_permission("read_file", {"file_path": "app.py"}, "plan")
            self.assertEqual(read_file["action"], "allow")

            bypass = tools.check_permission("run_shell", {"command": "rm -rf build"}, "bypassPermissions")
            self.assertEqual(bypass["action"], "allow")

    def test_project_permission_rules_take_precedence(self):
        with TempWorkspace() as ws, patch.object(tools.Path, "home", return_value=ws.home):
            settings_dir = ws.project / ".claude"
            settings_dir.mkdir()
            (settings_dir / "settings.json").write_text(
                '{"permissions": {"allow": ["run_shell(pytest*)"], "deny": ["write_file(secret*)"]}}',
                encoding="utf-8",
            )
            tools.reset_permission_cache()

            allowed = tools.check_permission("run_shell", {"command": "pytest -q"}, "default")
            denied = tools.check_permission("write_file", {"file_path": "secret.txt"}, "acceptEdits")

            self.assertEqual(allowed["action"], "allow")
            self.assertEqual(denied["action"], "deny")

    def test_read_before_edit_blocks_stale_or_unread_edits(self):
        with TempWorkspace():
            target = Path("example.py")
            target.write_text("value = 1\n", encoding="utf-8")
            state: dict[str, float] = {}

            unread = asyncio.run(
                tools.execute_tool(
                    "edit_file",
                    {"file_path": str(target), "old_string": "value = 1", "new_string": "value = 2"},
                    state,
                )
            )
            self.assertIn("must read this file", unread)

            read_result = asyncio.run(tools.execute_tool("read_file", {"file_path": str(target)}, state))
            self.assertIn("value = 1", read_result)

            edited = asyncio.run(
                tools.execute_tool(
                    "edit_file",
                    {"file_path": str(target), "old_string": "value = 1", "new_string": "value = 2"},
                    state,
                )
            )
            self.assertIn("Successfully edited", edited)
            self.assertIn("value = 2", target.read_text(encoding="utf-8"))

            asyncio.run(tools.execute_tool("read_file", {"file_path": str(target)}, state))
            time.sleep(0.02)
            target.write_text("value = 3\n", encoding="utf-8")

            stale = asyncio.run(
                tools.execute_tool(
                    "edit_file",
                    {"file_path": str(target), "old_string": "value = 3", "new_string": "value = 4"},
                    state,
                )
            )
            self.assertIn("modified externally", stale)

    def test_tool_result_truncation_preserves_head_tail_and_marker(self):
        result = "A" * 30000 + "MIDDLE" + "Z" * 30000
        truncated = tools._truncate_result(result)

        self.assertLessEqual(len(truncated), tools.MAX_RESULT_CHARS + 80)
        self.assertIn("truncated", truncated)
        self.assertTrue(truncated.startswith("A" * 100))
        self.assertTrue(truncated.endswith("Z" * 100))
        self.assertNotIn("MIDDLE", truncated)


class ContextCompressionEval(unittest.TestCase):
    def _fake_openai_agent(self):
        fake = object.__new__(agent.Agent)
        fake.use_openai = True
        fake.effective_window = 1000
        fake.last_input_token_count = 800
        fake.last_api_call_time = 0
        fake._openai_messages = []
        return fake

    def test_budget_tool_results_shortens_large_outputs(self):
        fake = self._fake_openai_agent()
        fake.effective_window = 1000
        fake.last_input_token_count = 800
        fake._openai_messages = [
            {"role": "system", "content": "system"},
            {"role": "tool", "tool_call_id": "1", "content": "A" * 40000},
        ]

        agent.Agent._budget_tool_results_openai(fake)

        content = fake._openai_messages[1]["content"]
        self.assertLess(len(content), 16000)
        self.assertIn("budgeted", content)

    def test_snip_stale_results_keeps_recent_tool_results(self):
        fake = self._fake_openai_agent()
        fake.last_input_token_count = 700
        fake._openai_messages = [{"role": "system", "content": "system"}]
        for i in range(6):
            fake._openai_messages.append({"role": "tool", "tool_call_id": str(i), "content": f"result-{i}"})

        agent.Agent._snip_stale_results_openai(fake)

        contents = [m["content"] for m in fake._openai_messages if m.get("role") == "tool"]
        self.assertEqual(contents[:3], [agent.SNIP_PLACEHOLDER] * 3)
        self.assertEqual(contents[-3:], ["result-3", "result-4", "result-5"])

    def test_microcompact_clears_old_results_after_idle_window(self):
        fake = self._fake_openai_agent()
        fake.last_api_call_time = time.time() - agent.MICROCOMPACT_IDLE_S - 1
        fake._openai_messages = [{"role": "system", "content": "system"}]
        for i in range(5):
            fake._openai_messages.append({"role": "tool", "tool_call_id": str(i), "content": f"old-result-{i}"})

        agent.Agent._microcompact_openai(fake)

        contents = [m["content"] for m in fake._openai_messages if m.get("role") == "tool"]
        self.assertEqual(contents[:2], ["[Old result cleared]", "[Old result cleared]"])
        self.assertEqual(contents[-3:], ["old-result-2", "old-result-3", "old-result-4"])

    def test_large_result_persistence_writes_full_output_and_keeps_preview(self):
        fake = self._fake_openai_agent()
        with TempWorkspace() as ws, patch.object(agent.Path, "home", return_value=ws.home):
            large = "\n".join(f"line-{i}" for i in range(5000))
            result = agent.Agent._persist_large_result(fake, "run_shell", large)

            self.assertIn("Result too large", result)
            self.assertIn("Full output saved to", result)
            self.assertIn("Preview (first 200 lines)", result)
            saved = list((ws.home / ".mini-claude" / "tool-results").glob("*-run_shell.txt"))
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].read_text(encoding="utf-8"), large)


class MemoryAndParsingEval(unittest.TestCase):
    def test_frontmatter_round_trip(self):
        content = frontmatter.format_frontmatter(
            {"name": "Repo convention", "type": "project", "description": "Coding style"},
            "Use pathlib for file paths.",
        )
        parsed = frontmatter.parse_frontmatter(content)

        self.assertEqual(parsed.meta["name"], "Repo convention")
        self.assertEqual(parsed.meta["type"], "project")
        self.assertEqual(parsed.body, "Use pathlib for file paths.")

    def test_memory_crud_updates_index(self):
        with TempWorkspace() as ws, patch.object(memory.Path, "home", return_value=ws.home):
            filename = memory.save_memory(
                "Project Style",
                "How this repo formats code",
                "project",
                "Prefer small modules and explicit tool schemas.",
            )

            entries = memory.list_memories()
            index = memory.load_memory_index()

            self.assertEqual(filename, "project_project_style.md")
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].name, "Project Style")
            self.assertIn("Project Style", index)

            self.assertTrue(memory.delete_memory(filename))
            self.assertEqual(memory.list_memories(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

