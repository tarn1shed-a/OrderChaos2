export const HAIR_STYLES = Object.freeze(['hair1','hair2','hair3']);
export const HAIR_COLORS = Object.freeze(['color1','color2','color3','color4','color5','color6']);
// The sixth source skin pair is 0,0; its native meaning is unresolved.
export const SKIN_COLORS = Object.freeze(['color1','color2','color3','color4','color5']);
export const defaultLook = () => ({ hair:'hair1', hairColor:'color1', skinColor:'color1' });
export function validLook(look) {
  return Boolean(look && typeof look==='object' && !Array.isArray(look) && Object.keys(look).length===3 &&
    HAIR_STYLES.includes(look.hair) && HAIR_COLORS.includes(look.hairColor) && SKIN_COLORS.includes(look.skinColor));
}
export function lookKey(look) {
  const value=validLook(look)?look:defaultLook();
  return `${value.hair}:${value.hairColor}:${value.skinColor}`;
}
