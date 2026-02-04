"""
tools/validation.py
工具参数运行时验证 - 防止AI编造内容的最后一道防线

使用方法：
    from tools.validation import validate_notion_params

    @tool
    async def manage_notion_note(...):
        # 在工具函数开头添加验证
        validation_error = validate_notion_params(
            content_markdown=content_markdown,
            title=title
        )
        if validation_error:
            return validation_error  # 返回错误消息，不执行工具

        # ... 原有逻辑
"""

import re
from typing import Optional


def validate_notion_params(
    content_markdown: str,
    title: str,
    action: str = "create",
    min_content_length: int = 10,
) -> Optional[str]:
    """
    验证 Notion 工具参数，防止AI编造内容

    Args:
        content_markdown: 笔记内容
        title: 笔记标题
        action: 操作类型 (create/overwrite)
        min_content_length: 最小内容长度（字符数）

    Returns:
        如果验证失败，返回错误消息字符串
        如果验证通过，返回 None
    """

    # ===================================================================
    # 检查 1: 内容长度
    # ===================================================================
    if not content_markdown or len(content_markdown.strip()) < min_content_length:
        return (
            f"❌ 参数验证失败：内容太短（<{min_content_length}字符）。\n"
            f"请提供实际要保存的内容，而不是占位符。\n"
            f"如果你不确定要保存什么，请询问用户。"
        )

    # ===================================================================
    # 检查 2: 通用占位符模式
    # ===================================================================
    PLACEHOLDER_PATTERNS = [
        r"placeholder",
        r"example content",
        r"sample text",
        r"lorem ipsum",
        r"test content",
        r"待补充",
        r"稍后填写",
        r"TODO",
        r"\[content here\]",
        r"\[insert.*here\]",
    ]

    content_lower = content_markdown.lower()
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            return (
                f"❌ 检测到占位符内容：'{pattern}'\n"
                f"请提供用户的实际内容，而不是示例或占位符。\n"
                f"如果用户没有提供具体内容，请先询问他们想要保存什么。"
            )

    # ===================================================================
    # 检查 3: AI 常见的编造模式
    # ===================================================================
    # AI 经常生成这种格式："# Topic\n- Example 1\n- Example 2"
    # 如果用户只说了 topic 没说 examples，这就是编造

    # 启发式检测：内容是否过于"结构化"且简短
    lines = content_markdown.strip().split("\n")
    if len(lines) <= 5:  # 短内容更可能是编造
        # 检查是否全是标题+列表项（没有实际解释）
        has_header = any(line.strip().startswith("#") for line in lines)
        list_items = sum(
            1 for line in lines if line.strip().startswith(("-", "*", "•"))
        )

        if has_header and list_items >= 2:
            # 进一步检查：列表项是否过于简单（无解释）
            simple_items = 0
            for line in lines:
                if line.strip().startswith(("-", "*", "•")):
                    # 移除列表符号后
                    item_content = re.sub(r"^[-*•]\s*", "", line.strip())
                    # 如果列表项少于15个字符，且没有冒号/句号，可能是编造
                    if (
                        len(item_content) < 15
                        and ":" not in item_content
                        and "。" not in item_content
                    ):
                        simple_items += 1

            if simple_items >= 2:
                return (
                    "⚠️ 内容可能过于简化（标题+简短列表项，无详细说明）。\n"
                    + "这看起来像是AI生成的示例框架，而不是用户的实际内容。\n\n"
                    + "请确认：\n"
                    + "1. 用户是否提供了这些具体的列表项？\n"
                    + "2. 是否遗漏了用户提供的详细说明或例句？\n\n"
                    + "如果用户只提供了主题但没有细节，请先询问他们想要记录哪些具体信息。"
                )

    # ===================================================================
    # 检查 4: 标题验证
    # ===================================================================
    if not title or len(title.strip()) < 2:
        return "❌ 标题不能为空或过短。\n" + "请提供一个有意义的标题，或询问用户他们希望如何命名这个笔记。"

    # 检查标题是否是占位符
    title_lower = title.lower().strip()
    if title_lower in ["untitled", "new note", "note", "test", "新笔记", "无标题"]:
        return f"❌ 标题 '{title}' 看起来像占位符。\n" f"请使用描述实际内容的标题，或询问用户想要什么标题。"

    # ===================================================================
    # 检查 5: 元数据泄露（AI 常见错误）
    # ===================================================================
    # AI 有时会把 title/summary 写进 content 里
    if re.search(r"^(title|标题):\s*", content_markdown, re.IGNORECASE | re.MULTILINE):
        return (
            "⚠️ 内容中包含 'Title:' 字段，这是元数据泄露。\n"
            + "请只保存笔记正文，不要包含 'Title:', 'Summary:' 等元数据标签。"
        )

    # ===================================================================
    # 所有检查通过
    # ===================================================================
    return None


def suggest_content_request(user_message: str) -> str:
    """
    根据用户消息生成"请提供内容"的友好提示

    Args:
        user_message: 用户的原始消息

    Returns:
        给AI的建议回复文本
    """
    # 提取用户提到的主题（如果有）
    topic_match = re.search(
        r"(?:about|关于|记录|保存)\s+(.{3,30})", user_message, re.IGNORECASE
    )
    topic = topic_match.group(1) if topic_match else "这个主题"

    return f"""我很乐意帮你保存关于 **{topic}** 的笔记！

为了确保笔记的质量和准确性，我需要你提供具体的内容。请告诉我：

**📝 你想记录什么信息？** 例如：
- 定义和概念说明
- 具体的例句或示例
- 使用场景和注意事项
- 你的个人理解或总结

你可以直接粘贴文本，或者告诉我你想要包含哪些要点，我会帮你整理成结构化的笔记。

💡 **提示**：内容越详细，未来检索和复习时就越有价值！"""


# ===================================================================
# 使用示例（供开发者参考）
# ===================================================================
if __name__ == "__main__":
    # 测试用例
    test_cases = [
        {
            "content": "Placeholder content",
            "title": "Test Note",
            "should_fail": True,
            "reason": "包含占位符",
        },
        {
            "content": "# Spanish Verbs\n- Hablar\n- Comer\n- Vivir",
            "title": "Verbs",
            "should_fail": True,
            "reason": "过于简化的列表（AI可能编造）",
        },
        {
            "content": "# Spanish Subjunctive\n\n虚拟式用于表达不确定的事情。\n\n**例句**：\n- Quiero que vengas. (I want you to come.)\n- Es importante que estudies. (It's important that you study.)\n\n**规则**：在表达愿望、建议、怀疑时使用。",
            "title": "Spanish Subjunctive Rules",
            "should_fail": False,
            "reason": "详细内容，包含解释和例句",
        },
        {
            "content": "Title: My Note\n\nSome content",
            "title": "Test",
            "should_fail": True,
            "reason": "元数据泄露",
        },
        {"content": "Short", "title": "Test", "should_fail": True, "reason": "内容过短"},
    ]

    print("运行验证测试...\n")
    for i, case in enumerate(test_cases, 1):
        result = validate_notion_params(
            content_markdown=case["content"], title=case["title"]
        )

        passed = (result is not None) == case["should_fail"]
        status = "✅ PASS" if passed else "❌ FAIL"

        print(f"Test {i}: {status}")
        print(f"  原因: {case['reason']}")
        if result:
            print(f"  验证消息: {result[:100]}...")
        print()
