#!/bin/zsh
set -eu
TASK_ROOT="$(cd "$(dirname "$0")" && pwd)"
TASK_NODE="${OC2_NODE:-$(command -v node || true)}"
if [[ -z "$TASK_NODE" ]]; then
  TASK_NODE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
fi
if [[ ! -x "$TASK_NODE" ]]; then
  print -u2 '找不到 Node.js。请安装 Node.js 22.13 或更新版本，或设置 OC2_NODE。'
  exit 1
fi
exec "$TASK_NODE" "$TASK_ROOT/tools/local_mvp.mjs" "$@"
