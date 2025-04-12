#!/bin/bash

VAULT_DIR=~/obsidean-viping-dev/viping.dev
ZOLA_DIR=~/viping-dev/content/blog

# Sync blog posts, exclude .obsidian/ and templates/
rsync -av --update \
  --exclude=".obsidian/" \
  --exclude="templates/" \
  "$VAULT_DIR/" "$ZOLA_DIR/"

cd ~/viping-dev

# Optional: verify Zola builds
zola build

# Commit and push
git add content/blog/
git commit -m "blog: publish latest posts from vault"
git push origin main

echo "✅ Blog updated and deployed!"