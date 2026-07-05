# Mini Claude Code Python 轻量评测

这个目录补的是项目机制评测，不是大模型能力评测。它的目标是证明 Mini Claude Code 的核心工程机制确实生效：工具可控、权限可控、编辑前先读、上下文结果可压缩、记忆索引可维护。

## 为什么先做这些评测

Agent 项目如果只写“实现了 Agent Loop / Tool Calling / Memory / Context Compression”，简历会像技术点罗列。更有说服力的写法应该是：

- 为了解决什么问题；
- 用什么机制解决；
- 如何验证这个机制确实工作。

本目录中的自动评测覆盖不需要真实 LLM API 的确定性逻辑，运行稳定、成本为 0，适合作为第一版 benchmark。

## 评测范围

当前自动评测覆盖：

- 工具 schema 与延迟工具激活：`tool_search` 激活 `enter_plan_mode` / `exit_plan_mode`。
- 权限控制：默认模式、`dontAsk`、`plan`、`bypassPermissions`、项目级 allow/deny 规则。
- Read Before Edit：未读文件禁止编辑，读后允许编辑，文件外部变化后要求重新读取。
- 工具结果截断：超长结果保留头尾并插入截断提示。
- 上下文压缩：预算截断、旧工具结果 snip、空闲 microcompact。
- 大工具结果落盘：超过阈值的结果保存到本地文件，消息上下文只保留路径和预览。
- Frontmatter 与 Memory：解析 frontmatter、保存 memory、更新 `MEMORY.md` 索引、删除 memory。

## 如何运行

在项目根目录执行：

```bash
cd python
python evals/run_evals.py
```

或者从仓库根目录执行：

```bash
python python/evals/run_evals.py
```

运行结束后会生成：

```text
python/evals/eval_results.json
```

这个文件记录测试是否通过、测试数量、失败数量、耗时和覆盖范围。

## 目前不测什么

这套评测暂时不测：

- 真实模型回答质量；
- SWE-bench 级别的代码修复能力；
- 不同模型之间的任务成功率；
- 真实 token 消耗统计。

这些属于第二阶段评测，需要稳定的 API Key、固定模型、固定任务集和多次重复实验。当前这版先验证项目自己的工程机制，避免把“模型强不强”和“框架设计是否生效”混在一起。

## 可以写进简历的表达

如果这些评测通过，可以在简历项目中补一句：

```text
构建轻量级机制评测集，覆盖权限拦截、read-before-edit、上下文压缩、工具结果落盘和 memory 索引等核心链路，用于验证 Agent 在本地开发任务中的安全性与上下文稳定性。
```

