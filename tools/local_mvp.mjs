// A local entry for the reviewed preview. This does not recreate original server rules.
import {readFileSync,existsSync,mkdirSync,openSync,writeFileSync,closeSync,unlinkSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {resolve,sep} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

export const ROOT=fileURLToPath(new URL('../',import.meta.url));
const DEFAULT_RUNTIME=resolve(ROOT,'analysis/raw/showcase-20261110/running-preview');
const MANIFEST=new URL('./local_mvp_runtime.json',import.meta.url);
const inside=(path,root)=>path.startsWith(resolve(root)+sep);
const hash=path=>createHash('sha256').update(readFileSync(path)).digest('hex');

export function inspectRuntime(runtime=DEFAULT_RUNTIME){
 runtime=resolve(runtime);
 if(!inside(runtime,resolve(ROOT,'analysis/raw')))throw Error('MVP 使用忽略目录内的独立运行资料');
 const manifest=JSON.parse(readFileSync(MANIFEST,'utf8'));
 for(const [name,digest]of Object.entries(manifest.files)){
  const path=resolve(runtime,name);
  if(!inside(path,runtime)||!existsSync(path)||hash(path)!==digest)
   throw Error(`MVP 本地运行文件缺失或有未核对改动：${name}。请保留现有文件并核对本地资料包。`);
 }
 const configPath=resolve(runtime,'prototype/native-physics.json');
 if(!existsSync(configPath))throw Error('缺少本地原物理配置；没有切换到替代碰撞');
 const config=JSON.parse(readFileSync(configPath,'utf8'));
 if(config.nativeSHA256!==manifest.nativeSHA256||!existsSync(config.library)||hash(config.library)!==manifest.nativeSHA256)
  throw Error('原版物理库身份不匹配');
 for(const key of ['python','worker','terrain','collision','terrainLighting','swimming','diving','animationBlending','stopQueue','layerQueue'])
  if(typeof config[key]!=='string'||!existsSync(config[key]))throw Error(`本地原物理输入未就绪：${key}`);
 if(!config.shoreTransitions)throw Error('缺少已核对的水岸动作配置');
 if(!Object.keys(config.sourceFiles||{}).length)throw Error('缺少已核对的原 PHY 文件');
 for(const [name,item]of Object.entries(config.sourceFiles))
  if(!existsSync(item.path)||hash(item.path)!==item.sha256)throw Error(`原碰撞文件不匹配：${name}`);
 for(const name of ['source-layers/elf-female.json','gameplay/native.json'])
  if(!existsSync(resolve(runtime,'game-data/converted',name)))throw Error(`缺少本地转换资料：${name}`);
 return {runtime,configPath,files:Object.keys(manifest.files).length,nativeSHA256:manifest.nativeSHA256};
}

export async function startLocalMvp({runtime=DEFAULT_RUNTIME,port=8876,maxPlayers=8,dataDir=resolve(ROOT,'runtime/mvp')}={}){
 if(!Number.isInteger(port)||port<0||port>65535)throw Error('端口必须在 0–65535 内');
 if(!Number.isInteger(maxPlayers)||maxPlayers<1||maxPlayers>32)throw Error('本地人数上限必须在 1–32 内');
 dataDir=resolve(dataDir);
 if(dataDir!==resolve(ROOT,'runtime/mvp')&&!inside(dataDir,resolve(ROOT,'analysis/raw')))
  throw Error('MVP 存档只使用独立 runtime/mvp 或忽略的验收目录');
 const ready=inspectRuntime(runtime);
 mkdirSync(dataDir,{recursive:true,mode:0o700});
 const lock=resolve(dataDir,'server.lock');
 let fd;
 try{fd=openSync(lock,'wx',0o600);}catch(e){if(e.code==='EEXIST')throw Error('这份 MVP 存档已有服务锁，请先关闭旧服务；崩溃遗留的锁需核对后处理');throw e;}
 try{writeFileSync(fd,JSON.stringify({pid:process.pid,port}));}
 catch(e){closeSync(fd);unlinkSync(lock);throw e;}
 closeSync(fd);
 let game,motion,released=false;
 const release=()=>{if(!released){released=true;unlinkSync(lock);}};
 try{
  const base=pathToFileURL(resolve(ready.runtime,'prototype/')+sep);
  const {loadNativeWindowCollision}=await import(new URL('game/native-window-collision.mjs',base));
  const {loadGameplay}=await import(new URL('game/basic-attack.mjs',base));
  const {createGameServer}=await import(new URL('server.mjs',base));
  motion=loadNativeWindowCollision(pathToFileURL(ready.configPath));
  if(!motion?.sourceNative)throw Error('原地图碰撞未就绪；不启用替代算法');
  const gameplay=loadGameplay();if(!gameplay)throw Error('原普攻/技能资料未就绪');
  game=createGameServer({maxPlayersPerRoom:maxPlayers,saveFile:resolve(dataDir,'characters.json'),gameplay,motion:null,mapWindowMotion:motion,navigation:null});
  await new Promise((ok,fail)=>{game.server.once('error',fail);game.server.listen(port,'127.0.0.1',()=>{game.server.off('error',fail);ok();});});
  const address=game.server.address();
  const url=`http://127.0.0.1:${address.port}/explore-map.html?room=MVP-01&sourceProfile=APK_Default`;
  let closing;
  return {game,url,saveFile:resolve(dataDir,'characters.json'),close(){
   return closing||=(async()=>{try{await game.close();}finally{release();}})();
  }};
 }catch(e){try{if(game)await game.close();else await motion?.close?.();}finally{release();}throw e;}
}

if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
 try{
  const args=process.argv.slice(2);
  if(args.length===1&&args[0]==='--check')console.log(JSON.stringify(inspectRuntime(),null,2));
  else{
   const options={};
   for(let i=0;i<args.length;i+=2){
    const key={'--port':'port','--max-players':'maxPlayers'}[args[i]];
    if(!key||!/^\d+$/.test(args[i+1]||'')||Object.hasOwn(options,key))throw Error('用法：local_mvp.mjs [--check | --port 8876 --max-players 8]');
    options[key]=Number(args[i+1]);
   }
   const running=await startLocalMvp(options);
   console.log(`本地 MVP 已启动：${running.url}\n存档：${running.saveFile}\n单人可进入；当前每房间上限 ${options.maxPlayers??8} 人。原地图/角色 + 明确的本地联机与战斗规则。Ctrl+C 保存并退出。`);
   let stopping=false;
   const stop=async()=>{if(stopping)return;stopping=true;try{await running.close();process.exit(0);}catch(e){console.error(e.message);process.exit(1);}};
   process.on('SIGINT',stop);process.on('SIGTERM',stop);
  }
 }catch(e){console.error(e.message);process.exitCode=1;}
}
