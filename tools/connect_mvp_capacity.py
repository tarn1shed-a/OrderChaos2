"""Expose local session capacity; this is not an original server rule."""
import hashlib
from pathlib import Path
from tutorial_map_geometry import ROOT,local_output
from connect_map_geometry import replace_once

PINS={
 'prototype/server.mjs':'5ca4b0f0b7af74e0d88cdc927a6add7823e8e8c6ef54714f9b9dd3a9d7f49223',
 'prototype/public/explore-map.js':'c10541905524a39ece8af8f35ef41b45d96d80852cad9201ae0cd1df81fd1b75',
}
def connect(runtime):
    runtime=local_output(runtime);pending={}
    for name,digest in PINS.items():
        p=runtime/name;old=p.read_bytes()
        if hashlib.sha256(old).hexdigest()!=digest:
            raise ValueError('Preserve unexplained or already-connected MVP changes: '+name)
        pending[name]=old.decode()
    name='prototype/server.mjs';text=pending[name]
    text=replace_once(text,'export function createGameServer({ saveFile,','export function createGameServer({ maxPlayersPerRoom=8, saveFile,')
    text=replace_once(text,'  if (saveFile &&',"  if(!Number.isInteger(maxPlayersPerRoom)||maxPlayersPerRoom<1||maxPlayersPerRoom>32)throw Error('本地房间容量必须为 1–32');\n  if (saveFile &&")
    text=replace_once(text,"if (room.size >= 8) return reject(ws, '这个房间已满（最多 8 人）');", "if (room.size >= maxPlayersPerRoom) return reject(ws, `这个房间已满（最多 ${maxPlayersPerRoom} 人）`);")
    text=replace_once(text,"const used = new Set([...room.values()].map(s => s.player.color));\n        const index = COLORS.findIndex(c => !used.has(c));", "const used = new Set([...room.values()].map(s => s.spawnSlot));\n        let index=0;while(used.has(index))index++;ws.spawnSlot=index;")
    text=replace_once(text,'color: COLORS[index],','color: COLORS[index % COLORS.length],')
    text=replace_once(text,"send(ws, { type: 'welcome', id: ws.player.id, room: roomId, scene, world,lab,", "send(ws, { type: 'welcome', id: ws.player.id, room: roomId, roomCapacity:maxPlayersPerRoom, scene, world,lab,")
    pending[name]=text
    name='prototype/public/explore-map.js';text=pending[name]
    text=replace_once(text,'const query = new URLSearchParams(location.search);','const query = new URLSearchParams(location.search);\nlet roomCapacity=8;')
    text=replace_once(text,'`${snapshot.length} / 8`','`${snapshot.length} / ${roomCapacity}`')
    text=replace_once(text,'monsterCooldownMs = msg.combat?.monsterCooldownMs ?? 1000;', 'monsterCooldownMs = msg.combat?.monsterCooldownMs ?? 1000;\n      roomCapacity=msg.roomCapacity??8;')
    pending[name]=text
    for name,text in pending.items():(runtime/name).write_text(text)
    return {'files':len(pending),'scope':'Local session transport configuration only','defaultCapacity':8,'minimumPlayersToJoin':1,'originalServerRuleRecovered':False}

if __name__=='__main__':
    import argparse
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--runtime',type=Path,required=True)
    print(connect(cli.parse_args().runtime))
