import os
import re
import logging
import argparse
import unicodedata
from typing import Optional

import pdfplumber
from PyPDF2 import PdfReader

def extract_title_from_pdf_pypdf2(pdf_path: str) -> Optional[str]:
    """使用 PyPDF2 提取标题：先读元数据，再读前几页文本。"""
    try:
        reader = PdfReader(pdf_path)

        # 1) 优先尝试元数据的标题（兼容不同 PyPDF2 版本/实现）
        meta = getattr(reader, "metadata", None)
        title_meta = None
        if meta:
            # 尝试属性访问
            title_meta = getattr(meta, "title", None)
            # 再尝试字典式访问
            if not title_meta:
                for k in ("/Title", "/title", "Title", "title"):
                    try:
                        if hasattr(meta, "get"):
                            title_meta = meta.get(k)
                        else:
                            title_meta = meta[k]  # type: ignore[index]
                    except Exception:
                        continue
                    if title_meta:
                        break
        if title_meta:
            return sanitize_candidate_title(str(title_meta))

        # 2) 无元数据标题时，尝试从前 3 页文本推断
        for page_num in range(min(3, len(reader.pages))):
            page = reader.pages[page_num]
            text = None
            try:
                text = page.extract_text()
            except Exception:
                text = None

            if not text:
                continue

            # Look for potential titles in the first part of the text
            lines = text.split('\n')[:20]  # Look at first 20 lines

            candidate = pick_title_from_lines(lines)
            if candidate:
                return candidate
    except Exception as e:
        logging.debug(f"PyPDF2 提取失败: {pdf_path}: {e}")

    return None

def extract_title_from_pdf_pdfplumber(pdf_path: str) -> Optional[str]:
    """使用 pdfplumber 兜底提取标题。"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num in range(min(2, len(pdf.pages))):  # Check first 2 pages
                page = pdf.pages[page_num]
                text = None
                try:
                    text = page.extract_text()
                except Exception:
                    text = None

                if not text:
                    continue

                lines = text.split('\n')[:30]  # Look at first 30 lines
                candidate = pick_title_from_lines(lines)
                if candidate:
                    return candidate
    except Exception as e:
        logging.debug(f"pdfplumber 提取失败: {pdf_path}: {e}")

    return None

def pick_title_from_lines(lines: list[str]) -> Optional[str]:
    """从若干行文本中挑选最可能的标题。"""
    for raw in lines:
        line = raw.strip()
        # Skip empty lines or lines with only special characters
        if not line or len(line) < 3 or line.count('.') > 5:
            continue

        low = line.lower()
        # Skip page numbers or author info
        if re.match(r'^\d+$', line) or '@' in low or 'email' in low or 'author' in low:
            continue

        # Check if this looks like a title (not sentence-like)
        if 5 < len(line) < 200:  # Reasonable title length
            cleaned = sanitize_candidate_title(line)
            if len(cleaned) > 5 and cleaned.count(' ') > 0:  # Has spaces, likely a title
                return cleaned.strip()
    return None

def sanitize_candidate_title(text: str) -> str:
    """对候选标题做基本清洗（去奇怪符号、控制字符、压缩空白）。"""
    # Remove control characters and normalize unicode
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    # Normalize whitespace (including newlines, tabs)
    text = re.sub(r"\s+", " ", text)
    # Remove special characters that might be in titles (keep common punctuation)
    text = re.sub(r'[^\w\s\-\—\–\.,;:!?\'\"]', '', text)
    return text.strip()

def normalize_filename(title: Optional[str]) -> str:
    """将标题规范化为安全文件名。"""
    if not title:
        title = "untitled"

    # 再次进行基本清洗
    title = sanitize_candidate_title(title)

    # 替换文件名非法字符（Windows）
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        title = title.replace(char, '_')

    # 连续下划线缩减
    title = re.sub(r'_+', '_', title)

    # 限制长度，避免路径过长问题
    if len(title) > 150:
        title = title[:150]

    # 去掉首尾空格和点
    title = title.strip('. ')

    # 防止空字符串
    if not title:
        title = "untitled"

    return title

def rename_pdf_files(directory: str, *, dry_run: bool = False) -> None:
    """根据 PDF 内容重命名文件。

    参数:
        directory: 目标目录
        dry_run: 仅预览，不实际重命名
    """
    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]
    logging.info(f"待处理 PDF 数量: {len(pdf_files)}")

    for i, filename in enumerate(pdf_files, 1):
        original_path = os.path.join(directory, filename)
        logging.info(f"({i}/{len(pdf_files)}) 处理: {filename}")

        # First try PyPDF2
        title = extract_title_from_pdf_pypdf2(original_path)

        # If PyPDF2 didn't work, try pdfplumber
        if not title:
            title = extract_title_from_pdf_pdfplumber(original_path)

        if title:
            normalized_title = normalize_filename(title)
            new_filename = normalized_title + ".pdf"

            # Ensure unique filename in case of duplicates
            counter = 1
            original_new_filename = new_filename
            while True:
                new_path = os.path.join(directory, new_filename)
                # 如果新路径与原路径不同且已存在，则递增后缀
                if new_path != original_path and os.path.exists(new_path):
                    name_part = original_new_filename.rsplit('.pdf', 1)[0]
                    new_filename = f"{name_part}_{counter}.pdf"
                    counter += 1
                    continue
                break

            new_path = os.path.join(directory, new_filename)

            if new_path != original_path:
                if dry_run:
                    logging.info(f"将重命名: '{filename}' -> '{new_filename}'  | 标题: '{title}'")
                else:
                    try:
                        os.rename(original_path, new_path)
                        logging.info(f"已重命名: '{filename}' -> '{new_filename}'")
                        logging.debug(f"标题: '{title}'")
                    except OSError as e:
                        logging.error(f"重命名失败 '{filename}': {e}")
            else:
                logging.info(f"无需更改: {filename}")
        else:
            logging.warning(f"无法提取标题: {filename}")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="根据 PDF 内容（元数据/前几页文本）批量重命名 PDF 文件"
    )
    parser.add_argument(
        "-d", "--directory", required=True,
        help="要处理的目录路径"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅预览重命名结果，不实际改名"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="打印更详细的调试日志"
    )
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s"
    )


if __name__ == "__main__":
    args = parse_args()
    setup_logging(args.verbose)

    target_dir = os.path.abspath(args.directory)
    if not os.path.isdir(target_dir):
        logging.error(f"目录不存在或不可访问: {target_dir}")
        raise SystemExit(1)

    rename_pdf_files(target_dir, dry_run=args.dry_run)
    logging.info("处理完成！")