"""Only explicit current body keys and an explicit readable-gather entry."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'tools')]
from world_gather_delivery_v1.portable import materialize

if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit('usage: materialize.py ABSOLUTE_PYTHON FROZEN_ENTRY_KEY BODY_KEY [BODY_KEY ...]')
    print(materialize(sys.argv[1], sys.argv[3:], sys.argv[2]))
