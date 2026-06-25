#!/usr/bin/env bash
# Deploy recommender API to EC2 (single host).
#
# This script ONLY syncs the Python source files we touched. It does NOT
# touch any data, model files, or anything else under recomender/etl/data/.
# It does NOT use --delete, so existing remote files are never removed.
#
# Usage:
#   export SSH_KEY=~/.ssh/recommender-key.pem
#   ./scripts/deploy-recommender.sh
#
# Optional env vars:
#   EC2_HOST       (default: 18.143.45.118)
#   REMOTE_USER    (default: ubuntu)
#   REMOTE_PATH    (default: /home/ubuntu/e-shop)

set -euo pipefail

EC2_HOST="${EC2_HOST:-18.143.45.118}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/recommender-key.pem}"
REMOTE_USER="${REMOTE_USER:-ubuntu}"
REMOTE_PATH="${REMOTE_PATH:-/home/ubuntu/e-shop}"

LOCAL_REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new)

# Exact list of files this deploy ships. Add to the list if a future task
# changes more files. Keeping the list explicit avoids accidentally pushing
# data, model checkpoints, or stale venv contents.
FILES=(
  "recomender/etl/Content_Base_Model/recommendation_api.py"
  "recomender/etl/Content_Base_Model/qdrant_vector_store.py"
  "recomender/etl/Content_Base_Model/tests/__init__.py"
  "recomender/etl/Content_Base_Model/tests/test_recommendation_by_text.py"
)

echo "==> Local repo:   $LOCAL_REPO"
echo "==> Remote host:  $REMOTE_USER@$EC2_HOST"
echo "==> Remote path:  $REMOTE_PATH"
echo "==> SSH key:      $SSH_KEY"
echo "==> Files to deploy:"
printf '    - %s\n' "${FILES[@]}"
echo

# ---- 1. Sync only the explicit files ----------------------------------------
echo "==> [1/4] rsync code (no data, no --delete)..."
for rel in "${FILES[@]}"; do
  src="$LOCAL_REPO/$rel"
  if [[ ! -f "$src" ]]; then
    echo "    SKIP (missing locally): $rel"
    continue
  fi
  # rsync the single file. -R keeps the directory structure so tests/ lands
  # inside Content_Base_Model on the remote.
  rsync -avzR \
    -e "ssh ${SSH_OPTS[*]}" \
    --no-perms --chmod=ugo=rwX \
    "$LOCAL_REPO/./$rel" \
    "$REMOTE_USER@$EC2_HOST:$REMOTE_PATH/"
done

# ---- 2. Sanity check on EC2 -------------------------------------------------
echo "==> [2/4] verifying files landed on EC2..."
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$EC2_HOST" "set -e
  cd $REMOTE_PATH
  for f in ${FILES[*]}; do
    test -f \"\$f\" && echo \"    OK \$f\" || { echo \"    MISSING \$f\"; exit 1; }
  done
"

# ---- 3. Rebuild + restart api container -------------------------------------
echo "==> [3/4] docker compose build + recreate 'api' container..."
ssh "${SSH_OPTS[@]}" "$REMOTE_USER@$EC2_HOST" "set -e
  cd $REMOTE_PATH/recomender/Docker
  docker compose build api
  docker compose up -d --force-recreate api
"

# ---- 4. Health + endpoint smoke test ----------------------------------------
echo "==> [4/4] waiting for /health..."
until curl -fs --max-time 3 "http://$EC2_HOST:8000/health" >/dev/null; do
  echo "    ... still warming up"
  sleep 3
done

echo
echo "✅ Deploy complete"
echo
echo "Health response:"
curl -s "http://$EC2_HOST:8000/health" | python3 -m json.tool || true

echo
echo "Test /recommend/by-text:"
curl -s -X POST "http://$EC2_HOST:8000/recommend/by-text" \
  -H "Content-Type: application/json" \
  -d '{"query":"lightweight summer shirt for hiking","k":5}' \
  | python3 -m json.tool || true
