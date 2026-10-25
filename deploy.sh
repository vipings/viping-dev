#!/bin/bash
set -e

DRY_RUN=0
[ "$1" = "--dry-run" ] && DRY_RUN=1

VAULT_DIR="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/viping.dev"
ZOLA_DIR=~/viping-dev/content/blog
ZOLA_BIN="$HOME/zola-0.18/zola"

cd ~/viping-dev

# Load env vars (needed when launched from GUI apps like Obsidian)
[ -f ~/.zshenv ] && source ~/.zshenv

# Enrich vault posts BEFORE rsync so enriched metadata is never overwritten
if [ $DRY_RUN = 0 ]; then
  BLOG_DIR="$VAULT_DIR/Blog" python3 ~/viping-dev/scripts/enrich_metadata.py
fi

# Sync blog posts from the Blog/ subfolder in the vault
rsync -av ${DRY_RUN:+--dry-run} \
  "$VAULT_DIR/Blog/" "$ZOLA_DIR/"

# Zola build (dry run writes to a temp dir so public/ is untouched)
if [ $DRY_RUN = 1 ]; then
  "$ZOLA_BIN" build --output-dir "$(mktemp -d)/site"
  echo "Dry run: skipping commit and push"
  exit 0
fi
"$ZOLA_BIN" build

# Git commit + push (only if there are changes)
git add content/blog/
if git commit -m "blog: publish latest posts from vault" --no-gpg-sign 2>/dev/null; then
  git push origin main
  echo "✅ Blog updated and deployed!"
else
  echo "✅ No changes to deploy (everything is up to date)"
fi
