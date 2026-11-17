"""Named subset materialization through the same frozen path-only core."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[2]/'tools')]
from world_latest_delivery_v1.portable import materialize
if __name__=='__main__':
    if len(sys.argv)<4:raise SystemExit('usage: materialize.py ABS_PYTHON ENTRY_KEY BODY_KEY [BODY_KEY ...]')
    print(materialize(sys.argv[1],sys.argv[3:],sys.argv[2]))
