"""
vector/splitter.py
[Level-Chunk Upgrade]
文本切分器 (The Butcher's Knife)
负责将长文本切分成适合向量检索的小块 (Child Chunks)
"""
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- 切分策略配置 ---
# 1. chunk_size=500:
#    这就好比发微博。500字大约是一段完整的论述。
#    切太小（100字）：语义破碎，AI 看不懂。
#    切太大（1000字）：包含太多杂音，向量不精准。
#
# 2. chunk_overlap=50:
#    重叠部分。防止一句话正好被切在两块中间，导致关键词断裂。
# --------------------

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    # 优先按段落切，其次按句子切，最后按字切
    separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""],
)


def split_text(text: str) -> list[str]:
    """
    输入：一篇长文 (Parent Document)
    输出：一堆碎片 (Child Chunks)
    """
    if not text:
        return []

    # 使用 LangChain 的递归切分器
    chunks = _splitter.split_text(text)

    # 过滤掉过短的碎片（比如只有 2 个字的标题残留）
    return [c for c in chunks if len(c) > 5]


if __name__ == "__main__":
    # 测试一下
    text = "Exocortex 是一个先进的系统。\n\n它采用前后端分离架构。"
    print(split_text(text))
