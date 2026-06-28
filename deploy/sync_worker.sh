#!/usr/bin/env bash
# Sync the render worker repo with this repo's source of truth.
#
# The cloud render runs in a SEPARATE public repo ($WORKER) which keeps its own
# copy of deploy/ci_render.py. That copy drifts whenever we fix ci_render.py here
# and forget to push it there — which is exactly what broke the smoke test
# ("No render.mp4 found in media/videos": the worker was running an old script
# that rendered with `-o render.mp4` instead of locating GenScene.mp4).
#
# Run this after any change to deploy/ci_render.py. Requires: gh (authenticated).
set -euo pipefail

WORKER="${CLOUD_RENDER_REPO:-gopheriv/manim-render-worker}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/ci_render.py"
DEST="deploy/ci_render.py"

echo ">> Syncing $DEST -> $WORKER"

# Skip the push if the remote already matches (avoids an empty commit).
remote_b64="$(gh api "repos/$WORKER/contents/$DEST" -q .content 2>/dev/null | tr -d '\n' || true)"
local_b64="$(base64 -w0 "$SRC")"
if [ -n "$remote_b64" ] && [ "$(printf '%s' "$remote_b64" | base64 -d | shasum)" = "$(base64 -d <<<"$local_b64" | shasum)" ]; then
  echo ">> Already up to date. Nothing to push."
  exit 0
fi

sha="$(gh api "repos/$WORKER/contents/$DEST" -q .sha 2>/dev/null || true)"
args=(-X PUT "repos/$WORKER/contents/$DEST"
      -f "message=fix: render GenScene and locate GenScene.mp4 (sync from manim-bot)"
      -f "content=$local_b64")
[ -n "$sha" ] && args+=(-f "sha=$sha")

commit="$(gh api "${args[@]}" -q '.commit.sha')"
echo ">> Pushed. Worker commit: $commit"
echo ">> Done. Run a smoke test:  python deploy/smoke_cloud.py"
