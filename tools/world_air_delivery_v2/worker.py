"""One portable entry into the unchanged shared first-history native worker."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools')]
from world_air_delivery_v2.portable import run

if __name__ == '__main__':
    run(sys.argv[1], __file__)
