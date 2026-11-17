"""Same frozen stdin transport, explicit portable Female15 provider only."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from female_world_delivery.portal import load
from female_air_null.source import source_method
import player_choice_human_male_air_worker as original
def own_load(path):
 e,cfg,info,methods=load(path,qa_evidence=False)
 return e,info
start,START_SHA=source_method(original.start,[("'human-male'","'human-female'",3),("valueBytes':1992","valueBytes':1928",1)],{'load':own_load,'FIELD':'sourceFemalePose'})
if __name__=='__main__':start(sys.argv[1])
