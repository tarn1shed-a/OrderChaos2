// Names select a local slot; only a server-issued ID/token can restore its save.
// Each slot is independent, so two tabs can use different characters.
const STORAGE_KEY = 'oc2.character-slots.v1';
let warning = '';

function slots() {
  try {
    const raw = globalThis.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { characters: Object.create(null), lastName: '' };
    const value = JSON.parse(raw);
    if (!value || !value.characters || typeof value.characters !== 'object' || Array.isArray(value.characters)) throw new Error('Invalid local character slots');
    const characters = Object.create(null);
    for(const [name,entry] of Object.entries(value.characters)) {
      if(entry&&typeof entry.id==='string'&&typeof entry.token==='string')characters[name]={id:entry.id,token:entry.token};
    }
    return { characters, lastName: typeof value.lastName==='string' ? value.lastName : '' };
  } catch {
    warning = '浏览器无法读取角色凭据，请保留本窗口；换浏览器不能自动恢复这个角色。';
    return null;
  }
}

export function restoreCredentials(name) {
  const entry = slots()?.characters[String(name).trim()];
  return entry && typeof entry.id === 'string' && typeof entry.token === 'string'
    ? { characterId: entry.id, resumeToken: entry.token } : {};
}

export function rememberCharacter(character, resumeToken) {
  if (!character?.id || !character?.name || typeof resumeToken !== 'string') return false;
  try {
    const data = slots();
    if (!data) return false;
    data.characters[character.name] = { id: character.id, token: resumeToken };
    data.lastName = character.name;
    globalThis.localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    warning = '';
    return true;
  } catch {
    warning = '角色保存在服务器，但浏览器无法记住恢复凭据；关闭本窗口后可能无法找回。';
    return false;
  }
}

export function lastCharacterName() { return slots()?.lastName || ''; }
export function characterSessionWarning() { return warning; }
