#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
露营装备评测站 · 每日自动发文脚本
由 GitHub Actions 调用，每天选下一个未写的题目，调用 LLM 生成英文评测文章，
写入 _posts/ 并提交。首页 index.md 用 Jekyll Liquid 自动列出所有文章，无需手动改。
依赖：仅标准库（urllib / json / os / glob / re / datetime / sys）。
"""

import os
import glob
import json
import sys
import datetime
import re
import urllib.request

# ===== 第一批 30 个题目（按顺序，写完一个跳下一个）=====
TOPICS = [
    "Best Camping Tents for Beginners in 2026",
    "Best 4-Person Tents Under $200",
    "Best Sleeping Bags for Cold Weather Under $100",
    "Best Sleeping Pads for Side Sleepers",
    "Best Camping Chairs for Bad Backs",
    "Best Portable Camping Stoves for Backpacking",
    "Best Camping Lanterns in 2026",
    "Best Camping Coolers Under $100",
    "Best Tent Heaters for Cold Weather Camping",
    "Best Camping Air Mattresses for Couples",
    "Best Hiking Backpacks Under $100",
    "Best Camping Hammocks with Bug Nets",
    "Best Camping Coffee Makers for Fresh Coffee Outdoors",
    "Best Camping Showers for Off-Grid Use",
    "Best Solar Chargers for Camping in 2026",
    "Best Camping Fans for Hot Weather",
    "Best Fixed-Blade Camping Knives Under $50",
    "Best Campfire Cooking Kits for Beginners",
    "Best Waterproof Tents for Heavy Rain",
    "Best Folding Camping Tables Under $60",
    "Best Winter Sleeping Bags for 0°F Nights",
    "Best Camping Toilets for Tent Camping",
    "Best Camping Grills: Propane vs Charcoal Compared",
    "Best Tent Footprints to Protect Your Tent Floor",
    "Best Camping Pillows for Backpacking",
    "Best 2-Person Backpacking Tents Under $150",
    "Best Camping Stove Windscreens That Actually Work",
    "Best Camping Water Filters and Purifiers",
    "Best Camping Tarps for Rain Protection",
    "Car Camping Essentials: Complete Gear Checklist",
]


def slugify(s: str) -> str:
    s = s.lower().replace("$", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def bootstrap():
    """首次运行时，若仓库里没有 _config.yml / index.md，自动补上。"""
    if not os.path.exists("_config.yml"):
        with open("_config.yml", "w", encoding="utf-8") as f:
            f.write("title: Camping Gear Reviews\n")
    if not os.path.exists("index.md"):
        idx = (
            "---\n"
            "title: Camping Gear Reviews\n"
            "---\n\n"
            "# Camping Gear Reviews\n\n"
            "No-nonsense outdoor camping gear reviews for US campers. "
            "We compare real products so you can buy with confidence.\n\n"
            "## Latest Reviews\n\n"
            "<ul>\n"
            "{% for post in site.posts %}\n"
            '  <li><a href="{{ post.url | relative_url }}">{{ post.title }}</a></li>\n'
            "{% endfor %}\n"
            "</ul>\n"
        )
        with open("index.md", "w", encoding="utf-8") as f:
            f.write(idx)


def next_topic():
    os.makedirs("_posts", exist_ok=True)
    existing = [os.path.basename(f) for f in glob.glob("_posts/*.md")]
    for t in TOPICS:
        sl = slugify(t)
        if any(f.endswith("-{}.md".format(sl)) for f in existing):
            continue
        return t, sl
    return None, None


SYSTEM = """You are a senior outdoor camping gear reviewer writing buying-guide articles for US readers. Write in fluent, natural, conversational American English.

Voice: like a knowledgeable friend giving honest advice — never salesy, never ad-like. Avoid hype words like "revolutionary" or "game-changing".

For every article you write, follow these HARD rules:
1. Use REAL, currently available products with REAL prices in USD. Never invent fake brand names, model numbers, or products.
2. If you are unsure about a specific spec or price, write [需核实] (needs verification) instead of guessing. Never fabricate data.
3. Exact structure, in order:
   - H1 title = the topic itself, verbatim.
   - ~100-word opening that drops the reader into a real pain-point scenario (e.g., rain leaking through a tent at 2am).
   - 5 to 7 product reviews. For EACH: product name, price range, exactly 3 pros (each 1-2 full sentences), exactly 1 con (1-2 full sentences), a 2-3 sentence real-world use scenario, and a "Best for:" line saying who should buy it.
   - A comparison table in MARKDOWN PIPE SYNTAX — mandatory. It must include a header row like `| Product | Price | Best For | Key Strength |` and a separator row `|---|---|---|---|`, then one row per product. Do NOT use any other table style.
   - A section with the EXACT heading `## Final Verdict` giving a clear top pick and a budget pick.
   - A section with the EXACT heading `## FAQ` containing exactly 5 FAQs with 2-3 sentence answers each.
   - The comparison table, the `## Final Verdict` heading, and the `## FAQ` heading are ALL mandatory and must appear in every article. Never omit them.
4. After EVERY product name, insert the exact placeholder {{PRODUCT_LINK}} (keep the curly braces, do not replace or explain it).
5. Length: write AT LEAST 2200 words, target 2200-2600. This is a HARD requirement — never stop before 2200 words. If you are running short, add more detail to each product description and expand the FAQs until you reach the minimum.
6. Output ONLY the markdown article. Start with the H1 title. No preamble, no "Here is your article"."""


def call_llm(topic: str, today: str) -> str:
    api_key = os.environ.get("LLM_API_KEY")
    if not api_key:
        print("ERROR: LLM_API_KEY secret is not set.")
        sys.exit(1)
    # 默认走 DeepSeek（api.deepseek.com，国产、国内可直连；充 ¥1 起即可，约 ¥0.01/篇，30篇≈¥0.3）。
    # 注意用 `or` 兜底：GitHub Actions 对"未创建的密钥"会传空字符串（不是不存在），
    # os.environ.get(key, 默认值) 遇到空串不会用默认值 → URL 变空 → 秒崩。用 or 同时防"没设置"和"设为空串"。
    base = (os.environ.get("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("LLM_MODEL") or "deepseek-chat"

    user = (
        "Write the full article for this exact topic:\n\n"
        + topic
        + "\n\nToday is "
        + today
        + "."
    )
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 5000,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        base + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            data = json.loads(r.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("API ERROR:", e)
        sys.exit(1)

    # 去掉可能的代码围栏
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return text


def qa_ok(text: str) -> bool:
    words = len(text.split())
    if words < 1800:
        print("QA FAIL: article too short ({} words). Not publishing.".format(words))
        return False
    if "Final Verdict" not in text or "FAQ" not in text or "|" not in text:
        print("QA FAIL: missing required section or comparison table.")
        return False
    low = text.lower()
    for w in ["as an ai", "i cannot", "i can't", "i am unable", "i'm unable"]:
        if w in low:
            print("QA FAIL: model refused or gave meta-response.")
            return False
    return True


def main():
    bootstrap()
    topic, sl = next_topic()
    if not topic:
        print("ALL 30 TOPICS DONE — nothing to publish today.")
        sys.exit(0)

    today = datetime.date.today().strftime("%Y-%m-%d")
    article = call_llm(topic, today)
    if not qa_ok(article):
        sys.exit(1)

    # 用 Jekyll {% raw %} 包裹正文，保留 {{PRODUCT_LINK}} 占位符不被 Liquid 解析
    fname = "_posts/{}-{}.md".format(today, sl)
    content = (
        "---\ntitle: \"" + topic + "\"\n---\n\n{% raw %}\n"
        + article
        + "\n{% endraw %}\n"
    )
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)

    words = len(article.split())
    print("PUBLISHED: " + topic)
    print("FILE: " + fname)
    print("WORDS: " + str(words))
    print("URL: /{}/{}/{}/{}.html".format(today[:4], today[5:7], today[8:10], sl))


# 直接调用（不用 if __name__ == "__main__" 判断：那个写法在复制粘贴时
# 极易混入零宽空格导致静默失败——任务显示绿勾但啥也不干）。
main()
