// Startup assembly only: reuse each existing motion, bridge, observer and gate.
// This has no game loop, clock, RPC protocol, physics/pose implementation or GL.
const checkedClosures=new WeakSet();
export async function verifyHumanFemaleWorldAssets({planBytes,expectedSHA256,loadBytes,crypto}){
 const digest=async b=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(v=>v.toString(16).padStart(2,'0')).join('');
 if(!(planBytes instanceof Uint8Array)||typeof loadBytes!=='function'||!crypto?.subtle||await digest(planBytes)!==expectedSHA256)throw Error('Pinned HumanF source asset plan required');
 const p=JSON.parse(new TextDecoder().decode(planBytes));if(p.format!=='oc2-human-female-world-integration-closure-v1'||p.runtimeOwnBody!==32||p.containsFiniteQATape!==false||p.files.length!==47)throw Error('Own world source closure differs');
 for(const row of p.files){const b=await loadBytes(row);if(!(b instanceof Uint8Array)||b.byteLength!==row.bytes||await digest(b)!==row.sha256)throw Error('HumanF world source asset differs: '+row.url);}
 const receipt=Object.freeze({bodyKey:'human-female',sourceModelId:32,filesVerified:p.files.length,planSHA256:expectedSHA256,actualGLClaimed:false});checkedClosures.add(receipt);return receipt;
}
