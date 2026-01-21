import os

# 🎯 配置：只读取这些后缀的源码文件
ALLOWED_EXTENSIONS = {
    ".py",
    ".tsx",
    ".ts",
    ".js",
    ".json",
    ".yml",
    ".yaml",
    ".md",
    ".env.example",
    "Dockerfile",
}

# 🚫 忽略：彻底屏蔽这些目录和文件
IGNORE_DIRS = {
    "node_modules",
    "__pycache__",
    ".git",
    ".next",
    ".idea",
    ".vscode",
    "venv",
    ".venv",
    "env",
    "qdrant_storage",
    "chroma_db",
    "dist",
    "build",
    "public",
}
IGNORE_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".DS_Store"}


def is_source_file(filename):
    return (
        any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS)
        and filename not in IGNORE_FILES
    )


def export_project():
    output_file = "biobrain_code_audit.txt"
    total_files = 0

    with open(output_file, "w", encoding="utf-8") as outfile:
        # 写入头部信息
        outfile.write("BIOBRAIN PROJECT SOURCE CODE DUMP\n")
        outfile.write("=================================\n\n")

        for root, dirs, files in os.walk("."):
            # 1. 过滤掉忽略的目录 (修改 dirs 列表会影响 os.walk 的后续遍历)
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for file in files:
                if is_source_file(file):
                    file_path = os.path.join(root, file)

                    # 🛡️ 过滤大文件：超过 500KB 的文件大概率不是代码，或者是巨大的 JSON
                    if os.path.getsize(file_path) > 500 * 1024:
                        print(f"⚠️ 跳过大文件: {file_path}")
                        continue

                    try:
                        # 格式化写入文件路径和内容
                        outfile.write(f"\n\n{'='*60}\n")
                        outfile.write(f"FILE PATH: {file_path}\n")
                        outfile.write(f"{'='*60}\n")

                        with open(
                            file_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content = f.read()
                            outfile.write(content)

                        print(f"✅ 已添加: {file_path}")
                        total_files += 1
                    except Exception as e:
                        print(f"❌ 读取错误 {file_path}: {e}")

    print(f"\n🎉 导出完成！共包含 {total_files} 个文件。")
    print(f"📂 请上传生成的文件: {output_file}")


if __name__ == "__main__":
    export_project()
