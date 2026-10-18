#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布后源级终检：对 _posts/ 里所有文章断言质量红线。
任一不过 → exit 1 → Actions 变红 → 问题当天暴露，不再裸奔。
红线（2026-10-18 大事故后定）：
  1. {{ 残留必须为 0（PRODUCT_LINK 占位符裸露事故）
  2. 每篇亚马逊搜索链接 >= 5（购买链路必须活着）
  3. 每篇 Disclosure 披露 >= 2（头尾各一段，FTC 合规）
  4. 每篇词数 >= 1800
  5. Final Verdict / FAQ / 对比表格必须在
"""
import glob
import os
import re
import sys

NL = chr(10)
PH = "{{"
MIN_WORDS = 1800
MIN_LINKS = 5
MIN_DISC = 2


def check(fname):
    md = open(fname, encoding="utf-8").read()
    body = md
    if body.startswith("---"):
        end = body.index("---", 3)
        body = body[end + 3:]
    body = body.replace("{% raw %}", "").replace("{% endraw %}", "")
    words = len(re.findall(r"[A-Za-z']+", body))
    links = body.count("amazon.com/s?k=")
    disc = body.count("Disclosure:")
    problems = []
    if PH in md:
        problems.append("placeholder-residue=%d" % md.count(PH))
    if links < MIN_LINKS:
        problems.append("product-links=%d(<%d)" % (links, MIN_LINKS))
    if disc < MIN_DISC:
        problems.append("disclosure=%d(<%d)" % (disc, MIN_DISC))
    if words < MIN_WORDS:
        problems.append("words=%d(<%d)" % (words, MIN_WORDS))
    if "Final Verdict" not in md:
        problems.append("no-final-verdict")
    if "FAQ" not in md:
        problems.append("no-faq")
    if md.count(NL + "| ") < 5:
        problems.append("no-comparison-table")
    return problems, words, links, disc


def main():
    files = sorted(glob.glob("_posts/*.md"))
    if not files:
        print("VERIFY FAIL: no posts found")
        sys.exit(1)
    failed = 0
    for f in files:
        problems, words, links, disc = check(f)
        if problems:
            failed += 1
            print("FAIL %s -> %s" % (os.path.basename(f), "; ".join(problems)))
        else:
            print("PASS %s (words=%d links=%d disc=%d)" % (os.path.basename(f), words, links, disc))
    print("-" * 50)
    if failed:
        print("VERIFY FAILED: %d/%d articles broken" % (failed, len(files)))
        sys.exit(1)
    print("VERIFY PASSED: %d/%d articles clean" % (len(files), len(files)))


main()
