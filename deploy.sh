#!/bin/bash
set -e

VAULT_DIR="/Users/vpillai/Library/Mobile Documents/iCloud~md~obsidian/Documents/viping.dev"
ZOLA_DIR=~/viping-dev/content/blog

# Sync blog posts from the Blog/ subfolder in the vault
rsync -av \
  "$VAULT_DIR/Blog/" "$ZOLA_DIR/"

cd ~/viping-dev

# Load env vars (needed when launched from GUI apps like Obsidian)
[ -f ~/.zshenv ] && source ~/.zshenv
[ -f ~/.zshrc ] && source ~/.zshrc

# Enrich empty post descriptions using Claude
python3 ~/viping-dev/scripts/enrich_metadata.py

# Zola build
/usr/local/bin/zola build

# Git commit + push (only if there are changes)
git add content/blog/
if git commit -m "blog: publish latest posts from vault" --no-gpg-sign 2>/dev/null; then
  git push origin main
  echo "✅ Blog updated and deployed!"
else
  echo "✅ No changes to deploy (everything is up to date)"
fi
