# Notion 自动同步行为说明

## 📋 当前行为

**是的，每次运行 `docker-compose up -d --build exocortex` 时，系统会在启动30秒后自动从 Notion 抓取一次数据。**

## 🔍 详细流程

### 1. 启动时序

```
docker-compose up -d --build exocortex
  ↓
FastAPI 应用启动
  ↓
@app.on_event("startup") 触发 (server.py:542)
  ↓
启动后台任务: auto_sync_scheduler()
  ↓
等待 30 秒
  ↓
第一次同步执行: 从 Notion 抓取所有西语数据库内容
  ↓
将数据写入向量库 (SQLite + ChromaDB)
  ↓
之后每 24 小时自动同步一次
```

### 2. 代码位置

**启动事件** (`server.py:542-545`)
```python
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(auto_sync_scheduler())
    logger.info("🚀 [System] 自动同步任务已挂载，将每隔 1 小时自动检查 Notion。")
```

**自动同步逻辑** (`server.py:510-539`)
```python
async def auto_sync_scheduler():
    await asyncio.sleep(30)  # 等待 30 秒
    while True:
        try:
            # 从 Notion 抓取所有页面
            pages = service.fetch_database_content(config.DB_SPANISH_ID)

            if pages:
                for page in pages:
                    await asyncio.sleep(1.5)  # 限流保护
                    # 写入向量库
                    vs.add_memory(...)

            await asyncio.sleep(86400)  # 24 小时后再次同步
        except Exception as e:
            await asyncio.sleep(300)  # 出错后 5 分钟重试
```

## ⚠️ 潜在问题

### 1. 重复索引问题

- **SQLite (父文档)**: ✅ 有去重
  - 使用 `REPLACE INTO`，相同 `doc_id` 会被替换

- **ChromaDB (向量)**: ⚠️ 可能重复
  - 使用 `collection.add(ids=ids, ...)`
  - 如果相同的 `chunk_id` (如 `{page_id}_chunk_0`) 已存在，ChromaDB 的行为取决于配置
  - 可能会创建重复的向量条目

### 2. 性能问题

- 每次启动都要等待 30 秒
- 如果 Notion 数据库很大，同步过程可能很长
- 每个页面写入前等待 1.5 秒（限流保护），大量页面会耗时

### 3. API 限制

- Notion API 有速率限制（RPM - Requests Per Minute）
- 虽然代码中加了限流保护（1.5秒/页），但每次启动都全量同步可能触发限制

## 💡 改进建议

### 方案 1: 增量同步（推荐）

只在有新内容或内容更新时才同步：

```python
async def auto_sync_scheduler():
    await asyncio.sleep(30)
    last_sync_time = get_last_sync_time()  # 从数据库读取

    while True:
        try:
            # 只获取 last_sync_time 之后更新的页面
            pages = service.fetch_database_content_since(
                config.DB_SPANISH_ID,
                last_sync_time
            )

            if pages:
                for page in pages:
                    # 检查是否已存在
                    if not vector_store.page_exists(page["id"]):
                        await asyncio.sleep(1.5)
                        vs.add_memory(...)

            update_last_sync_time()  # 更新同步时间
            await asyncio.sleep(86400)
        except Exception as e:
            await asyncio.sleep(300)
```

### 方案 2: 跳过启动时首次同步

通过环境变量控制：

```python
SKIP_INITIAL_SYNC = os.getenv("SKIP_INITIAL_SYNC", "false").lower() == "true"

@app.on_event("startup")
async def startup_event():
    if not SKIP_INITIAL_SYNC:
        asyncio.create_task(auto_sync_scheduler())
    else:
        logger.info("⏭️ [System] 跳过启动时自动同步（已通过环境变量禁用）")
```

### 方案 3: 手动触发同步

禁用自动同步，改为手动调用 `/sync_notion` API：

```python
# 移除或注释掉 startup_event 中的自动同步
# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(auto_sync_scheduler())
```

然后通过 API 手动触发：
```bash
curl -X POST http://localhost:8000/sync_notion \
  -H "Authorization: Bearer YOUR_API_SECRET"
```

## 📝 当前配置总结

- ✅ 每次启动后 30 秒自动同步
- ✅ 之后每 24 小时自动同步一次
- ⚠️ 没有增量同步机制
- ⚠️ 没有去重检查（对 ChromaDB 向量）
- ✅ 有限流保护（1.5秒/页）
- ✅ 有错误重试机制（出错后 5 分钟重试）

## 🎯 建议

如果 Notion 数据库很大或更新频繁，建议：
1. 实现增量同步机制
2. 添加 ChromaDB 去重检查
3. 或禁用启动时自动同步，改为手动触发
