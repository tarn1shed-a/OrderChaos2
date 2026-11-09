#!/bin/zsh
# Open the local original-ELF analysis project; never starts the game.
set -eu
project_root="${0:A:h:h}"
ghidra_root="${OC2_GHIDRA_ROOT:-$HOME/Applications/OC2Tools/ghidra_12.2_PUBLIC}"
export JAVA_HOME="${OC2_JDK_ROOT:-$HOME/Applications/OC2Tools/jdk-25.0.5+8/Contents/Home}"
project_file="$project_root/analysis/raw/ghidra-projects/OC2_31320_ARM64.gpr"
if [[ ! -f "$project_file" || ! -x "$ghidra_root/ghidraRun" || ! -x "$JAVA_HOME/bin/java" ]]; then
  print -u2 'Missing local Ghidra, JDK or imported project. See docs/GHIDRA_MAP_FLOW.md.'
  exit 1
fi
# Keep the Java process attached so desktop/terminal launchers retain it.
exec "$ghidra_root/support/launch.sh" fg jdk Ghidra 8G '' ghidra.GhidraRun "$project_file"
