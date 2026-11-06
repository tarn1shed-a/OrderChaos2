#!/bin/zsh
set -eu
TASK_DIR="${0:A:h}"
cd "$TASK_DIR/prototype"
if [[ -n "${NODE_BIN:-}" ]]; then
  TASK_NODE="$NODE_BIN"
elif command -v node >/dev/null 2>&1; then
  TASK_NODE="$(command -v node)"
elif [[ -x "$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node" ]]; then
  TASK_NODE="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
else
  print '请先安装 Node.js 22.13 或更高版本，再在 prototype 目录安装依赖并启动。'
  exit 1
fi
"$TASK_NODE" -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 13)) { console.error("需要 Node.js 22.13 或更高版本"); process.exit(1); }'
if [[ ! -d node_modules/ws || ! -d node_modules/three ]]; then
  print '缺少依赖。请先在 prototype 目录运行：pnpm install --frozen-lockfile'
  exit 1
fi
exec "$TASK_NODE" --env-file-if-exists="$TASK_DIR/.env" server.mjs
