# BioBrain 项目开发规范

## 项目上下文
- **前端**: React (Vite) + TypeScript + Tailwind CSS
- **后端**: Python (FastAPI) + LangGraph (Agent 框架)
- **存储**: Qdrant (向量数据库) + Redis (缓存)

## 命名与编码惯例
1. **Python (后端)**:
   - 变量与函数使用 `snake_case`。
   - 类名使用 `PascalCase`。
   - 必须使用 Type Hints (类型提示)。
2. **TypeScript (前端)**:
   - 组件文件使用 `PascalCase.tsx`。
   - 普通函数与变量使用 `camelCase`。
   - 严禁使用 `any` 类型，必须定义具体的 `interface` 或 `type`。

## 核心优化原则 (必须遵守)
1. **防御性编程与异常处理**:
   - 对外部不稳定调用（如网络请求、第三方 API）必须使用 `try...except` / `try...catch` 并妥善处理降级。
   - 对于系统级或无法局部处理的异常，允许向上抛出（`raise` / `throw`），交由 FastAPI 等全局异常中间件统一处理。严禁使用空的 `except Exception:` 吞没错误。
2. **状态不可变原则 (LangGraph 铁律)**:
   - 在 LangGraph 节点函数中，严禁直接原地修改传入的 `state` 对象（例如禁止 `state["messages"].append()`）。必须将需要更新的字段作为新的字典返回（例如 `return {"messages": [new_msg]}`），交由框架完成状态合并。
3. **逻辑简洁性与文件拆分**:
   - 优先选择简单的逻辑实现，禁止引入复杂的模式（如过度解耦、抽象工厂等）。
   - 普通业务函数尽量控制在 50 行以内。但对于高度聚合的 LangGraph 节点（如包含大段 Prompt 组装）和包含完整 JSX 结构的 React 组件允许适当放宽，禁止为了满足行数限制而进行毫无意义的碎片化拆分。
4. **中文文档化**:
   - 每一处逻辑修改必须在代码上方添加中文注释，解释“为什么要这么做”而非“这段代码做了什么”。
   - 复杂的 LangGraph 节点必须在注释中注明“输入状态”和“预期输出状态”。
5. **不破坏原则**:
   - 禁止删除现有的功能性注释（如包含特殊业务逻辑说明的注释）。
   - 禁止修改 `.env.example` 之外的 `.env` 本地环境配置文件。
   - 修改 API 接口时，必须检查前端对应的 Hook 是否需要同步更新。

## 验证与测试
1. **自我检查**:
   - 每次完成后端修改后，AI 必须尝试运行 `pytest`（如有）或确保终端无语法报错。
   - 每次完成前端修改后，AI 必须运行 `npx tsc --noEmit` 或 `npm run build` 来严格检查 TypeScript 类型与语法错误（仅运行 `npm run dev` 是不够的）。
2. **流程跑通**: 如果修改了 LangGraph 的节点逻辑，必须验证状态机（State）的流转是否依然闭环，避免死循环或断链。

## 常用命令
- 启动后端: `uvicorn api.main:app --reload`
- 启动前端: `cd web && npm run dev`
- 前端类型检查: `cd web && npx tsc --noEmit`
- 依赖安装: `pip install -r requirements.txt` 或 `npm install`

# GitNexus — Code Intelligence

This project is indexed by GitNexus as **notion-prism-react** (1072 symbols, 2537 relationships, 70 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/notion-prism-react/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/notion-prism-react/context` | Codebase overview, check index freshness |
| `gitnexus://repo/notion-prism-react/clusters` | All functional areas |
| `gitnexus://repo/notion-prism-react/processes` | All execution flows |
| `gitnexus://repo/notion-prism-react/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
