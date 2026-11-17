"""One composed start: Player normal core plus NPC readonly frame observer.

No normal algorithm, RPC parser/loop, clock, engine or approval is implemented
here. Gather flags on the Node host do not select a different normal loader.
"""
from pathlib import Path
import hashlib,importlib.util
from player_world_normal_sync_v1 import worker as normal
from source_own_gather_runtime_v1 import worker as readable
from source_gather_frame_v1.hook import compose_start

ROOT=Path(__file__).resolve().parents[2]
FACTS=ROOT/'analysis/raw/common-eight-gather-run-prefix-20261117/native_posture.py'
FACTS_SHA='1e250d4fa1625faf33fd6d974d1acc2896b2a1899511fa633bd94ded2ffaa351'
if hashlib.sha256(FACTS.read_bytes()).hexdigest()!=FACTS_SHA:
    raise ValueError('Exact original readonly posture facts helper required')
spec=importlib.util.spec_from_file_location('_latest_own_native_posture',FACTS)
facts=importlib.util.module_from_spec(spec);spec.loader.exec_module(facts)
start=compose_start(normal,readable.ReadableRuntimeRPC,read_native_facts=facts.read_own_posture_facts)
