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
1. **防御性编程**: 所有的 API 调用、数据库查询、文件读取必须包裹在 `try...except` 或 `try...catch` 中。
2. **逻辑简洁性**:
   - 优先选择简单的逻辑实现，禁止引入复杂的模式（如过度解耦、抽象工厂等）。
   - 单个函数尽量控制在 50 行以内，超过则考虑拆分。
3. **中文文档化**:
   - 每一处逻辑修改必须在代码上方添加中文注释，解释“为什么要这么做”而非“这段代码做了什么”。
   - 复杂的 LangGraph 节点必须在注释中注明“输入状态”和“预期输出状态”。
4. **不破坏原则**:
   - 禁止删除现有的功能性注释（如包含特殊业务逻辑说明的注释）。
   - 禁止修改 `.env.example` 之外的 `.env` 本地环境配置文件。
   - 修改 API 接口时，必须检查前端对应的 Hook 是否需要同步更新。

## 验证与测试
1. **自我检查**: 每次完成修改后，AI 必须尝试运行 `pytest` 或 `npm run dev` 检查是否有语法错误。
2. **流程跑通**: 如果修改了 LangGraph 的节点逻辑，必须验证状态机（State）的流转是否依然闭环。

## 常用命令
- 启动后端: `uvicorn api.main:app --reload`
- 启动前端: `cd web && npm run dev`
- 依赖安装: `pip install -r requirements.txt` 或 `npm install`
