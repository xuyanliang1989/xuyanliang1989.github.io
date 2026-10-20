# -*- coding: utf-8 -*-
"""IndexNow URL submitter.

Usage:
    python indexnow_submit.py <site_host> --all          # submit every article URL (manual/one-off)
    python indexnow_submit.py <site_host> --from-git     # submit only articles added in HEAD~1..HEAD (used by publish.yml)

IndexNow (https://www.indexnow.org) lets a site ping Bing/Yandex (and the
engines that consume their index) the moment a URL is published, instead of
waiting for the crawler to discover it. The key file <key>.txt at the site
root proves ownership.

Design rules (battle-tested):
- Never fail the calling workflow on network errors: the article is already
  live by the time this runs; a failed ping only delays discovery.
- Empty URL list = exit 0 silently (nothing new published).
"""
import json
import re
import subprocess
import sys
import urllib.request
import urllib.error

INDEXNOW_KEY = "wbindexnow9f2a71c4e8d3b60a5f1c7e2d94b83a06"
KEY_LOCATION = "https://xuyanliang1989.github.io/%s.txt"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"
POST_RE = re.compile(r"^_posts/(\d{4})-(\d{2})-(\d{2})-(.+)\.md$")


def article_url(host, prefix, match):
    y, mo, d, slug = match.groups()
    if prefix and not prefix.startswith("/"):
        prefix = "/" + prefix
    prefix = prefix.rstrip("/")
    return "https://%s%s/%s/%s/%s/%s.html" % (host, prefix, y, mo, d, slug)


def urls_from_git(host, prefix):
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=A", "HEAD~1", "HEAD"],
            capture_output=True, text=True, timeout=30,
        ).stdout
    except Exception as e:
        print("WARN: git diff failed:", e)
        return []
    urls = []
    for line in out.splitlines():
        m = POST_RE.match(line.strip())
        if m:
            urls.append(article_url(host, prefix, m))
    return urls


def urls_from_disk(host, prefix):
    import os
    urls = []
    if not os.path.isdir("_posts"):
        return urls
    for name in os.listdir("_posts"):
        m = POST_RE.match(name)
        if m:
            urls.append(article_url(host, prefix, m))
    return sorted(urls)


def submit(host, urls):
    if not urls:
        print("No URLs to submit; nothing to do.")
        return
    payload = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": KEY_LOCATION % INDEXNOW_KEY,
        "urlList": urls,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print("IndexNow submitted %d URL(s), HTTP %s" % (len(urls), r.status))
    except urllib.error.HTTPError as e:
        # 422 usually means a malformed URL; 403 a bad key. Log loudly, never fail the workflow.
        print("WARN: IndexNow HTTP %s: %s" % (e.code, e.read().decode("utf-8", "replace")[:300]))
    except Exception as e:
        print("WARN: IndexNow request failed:", e)


def main():
    args = list(sys.argv[1:])
    mode = None
    for a in list(args):
        if a in ("--all", "--from-git"):
            mode = a
            args.remove(a)
    if mode is None or not args:
        print("usage: indexnow_submit.py <site_host> [path_prefix] (--all | --from-git)")
        sys.exit(2)
    host = args[0]
    prefix = args[1] if len(args) > 1 else ""
    # Guard against Git-Bash/MSYS path conversion leaking into prefix
    # (e.g. "/fishing-gear-reviews" -> "D:/.../PortableGit/fishing-gear-reviews").
    if ":" in prefix or "\\" in prefix:
        print("FATAL: prefix looks path-converted:", prefix)
        sys.exit(3)
    if mode == "--all":
        urls = urls_from_disk(host, prefix)
    else:
        urls = urls_from_git(host, prefix)
    print("host=%s prefix=%s mode=%s urls=%d" % (host, prefix or "/", mode, len(urls)))
    for u in urls:
        print("  ", u)
    submit(host, urls)


if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()
