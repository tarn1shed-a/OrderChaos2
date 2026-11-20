"""Only generate a new projected config in an already verified private root."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from female_world_delivery.portal import RUNTIME,CONFIG,projected,inside,validate
def materialize(python):
 plan=json.loads(inside('native-inputs/player-human-female-actions-v1/projection.json').read_text())
 recipe=json.loads(inside(plan['recipeTarget']).read_text());cfg=projected(recipe,plan,python);validate(cfg)
 p=inside(CONFIG)
 if p.exists():p.unlink() # Only this explicitly derived new config, never source inputs.
 p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
 return p
if __name__=='__main__':print(materialize(sys.argv[1]))
