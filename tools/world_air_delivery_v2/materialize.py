"""Generate only named new derivative configs in the installed private root."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'tools')]
from world_air_delivery_v2.portable import materialize

if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit('usage: materialize.py ABSOLUTE_PYTHON FROZEN_ENTRY_KEY BODY_KEY [BODY_KEY ...]')
    print(materialize(sys.argv[1], sys.argv[3:], sys.argv[2]))
