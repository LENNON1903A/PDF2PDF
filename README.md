# PDF2PDF

将英文或西班牙文 PDF 翻译为中文，并尽量保留原页面布局。项目包名为 `pdf2zh-layout`，命令行入口为 `pdf2zh`。

## 当前能力

- 分析 PDF 布局并输出分析报告。
- 按质量预设翻译并渲染新的 PDF。
- 查看可用质量预设。
- 翻译、渲染逻辑位于 `src/pdf2zh`；规则测试位于 `tests/test_rules.py`。

## 环境要求

- Python 3.11 或更高版本
- 依赖由 `pyproject.toml` 声明：PyMuPDF、Pillow、requests
- 开发测试依赖：pytest

## 安装

在仓库根目录执行：

```powershell
python -m pip install -e .
```

安装开发依赖并运行测试：

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## 命令示例

```powershell
pdf2zh quality
pdf2zh quality --json
pdf2zh analyze "input.pdf" --output "analysis.json"
pdf2zh translate "input.pdf" --output "translated.pdf" --quality standard
```

翻译命令还支持 `--cache` 和 `--batch-size`。可运行 `pdf2zh translate --help` 查看当前参数。

## 注意事项

- 页面布局保持效果依赖原 PDF 的字体、扫描质量、文字方向和页面复杂度；请人工抽查输出。
- 项目描述目标语言为中文，不能据此推断所有语言组合均受支持。
- 当前仓库未发现许可证文件；公开复用前请明确许可证及第三方字体/模型服务要求。
