// Shared server route contract for source-backed entry deliveries.
import {CREATION_STAGES_PROFILES} from './creation_stages_profile.mjs';
export const CREATION_ENTRY_PROFILES=Object.freeze([
 ...['manifest.json','manifest-v2.json','manifest-v3.json','manifest-races-v1.json','manifest-conditional-v1.json'].map(name=>'/assets/source-creation-stage/'+name),
 ...CREATION_STAGES_PROFILES,
]);
export const isCreationEntryProfile=url=>CREATION_ENTRY_PROFILES.includes(url);
