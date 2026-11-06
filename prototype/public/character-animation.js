// Recovered source skeletons/clips; each character owns its bones and mixer.
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
  const geometries = data.meshes.map((mesh, index) => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(mesh.positions, 3));
    geometry.setAttribute('normal', new THREE.Float32BufferAttribute(mesh.normals, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute(mesh.uvs, 2));
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
    const skeletons = [];
    for (const [index, mesh] of data.meshes.entries()) {
      const skin = skinByMesh.get(index);
      const material = mesh.groups?.length ? materials : materials[mesh.material ?? 0];
      const object = skin ? new THREE.SkinnedMesh(geometries[index], material) : new THREE.Mesh(geometries[index], material);
      if (skin) {
        const skeleton = new THREE.Skeleton(skin.boneNodes.map(node => nodes[node]), skin.inverseBindMatrices.map(matrix => new THREE.Matrix4().fromArray(matrix)));
        // Source inverse matrices already include the mesh bind-shape transform.
        // Applying bindShapeMatrix again would transform the held weapon twice.
        object.bind(skeleton, new THREE.Matrix4()); skeletons.push(skeleton);
        object.frustumCulled = false;
      }
      object.castShadow = true; object.receiveShadow = true; group.add(object);
    }
    group.updateMatrixWorld(true);
    for (const skeleton of skeletons) skeleton.update();
    const box = new THREE.Box3().setFromObject(group, true), center = box.getCenter(new THREE.Vector3());
    group.position.set(-center.x, -box.min.y, -center.z);
    root.userData.height = box.max.y - box.min.y;
    const mixer = new THREE.AnimationMixer(root);
    const idle = mixer.clipAction(clips.find(clip => clip.name === 'idle')).play();
    const walk = mixer.clipAction(clips.find(clip => clip.name === 'walk_forward')).play();
    idle.setEffectiveWeight(1); walk.setEffectiveWeight(0);
    const shots = {};
    if (combatClips.every(Boolean)) for (const clip of [combatClips[0],hurtClip,combatClips[2]]) {
      const action = mixer.clipAction(clip).setLoop(THREE.LoopOnce, 1).play();
      action.clampWhenFinished = true; action.paused = true; action.setEffectiveWeight(0);
      shots[clip.name] = action;
    }
    controllers.set(root, { mixer, idle, walk, nodes, skeletons, shots, weight: 0, moving: false,
      now: 0, phase: 'idle', dead: false, lifeSince: -Infinity, lastSnapshotAt: -Infinity,
      attackAt: -Infinity, hitAt: -Infinity, deathAt: null, attackSeconds: .7, attackWeight: 0, hurtWeight: 0 });
    mixer.update(0); root.updateMatrixWorld(true);
    return root;
  };
}

export function playCharacterAction(root, kind, { at, now, attackSeconds } = {}) {
  const c = controllers.get(root);
  if (!c?.shots[kind]) return false;
  now = Number.isFinite(now) ? now : c.now;
  at = Number.isFinite(at) ? at : now;
  if (at < c.lifeSince) return false;
  c.now = Math.max(c.now, now);
  if (kind === 'death') {
    if (c.dead) return false;
    c.dead = true; c.deathAt = at; c.attackWeight = 0; c.hurtWeight = 0;
    return true;
  }
  if (c.dead) return false;
  const field = kind === 'attack' ? 'attackAt' : 'hitAt';
  if (at <= c[field]) return false;
  c[field] = at;
  if (kind === 'attack' && Number.isFinite(attackSeconds) && attackSeconds > 0) c.attackSeconds = attackSeconds;
  return true;
}

export function respawnCharacterAnimation(root, { at, now } = {}) {
  const c = controllers.get(root);
  if (!c) return;
  now = Number.isFinite(now) ? now : c.now;
  at = Number.isFinite(at) ? at : now;
  if (at <= c.lifeSince) return;
  c.dead = false; c.deathAt = null; c.lifeSince = at;
  c.attackAt = c.hitAt = -Infinity; c.attackWeight = c.hurtWeight = c.weight = 0;
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
  if (Number.isFinite(animation.attackAt)) playCharacterAction(root, 'attack', { at: animation.attackAt, now: serverTime, attackSeconds });
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
  const c = controller, { attack, hurt, death } = c.shots;
  const attackAge = (c.now - c.attackAt) / 1000;
  const attacking = !c.dead && attack && attackAge >= 0 && attackAge < c.attackSeconds;
  c.attackWeight += ((attacking ? 1 : 0) - c.attackWeight) * (1 - Math.exp(-dt * 30));
  if (c.dead || c.attackWeight < .0001) c.attackWeight = 0;
  if (attack) {
    attack.time = attack.getClip().duration * Math.min(1, Math.max(0, attackAge / c.attackSeconds));
    attack.setEffectiveWeight(c.attackWeight);
  }
  const hurtAge = (c.now - c.hitAt) / 1000;
  const hurtDuration = hurt?.getClip().duration || 0;
  const hurting = !c.dead && hurt && hurtAge >= 0 && hurtAge < hurtDuration;
  c.hurtWeight = hurting ? Math.max(0, Math.min(1, hurtAge / .06, (hurtDuration - hurtAge) / .09)) : 0;
  if (hurt) { hurt.time = Math.max(0, Math.min(hurtDuration, hurtAge)); hurt.setEffectiveWeight(c.hurtWeight); }
  if (death) {
    const age = c.dead ? Math.max(0, (c.now - c.deathAt) / 1000) : 0;
    death.time = Math.min(death.getClip().duration, age); death.setEffectiveWeight(c.dead ? 1 : 0);
    c.phase = c.dead ? (age < death.getClip().duration ? 'death' : 'dead') : attacking ? 'attack' : hurting ? 'hurt' : c.moving ? 'walk' : 'idle';
  } else c.phase = c.moving ? 'walk' : 'idle';
  const baseWeight = c.dead ? 0 : 1 - c.attackWeight;
  controller.idle.setEffectiveWeight((1 - controller.weight) * baseWeight);
  controller.walk.setEffectiveWeight(controller.weight * baseWeight);
  controller.walk.setEffectiveTimeScale(controller.moving ? Math.max(.5, Math.min(1.8, (motion.speed || 4.8) / 4.8)) : 1);
  controller.mixer.update(dt);
}

export function characterAnimationState(root) {
  const controller = controllers.get(root);
  return controller ? { moving: controller.moving, walkWeight: controller.walk.getEffectiveWeight(),
    idleTime: controller.idle.time, walkTime: controller.walk.time,
    phase: controller.phase, dead: controller.dead, attackWeight: controller.attackWeight,
    hurtWeight: controller.hurtWeight, attackTime: controller.shots.attack?.time,
    deathTime: controller.shots.death?.time, combatEnabled: Boolean(controller.shots.death),
    bones: controller.nodes, skeletons: controller.skeletons } : null;
}

export function disposeCharacterAnimation(root) {
  const controller = controllers.get(root);
  if (!controller) return;
  controller.mixer.stopAllAction(); controller.mixer.uncacheRoot(root);
  for (const skeleton of controller.skeletons) skeleton.dispose();
  controllers.delete(root);
}
