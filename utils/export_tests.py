"""
utils/export_tests.py
测试用例导出工具 (Code Extract Version)
功能：
1. 自动扫描所有 Pytest 测试项。
2. 解析 Python AST，提取每个测试函数的完整源代码。
3. 生成包含代码细节的详细测试报告。
"""
import ast
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime


def get_test_source_code(file_path: str, test_signature: str) -> str:
    """
    使用 AST 解析文件并提取指定测试函数的源代码
    test_signature 示例: "test_function" 或 "TestClass::test_method"
    """
    if not os.path.exists(file_path):
        return "⚠️ 文件未找到"

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # 处理路径: TestClass::test_method -> ['TestClass', 'test_method']
        # 还要处理参数化后缀: test_add[1+1] -> test_add
        parts = [p.split("[")[0] for p in test_signature.split("::")]

        current_node = tree
        target_node = None

        # 逐层查找节点 (Module -> ClassDef -> FunctionDef)
        for part in parts:
            found = False
            # 遍历当前节点的所有子节点
            for node in ast.iter_child_nodes(current_node):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    if node.name == part:
                        current_node = node
                        target_node = node
                        found = True
                        break
            if not found:
                return f"⚠️ 代码解析未找到节点: {part}"

        if target_node:
            return ast.get_source_segment(source, target_node)

    except Exception as e:
        return f"❌ 提取代码时出错: {str(e)}"

    return "⚠️ 未知错误"


def export_test_inventory(output_file="project_tests_with_code.txt"):
    """
    执行 pytest 收集并导出带代码的报告
    """
    print("🔍 正在扫描测试用例 (Running pytest collection)...")

    # 构造命令 (禁用插件干扰)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "--collect-only",
        "-q",
        "-p",
        "no:cov",
        "-p",
        "no:warnings",
        "-o",
        "addopts=",
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        raw_output = result.stdout.strip()

        if result.returncode != 0:
            print(f"❌ Pytest 执行出错 (Code: {result.returncode})")
            print(result.stderr)
            return

        lines = raw_output.split("\n")
        test_ids = [
            line
            for line in lines
            if "::" in line and not line.startswith("no tests ran")
        ]

        if not test_ids:
            print("⚠️ 未找到测试用例。")
            return

        total_tests = len(test_ids)
        grouped_tests = defaultdict(list)

        for test_id in test_ids:
            clean_id = test_id.strip().split(" ")[0]  # 去除可能的后缀
            parts = clean_id.split("::")
            if len(parts) >= 2:
                file_path = parts[0]
                test_name = " :: ".join(parts[1:])
                grouped_tests[file_path].append(test_name)

        # 写入大文件
        print(f"📝 正在提取 {total_tests} 个测试用例的源码...")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("BIOBRAIN DETAILED TEST REPORT\n")
            f.write("=============================\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Tests: {total_tests}\n")
            f.write("=============================\n\n")

            for file_path in sorted(grouped_tests.keys()):
                tests = grouped_tests[file_path]

                f.write(f"📂 FILE: {file_path}\n")
                f.write(f"{'='*80}\n\n")

                for t_name in tests:
                    # 获取源码
                    code_content = get_test_source_code(file_path, t_name)

                    f.write(f"🔹 TEST CASE: {t_name}\n")
                    f.write(f"{'-'*40}\n")
                    f.write(f"{code_content}\n")
                    f.write(f"{'-'*40}\n\n")

                f.write("\n")

        print("✅ 导出完成！")
        print(f"📄 详细报告已保存至: {os.path.abspath(output_file)}")

    except Exception as e:
        print(f"❌ 脚本执行出错: {e}")


if __name__ == "__main__":
    export_test_inventory()
