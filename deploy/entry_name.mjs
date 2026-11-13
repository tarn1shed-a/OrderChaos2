// Local checks visible in input_name_mc.onNormalUpdateText. This is not an
// original server name-availability/emoji/reserved-word approval response.
const forbidden=new Set(['(', ',', '[', '.', ']', '{', '}', "'", '"', ')', '&', '*', '@', '$', '%', '#', '^', '\\', ' ', '!', '<', '>', '?', ':', '-', ';', '/', '_', '~', '|', '=', '¥', '¡', '¿']);
export function entryNameError(name){
  if(typeof name!=='string')return 'GENERAL_ERROR_CREATION_NAME_LESS';
  const bytes=new TextEncoder().encode(name).length,characters=[...name].length;
  // 0x7006ac counts the original converted wide string, limits UTF-8 to 21
  // bytes and the converted count to 15, and promotes a multibyte pair to 3.
  // Original 0xa8fb38 was executed against ASCII and Chinese fixtures.
  const length=bytes>21||characters>15?99:characters===2&&bytes>2?3:characters;
  if(length<3)return 'GENERAL_ERROR_CREATION_NAME_LESS';
  if(length>15)return 'GENERAL_CH_SELEC_45';
  // Supplementary-character/emoji handling is not represented as recovered.
  if([...name].some(c=>c.codePointAt(0)>0xffff))return 'GENERAL_ERROR_GUILD_NAME_ILLEGAL';
  if([...name].some(c=>forbidden.has(c)))return 'GENERAL_ERROR_GUILD_NAME_ILLEGAL';
  if(!Number.isNaN(Number(name)))return 'GENERAL_ERROR_CREATION_ENTER_NAME_NUMBER';
  return null;
}
