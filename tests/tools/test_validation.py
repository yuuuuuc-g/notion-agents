"""
tests/tools/test_validation.py
测试参数验证器 - 防止AI编造内容
版本: v1.1 - 修复误判问题

修复记录:
- 使用非占位符标题（避免 "Test" 被误判）
- 调整真实内容测试用例（符合新的 TODO 检测规则）
- 更新集成测试数据
"""
import pytest

from tools.validation import suggest_content_request, validate_notion_params


class TestContentLengthValidation:
    """测试内容长度验证"""

    def test_empty_content(self):
        """空内容应该被拒绝"""
        error = validate_notion_params(content_markdown="", title="Valid Title")
        assert error is not None
        assert "太短" in error

    def test_whitespace_only_content(self):
        """纯空白应该被拒绝"""
        error = validate_notion_params(
            content_markdown="   \n\n   ", title="Valid Title"
        )
        assert error is not None
        assert "太短" in error

    def test_short_content(self):
        """少于10字符应该被拒绝"""
        error = validate_notion_params(content_markdown="Short", title="Valid Title")
        assert error is not None
        assert "太短" in error

    def test_valid_length_content(self):
        """正常长度应该通过"""
        content = "This is a valid content with more than 10 characters."
        error = validate_notion_params(content_markdown=content, title="My Note")
        assert error is None


class TestPlaceholderDetection:
    """测试占位符检测"""

    def test_placeholder_keyword(self):
        """包含 'placeholder' 应该被拒绝"""
        error = validate_notion_params(
            content_markdown="This is a placeholder content", title="Valid Title"
        )
        assert error is not None
        assert "占位符" in error

    def test_example_content_keyword(self):
        """包含 'example content' 应该被拒绝"""
        error = validate_notion_params(
            content_markdown="Example content here", title="Valid Title"
        )
        assert error is not None
        assert "占位符" in error

    def test_todo_placeholder(self):
        """孤立的 TODO 占位符应该被拒绝"""
        error = validate_notion_params(
            content_markdown="TODO: Add content later", title="Valid Title"
        )
        assert error is not None
        assert "占位符" in error

    def test_chinese_placeholders(self):
        """中文占位符应该被拒绝"""
        error = validate_notion_params(content_markdown="待补充的内容", title="Valid Title")
        assert error is not None
        assert "占位符" in error

    def test_bracket_placeholder(self):
        """方括号占位符应该被拒绝"""
        error = validate_notion_params(
            content_markdown="[content here] to be filled", title="Valid Title"
        )
        assert error is not None
        assert "占位符" in error

    def test_legitimate_todo_list(self):
        """合法的 TODO 列表（不是占位符）应该通过"""
        content = """
# My Daily Tasks
- TODO: Buy groceries at 5pm and prepare dinner
- TODO: Call dentist to schedule appointment for next week
- TODO: Review pull request #123 and provide feedback

These are my actual tasks for today, with specific details and deadlines.
        """
        error = validate_notion_params(content_markdown=content, title="Daily Tasks")
        assert error is None


class TestAIFabricationPatterns:
    """测试AI常见编造模式"""

    def test_simple_header_with_short_list(self):
        """标题 + 简短列表项（无解释）应该被警告"""
        content = """
# Spanish Verbs
- Hablar
- Comer
- Vivir
        """
        error = validate_notion_params(content_markdown=content, title="Verbs")
        assert error is not None
        assert "过于简化" in error or "简短列表" in error

    def test_header_with_detailed_list(self):
        """标题 + 详细列表项（有解释）应该通过"""
        content = """
# Spanish Subjunctive Rules

The subjunctive mood is used to express uncertainty, desires, and hypothetical situations.

## Key Usage Patterns:
- **Expressing Wishes**: Use after verbs like 'querer', 'desear', 'esperar'
  - Example: Quiero que vengas. (I want you to come.)
  - Explanation: The action 'vengas' is uncertain - it hasn't happened yet.

- **Doubt and Uncertainty**: Use after expressions like 'es posible que', 'dudo que'
  - Example: Dudo que llueva mañana. (I doubt it will rain tomorrow.)
  - Why: The speaker is uncertain about the future weather.

- **Emotional Reactions**: After verbs expressing emotion
  - Example: Me alegra que estés aquí. (I'm glad you're here.)
  - Note: The emotion is about an action or state.
        """
        error = validate_notion_params(
            content_markdown=content, title="Spanish Grammar"
        )
        assert error is None

    def test_very_short_fabricated_content(self):
        """非常短的生成内容应该被拒绝"""
        content = "# Topic\n- Item 1\n- Item 2"
        error = validate_notion_params(content_markdown=content, title="My Topic")
        assert error is not None


class TestTitleValidation:
    """测试标题验证"""

    def test_empty_title(self):
        """空标题应该被拒绝"""
        error = validate_notion_params(content_markdown="Valid content here", title="")
        assert error is not None
        assert "标题" in error

    def test_whitespace_title(self):
        """纯空白标题应该被拒绝"""
        error = validate_notion_params(content_markdown="Valid content", title="   ")
        assert error is not None
        assert "标题" in error

    def test_short_title(self):
        """1字符标题应该被拒绝"""
        error = validate_notion_params(content_markdown="Valid content", title="A")
        assert error is not None
        assert "标题" in error

    def test_placeholder_title_untitled(self):
        """'Untitled' 标题应该被拒绝"""
        error = validate_notion_params(
            content_markdown="Valid content here", title="Untitled"
        )
        assert error is not None
        assert "占位符" in error

    def test_placeholder_title_new_note(self):
        """'New Note' 标题应该被拒绝"""
        error = validate_notion_params(
            content_markdown="Valid content", title="New Note"
        )
        assert error is not None
        assert "占位符" in error

    def test_valid_title(self):
        """正常标题应该通过"""
        content = "Detailed explanation about Python decorators with examples."
        error = validate_notion_params(
            content_markdown=content, title="Python Decorators"
        )
        assert error is None


class TestMetadataLeakage:
    """测试元数据泄露检测"""

    def test_title_field_in_content(self):
        """内容中包含 'Title:' 应该被拒绝"""
        content = "Title: My Note\n\nThis is the actual content."
        # 🔥 修复：使用非占位符标题
        error = validate_notion_params(content_markdown=content, title="My Document")
        assert error is not None
        assert "元数据泄露" in error

    def test_legitimate_title_word(self):
        """正常使用 'title' 单词应该通过"""
        content = "The title of the book is 'Clean Code'. It's a great resource."
        error = validate_notion_params(content_markdown=content, title="Book Review")
        assert error is None


class TestEdgeCases:
    """测试边界情况"""

    def test_unicode_content(self):
        """Unicode 内容应该正常处理"""
        content = "这是一段中文内容，包含了足够的字符来通过验证。包括一些例句和说明。"
        error = validate_notion_params(content_markdown=content, title="中文笔记")
        assert error is None

    def test_code_block_content(self):
        """代码块应该被正常处理"""
        content = """
# Python Code Example

```python
def hello_world():
    print("Hello, World!")
    return True
```

This function prints a greeting message.
        """
        error = validate_notion_params(
            content_markdown=content, title="Python Tutorial"
        )
        assert error is None

    def test_long_valid_content(self):
        """长内容应该通过"""
        content = "A" * 500
        error = validate_notion_params(content_markdown=content, title="Long Note")
        assert error is None

    def test_special_characters(self):
        """特殊字符应该被正常处理"""
        content = "Content with special chars: @#$%^&*()_+-=[]{}|;:',.<>?/~`"
        error = validate_notion_params(content_markdown=content, title="Special")
        assert error is None


class TestActionParameter:
    """测试 action 参数"""

    def test_create_action(self):
        """create 动作应该正常工作"""
        content = "Valid content for creation"
        # 🔥 修复：使用非占位符标题
        error = validate_notion_params(
            content_markdown=content, title="My New Note", action="create"
        )
        assert error is None

    def test_overwrite_action(self):
        """overwrite 动作应该正常工作"""
        content = "Valid content for overwrite"
        # 🔥 修复：使用非占位符标题
        error = validate_notion_params(
            content_markdown=content, title="Updated Note", action="overwrite"
        )
        assert error is None


class TestSuggestContentRequest:
    """测试内容请求建议生成"""

    def test_extract_topic_from_message(self):
        """从用户消息中提取主题"""
        result = suggest_content_request("帮我保存一个关于 Python 的笔记")
        assert "Python" in result

    def test_generic_message(self):
        """通用消息应该生成友好提示"""
        result = suggest_content_request("保存笔记")
        assert "请告诉我" in result or "提供" in result

    def test_english_message(self):
        """英文消息应该也能处理"""
        result = suggest_content_request("save a note about Machine Learning")
        assert "Machine Learning" in result


class TestIntegrationScenarios:
    """集成场景测试"""

    def test_real_user_content_spanish_grammar(self):
        """真实用户内容：西班牙语语法笔记"""
        # 🔥 修复：移除 TODO（改为 "Usage Cases"）
        content = """
# Subjuntivo: Usage Cases

## 1. Expresar Deseos
Después de verbos como 'querer', 'desear', 'esperar':
- Quiero que vengas a la fiesta. (I want you to come to the party.)
- Espero que todo salga bien. (I hope everything goes well.)

## 2. Duda e Incertidumbre
Con expresiones como 'es posible que', 'dudo que':
- Es posible que llueva mañana.
- Dudo que él sepa la respuesta.

## 3. Regla General
Se usa cuando la acción es incierta, no realizada, o depende de otra condición.
        """
        error = validate_notion_params(
            content_markdown=content, title="Subjuntivo - Guía Completa"
        )
        assert error is None

    def test_fabricated_minimal_content(self):
        """AI 编造的最小内容应该被拒绝"""
        content = "# Spanish Verbs\n- Hablar\n- Comer"
        error = validate_notion_params(content_markdown=content, title="Verbs")
        assert error is not None

    def test_user_quick_note(self):
        """用户的快速笔记（简短但真实）"""
        content = "记住：明天下午3点开会，地点在会议室A。需要带笔记本。"
        error = validate_notion_params(content_markdown=content, title="明天的会议")
        assert error is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=tools.validation", "--cov-report=term-missing"])
