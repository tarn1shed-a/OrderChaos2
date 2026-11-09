#!/bin/zsh
# Local research service for the original ELF, using a separate project snapshot.
set -eu
project_root="${0:A:h:h}"
tool_root="$HOME/Applications/OC2Tools"
export JAVA_HOME="$tool_root/jdk-25.0.5+8/Contents/Home"
export GHIDRA_INSTALL_DIR="$tool_root/ghidra_12.2_PUBLIC"
exec "$tool_root/ghidra-mcp-venv/bin/ghidra-mcp" \
  --headless --no-analyze --save \
  --binary "$project_root/analysis/raw/ghidra-20261110/input/libOrderChaos2.so" \
  --project "$project_root/analysis/raw/ghidra-mcp-projects" \
  --project-name OC2_31320_ARM64 \
  --extension-jar "$tool_root/GhidraMCP/extension/build/libs/GhidraMCP.jar" \
  --transport streamable-http --mcp-host 127.0.0.1 --mcp-port 8766
