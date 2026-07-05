# Code Task Evals

这套评测用来衡量 Coding Agent 是否真的能完成“改代码”任务，而不只是验证权限、工具、上下文压缩这些机制是否存在。

它分成两种运行模式：

- `agent`：让 Mini Claude Code 真实接手一个带 bug 的小仓库，根据 `prompt.txt` 修改代码，然后运行测试判断是否通过。
- `oracle`：不调用大模型，直接把 `solution/` 里的标准答案覆盖到临时仓库，再运行测试。这个模式用来验证 benchmark case 本身是否合理。

## 如何运行

在仓库根目录运行：

```bash
python python/evals/code_tasks/run_code_task_evals.py --mode oracle
```

如果要评测真实 Agent，需要先配置 API Key，然后运行：

```bash
python python/evals/code_tasks/run_code_task_evals.py --mode agent --max-turns 12
```

OpenAI 兼容后端示例：

```bash
set OPENAI_API_KEY=sk-xxx
set OPENAI_BASE_URL=https://api.openai.com/v1
set MINI_CLAUDE_MODEL=gpt-4o
python python/evals/code_tasks/run_code_task_evals.py --mode agent --max-turns 12
```

Anthropic 后端示例：

```bash
set ANTHROPIC_API_KEY=sk-ant-xxx
set MINI_CLAUDE_MODEL=claude-sonnet-4-6
python python/evals/code_tasks/run_code_task_evals.py --mode agent --max-turns 12
```

## 评测结果

运行后会生成：

```text
python/evals/code_tasks/code_task_results.json
```

核心指标包括：

- `tasks_run`：任务数量；
- `passed`：最终测试通过的任务数；
- `pass_rate`：任务通过率；
- `baseline_failed`：初始仓库中测试失败的任务数，证明任务确实有 bug；
- `tests_modified`：Agent 是否修改了测试文件；
- `changed_files`：Agent 修改了哪些源码文件；
- `duration_seconds`：每个任务耗时。

## 当前任务集

- `case_001_average_empty_input`：修复 `average([])` 的边界处理。
- `case_002_slugify_normalization`：修复 slug 生成中的空白、标点和大小写处理。
- `case_003_frontmatter_colon_values`：修复 frontmatter 解析中 value 含冒号、缺少闭合符等情况。

这些任务都很小，目的是先建立一个稳定、低成本、可解释的本地代码任务 benchmark。后续可以继续扩展到真实项目函数、跨文件修改、CLI 行为修复等任务。

