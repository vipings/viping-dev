#!/bin/bash
set -e

VAULT_DIR="/Users/vpillai/Library/Mobile Documents/iCloud~md~obsidian/Documents/viping.dev"
ZOLA_DIR=~/viping-dev/content/blog

# Sync blog posts, exclude .obsidian/ and templates/
rsync -av --update \
  --exclude=".obsidian/" \
  --exclude="templates/" \
  "$VAULT_DIR/" "$ZOLA_DIR/"

cd ~/viping-dev

# Zola build
/usr/local/bin/zola build

# Git commit + push
git add content/blog/
git commit -m "blog: publish latest posts from vault" --no-gpg-sign
git push origin main

echo "✅ Blog updated and deployed!"
