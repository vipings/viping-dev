#!/usr/bin/env python3
"""Auto-fill empty post metadata (title, description, tags, categories) using Claude."""

import json
import os
import re
import sys
from pathlib import Path

BLOG_DIR = Path(os.environ.get("BLOG_DIR", Path.home() / "viping-dev" / "content" / "blog"))
MAX_BODY_CHARS = 800


def get_client():
    try:
        import anthropic
    except ImportError:
        print("WARNING: anthropic package not installed — skipping enrichment")
        print("  Run: pip3 install anthropic")
        sys.exit(0)

    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    bedrock_url = os.environ.get("ANTHROPIC_BEDROCK_BASE_URL")

    if api_key:
        return anthropic.Anthropic(api_key=api_key)
    elif bedrock_url and auth_token:
        # Salesforce Bedrock gateway — standard Anthropic client with custom base URL
        return anthropic.Anthropic(api_key=auth_token, base_url=bedrock_url)
    else:
        print("WARNING: No API credentials found — skipping metadata enrichment")
        print("  Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BEDROCK_BASE_URL")
        sys.exit(0)


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


def generate_metadata(client, frontmatter, body):
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
        "title": 'a short, punchy title (max 60 chars)',
        "description": 'a single sentence description (max 160 chars) in the author\'s conversational, personal tone',
        "tags": 'a JSON array of 2-4 lowercase tag strings',
        "categories": 'a JSON array with exactly one category string from: ["personal", "tech", "books", "fitness", "productivity"]',
    }

    requested = {f: fields_desc[f] for f in missing}
    fields_list = "\n".join(f'- "{k}": {v}' for k, v in requested.items())

    prompt = (
        f"{context}\n\n"
        f"Based on the post above, generate the following metadata fields:\n"
        f"{fields_list}\n\n"
        f"Return ONLY a valid JSON object with these keys. No explanation, no markdown."
    )

    message = client.messages.create(
        model=os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5"),
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


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


def enrich_file(client, path):
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    if frontmatter is None:
        return False
    if not needs_enrichment(frontmatter):
        return False

    metadata = generate_metadata(client, frontmatter, body)
    new_frontmatter = apply_metadata(frontmatter, metadata)

    new_text = f"+++\n{new_frontmatter}\n+++\n{body}"
    path.write_text(new_text, encoding="utf-8")
    filled = ", ".join(metadata.keys())
    print(f"  enriched [{filled}]: {path.name}")
    return True


def main():
    client = get_client()

    md_files = list(BLOG_DIR.rglob("*.md"))
    enriched = 0
    for path in md_files:
        try:
            if enrich_file(client, path):
                enriched += 1
        except Exception as e:
            print(f"  WARNING: failed to enrich {path.name}: {e}")

    if enriched:
        print(f"Enriched {enriched} post(s).")
    else:
        print("No posts needed metadata enrichment.")


if __name__ == "__main__":
    main()
