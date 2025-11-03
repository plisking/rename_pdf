# rename_pdf

批量根据 PDF 文件内容中的的“标题”，重命名文件，适用于 Windows/macOS/Linux。

## 安装依赖

```powershell
pip install -r requirements.txt
```

## 使用方法（Windows PowerShell）

- 仅预览将要发生的改名（不实际改名）：
```powershell
python .\rename_pdfs.py -d "D:\\Your\\PDF\\Folder" --dry-run
```

- 执行改名：
```powershell
python .\rename_pdfs.py -d "D:\\Your\\PDF\\Folder"
```

- 打印更详细调试信息：
```powershell
python .\rename_pdfs.py -d "D:\\Your\\PDF\\Folder" -v
```

## 说明

- 标题来源：
  1. PDF 元数据中的 Title（若存在）
  2. 前 1-3 页（或 pdfplumber 兜底时前 1-2 页）中“看起来像标题”的文本行
- 文件名安全处理：
  - 替换 Windows 非法字符 `< > : " / \\ | ? *` 为下划线 `_`
  - 合并多余下划线，长度最长 150 字符，修剪首尾空格与点
  - 如有重名，将自动追加 `_1`, `_2`, ...
- OCR：暂未启用（扫描版/图片版 PDF 可能无法提取标题）

## 已知限制

- 扫描版 PDF（无文本层）无法提取标题；需要 OCR 才能识别
- 标题启发式为通用规则，可能与具体文档版式有关，欢迎根据需要调优
