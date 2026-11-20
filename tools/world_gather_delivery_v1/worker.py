"""Verified readable-gather source entry, not a native algorithm/clock."""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'tools')]
from world_gather_delivery_v1.portable import run

if __name__ == '__main__':
    run(sys.argv[1], __file__)
