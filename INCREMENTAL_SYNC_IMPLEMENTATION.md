# 增量同步和去重功能实现总结

## 📋 实现概述

已成功实现 Notion 数据的增量同步和去重检查功能，避免每次启动时重复同步所有数据。

## ✨ 主要改进

### 1. 同步状态跟踪 (`vector/doc_store.py`)

**新增功能：**
- `sync_status` 表：记录每个已同步的 `page_id` 和同步时间
- `sync_metadata` 表：记录最后一次全量同步的时间戳

**新增方法：**
```python
is_page_synced(page_id: str) -> bool              # 检查页面是否已同步
mark_page_synced(page_id: str, source: str)       # 标记页面为已同步
get_synced_page_ids(source: str) -> set           # 获取所有已同步的页面 ID
get_last_full_sync_time() -> Optional[str]        # 获取最后同步时间
update_last_full_sync_time()                      # 更新最后同步时间
```

### 2. 去重检查 (`vector/vector_store.py`)

**新增功能：**
- `page_exists()` 方法：检查页面是否已存在于向量库中
- `add_memory()` 方法新增 `skip_if_exists` 参数：支持跳过已存在的页面
- 自动删除已存在的 chunk：更新时先删除旧的 chunk，再添加新的

**改进逻辑：**
```python
# 如果 skip_if_exists=True 且页面已存在，则跳过
if skip_if_exists and self.page_exists(page_id):
    return False

# 更新时先删除已存在的 chunk
existing_chunks = self.collection.get(ids=[chunk_id for chunk_id in ids])
if existing_chunks.get("ids"):
    self.collection.delete(ids=existing_chunks["ids"])
```

### 3. 增量同步逻辑 (`server.py`)

**自动同步任务 (`auto_sync_scheduler`)：**
- ✅ 获取已同步的页面 ID 列表
- ✅ 只处理新页面或需要更新的页面
- ✅ 统计新增、更新、跳过的数量
- ✅ 自动标记页面为已同步
- ✅ 更新最后一次同步时间

**手动同步接口 (`/sync_notion`)：**
- ✅ 同样支持增量同步
- ✅ 返回详细的统计信息

## 🔄 工作流程

### 首次启动（全量同步）
```
启动 → 等待30秒 → 获取所有 Notion 页面 → 全部同步 → 标记为已同步
```

### 后续启动（增量同步）
```
启动 → 等待30秒 → 获取已同步页面列表 → 获取所有 Notion 页面
→ 过滤出新页面 → 只同步新页面 → 标记为已同步 → 更新同步时间
```

### 更新已存在页面
```
检查页面是否已存在 → 删除旧的 chunk → 添加新的 chunk → 更新父文档
```

## 📊 统计信息

同步完成后会显示详细的统计信息：
```
✅ [Scheduler] 增量同步完成:
   新增 5 条, 更新 2 条, 跳过 0 条, 总计 7 条内容。
```

## 🎯 优势

1. **性能提升**
   - 只同步新内容，减少 API 调用
   - 避免重复索引，节省计算资源
   - 大幅缩短同步时间

2. **API 限制保护**
   - 减少对 Notion API 的请求次数
   - 降低触发速率限制的风险

3. **数据一致性**
   - 支持内容更新（如果 Notion 中内容变化）
   - 自动删除旧的 chunk，避免重复数据

4. **可观测性**
   - 详细的日志记录
   - 清晰的统计信息
   - 便于监控和调试

## 🔍 代码示例

### 检查页面是否已同步
```python
from vector.doc_store import DOC_STORE

if DOC_STORE.is_page_synced(page_id):
    print("页面已同步，跳过")
```

### 手动标记页面已同步
```python
DOC_STORE.mark_page_synced(page_id, source="notion")
```

### 获取所有已同步的页面
```python
synced_ids = DOC_STORE.get_synced_page_ids(source="notion")
print(f"已同步 {len(synced_ids)} 个页面")
```

### 使用去重检查
```python
# 跳过已存在的页面
success = vector_store.add_memory(
    page_id=page_id,
    text=content,
    skip_if_exists=True  # 如果已存在则跳过
)

# 允许更新已存在的页面
success = vector_store.add_memory(
    page_id=page_id,
    text=content,
    skip_if_exists=False  # 即使存在也更新
)
```

## 📝 数据库结构

### sync_status 表
| 字段 | 类型 | 说明 |
|------|------|------|
| page_id | TEXT PRIMARY KEY | Notion 页面 ID |
| last_synced_at | TEXT | 最后同步时间（ISO 格式） |
| source | TEXT | 数据源（默认 "notion"） |

### sync_metadata 表
| 字段 | 类型 | 说明 |
|------|------|------|
| key | TEXT PRIMARY KEY | 元数据键（如 "last_full_sync"） |
| value | TEXT | 元数据值（如时间戳） |

## ⚠️ 注意事项

1. **首次同步**
   - 首次运行时，所有页面都会被视为新页面
   - 会执行全量同步

2. **内容更新**
   - 如果 Notion 中页面内容已更新，下次同步时会更新向量库
   - 旧的 chunk 会被删除，新的会被添加

3. **数据清理**
   - `sync_status` 表中的记录会一直保留
   - 如需清理，可以手动删除不需要的记录

## 🚀 使用建议

1. **监控同步日志**
   - 观察新增、更新、跳过的数量
   - 确保同步正常工作

2. **定期检查同步状态**
   - 使用 `get_synced_page_ids()` 查看已同步的页面
   - 验证同步是否完整

3. **手动触发同步**
   - 可通过 `/sync_notion` API 手动触发同步
   - 查看返回的统计信息

## 📚 相关文件

- `vector/doc_store.py` - 同步状态跟踪
- `vector/vector_store.py` - 去重检查和向量存储
- `server.py` - 自动同步逻辑

---

**实现日期**: 2026-01-16
**状态**: ✅ 已完成并通过测试
