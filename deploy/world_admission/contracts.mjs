// Frozen own body data, not preparation, admission or creation approval.
const freeze=v=>{if(v&&typeof v==='object'){for(const x of Object.values(v))freeze(x);Object.freeze(v);}return v;};
export const WORLD_BODY_CONTRACTS=freeze({
  "human-male": {
    "id": "human-male:ground",
    "bodyKey": "human-male",
    "mode": "ground",
    "poseField": "sourceHumanPose",
    "policy": {
      "bodyKey": "human-male",
      "modelId": 1,
      "mapId": 1,
      "motionSHA256": "14adc20cc5f602ab97c9f10414522a38e7590199efc90cb57dfe0868af21cada",
      "bindingId": "4032ecda85c04ddd350db92ff1eee1a8934ad5b3f69bb3236ea0cc2810609b85",
      "valueBytes": 1992
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "14adc20cc5f602ab97c9f10414522a38e7590199efc90cb57dfe0868af21cada",
      "key": "human-male",
      "race": 0,
      "gender": 0,
      "sourceModelId": 1
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 135
  },
  "human-female": {
    "id": "human-female:normal15",
    "bodyKey": "human-female",
    "mode": "normal15",
    "poseField": "sourceFemalePose",
    "policy": {
      "bodyKey": "human-female",
      "modelId": 32,
      "mapId": 1,
      "motionSHA256": "c5c940718e49f560ed7160209687b1417d6231cf5ec479a723bc89c1b42763d1",
      "bindingId": "15aab4f91ae4e3eca40bc5ef7759569c608d70932912bcfab979a707c3648d5d",
      "valueBytes": 1928
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "c5c940718e49f560ed7160209687b1417d6231cf5ec479a723bc89c1b42763d1",
      "key": "human-female",
      "race": 0,
      "gender": 1,
      "sourceModelId": 32
    },
    "capabilities": {
      "jump": true,
      "gatherHostPort": true
    },
    "evidenceScope": "existing own normal15 input/first-pose port",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 131
  },
  "elf-male": {
    "id": "elf-male:ground",
    "bodyKey": "elf-male",
    "mode": "ground",
    "poseField": "sourceElfMalePose",
    "policy": {
      "bodyKey": "elf-male",
      "modelId": 33,
      "mapId": 1,
      "motionSHA256": "e2ea3c4f68f15b7ae9bcdd2bf4072804b3e62ad3dac8c2f3737bd9b34a05f8c7",
      "bindingId": "f9116aa4389602967a49d9c05ca554b5921ac10f5a6a58f995da9f87a690a24c",
      "valueBytes": 1192
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "e2ea3c4f68f15b7ae9bcdd2bf4072804b3e62ad3dac8c2f3737bd9b34a05f8c7",
      "key": "elf-male",
      "race": 1,
      "gender": 0,
      "sourceModelId": 33
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 82
  },
  "orc-male": {
    "id": "orc-male:ground",
    "bodyKey": "orc-male",
    "mode": "ground",
    "poseField": "sourceOrcMalePose",
    "policy": {
      "bodyKey": "orc-male",
      "modelId": 28,
      "mapId": 1,
      "motionSHA256": "7a1c1bdec1d24758d51b9729935a97b937963a151ab01c7ec873c591a532cfad",
      "bindingId": "065340cd06bd0ed6ac4da8597c27db65f5edeb20d72ab1e1c8caf31cffece4c9",
      "valueBytes": 2120
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "7a1c1bdec1d24758d51b9729935a97b937963a151ab01c7ec873c591a532cfad",
      "key": "orc-male",
      "race": 2,
      "gender": 0,
      "sourceModelId": 28
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 146
  },
  "elf-female": {
    "id": "elf-female:ground",
    "bodyKey": "elf-female",
    "mode": "ground",
    "poseField": "sourceElfFemalePose",
    "policy": {
      "bodyKey": "elf-female",
      "modelId": 2,
      "mapId": 1,
      "motionSHA256": "2347556404f2a5967b57e1fa19958912e6fe580806c4590897437bdd21c413e5",
      "bindingId": "f7315b6c3d7801862531672f7ad22d69e19ac8e6c6b04bbe0513f0fc945ebc01",
      "valueBytes": 1536
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "2347556404f2a5967b57e1fa19958912e6fe580806c4590897437bdd21c413e5",
      "key": "elf-female",
      "race": 1,
      "gender": 1,
      "sourceModelId": 2
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 110
  },
  "mendel-male": {
    "id": "mendel-male:ground",
    "bodyKey": "mendel-male",
    "mode": "ground",
    "poseField": "sourceMendelMalePose",
    "policy": {
      "bodyKey": "mendel-male",
      "modelId": 34,
      "mapId": 1,
      "motionSHA256": "5ad334301aec53618b7a23a2fb385d0717e0868fc2078aba9bb0acacb07c4684",
      "bindingId": "3b6bc28e94d68d7936a49221bfb44fe1fd10320befb15df588497a5471ca4d6c",
      "valueBytes": 1136
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "5ad334301aec53618b7a23a2fb385d0717e0868fc2078aba9bb0acacb07c4684",
      "key": "mendel-male",
      "race": 5,
      "gender": 0,
      "sourceModelId": 34
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 78
  },
  "mendel-female": {
    "id": "mendel-female:ground",
    "bodyKey": "mendel-female",
    "mode": "ground",
    "poseField": "sourceMendelFemalePose",
    "policy": {
      "bodyKey": "mendel-female",
      "modelId": 31,
      "mapId": 1,
      "motionSHA256": "75bc8f679224324bf3c51274e77c8caadb84f9e341c7575bf11888de0cb32bbc",
      "bindingId": "ab388faf693e5360f27ff7d6706809c452d8d194ffe717a02744e83996848ccf",
      "valueBytes": 1496
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "75bc8f679224324bf3c51274e77c8caadb84f9e341c7575bf11888de0cb32bbc",
      "key": "mendel-female",
      "race": 5,
      "gender": 1,
      "sourceModelId": 31
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 107
  },
  "orc-female": {
    "id": "orc-female:ground",
    "bodyKey": "orc-female",
    "mode": "ground",
    "poseField": "sourceOrcFemalePose",
    "policy": {
      "bodyKey": "orc-female",
      "modelId": 30,
      "mapId": 1,
      "motionSHA256": "6998976fe27a9774798b6cff6376d82c96f693127f4f7972ab8b24f51c6b6628",
      "bindingId": "5ab692faff86e12513ac4e54d2a6e33405b06d47cd5a88da0f1a58365ff36a7b",
      "valueBytes": 1332
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "6998976fe27a9774798b6cff6376d82c96f693127f4f7972ab8b24f51c6b6628",
      "key": "orc-female",
      "race": 2,
      "gender": 1,
      "sourceModelId": 30
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 95
  },
  "kartan": {
    "id": "kartan:ground",
    "bodyKey": "kartan",
    "mode": "ground",
    "poseField": "sourceKartanPose",
    "policy": {
      "bodyKey": "kartan",
      "modelId": 29,
      "mapId": 1,
      "motionSHA256": "e1001d1f158475e064031dec519b4749124c978409bd5d445011e9af7b33e157",
      "bindingId": "3d00ad93928a7c162399713eb707b32ee459d8408f8ac7d25fa0a8765a873bf3",
      "valueBytes": 1264
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "e1001d1f158475e064031dec519b4749124c978409bd5d445011e9af7b33e157",
      "key": "kartan",
      "race": 4,
      "gender": 0,
      "sourceModelId": 29
    },
    "capabilities": {
      "jump": false,
      "gatherHostPort": false
    },
    "evidenceScope": "frozen own ground packet/consumer; common bridge/first-pose integration still required",
    "creationAuthorizedByIndex": false,
    "sourceProperties": 86
  }
});

export const LEGACY_WORLD_CONTRACT_SET=freeze({id:'legacy-ground-hf-normal15',sourceIndexSHA256:null,contracts:WORLD_BODY_CONTRACTS});
export const SOURCE_WORLD_CONTRACT_SET=freeze({id:'source-eight-own-air-hf-normal15',sourceIndexSHA256:"643189e7ad56edf1b114cf3435907ddba56d406159b98460eaf84a05fb0d6f88",contracts:freeze({
  "elf-male": {
    "id": "elf-male:own-air",
    "bodyKey": "elf-male",
    "mode": "own-air",
    "poseField": "sourceElfMalePose",
    "policy": {
      "bodyKey": "elf-male",
      "modelId": 33,
      "mapId": 1,
      "motionSHA256": "be34ab1d98a20d2ece59eef20d70967853006beeb34da6c7ffd4acfe6fadcf8a",
      "bindingId": "1c8834ef042f4f34f007c02b0623f47ec0bdc01bc79f0489d1745b220dc1acbf",
      "valueBytes": 1192
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "be34ab1d98a20d2ece59eef20d70967853006beeb34da6c7ffd4acfe6fadcf8a",
      "key": "elf-male",
      "race": 1,
      "gender": 0,
      "sourceModelId": 33
    },
    "sourceProperties": 82,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "orc-male": {
    "id": "orc-male:own-air",
    "bodyKey": "orc-male",
    "mode": "own-air",
    "poseField": "sourceOrcMalePose",
    "policy": {
      "bodyKey": "orc-male",
      "modelId": 28,
      "mapId": 1,
      "motionSHA256": "eefd6665128219c93b33942c72d9acf3025e1a664129ec40d1831174d1b0c05d",
      "bindingId": "c1ef0d576fad2709112e726fc05e681274764f62e3acb228aae48d7d4f1ff763",
      "valueBytes": 2120
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "eefd6665128219c93b33942c72d9acf3025e1a664129ec40d1831174d1b0c05d",
      "key": "orc-male",
      "race": 2,
      "gender": 0,
      "sourceModelId": 28
    },
    "sourceProperties": 146,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "mendel-male": {
    "id": "mendel-male:own-air",
    "bodyKey": "mendel-male",
    "mode": "own-air",
    "poseField": "sourceMendelMalePose",
    "policy": {
      "bodyKey": "mendel-male",
      "modelId": 34,
      "mapId": 1,
      "motionSHA256": "d175d7951b265b2fae4f59fc1513bef93001963c10e36874c058366eff07a18a",
      "bindingId": "e1b943cdfeaa9b8b10aca6324c74a478ec783212b86cfbb4282ae3388a7d0e7c",
      "valueBytes": 1136
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "d175d7951b265b2fae4f59fc1513bef93001963c10e36874c058366eff07a18a",
      "key": "mendel-male",
      "race": 5,
      "gender": 0,
      "sourceModelId": 34
    },
    "sourceProperties": 78,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "mendel-female": {
    "id": "mendel-female:own-air",
    "bodyKey": "mendel-female",
    "mode": "own-air",
    "poseField": "sourceMendelFemalePose",
    "policy": {
      "bodyKey": "mendel-female",
      "modelId": 31,
      "mapId": 1,
      "motionSHA256": "24bd82303f6a261a007d63ca41ab1086e9d76c6e5becc26e1e0c97a2047c044d",
      "bindingId": "a6f6804dfff13ac43e4758f6b51791ba777671028b988b96ae5d6feef2e58084",
      "valueBytes": 1496
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "24bd82303f6a261a007d63ca41ab1086e9d76c6e5becc26e1e0c97a2047c044d",
      "key": "mendel-female",
      "race": 5,
      "gender": 1,
      "sourceModelId": 31
    },
    "sourceProperties": 107,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "orc-female": {
    "id": "orc-female:own-air",
    "bodyKey": "orc-female",
    "mode": "own-air",
    "poseField": "sourceOrcFemalePose",
    "policy": {
      "bodyKey": "orc-female",
      "modelId": 30,
      "mapId": 1,
      "motionSHA256": "2e9a5d7d0e55f6c9ab8eb09cb36df29630a7a6199f4d0084bd1936c9a41f094e",
      "bindingId": "248363cb903bc87ddaabe8de6947ab24d5abbf1c5428ff1a0a3f0273d9199949",
      "valueBytes": 1332
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "2e9a5d7d0e55f6c9ab8eb09cb36df29630a7a6199f4d0084bd1936c9a41f094e",
      "key": "orc-female",
      "race": 2,
      "gender": 1,
      "sourceModelId": 30
    },
    "sourceProperties": 95,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "kartan": {
    "id": "kartan:own-air",
    "bodyKey": "kartan",
    "mode": "own-air",
    "poseField": "sourceKartanPose",
    "policy": {
      "bodyKey": "kartan",
      "modelId": 29,
      "mapId": 1,
      "motionSHA256": "cb1665bc16d16d0e785ebcedf1279e3fa19edac16cd4403788c1dd7cc6a7fefc",
      "bindingId": "90b532e89c1078c53d5c51afbe3059adf596481b3482037daa95ab9604648064",
      "valueBytes": 1264
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "cb1665bc16d16d0e785ebcedf1279e3fa19edac16cd4403788c1dd7cc6a7fefc",
      "key": "kartan",
      "race": 4,
      "gender": 0,
      "sourceModelId": 29
    },
    "sourceProperties": 86,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "human-male": {
    "id": "human-male:own-air",
    "bodyKey": "human-male",
    "mode": "own-air",
    "poseField": "sourceHumanPose",
    "policy": {
      "bodyKey": "human-male",
      "modelId": 1,
      "mapId": 1,
      "motionSHA256": "306f6aece71c7c6373386c3692046980c97099ee39ecef2398d4097a5fcea057",
      "bindingId": "eedb6330788c25a92203db8162a0be57df2506cd5d1c0e3994a8348ab59f9a53",
      "valueBytes": 1992
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "306f6aece71c7c6373386c3692046980c97099ee39ecef2398d4097a5fcea057",
      "key": "human-male",
      "race": 0,
      "gender": 0,
      "sourceModelId": 1
    },
    "sourceProperties": 135,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  },
  "elf-female": {
    "id": "elf-female:own-air",
    "bodyKey": "elf-female",
    "mode": "own-air",
    "poseField": "sourceElfFemalePose",
    "policy": {
      "bodyKey": "elf-female",
      "modelId": 2,
      "mapId": 1,
      "motionSHA256": "be47f327b040e7328a8762be56c98a5cf7d1cf804a07ec1388e370d09551990e",
      "bindingId": "4a62b1869dc491d572c0936ecfe23490e88e44ab6d6f74eef4ffd44908362a17",
      "valueBytes": 1536
    },
    "sourceMotion": {
      "format": "oc2-source-species-motion-v1",
      "sha256": "be47f327b040e7328a8762be56c98a5cf7d1cf804a07ec1388e370d09551990e",
      "key": "elf-female",
      "race": 1,
      "gender": 1,
      "sourceModelId": 2
    },
    "sourceProperties": 110,
    "capabilities": {
      "jump": true,
      "gatherHostPort": false
    },
    "evidenceScope": "fixed own runtime-index; still requires real preparation/bootstrap/consumed first pose",
    "creationAuthorizedByIndex": false
  }
,"human-female":WORLD_BODY_CONTRACTS["human-female"]})});
const trustedSets=new Set([LEGACY_WORLD_CONTRACT_SET,...(SOURCE_WORLD_CONTRACT_SET?[SOURCE_WORLD_CONTRACT_SET]:[])]),receiptSets=new WeakMap();
export function assertTrustedWorldContractSet(set){if(!trustedSets.has(set))throw Error('Explicit compiled trusted contract set required');return set;}
export function bindWorldContractSetReceipt(value,set){assertTrustedWorldContractSet(set);if(!value||typeof value!=='object')throw Error('Private native receipt required');receiptSets.set(value,set);return value;}
export function worldContractSetReceiptMatches(value,set){assertTrustedWorldContractSet(set);return receiptSets.has(value)?receiptSets.get(value)===set:set===LEGACY_WORLD_CONTRACT_SET;}
export function selectWorldContract(registry,record,resolveContract,contractSet=LEGACY_WORLD_CONTRACT_SET){
 assertTrustedWorldContractSet(contractSet);if(typeof resolveContract!=='function')return null;
 const avatar=registry.check(record.sourceAvatar,record.profession),c=resolveContract(record,avatar);
 return c&&Object.values(contractSet.contracts).includes(c)&&c.bodyKey===avatar.key&&c.policy.modelId===avatar.sourceModelId?c:null;
}
export function preparedWorldContract(c,value){return!!c&&value?.ready===true&&value.key===c.bodyKey&&value.pose?.field===c.poseField&&value.pose.bindingId===c.policy.bindingId&&value.pose.valueBytes===c.policy.valueBytes;}
export function matchesSourceMotion(c,value){return!!value&&Object.entries(c.sourceMotion).every(([k,v])=>value[k]===v);}
export function readyWorldContract(c,r,value,contractSet=LEGACY_WORLD_CONTRACT_SET){return worldContractSetReceiptMatches(value,contractSet)&&
 (c.mode!=='own-air'||value?.mode===c.mode&&value.bodyKey===c.bodyKey&&value.poseField===c.poseField)&&
 value?.actualNativeActorAndConsumedPose===true&&value.actorKey===r.record.id&&value.identity===r.identity&&value.generation===r.generation&&value.roomKey===r.roomKey&&value.mapId===c.policy.mapId&&value.sourceModelId===c.policy.modelId&&value.bindingId===c.policy.bindingId&&value.valueBytes===c.policy.valueBytes&&value.sourceMotion===c.policy.motionSHA256;}
