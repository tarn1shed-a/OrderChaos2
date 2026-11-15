# 五职业选择与只读技能窗口接线（2026-11-15）

五职业编号没有在当前选择链里错位。真正的新断点是任务页面替换了地图入口脚本，旧人物面板接线没有在该页面运行；任务入口还主动隐藏技能按钮和全部战斗栏。本批新增独立 `deploy/character_choice_skills.mjs`，供root将**原技能目录窗口**接回当前任务页面。没有改共享入口、原窗口布局、角色存档或生产，也没有补其它职业默认技能。

## 已核接线与断点

| 层 | 当前真实输入/消费者 | 结论 |
| --- | --- | --- |
| 原选择 | 原UI顺序战士、游侠、法师、血骑士、僧侣；native及现 `entry_ui.mjs` 创建表达式 `[1,3,2,5,4][draft.cls]` | 原职业号分别1、3、2、5、4；不能以UI序号当职业号 |
| 身份/身体 | `player_choice_registry.mjs` 的45草稿与 `registry.check(sourceAvatar,profession)`；认证welcome的 `character.profession/sourceAvatar` | sourceAvatar绑定身体和原外观；技能目录使用该角色profession，不从种族/Model/创角display推职业 |
| 目录 | 现 `sourceProfessionSkills(profile,role.profession,source,role.id)` | 五职业各9主动、5被动。第一个目录ID按1..5为24、90、190、243、256；目录不是已学或已装备 |
| 原状态 | 既有原 `SkillInit` 学习/装备/shortcut及原属性消费 | 真实本服快照仍缺；本helper传入source:null，不按网页等级或45项草稿推断 |
| 旧地图窗口 | `prepare_delivery.mjs` 对explore-map生成 `stageCharacterPanelsEntry` / hotbar overlay | 原窗口和职业过滤已存在，仍可复用；不能因此称所有页面都已接入 |
| 当前任务页面 | `quest_delivery.mjs` 将页面脚本改为 `/__delivery/quest_world.mjs` | 该模块没有导入人物面板；其init隐藏field-skills，mountHUD隐藏全部hotbar/普攻。因此旧overlay的K/菜单接线不执行 |
| 当前身体准入 | 本次审计时quest_world welcome仍统一拒绝sourceAvatar | 身体专线/root正在接入；本批只记录，不抢改此分支或扩大身体准入 |
| 网页战斗 | 旧审定combat的native分支只接数字profession2；`native_cast.py` 固定17/94/90三法术 | 是既有法师试玩能力。旧hotbar wrapper撤掉其它职业错误三图；不代表其它职业战斗已恢复 |

源文件SHA及各断点行号在私有 `analysis/raw/character-choice-skill-20261115/audit-v1/audit.json`。共享身体接线会继续变动，收据描述该审计时点，不拿旧行号阻挡root的后续集成。

## 最小可接模块

```js
import {createCharacterChoiceSkills} from '/__delivery/character_choice_skills.mjs';

const skills=createCharacterChoiceSkills({
  readSession:()=>({connected,character,epoch:generation}),
  button:document.getElementById('field-skills'),
  stop,
  beforeOpen:()=>{ /* 关闭现有任务窗口、清pointer；由当前入口注入 */ },
  focusGame:()=>canvas.focus({preventScroll:true}),
  onError:error=>note(error.message),
});
```

只接受已连接、有UUID、数值profession1..5及显式epoch的认证会话；没有创建草稿参数。sourceAvatar按原认证资料只读保留，不要求旧角色补种族字段，九身体均用同一profession目录入口。每次传给原面板的是角色副本与 `{source:null,trialProgress:null}`，不把网页60xp演示或角色级别转成原学习/锁态。

root最小共享接点：

1. 认证welcome完成赋值后 `skills.sync()`；断线/reset、打开角色选择页之前 `skills.disconnect()`。选择页可能在旧socket尚连接时打开，所以不能只依赖connected=false清理；所有 `entry.open()` 路径也应先disconnect。
2. 由helper接管已有field-skills按钮的显隐与点击；该按钮不再加入任务入口的固定隐藏数组。保持原按钮位置和原窗口。`K`只需在当前键盘门禁内调用open/close，不新增悬浮按钮。
3. 当前移动/拾取/跳跃等 `blocked()` 门禁追加 `skills.isOpen`；打开任务/选择页时关闭技能窗口。上述控制由真实当前入口提供，helper不自造战斗或移动权限。
4. 页面退出调用 `skills.dispose()`。generation/角色更换必须先走sync或disconnect，使旧原窗口的ticket立即失效。
5. 新增URL映射 `/__delivery/character_choice_skills.mjs`，并核下面原素材闭包。模块和样式仅首次打开目录时加载，不放进地图critical阻塞入图。

`open()`返回Promise<boolean>；菜单按钮已绑定toggle。`sync()`返回当前身份是否有效。`close/disconnect/dispose`同步使旧请求失效。`isOpen`只代表当前认证角色的实际原dialog。

模块/CSS晚回包会再次核UUID、profession和epoch；原共享面板的异步mount严格串行，避免旧职业drawing覆盖新页。旧mount即使在disconnect先close后才自行show，旧run完成时也再次**实际close view**，不是仅用helper getter遮蔽残留窗口。没有新open时同样覆盖该负例。

## 原窗口与依赖闭包

只调用现有 `createCharacterSourcePanels().openSkills()`，其原 `SkillSetting` / `SkillPassive` / `WindowStack` SVG及顶栏、返回按钮、职业图和铭文图完全复用。没有属性模型预览，没有新UI布局。原候选已有的学习/装备操作保持隐藏，缺装备快照时原slot artwork清空；目录可读不等于标记解锁或装备。

复用已冻结f1dc28人物包的材料，不必重做职业图或写存档。`audit-v1/audit.json` 已沿实际技能页使用的profile字段及SVG href闭合**99个既有URL**，全部本地存在，逐一带SHA：

- 90个 `/assets/character-source/` 成员，含panels.json、三个原窗口和实际引用图。
- 4个模块/样式：`/character-source-panels.mjs`、`/character-source-state.mjs`、`/source-ui-svg.js`、`/character-source-panels.css`。
- 3个原字体：`/assets/ui/chineseText.woff`、`chineseDisplay.woff`、`leagueGothic.woff`。
- 2个原图集：`/assets/ui/igm-atlas-1.png`、`igm-atlas-8.png`。

另加本次helper一个外置URL。若交付沿用完整人物包，也可保留原101份人物素材全后台预取；99是技能窗口实际消费闭包，不是要求删除其它文件。CSS使用原已有字体和样式，首次打开时等待load/error；失败只报告目录打开失败，不影响正常入图。当前任务包是否已包含这些URL须由root在实际files清单核对，不能仅因旧f1dc包曾上线就默认新任务包仍完整。

## 检查与边界

```sh
node --test tools/character_choice_skill_tests.mjs
.venv/bin/python tools/character_choice_skill_audit.py \
  --output analysis/raw/character-choice-skill-20261115/recheck
```

13项全部通过：五职业认证输入；草稿/无连接/错误职业/epoch负例；模块与CSS晚回包；原共享mount串行；关闭后迟到view实际关闭；UUID不变但职业/epoch变化；CSS/模块加载错误的局部处理、CSS重试及真实link错误事件；原按钮toggle与销毁；实际entry创建表达式；真实source-state模块保持目录/学习分层；私有原45项registry到五目录（各9主动/5被动）。最后一项缺原私有registry/profile时明确skip，其余12项只用公开代码和明确内存DOM/异步view夹具，不依赖分析包。原面板自身内部drawing初始化失败后的重试仍沿用冻结模块，本批没有改其加载器。

45项检查运行的是原已导出材料和现适配器，不是重新执行原CPU、完整Flash VM或实际浏览器。真实DOM/地图/两角色切换/刷新由root/NPC独占浏览器专线验收，本批不抢浏览器。没有读取玩家存档、连接服务、分发技能、发送施法、接装备页或部署。

原技能目录、原SkillInit学习记录、原装备页/FreeBar槽内容、网页兼容执行继续分层。此批可恢复当前任务入口的五职业只读目录；全职业真实学习、快捷装配、施法及动作权限仍需确切原输入，不能把这次目录接线报告成所有职业已可战斗。

## root接入与实际界面复核

同日root已将helper接回普通任务页。只在交付清单含完整原面板模块/资料入口时标记 `data-source-character-skills="1"`，旧不含原面板的包保持隐藏；不完整模块组合在准备交付时拒绝。原技能按钮和K开关共用该窗口，角色选择、断线、任务窗口和页面退出均关闭它。打开目录立即停止当前移动，再按需加载原模块和CSS，不把99份目录素材变成入图阻塞项。没有恢复未知的原学习/装备操作，也没有填充法师试玩热栏。

原f1dc28完整素材包实际字节SHA已重新核对，99个技能依赖的成员大小与SHA全部相同，无需新造或替换图。准备交付增加缺模块负例；实际任务页键盘事件测试覆盖面板打开时K仍可关闭、输入/选角/断线/组合键不会误开窗口。

在全新59610隔离库，root真实使用原UI创建五名人类女性，逐个开始并显示自己的Model32身体与完整131属性/1928B姿势。五职业目录实际分别显示旋风斩、瞄准射击、奥术飞弹、恶魔冲拳、伏虎掌；游侠被动页显示游猎者。K关闭通过，换职业和刷新后回到战士没有残留僧侣目录；学习状态仍未知、装备格为空。

战士实际按键行走/停步、刷新后同UUID和同位置恢复，并实际点击原NPC靠近、打开普通461的原任务正文、确认接取，原追踪显示0/4。该条使用此前已授权的普通任务兼容执行，不涉及主线208审批或缺失对白。浏览器warning/error为空，GPU错误为0；没有跳跃/空中或五职业战斗的完成声明。

独立实测与截图在忽略目录 `analysis/raw/player-choice-motion-20261115/browser-check-v1/`，`acceptance.json`列出各身份/职业/身体、恢复位置差、截图SHA和边界。测试页面285已关闭；59610服务由协作专线保存隔离交接。正式发布状态另由root记录，不将本地女性五职业测试扩大成线上全部45种身体组合已可玩。
