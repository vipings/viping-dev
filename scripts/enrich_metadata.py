#!/usr/bin/env python3
"""Auto-fill empty post metadata (title, description, tags, categories) using a local Ollama model."""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

BLOG_DIR = Path(os.environ.get("BLOG_DIR", Path.home() / "viping-dev" / "content" / "blog"))
MAX_BODY_CHARS = 800
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
JEV_URL = os.environ.get("JEV_URL", "https://api.typesafe.ai/v1/systemone")


def get_client():
    try:
        urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5)
    except OSError as e:
        print(f"ERROR: Ollama is not reachable at {OLLAMA_URL}: {e}")
        print("  Start the Ollama app, then rerun deploy.sh")
        sys.exit(1)
    return OLLAMA_MODEL


def parse_frontmatter(text):
    """Return (frontmatter_str, body_str) for TOML +++ delimited files."""
    match = re.match(r"^\s*\+\+\+\n(.*?)\n\+\+\+\n?(.*)", text, re.DOTALL)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def field_is_empty(frontmatter, field):
    """Check if a TOML field is empty string or empty array."""
    m = re.search(rf'^{field}\s*=\s*(.+)', frontmatter, re.MULTILINE)
    if not m:
        return False
    val = m.group(1).strip()
    return val in ('""', '[]')


def needs_enrichment(frontmatter):
    return any(
        field_is_empty(frontmatter, f)
        for f in ("title", "description", "tags", "categories")
    )


def get_current(frontmatter, field):
    m = re.search(rf'^{field}\s*=\s*(.+)', frontmatter, re.MULTILINE)
    if not m:
        return None
    val = m.group(1).strip()
    if val in ('""', '[]'):
        return None
    return val


def generate_metadata(model, frontmatter, body):
    current_title = get_current(frontmatter, "title")

    missing = []
    if field_is_empty(frontmatter, "title"):
        missing.append("title")
    if field_is_empty(frontmatter, "description"):
        missing.append("description")
    if field_is_empty(frontmatter, "tags"):
        missing.append("tags")
    if field_is_empty(frontmatter, "categories"):
        missing.append("categories")

    context = f'Post title: {current_title}\n' if current_title else ''
    context += f'Post content:\n{body[:MAX_BODY_CHARS]}'

    fields_desc = {
        "title": 'a short, punchy title (max 60 chars) that names the post\'s main topic',
        "description": 'one sentence (max 160 chars) summarizing what the post is about, written in your own words in the author\'s conversational, personal tone. Do not copy sentences from the post',
        "tags": 'a JSON array of 2-4 lowercase tag strings, each 1-2 words, hyphenated (e.g. "note-taking")',
        "categories": 'a JSON array with exactly one category string, chosen from: ["personal", "tech", "books", "fitness", "productivity"]',
    }

    metadata = {}
    if "categories" in missing:
        category = jev_category(context)
        if category:
            metadata["categories"] = [category]
            missing.remove("categories")
    if not missing:
        return metadata

    requested = {f: fields_desc[f] for f in missing}
    fields_list = "\n".join(f'- "{k}": {v}' for k, v in requested.items())

    prompt = (
        f"{context}\n\n"
        f"Based on the post above, generate the following metadata fields:\n"
        f"{fields_list}\n\n"
        f"Return ONLY a valid JSON object with these keys. No explanation, no markdown."
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
        "options": {"num_predict": 200},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat", data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.loads(resp.read())["message"]["content"].strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return {**clean_metadata(json.loads(raw), missing), **metadata}


ALLOWED_CATEGORIES = ["personal", "tech", "books", "fitness", "productivity"]


def jev_category(context):
    """Pick the category with TypeSafe's Jev classifier; None means fall back to Ollama."""
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        return None
    payload = json.dumps({
        "model": "jev-latest",
        "state": context,
        "questions": {"category": {
            "type": "choice",
            "instructions": "Which blog category fits this post best?",
            "criteria": {c: None for c in ALLOWED_CATEGORIES},
        }},
    }).encode("utf-8")
    req = urllib.request.Request(
        JEV_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            choice = json.loads(resp.read())["answers"]["category"]["choice"]
    except (OSError, ValueError, KeyError) as e:
        print(f"  WARNING: Jev failed, using Ollama for category: {e}")
        return None
    return choice if choice in ALLOWED_CATEGORIES else None


def clean_metadata(metadata, missing):
    cleaned = {}
    if "title" in missing and isinstance(metadata.get("title"), str):
        cleaned["title"] = metadata["title"].strip()[:60]
    if "description" in missing and isinstance(metadata.get("description"), str):
        cleaned["description"] = metadata["description"].strip()[:160]
    if "tags" in missing and isinstance(metadata.get("tags"), list):
        tags = [re.sub(r"[^a-z0-9-]+", "-", str(t).lower()).strip("-") for t in metadata["tags"]]
        cleaned["tags"] = [t for t in tags if t][:4]
    if "categories" in missing and isinstance(metadata.get("categories"), list):
        match = [c for c in metadata["categories"] if c in ALLOWED_CATEGORIES]
        cleaned["categories"] = match[:1]
    return {k: v for k, v in cleaned.items() if v}


def apply_metadata(frontmatter, metadata):
    fm = frontmatter

    if "title" in metadata:
        title = metadata["title"].replace('"', '\\"')
        fm = re.sub(r'^(title\s*=\s*)""', f'\\1"{title}"', fm, flags=re.MULTILINE)

    if "description" in metadata:
        desc = metadata["description"].replace('"', '\\"')
        fm = re.sub(r'^(description\s*=\s*)""', f'\\1"{desc}"', fm, flags=re.MULTILINE)

    if "tags" in metadata:
        tags = metadata["tags"]
        if isinstance(tags, list):
            tags_str = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
            fm = re.sub(r'^(tags\s*=\s*)\[\]', f'\\1{tags_str}', fm, flags=re.MULTILINE)

    if "categories" in metadata:
        cats = metadata["categories"]
        if isinstance(cats, list):
            cats_str = "[" + ", ".join(f'"{c}"' for c in cats) + "]"
            fm = re.sub(r'^(categories\s*=\s*)\[\]', f'\\1{cats_str}', fm, flags=re.MULTILINE)

    return fm


def enrich_file(model, path):
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    if frontmatter is None:
        return False
    if not needs_enrichment(frontmatter):
        return False

    metadata = generate_metadata(model, frontmatter, body)
    new_frontmatter = apply_metadata(frontmatter, metadata)

    new_text = f"+++\n{new_frontmatter}\n+++\n{body}"
    path.write_text(new_text, encoding="utf-8")
    filled = ", ".join(metadata.keys())
    print(f"  enriched [{filled}]: {path.name}")
    return True


def main():
    model = get_client()

    md_files = list(BLOG_DIR.rglob("*.md"))
    enriched = 0
    for path in md_files:
        try:
            if enrich_file(model, path):
                enriched += 1
        except Exception as e:
            print(f"  WARNING: failed to enrich {path.name}: {e}")

    if enriched:
        print(f"Enriched {enriched} post(s).")
    else:
        print("No posts needed metadata enrichment.")


if __name__ == "__main__":
    main()
