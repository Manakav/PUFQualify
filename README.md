# PUF HSPICE `.mt0` 输出分析工具

本仓库包含两套工具：命令行分析脚本与基于 Tkinter 的 GUI（图形界面）。

- `analyze_mt0.py`：命令行/脚本模式的 MT0 文件分析工具，适合批量或脚本化运行。
- `analyze_gui.py`：交互式 GUI，集成 Reliability（可靠性）计算与 MT0 单文件分析两个标签页。

核心功能
----------
- 将每条样本的 32 个电压值二值化（默认阈值 0.5V），生成 32-bit 序列。
- 单片内均匀性分析（1/0 计数、balance ratio、与全零向量相似度）。
- 多片间唯一性/相似度分析（两两汉明距离、平均相似度、最相似/最不相似对）。

快速开始
-----------
Python 环境建议使用 `3.10+`（在仓库 CI/打包中使用 3.10）。

运行 GUI

```bash
python analyze_gui.py
```

GUI 概览：
- `Reliability` 标签页：可添加多个 `.mt0` 文件、标记参考样本、填写温度/电压元数据，点击 `Compute Reliability` 计算每个 index 的 BER/可靠性并可导出 per-index CSV。
- `MT0 Analysis` 标签页：用于单文件的详细展示（显示每个 index 的 32-bit 序列、样本内/样本间统计）。可设置二值化阈值并运行快速分析。

命令行使用（CLI）

```bash
python analyze_mt0.py                 # 交互式选择或使用默认 R.mt0
python analyze_mt0.py path/to/file.mt0
```

打包（生成可执行文件）
-----------------
项目包含 `build_exe.py`，用于基于 PyInstaller 生成一个包含字体资源的单文件可执行。

准备打包环境：

```bash
pip install --upgrade pip
pip install pyinstaller
```

构建 GUI 可执行：

```bash
python build_exe.py
```

说明：`build_exe.py` 会尝试把 `fonts/` 下的字体打包进去，以保证 GUI 字体一致性。跨平台注意事项：在 Linux 上打包 Windows exe 需要额外环境（如 Wine），本脚本不做自动交叉编译。

持续集成（GitHub Actions）
--------------------------
仓库已包含一个打包工作流：`.github/workflows/package.yml`。
- 作用：在 `ubuntu-latest` / `windows-latest` / `macos-latest` runner 上运行 `python build_exe.py` 打包 `analyze_gui`，并把 `dist/` 上传为 artifact。
- 触发方式：推送到 `main`/`master` 分支或手动触发（workflow_dispatch）。

建议
-----
- 将 `dist/` 与 `build/` 加入 `.gitignore`：

```
dist/
build/
*.pyc
__pycache__/
```

- 若希望仅在发布时打包，可把工作流调整为仅在 tag/release 触发，或在成功构建后自动创建 GitHub Release（需配置 repo token）。

仓库文件一览
--------------
- `analyze_gui.py` — GUI 程序（Tkinter）
- `analyze_mt0.py` — CLI/脚本分析工具
- `build_exe.py` — PyInstaller 打包辅助脚本（打包 GUI，并包含 fonts）
- `analyze_gui.spec` — PyInstaller spec（GUI）
- `analyze_mt0.spec` — PyInstaller spec（CLI，保留供需要时使用）
- `fonts/` — 可选的字体文件，用于打包时包含

许可
----
参见仓库中的 `LICENSE`。

反馈与贡献
------------
欢迎通过 GitHub issues 或 pull requests 提交 bug 报告和改进建议。若需要我帮你把工作流改成仅在 release tag 触发或自动发布 Release，我可以继续修改。
