// Original model UVs and the decoded PVR rows are kept in source order.
// TextureLoader's default flipY=true was an extra web-only inversion.
export function sourceCharacterTexture(THREE, cached) {
  if (!cached?.isTexture || cached.colorSpace !== THREE.NoColorSpace) throw Error('Expected original-space character texture');
  const texture = cached.clone();
  texture.flipY = false;
  texture.needsUpdate = true;
  return texture;
}
