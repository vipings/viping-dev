#!/bin/bash

VAULT_DIR=~/obsidean-viping-dev/viping.dev
ZOLA_DIR=~/viping-dev/content/blog

# Sync blog posts (copies new or updated ones)
rsync -av --update "$VAULT_DIR/" "$ZOLA_DIR/"

cd ~/viping-dev

# Commit and push
git add content/blog/
git commit -m "blog: sync and deploy latest posts"
git push origin main

echo "✅ Blog post pushed! Deploy will trigger via GitHub Actions."