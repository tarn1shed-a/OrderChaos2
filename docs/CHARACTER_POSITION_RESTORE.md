# 网页位置存档与指定角色脱困审计（2026-11-14）

本批只读源码并执行全新内存夹具，新增 `tools/character_position_audit_probe.py`、`character_position_audit_tests.py` 与本文。没有打开真实角色存档、发送重置请求、启动游戏服务，或改动共享deploy/原127文件/角色。原技能刷新与帧批冻结保持。报告、原源码片段和SHA收据只留忽略目录 `analysis/raw/character-position-restore-20261114/`。

**已有returnEntry可按角色凭证、离线条件、备份、位置替换执行一次脱困；刷新本身会恢复保存的位置，不是脱困操作。** 主任务待用户指定角色后负责真实备份和位置单项修复，本代理仅审计与给接口边界。

## positions.resources不是原服入图坐标

审定 `prototype/game/character-store.mjs` 的记录以UUID为键。`positions`可有camp/resources两个场景；resources中x/y是网页逻辑平面坐标，对应原世界X/Z，groundY才是原世界方向的Y。房间号、mapWindow、map_id、碰撞版本/楼层、姿态与临时空中高度均未作为该位置记录的键或字段。

`savePosition(record,scene,player)`的实际逻辑：

- x/y变化即保存，不要求grounded；groundY仅在 `(grounded || swimming===true) && finite(worldY)` 时取当前worldY，否则保留旧位置的groundY。
- 踏空移动夹具把x/y改为44/55、当前worldY=120但grounded=false，保存仍是 `{x:44,y:55,groundY:172}`；落地后groundY才变132，游泳时又可保存130。非有限高度保留旧值。
- 因此groundY不是“最后安全完整XYZ”。空中时可把新X/Z与旧高度组合；落到受困低处后，也可能把低处作为新的落地高度保存。本审计没有读取用户现场，不能仅凭这条规则判断那次跌落的具体成因。
- 位置变化会touch角色updatedAt并标dirty；完全相同位置不touch。savePosition本身不flush。

服务端每50ms移动后调用savePosition；普通changed/save请求、join、当前连接close、服务close也会保存。每5秒dirty会整体flush。flush使用临时文件、文件fsync、rename替换整个version6文档；不是只写一个角色的磁盘字段。constructor读取v1..5时还会准备旧版迁移；这不应被拿来执行一次“只改位置”的旧存档维修。

## 身份、join与活跃会话

`resolveCharacter(name,characterId,resumeToken,profession)`在给凭证时按ID查record，再核SHA256 token；返回原record，忽略请求里的name/profession。未给凭证则创建新UUID。名字没有唯一性约束，同名可以是不同角色；不能按名字找到第一条就改。

join的身份恢复标记 `restored=true`只表示凭证恢复。实际位置恢复另要求：非lab、有scene位置、原网页walkable水平边界通过且record.hp>0。walkable不是原三维PHY支撑验证。

真实join位置语句已在记录motion接口的fixture中执行：

1. 建player的x/y，先执行motion.place。
2. restorePosition为true且groundY有限时，sourceCameraCPU分支再调用motion.restoreHeight(player,groundY)；否则旧分支以原平面转换后的X/Z及groundY+step查询support。
3. 没有groundY就只有place；死亡或水平边界外会用spawn。正式sourceWindow新入场不再套并发index*35偏移。
4. 加入activeCharacters和room，然后保存、touch、flush。`restored=true`不能用来断言原存档高度实际被采用。

实际native-window绑定的restoreHeight会向worker发restore-height，再清除initialized；首次move还会reset该identity的worker actor。worker reset删除该identity旧actor再重建。这里是当前网页/宿主绑定，未执行原EnterMap网络流程。

同角色活跃检查以全进程 `activeCharacters.has(record.id)`为准，跨房间同样拒绝。**它比后台online严格**：后台报告用readyState===1；socket已CLOSING但close未清Map时，returnEntry仍会拒绝。应等该ID从active Map移除，不能只按后台显示offline判断。

close保存还核 `activeCharacters.get(id)===ws`。实际原语句夹具确认旧socket不匹配当前socket时，既不保存旧player，也不删除当前连接；匹配时才savePosition/flush/delete。active Map是当前进程的状态，不能替代停止其它持有同一存档的写入进程。

## 已存在的显式returnEntry

`deploy/entry_manage.mjs`的 `trialRoleManager.returnEntry` 已接POST `/__entry/return`。它要求有效ID/token、anchor严格为cinematic7且entryPosition可用；同角色仍active则拒绝。HTTP适配要求同源Origin与JSON POST，限制请求体；后台admin当前只有只读角色报告，没有按名字重置接口。

执行顺序为：

`身份核对 → anchor核对 → active.has拒绝 → 当前motion求有限x/y/groundY → 备份完整record → 替换positions.resources整对象 → dirty=true → flush`。

备份默认写entry-backups，独占新文件、权限0600，目录0700。备份失败不改record；flush失败会恢复旧positions对象、dirty和savedAt。内存fixture实际覆盖错凭证、错角色、未知anchor、OPEN/CLOSING会话、无支撑、备份失败与flush失败，全部保持原记录。

成功时只替换resources，保留camp、其它角色和全部非位置字段，包括角色updatedAt；全局文档savedAt会更新。正常随后join又会touch updatedAt，不要把“重置操作只改位置”的验收与之后正常join元数据变化混为一谈。

原入口UI在所选角色开始前，仅在URL含trialEntry=cinematic7时调用该路径；成功后删除URL参数，再connect。普通刷新/重连不自动重置。

目标仍是用户此前同意的原镜头7结束锚点 `(-2594,136,-64)`：当前helper转换X/Z，并从配置Y+5即141查询支撑。135.72999572753906是此前碰撞结果，不应硬编码给另一份碰撞部署；真实执行应由当前motion求目标。它不是已找回原首次出生点。

## 本轮最小位置修复接口要求

现有角色主人能使用原浏览器凭证时，最小操作就是已有returnEntry，不需要新增技能/复活/传送规则，也不需要永久管理重置API。主任务在收到角色名后应先锁定唯一UUID；重名则继续核对身份，不能跨角色猜选。

此次授权的具体操作至少应绑定：**被授权UUID、预期旧resources位置/存档版本、目标anchor=cinematic7、当前有效支撑、离线状态、可核SHA的操作前备份**。现有returnEntry已做所有权、离线、备份和目标检查；预期旧值/备份SHA可由主任务的维护收据核对，不必改变原127或角色schema。

如由维护进程直接修文件，须先停止所有会写该文件的运行进程，完成最后flush/close后再备份并核目标ID/旧值；只替换该ID的positions.resources，原版本/其它角色/其它字段保持，原子落盘并记录前后差异。**不能在服务器仍持有store Map时只改磁盘**：下一次5秒flush、退出或关服保存会把旧内存位置写回。也不能只改groundY而把受困X/Z留下，或统一抬高所有角色。

完成后只验指定角色下一次join的X/Y/worldY与当前支撑、刷新恢复，并核其它角色和进度/装备/技能未被该操作改动。原用户实际位置修复由父任务执行，本工具没有apply/reset模式，不接收任意角色文件路径或生产凭证。

## 与原Native EnterMap证据分开

原证据见 `docs/MAP_ENTRY_AND_FLOOR.md`：GS2C_EnterMap.location包含原Vec3；a34f28读取三坐标，经virtual+448→a0e3ac→9037d4→virtual+68→a0902c同时写当前位置+118与待处理位置+1ac，保留输入Y。特定加载状态下90c348从待处理Y+0.5查支撑，水/保留分支也有条件；并非无条件选择最高楼层。

这些原CPU证据不把网页positions.resources或returnEntry变成原协议。真实map5首入location/加载生命周期仍缺；本批未重跑原入图CPU、未伪造原服包，也未通过保存groundY推断原出生/安全复活规则。

## 复跑

```sh
.venv/bin/python tools/character_position_audit_probe.py \
  --output analysis/raw/character-position-restore-20261114/recheck
.venv/bin/python tools/character_position_audit_tests.py -v
```

8项检查为3项公开deploy方法内存夹具、5项可选审定私有源码消费检查。只读4个固定原127源码路径，并按tools/local_mvp_runtime.json核SHA；不打开任何characters.json。私有源码缺失时5项明确skip，公开组不需分析依赖。join高度接口和walkable运行在明确fixture中，未冒充原碰撞/浏览器或现场脱困验收。
