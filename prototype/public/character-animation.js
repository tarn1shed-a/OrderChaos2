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
    controllers.set(root, { mixer, idle, walk, nodes, skeletons, weight: 0, moving: false });
    mixer.update(0); root.updateMatrixWorld(true);
    return root;
  };
}

export function updateCharacterAnimation(root, seconds, motion) {
  const controller = controllers.get(root);
  if (!controller) return;
  const dt = Math.max(0, Math.min(seconds, .1));
  controller.moving = Boolean(motion?.moving);
  const goal = controller.moving ? 1 : 0;
  controller.weight += (goal - controller.weight) * (1 - Math.exp(-dt * 20));
  if (Math.abs(goal - controller.weight) < 0.0001) controller.weight = goal;
  controller.idle.setEffectiveWeight(1 - controller.weight);
  controller.walk.setEffectiveWeight(controller.weight);
  controller.walk.setEffectiveTimeScale(controller.moving ? Math.max(.5, Math.min(1.8, (motion.speed || 4.8) / 4.8)) : 1);
  controller.mixer.update(dt);
}

export function characterAnimationState(root) {
  const controller = controllers.get(root);
  return controller ? { moving: controller.moving, walkWeight: controller.weight,
    idleTime: controller.idle.time, walkTime: controller.walk.time,
    bones: controller.nodes, skeletons: controller.skeletons } : null;
}

export function disposeCharacterAnimation(root) {
  const controller = controllers.get(root);
  if (!controller) return;
  controller.mixer.stopAllAction(); controller.mixer.uncacheRoot(root);
  for (const skeleton of controller.skeletons) skeleton.dispose();
  controllers.delete(root);
}
