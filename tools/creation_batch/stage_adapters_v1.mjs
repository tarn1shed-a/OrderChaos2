// One pinned policy entry and one shared implementation, not a renderer per body.
// Existing v1 bytes remain frozen. New policies cannot be admitted by caller data.
import {createPinnedCreationStageAdapters} from './stage_adapter_core_v1.mjs';
const POLICIES = Object.freeze([
 'bca0b324a56c3e7c577b6b0b63761f4b4ec6efb66e50c1dd4ca1a626aeefdac4',
 '14d1d8cae37a6e5c44b87886bf1ddf097ce2e48a7a7b091db80111f6564437c7',
]);
export async function createCreationStageAdapters({policyBytes,registryBytes,crypto}) {
 if (!(policyBytes instanceof Uint8Array) || !crypto?.subtle) throw Error('Exact source policy bytes required');
 const actual = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',policyBytes)),v=>v.toString(16).padStart(2,'0')).join('');
 if (!POLICIES.includes(actual)) throw Error('Source policy is outside the frozen body batch registry');
 return createPinnedCreationStageAdapters({policyBytes,registryBytes,crypto,policySHA256:actual});
}
