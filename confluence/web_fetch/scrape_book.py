#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用爬书脚本 —— 从 5000yan.com 风格的网站抓取古文+译文，生成带目录的 HTML 文件。

用法：
    python scrape_book.py

运行后会弹出两个输入框：
    1. 输出文件名（不含扩展名，如：聊斋志异）
    2. 书籍目录页 URL（如：https://liaozhai.5000yan.com/）

工作流程：
    1. 解析目录页 → 获取所有卷名和每篇文章的链接
    2. 逐篇抓取 → 提取【原文】和【翻译】
    3. 生成 HTML → 与 confluence/聊斋志异.html 相同格式

要求：Python 3.6+，标准库即可，无需额外安装。
"""

import urllib.request
import urllib.error
import re
import os
import time
import html as html_mod
import tkinter as tk
from tkinter import simpledialog

# ──────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────

def fetch_html(url, retries=3, timeout=20):
    """GET 获取页面 HTML，带重试。"""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            })
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
            else:
                raise
    return ""


def strip_tags(html_text):
    """移除 HTML 标签，保留纯文本。"""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_mod.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def extract_original_and_translation(html_text):
    """从文章页面提取【原文】和【翻译】。"""
    text = strip_tags(html_text)

    # 匹配【原文】...【翻译】
    m1 = re.search(r'【原文】(.*?)【翻译】', text, re.DOTALL)
    # 匹配【翻译】...【点评】或 评论区
    m2 = re.search(r'【翻译】(.*?)(?:【点评】|评论区|登录|注册)', text, re.DOTALL)

    original = m1.group(1).strip() if m1 else ""
    translation = m2.group(1).strip() if m2 else ""

    # 清理尾部常见的多余字符
    translation = re.sub(r'\s*$', '', translation)

    return original, translation


def escape_html(text):
    """转义 HTML 特殊字符（在 pre 块内使用）。"""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


# ──────────────────────────────────────────────────────────
# 目录解析
# ──────────────────────────────────────────────────────────

def resolve_url(href, base_url):
    """将相对链接补全为绝对 URL。"""
    from urllib.parse import urlparse
    if href.startswith('http'):
        return href
    if href.startswith('/'):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}://{parsed.netloc}{href}"
    if base_url.endswith('/'):
        return base_url + href
    return base_url.rsplit('/', 1)[0] + '/' + href


def parse_toc(html_text, base_url):
    """
    解析目录页 HTML，返回 [(卷名, [(标题, url), ...]), ...]。

    支持两种常见格式：
      A. 5000yan.com 风格：
         <h3 class="category-block-title"> 卷一</h3>
         <ul class="category-list">
           <li class="category-item"><a class="category-link" href="...">标题</a></li>
         </ul>
      B. 通用 <h3> + <ul><li><a> 结构
    """
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html_text, re.DOTALL)
    body = body_match.group(1) if body_match else html_text

    volumes = []

    # 策略A：按 <h3> 或 <h2> 标题分段，找紧随其后的 <ul> 里的链接
    # 先用一个宽松的正则匹配 "标题标签 + 后续内容直到下一个同级标题"
    # 更稳健的方式：找到所有 h3/h2 的位置，然后在相邻标题之间提取链接

    # 找所有卷标题
    vol_headers = list(re.finditer(
        r'<(h[23])[^>]*class="[^"]*(?:category-block-title|vol|chapter)[^"]*"[^>]*>\s*(.*?)\s*</\1>',
        body, re.DOTALL | re.IGNORECASE
    ))
    if not vol_headers:
        # 回退：找所有包含卷/章/第等字样的 h2/h3
        vol_headers = list(re.finditer(
            r'<(h[23])[^>]*>\s*(.*?)\s*</\1>',
            body, re.DOTALL | re.IGNORECASE
        ))
        vol_headers = [m for m in vol_headers if re.search(r'[卷章节部第]', m.group(2))]

    if vol_headers:
        for i, vm in enumerate(vol_headers):
            vol_name = strip_tags(vm.group(2)).strip()
            # 该标题之后到下一个标题（或 body 末尾）之间的内容
            start = vm.end()
            end = vol_headers[i + 1].start() if i + 1 < len(vol_headers) else len(body)
            segment = body[start:end]

            stories = []
            # 找所有 <a href="...">标题</a>，过滤掉导航类链接
            for a_match in re.finditer(
                r'<a\s+[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
                segment, re.DOTALL | re.IGNORECASE
            ):
                href = a_match.group(1)
                title = strip_tags(a_match.group(2))
                # 过滤：跳过纯导航链接（太短的、纯数字的、包含"首页"等的）
                if not title:
                    continue
                if href.startswith('#'):
                    continue
                if any(kw in title for kw in ['首页', '登录', '注册', '忘记密码', '热门', '讨论', '下一页', '上一页']):
                    continue
                if re.match(r'^[\d\s\.\-\+×]+$', title):
                    continue
                # 跳过明显的非文章链接
                if any(kw in href.lower() for kw in ['search', 'login', 'register', 'javascript:', 'list.php']):
                    continue

                full_url = resolve_url(href, base_url)
                stories.append((title, full_url))

            if stories:
                volumes.append((vol_name, stories))
    else:
        # 策略B：没有任何卷标题，直接把所有看起来像文章链接的收集起来
        stories = []
        for a_match in re.finditer(
            r'<a\s+[^>]*href="([^"]+)"[^>]*>\s*(.*?)\s*</a>',
            body, re.DOTALL | re.IGNORECASE
        ):
            href = a_match.group(1)
            title = strip_tags(a_match.group(2))
            if not title or href.startswith('#'):
                continue
            if any(kw in title for kw in ['首页', '登录', '注册', '忘记密码', '热门', '讨论']):
                continue
            if any(kw in href.lower() for kw in ['search', 'login', 'register', 'javascript:', 'list.php']):
                continue
            full_url = resolve_url(href, base_url)
            stories.append((title, full_url))
        if stories:
            volumes.append(("目录", stories))

    return volumes


# ──────────────────────────────────────────────────────────
# HTML 生成
# ──────────────────────────────────────────────────────────

CSS = r"""
    :root { --bg:#f5f6fa; --card:#fff; --accent:#356ae6; --muted:#7d8599; --line:#e2e5ee; --text:#1a1a2e; --radius:12px; }
    * { margin:0; padding:0; box-sizing:border-box; }
    body { font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); line-height:1.8; min-height:100vh; }
    .topbar { position:sticky; top:0; z-index:10; background:rgba(255,255,255,.92); backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); border-bottom:1px solid var(--line); padding:10px 16px; display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
    .topbar h1 { font-size:17px; background:linear-gradient(135deg,#8b3fc7,#c44d34); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
    .topbar .count { font-size:13px; color:var(--muted); }
    .toc { max-width:900px; margin:0 auto; padding:14px; }
    .toc details { margin-bottom:6px; }
    .toc summary { cursor:pointer; padding:8px 14px; background:var(--card); border-radius:8px; font-weight:700; font-size:15px; user-select:none; border:1px solid var(--line); }
    .toc summary:hover { background:#f8f9fd; }
    .toc a { display:inline-block; padding:3px 10px; margin:2px 4px; font-size:13px; color:var(--accent); text-decoration:none; border-radius:4px; transition:background .15s; }
    .toc a:hover { background:#e8ecf9; }
    .container { max-width:900px; margin:0 auto; padding:14px; }
    .story { background:var(--card); border-radius:var(--radius); margin-bottom:14px; padding:18px 20px; box-shadow:0 2px 12px rgba(0,0,0,.04); }
    .story h2 { font-size:18px; color:var(--accent); margin-bottom:10px; border-bottom:2px solid var(--accent); padding-bottom:6px; }
    .story h3 { font-size:14px; color:var(--muted); margin:12px 0 6px; }
    .story pre { background:#f8f9fc; border:1px solid var(--line); border-radius:8px; padding:12px 16px; font-family:"PingFang SC","Microsoft YaHei",sans-serif; font-size:14px; line-height:1.9; white-space:pre-wrap; word-break:break-all; overflow-x:auto; color:#2d3436; }
    .back-top { position:fixed; bottom:20px; right:20px; width:42px; height:42px; border-radius:50%; background:var(--accent); color:#fff; border:0; font-size:18px; cursor:pointer; box-shadow:0 4px 16px rgba(53,106,230,.35); display:none; align-items:center; justify-content:center; z-index:10; transition:transform .2s; }
    .back-top.visible { display:flex; }
    .back-top:active { transform:scale(.92); }
    @media (max-width:600px) {
      .topbar { padding:8px 10px; }
      .story { padding:12px 14px; }
      .story h2 { font-size:16px; }
      .story pre { padding:10px 12px; font-size:13px; }
      .back-top { bottom:14px; right:14px; width:36px; height:36px; font-size:16px; }
    }
"""

JS = r"""
    (function(){
      var btn = document.getElementById('backTop');
      window.addEventListener('scroll', function(){
        btn.className = (window.scrollY > 300) ? 'back-top visible' : 'back-top';
      });
      btn.addEventListener('click', function(){ window.scrollTo({top:0,behavior:'smooth'}); });
    })();
"""


def build_toc_html(volumes):
    """生成目录 HTML。"""
    parts = ['<div class="toc">']
    for vol_name, stories in volumes:
        parts.append(f'  <details><summary>{escape_html(vol_name)}（{len(stories)}篇）</summary>')
        for title, _ in stories:
            parts.append(f'    <a href="#{escape_html(title)}">{escape_html(title)}</a>')
        parts.append('  </details>')
    parts.append('</div>')
    return '\n'.join(parts)


def build_story_html(num, title, original, translation):
    """生成单篇故事 HTML。"""
    return f"""<div class="story" id="{escape_html(title)}">
  <h2>{num}. {escape_html(title)}</h2>
  <h3>📜 古文</h3>
  <pre>'''{escape_html(original)}'''</pre>
  <h3>📖 译文</h3>
  <pre>'''{escape_html(translation)}'''</pre>
</div>"""


def build_full_html(book_title, volumes, stories_data):
    """
    生成完整 HTML。
    stories_data: [(title, original, translation), ...] 按编号顺序
    """
    toc_html = build_toc_html(volumes)
    story_blocks = []
    for i, (title, original, translation) in enumerate(stories_data, 1):
        story_blocks.append(build_story_html(i, title, original, translation))

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_html(book_title)} - 全文（古文+译文）</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="topbar">
    <h1>{escape_html(book_title)}</h1>
    <span class="count">共 {len(stories_data)} 篇 · 古文+译文</span>
  </div>
  {toc_html}
  <div class="container">
    {chr(10).join(story_blocks)}
  </div>
  <button id="backTop" class="back-top" title="回到顶部">↑</button>
  <script>{JS}</script>
</body>
</html>"""


# ──────────────────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────────────────

def main():
    # ── 弹窗获取参数 ──
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口

    book_title = simpledialog.askstring(
        "爬书脚本", "请输入书名（输出文件名，不含扩展名）\n例如：聊斋志异",
        parent=root
    )
    if not book_title:
        print("已取消：未输入书名。")
        return

    toc_url = simpledialog.askstring(
        "爬书脚本", "请输入书籍目录页 URL\n例如：https://liaozhai.5000yan.com/",
        parent=root
    )
    root.destroy()

    if not toc_url:
        print("已取消：未输入 URL。")
        return

    # 清理 URL
    toc_url = toc_url.strip()
    if not toc_url.startswith('http'):
        toc_url = 'https://' + toc_url

    print(f"\n{'='*60}")
    print(f"书名: {book_title}")
    print(f"目录页: {toc_url}")
    print(f"{'='*60}\n")

    # ── 第1步：获取目录 ──
    print("[1/3] 正在获取目录...")
    toc_html = fetch_html(toc_url)
    volumes = parse_toc(toc_html, toc_url)

    total_stories = sum(len(s) for _, s in volumes)
    print(f"  发现 {len(volumes)} 卷，共 {total_stories} 篇\n")

    if not volumes:
        print("错误：未能解析到任何文章链接，请检查 URL 是否正确。")
        return

    # ── 第2步：逐篇抓取 ──
    print("[2/3] 正在抓取文章内容...")
    stories_data = []
    failed = []

    for vol_idx, (vol_name, stories) in enumerate(volumes, 1):
        print(f"\n  --- {vol_name} ({len(stories)}篇) ---")
        for idx, (title, url) in enumerate(stories, 1):
            global_idx = len(stories_data) + 1
            print(f"    [{global_idx}/{total_stories}] {title}", end=' ', flush=True)

            try:
                html_text = fetch_html(url)
                original, translation = extract_original_and_translation(html_text)
                orig_len = len(original)
                trans_len = len(translation)

                if original or translation:
                    stories_data.append((title, original, translation))
                    print(f"✓ ({orig_len}字/{trans_len}字)")
                else:
                    failed.append((title, url, "内容为空"))
                    stories_data.append((title, "[抓取失败]", "[抓取失败]"))
                    print("✗ 内容为空")

            except Exception as e:
                failed.append((title, url, str(e)))
                stories_data.append((title, f"[抓取失败: {e}]", f"[抓取失败: {e}]"))
                print(f"✗ {e}")

            # 礼貌延迟，避免被限流
            time.sleep(0.3)

    # ── 第3步：生成 HTML ──
    print(f"\n[3/3] 正在生成 HTML 文件...")
    html_output = build_full_html(book_title, volumes, stories_data)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(script_dir, f"{book_title}.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_output)

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n{'='*60}")
    print(f"✅ 完成！")
    print(f"   成功: {len(stories_data)} 篇")
    if failed:
        print(f"   失败: {len(failed)} 篇")
        for title, url, err in failed[:10]:
            print(f"     - {title}: {err}")
    print(f"   输出: {output_path}")
    print(f"   大小: {size_mb:.2f} MB")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
