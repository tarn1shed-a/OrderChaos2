// Recovered source skeletons/clips; each character owns its bones and mixer.
import { skillById } from './skills.js';
import { validateEquipmentAppearance, applyEquipmentMeshes, equipmentAppearanceKey } from './character-equipment.js';
import { defaultLook, validLook, lookKey } from './character-look.js';
import { setCharacterMaterialLook } from './character-materials.js';
import { jumpPose } from './jump.js';
import {castPose} from './cast-pose.js';
const controllers = new WeakMap();

export function snapshotMotion(previous, current, seconds, worldUnitsPerLogicalUnit) {
  if (!previous || !current || current.hp <= 0 || seconds <= 0 || !Number.isFinite(seconds)) return { moving: false, speed: 0 };
  const distance = Math.hypot(current.x - previous.x, current.y - previous.y) * worldUnitsPerLogicalUnit;
  // A respawn/teleport updates position without playing a high-speed walk.
  if (!Number.isFinite(distance) || distance > Math.max(1, seconds * 20)) return { moving: false, speed: 0 };
  return { moving: distance > 0.00001, speed: distance / seconds };
}

export function createCharacterFactory(THREE, data, materials) {
  if (data.format !== 'bdae946-character-v1' || !data.rig?.nodes?.length || !data.clips?.length) throw new Error('角色骨架或动画缺失，请重新构建本地资源');
  const skinByMesh = new Map(data.rig.skins.map(skin => [skin.mesh, skin]));
  const appearance = validateEquipmentAppearance(data);
  const geometries = data.meshes.map((mesh, index) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(mesh.normals, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(mesh.uvs, 2));
    if(mesh.sourceTangents)geometry.setAttribute('sourceTangent',new THREE.Float32BufferAttribute(mesh.sourceTangents,3));
    if(mesh.sourceBinormals)geometry.setAttribute('sourceBinormal',new THREE.Float32BufferAttribute(mesh.sourceBinormals,3));
    geometry.setIndex(mesh.indices);
    for (const group of mesh.groups || []) geometry.addGroup(group.start, group.count, group.material);
    const skin = skinByMesh.get(index);
    if (skin) {
      geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute(skin.skinIndices, 4));
      geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute(skin.skinWeights, 4));
    }
    return geometry;
  });
  const clips = data.clips.map(clip => new THREE.AnimationClip(clip.name, clip.duration, clip.tracks.map(track => {
    const name = `node_${track.node}.${track.type}`;
    if (track.type === 'quaternion') return new THREE.QuaternionKeyframeTrack(name, track.times, track.values);
    return new THREE.VectorKeyframeTrack(name, track.times, track.values);
  })));
  if (!clips.some(clip => clip.name === 'idle') || !clips.some(clip => clip.name === 'walk_forward')) throw new Error('角色缺少待机或行走片段');
  const combatClips = ['attack','hurt','death'].map(name => clips.find(clip => clip.name === name));
  if (combatClips.some(Boolean) && !combatClips.every(Boolean)) throw new Error('角色战斗动画不完整，请重新构建本地资源');
  const hurtClip = combatClips[1] ? THREE.AnimationUtils.makeClipAdditive(combatClips[1].clone()) : null;

  return function createCharacter() {
    const root = new THREE.Group(), group = new THREE.Group();
    root.add(group);
    const nodes = data.rig.nodes.map((node, index) => {
      const bone = new THREE.Bone(); bone.name = `node_${index}`;
      bone.position.fromArray(node.position); bone.quaternion.fromArray(node.quaternion); bone.scale.fromArray(node.scale);
      return bone;
    });
    for (const [index, node] of data.rig.nodes.entries()) {
      if (node.parent < 0) group.add(nodes[index]); else nodes[node.parent].add(nodes[index]);
    }
    const skeletons = [], meshObjects = [], ownedMaterials=new Map();
    const instanceMaterial=material=>{
      if(!material?.userData.characterMaterial)return material;
      if(!ownedMaterials.has(material))ownedMaterials.set(material,material.clone());return ownedMaterials.get(material);
    };
    for (const [index, mesh] of data.meshes.entries()) {
      const skin = skinByMesh.get(index);
      const material = mesh.groups?.length ? materials.map(instanceMaterial) : instanceMaterial(materials[mesh.material ?? 0]);
      const object = skin ? new THREE.SkinnedMesh(geometries[index], material) : new THREE.Mesh(geometries[index], material);
      if (skin) {
        const skeleton = new THREE.Skeleton(skin.boneNodes.map(node => nodes[node]), skin.inverseBindMatrices.map(matrix => new THREE.Matrix4().fromArray(matrix)));
        // Source inverse matrices already include the mesh bind-shape transform.
        // Applying bindShapeMatrix again would transform the held weapon twice.
        object.bind(skeleton, new THREE.Matrix4()); skeletons.push(skeleton);
        object.frustumCulled = false;
      }
      object.name = mesh.name || `mesh_${index}`;
      object.userData.sourceMeshIndex = index;
      if (mesh.attachment) {
        object.matrix.fromArray(mesh.attachment.matrix); object.matrix.decompose(object.position, object.quaternion, object.scale);
        nodes[mesh.attachment.node].add(object);
      } else group.add(object);
      object.castShadow = true; object.receiveShadow = true; meshObjects.push(object);
    }
    const equipmentState = appearance ? applyEquipmentMeshes(meshObjects, appearance, {}) : null;
    group.updateMatrixWorld(true);
    for (const skeleton of skeletons) skeleton.update();
    const box = new THREE.Box3();
    if (appearance) for (const index of appearance.baseMeshIndices) box.union(new THREE.Box3().setFromObject(meshObjects[index], true));
    else box.setFromObject(group, true);
    const center = box.getCenter(new THREE.Vector3());
    group.position.set(-center.x, -box.min.y, -center.z);
    root.userData.height = box.max.y - box.min.y;
    const mixer = new THREE.AnimationMixer(root);
    const idle = mixer.clipAction(clips.find(clip => clip.name === 'idle')).play();
    const walk = mixer.clipAction(clips.find(clip => clip.name === 'walk_forward')).play();
    idle.setEffectiveWeight(1); walk.setEffectiveWeight(0);
    const shots = {};
    if (combatClips.every(Boolean)) for (const clip of [combatClips[0],hurtClip,combatClips[2], ...clips.filter(clip => clip.name.startsWith('attack_')||clip.name.startsWith('skill_')||clip.name.startsWith('jump_')||clip.name==='jumplandrun')]) {
      const action = mixer.clipAction(clip).setLoop(THREE.LoopOnce, 1).play();
      action.clampWhenFinished = true; action.paused = true; action.setEffectiveWeight(0);
      shots[clip.name] = action;
    }
    const namedNodes = new Map();
    data.rig.nodes.forEach((node,index) => { for (const name of [node.name,...(node.aliases || [])]) if (name) namedNodes.set(name,nodes[index]); });
    controllers.set(root, { mixer, idle, walk, nodes, namedNodes, skeletons, meshObjects, ownedMaterials:[...ownedMaterials.values()], appearance, equipmentState, equipment:{}, look:defaultLook(), lookKey:lookKey(defaultLook()), shots, weight: 0, moving: false,
      now: 0, phase: 'idle', dead: false, lifeSince: -Infinity, lastSnapshotAt: -Infinity,
      attackAt: -Infinity, hitAt: -Infinity, deathAt: null, attackSeconds: .7, attackWeight: 0, hurtWeight: 0,
      cast: null, jump:null, jumpHeight:0, lastCastAt: -Infinity, skillWeight: 0 });
    mixer.update(0); root.updateMatrixWorld(true);
    return root;
  };
}

export function setCharacterEquipment(root, equipment) {
  const c = controllers.get(root);
  if (!c?.appearance || c.equipmentState.key === equipmentAppearanceKey(equipment)) return false;
  c.equipment={...equipment};c.equipmentState = applyEquipmentMeshes(c.meshObjects, c.appearance, equipment,c.look);
  return true;
}

export function setCharacterLook(root,look){
  const c=controllers.get(root);if(!c)return false;
  const value=validLook(look)?look:defaultLook(),key=lookKey(value);
  if(c.lookKey===key)return false;
  const changed=true;c.look={...value};c.lookKey=key;
  if(c.appearance)c.equipmentState=applyEquipmentMeshes(c.meshObjects,c.appearance,c.equipment,c.look);
  const materials=new Set();for(const object of c.meshObjects)for(const material of Array.isArray(object.material)?object.material:[object.material])materials.add(material);
  for(const material of materials)setCharacterMaterialLook(material,value);
  return changed;
}

export function characterEquipmentState(root) {
  const state = controllers.get(root)?.equipmentState;
  return state ? { key: state.key, items: [...state.items], visibleMeshIndices: [...state.visibleMeshIndices] } : null;
}

export function characterAttachment(root, name, target) {
  const node = controllers.get(root)?.namedNodes.get(name);
  if (!node) return null;
  return node.getWorldPosition(target);
}

export function characterAttachmentTransform(root, name, target) {
  const node=controllers.get(root)?.namedNodes.get(name);if(!node)return null;
  node.updateWorldMatrix(true,false);node.getWorldPosition(target.position);node.getWorldQuaternion(target.quaternion);node.getWorldScale(target.scale);
  return target;
}

export function playCharacterAction(root, kind, { at, now, attackSeconds, basicAttack } = {}) {
  const c = controllers.get(root);
  if (!c?.shots[kind]) return false;
  now = Number.isFinite(now) ? now : c.now;
  at = Number.isFinite(at) ? at : now;
  if (at < c.lifeSince) return false;
  c.now = Math.max(c.now, now);
  if (kind === 'death') {
    if (c.dead) return false;
    c.dead = true; c.deathAt = at; c.attackWeight = 0; c.hurtWeight = 0; c.cast = null; c.skillWeight = 0;
    return true;
  }
  if (c.dead) return false;
  const field = kind === 'attack' ? 'attackAt' : 'hitAt';
  if (at <= c[field]) return false;
  c[field] = at;
  if (kind === 'attack' && Number.isFinite(attackSeconds) && attackSeconds > 0) c.attackSeconds = attackSeconds;
  if(kind==='attack') {
    c.attackClip=basicAttack?.clip&&c.shots[basicAttack.clip]?basicAttack.clip:'attack';
    if(c.attackClip!=='attack')c.attackSeconds=c.shots[c.attackClip].getClip().duration;
  }
  return true;
}

export function playCharacterSkill(root, cast, { now } = {}) {
  const c = controllers.get(root), skill = skillById(cast?.skillId);
  if (!c || c.dead || !skill || !c.shots[skill.clip] || !Number.isFinite(cast.startedAt) || !Number.isFinite(cast.releaseAt)
    || (cast.stage===undefined&&cast.releaseAt<=cast.startedAt) || cast.startedAt < c.lifeSince) return false;
  if(c.cast?.id===cast.id&&cast.stage!==undefined){
    if(cast.revision<=c.cast.revision)return false;
  }else if(cast.startedAt<=c.lastCastAt)return false;
  c.cast = { ...cast }; c.lastCastAt = cast.startedAt;
  c.now = Math.max(c.now, Number.isFinite(now) ? now : cast.startedAt);
  return true;
}

export function cancelCharacterSkill(root, castId) {
  const c = controllers.get(root);
  if (c?.cast?.id === castId) { c.cast = null; c.skillWeight = 0; }
}

export function respawnCharacterAnimation(root, { at, now } = {}) {
  const c = controllers.get(root);
  if (!c) return;
  now = Number.isFinite(now) ? now : c.now;
  at = Number.isFinite(at) ? at : now;
  if (at <= c.lifeSince) return;
  c.dead = false; c.deathAt = null; c.lifeSince = at;
  c.attackAt = c.hitAt = -Infinity; c.attackWeight = c.hurtWeight = c.weight = 0;
  c.cast = null; c.jump=null;c.jumpHeight=0;c.skillWeight = 0; c.lastCastAt = -Infinity;
  for (const action of Object.values(c.shots)) { action.time = 0; action.setEffectiveWeight(0); }
  c.idle.time = 0; c.walk.setEffectiveWeight(0); c.idle.setEffectiveWeight(1);
  c.phase = 'idle'; c.now = Math.max(c.now, now); c.mixer.update(0);
}

export function syncCharacterCombat(root, snapshot, serverTime, attackSeconds) {
  const c = controllers.get(root);
  if (!c || !Number.isFinite(serverTime) || serverTime < c.lastSnapshotAt || serverTime < c.lifeSince) return;
  c.lastSnapshotAt = serverTime; c.now = Math.max(c.now, serverTime);
  const alive = snapshot.alive ?? snapshot.hp > 0;
  const animation = snapshot.animation || {};
  if (c.dead && alive && serverTime < c.deathAt) return;
  if (!alive) {
    playCharacterAction(root, 'death', { at: animation.deathAt, now: serverTime });
    return;
  }
  if (c.dead) respawnCharacterAnimation(root, { at: serverTime, now: serverTime });
  c.jump=snapshot.jump?{...snapshot.jump}:null;
  if (snapshot.cast||snapshot.lastCast) playCharacterSkill(root, snapshot.cast||snapshot.lastCast, { now: serverTime });
  if (Number.isFinite(animation.attackAt)) playCharacterAction(root, 'attack', { at: animation.attackAt, now: serverTime, attackSeconds, basicAttack:snapshot.basicAttack });
  if (Number.isFinite(animation.hitAt)) playCharacterAction(root, 'hurt', { at: animation.hitAt, now: serverTime });
}

export function updateCharacterAnimation(root, seconds, motion, serverTime) {
  const controller = controllers.get(root);
  if (!controller) return;
  const dt = Math.max(0, Math.min(seconds, .1));
  controller.now = Number.isFinite(serverTime) ? Math.max(controller.now, serverTime) : controller.now + dt * 1000;
  controller.moving = !controller.dead && Boolean(motion?.moving);
  const goal = controller.moving ? 1 : 0;
  controller.weight += (goal - controller.weight) * (1 - Math.exp(-dt * 20));
  if (Math.abs(goal - controller.weight) < 0.0001) controller.weight = goal;
  const c = controller, { hurt, death } = c.shots, attack=c.shots[c.attackClip||'attack'];
  const jumping=!c.dead?jumpPose(c.jump,c.now):null;
  const jumpWeight=jumping&&c.shots[jumping.phase]?jumping.weight:0;
  c.jumpHeight=jumping?.height||0;
  for(const [name,action] of Object.entries(c.shots))if(name.startsWith('jump_')||name==='jumplandrun'){
    action.setEffectiveWeight(name===jumping?.phase?jumpWeight:0);
    if(name===jumping?.phase)action.time=action.getClip().duration*jumping.fraction;
  }
  const skill = skillById(c.cast?.skillId), skillAge = c.cast ? (c.now-c.cast.startedAt)/1000 : Infinity;
  const skillDuration = c.cast ? (c.cast.releaseAt-c.cast.startedAt)/1000 : 0;
  const sourcePose=castPose(c.cast,c.now),sourceCast=c.cast?.stage!==undefined;
  const casting = !c.dead && skill && (sourceCast?Boolean(sourcePose):skillAge >= 0 && skillAge < skillDuration);
  c.activeSkillClip=sourceCast?sourcePose?.clip:skill?.clip;
  c.skillWeight += ((casting ? 1 : 0)-c.skillWeight) * (1-Math.exp(-dt*30));
  if (c.dead || c.skillWeight < .0001) c.skillWeight = 0;
  for (const [name, action] of Object.entries(c.shots)) if (name.startsWith('skill_')) {
    action.setEffectiveWeight(name === c.activeSkillClip ? c.skillWeight*(1-jumpWeight) : 0);
    if (name === c.activeSkillClip) action.time = sourceCast?sourcePose.time:action.getClip().duration*Math.max(0,Math.min(1,skillAge/skillDuration));
  }
  const attackAge = (c.now - c.attackAt) / 1000;
  const attacking = !c.dead && attack && attackAge >= 0 && attackAge < c.attackSeconds;
  c.attackWeight += ((attacking ? 1 : 0) - c.attackWeight) * (1 - Math.exp(-dt * 30));
  if (c.dead || c.attackWeight < .0001) c.attackWeight = 0;
  if (attack) {
    attack.time = attack.getClip().duration * Math.min(1, Math.max(0, attackAge / c.attackSeconds));
    attack.setEffectiveWeight(c.attackWeight * (1-c.skillWeight)*(1-jumpWeight));
  }
  for(const [name,action] of Object.entries(c.shots))if((name==='attack'||name.startsWith('attack_'))&&action!==attack)action.setEffectiveWeight(0);
  const hurtAge = (c.now - c.hitAt) / 1000;
  const hurtDuration = hurt?.getClip().duration || 0;
  const hurting = !c.dead && hurt && hurtAge >= 0 && hurtAge < hurtDuration;
  c.hurtWeight = hurting ? Math.max(0, Math.min(1, hurtAge / .06, (hurtDuration - hurtAge) / .09)) : 0;
  if (hurt) { hurt.time = Math.max(0, Math.min(hurtDuration, hurtAge)); hurt.setEffectiveWeight(c.hurtWeight); }
  if (death) {
    const age = c.dead ? Math.max(0, (c.now - c.deathAt) / 1000) : 0;
    death.time = Math.min(death.getClip().duration, age); death.setEffectiveWeight(c.dead ? 1 : 0);
    c.phase = c.dead ? (age < death.getClip().duration ? 'death' : 'dead') : jumping ? jumping.phase : casting ? c.activeSkillClip : attacking ? 'attack' : hurting ? 'hurt' : c.moving ? 'walk' : 'idle';
  } else c.phase = c.moving ? 'walk' : 'idle';
  const baseWeight = c.dead ? 0 : (1 - c.attackWeight) * (1 - c.skillWeight)*(1-jumpWeight);
  controller.idle.setEffectiveWeight((1 - controller.weight) * baseWeight);
  controller.walk.setEffectiveWeight(controller.weight * baseWeight);
  controller.walk.setEffectiveTimeScale(controller.moving ? Math.max(.5, Math.min(1.8, (motion.speed || 4.8) / 4.8)) : 1);
  controller.mixer.update(dt);
}

export function characterAnimationState(root) {
  const controller = controllers.get(root);
  return controller ? { moving: controller.moving, walkWeight: controller.walk.getEffectiveWeight(),
    idleTime: controller.idle.time, walkTime: controller.walk.time,
    phase: controller.phase, dead: controller.dead, jumpHeight:controller.jumpHeight,jumpWorldMotion:controller.jump?.physics==='source-world-v1', attackWeight: controller.attackWeight,
    hurtWeight: controller.hurtWeight, skillWeight: controller.skillWeight, castId: controller.cast?.id,
    skillTime: controller.cast ? controller.shots[controller.activeSkillClip]?.time : null,
    attackClip:controller.attackClip||'attack',attackTime: controller.shots[controller.attackClip||'attack']?.time,
    deathTime: controller.shots.death?.time, combatEnabled: Boolean(controller.shots.death),
    bones: controller.nodes, skeletons: controller.skeletons } : null;
}

export function disposeCharacterAnimation(root) {
  const controller = controllers.get(root);
  if (!controller) return;
  controller.mixer.stopAllAction(); controller.mixer.uncacheRoot(root);
  for (const skeleton of controller.skeletons) skeleton.dispose();
  for(const material of controller.ownedMaterials)material.dispose();
  controllers.delete(root);
}
