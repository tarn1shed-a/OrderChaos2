# 战斗栏职业资格修正（2026-11-14）

游侠技能书已按职业过滤，右下仍出现炎爆术/霜爆术/奥术飞弹，是旧试玩战斗栏没有职业资格判断。它不是旧角色缓存。本批撤掉错误职业的三招演示显示及输入，不称其它职业技能已能使用，也不称原技能栏完整恢复。

## 当前已接服务的事实

- 审定 `prototype/game/combat.mjs:118` 对当前原法术明确检查 `native && ws.character.profession !== 2` 并拒绝。此判断是当前本服已接能力边界，不是完整原服职业/学习规则。
- `tools/native_cast.py` 的固定 BINDINGS：`fireball→17`、`frost_blast→94`、`arcane_missile→90`。
- 原审定 `public/hotbar-settings.js` 的 `defaultHotbar` 硬塞这三招，`validHotbar` 要求三招各一次；`hotbar-ui.js` 在每次 render 把三按钮放到保存的逻辑格；`mobile-hud.js` 根据三个固定按钮 ID 排到原手机位置，并重设 `slot.hidden`。

因此不能只在角色更新时藏一次图标，不能把过滤后的空配置交给旧 validator 或写回服务器。本批不改这些源文件、validators、原127、私有f1dc28包、数据库/角色存档或服务器协议。

## 本批4文件

- `deploy/character_hotbar.mjs`：纯显示/输入资格适配器，`createCharacterHotbar` 包装原 hotbar/mobile HUD 工厂。
- `tools/preview/character-hotbar-overlay.mjs`：`stageCharacterHotbarEntry`，严格唯一锚点变换，在已接人物面板的 staged entry 后使用。
- `tools/character_hotbar_tests.mjs`：真实原 hotbar/settings/sync 模块与显式内存 DOM/存储spy，以及实际生成入口函数的7项检查。
- 本文档。

资格为：当前已连接角色存在、ID与已交给原热栏的角色一致、`profession===2`。不接受字符串`"2"`代替原服务判断中的数字2，不接受旧角色绑定继续给换角后的对象提供技能。

非2职业、未登录或绑定角色不匹配时：

- 隐藏三招的整个当前父 slot（图标/框/键位一起），同时禁用、inert并移出按钮焦点；旧 camp 中的对应 skill 按钮也隐藏。
- 关闭并禁用旧键位编辑。document捕获阶段拒绝对应按钮、编辑入口和编辑面板内的点击/指针事件，防止旧监听器执行默认/重试动作。
- `skillForEvent` 不解析出任何这三招；实际 `useSkill` 函数第一条资格门禁再次拒绝，覆盖直接调用和旧点击监听器。
- 不给非2角色调用原 `setCharacter/syncCharacter/receiveResult` 保存链；detach只断开旧同步和关闭编辑，避免原 `hotbar===null` 自动初始化/旧确认缓存把三招再写入该角色。
- 不替换成其它职业默认技能，不从静态目录推断已学或已装备。

法师正常交给原热栏的角色、配置、顺序和快捷键原样保留；其原有编辑/同步机制不重写。普攻、跳跃、摇杆、原位置、服务器冷却与请求内容不改。适配器本身没有 storage 或 send 写操作。

隐藏使用自有 `display:none!important` 覆盖，保留原 `slot.hidden` 的布局所有权；恢复法师时只撤销自有覆盖，不用旧 hidden 值覆盖新的手机布局。原 render 的 `onChange`、每次 mobile `layout()`、角色进度/同步/结果、断开连接、每次 `updateSkills()` 后都重新应用资格，防止回显。记录只在内存中用于恢复 DOM 状态，不写角色配置。

## 主任务接入

共享 `prepare_delivery` 在原 `stageCharacterPanelsEntry` 后、仅人物清单存在时追加：

```js
import {stageCharacterHotbarEntry} from '../tools/preview/character-hotbar-overlay.mjs';
entrySource = stageCharacterHotbarEntry(entrySource);
```

把 `/__delivery/character_hotbar.mjs` 映射到 `deploy/character_hotbar.mjs`。这是部署代码适配，不需要重打私有f1dc28包，也没有新游戏入口或素材。root负责共享接线/Docker/context/CI、Linux与浏览器、最终发布。

overlay重复应用、缺失人物面板前置、缺失或重复任一锚点都会失败。原 hotbar 的全部保存配置仍保持原形；没有向服务器发送 filtered hotbar。

## 验证

```sh
node tools/character_hotbar_tests.mjs
```

7项通过：

1. 1..5职业和无角色；只有数字2角色有现有三招资格。
2. 法师打开编辑后换到其它4职业，再回法师、断开；progress与mobile布局重设后仍不回显，普攻/跳跃位置不变。
3. 法师保存的第8逻辑格、Shift+Z自定义顺序/按键保留，切回不改配置对象；非2旧确认不能缓存写入。
4. 非2空配置不读取旧存储、不发初始化/保存请求，编辑/重置/重试/法术按钮的DOM负例被挡。
5. 实际 stageEntry→inside→panels→hotbar 变换的唯一锚点、JavaScript语法、原attack/jump/send路径保持。
6. 实际生成的useSkill对五职业/无角色负例在send前拒绝；法师原请求内容不变。
7. 实际生成的键盘handler在五职业中只允许法师解析保存按键。

DOM/角色/存储均为显式内存夹具，没有读写用户或线上角色。真实旧模块来自忽略目录的审定127副本；没有私有副本的CI须由root条件运行该组，不能把跳过说成原模块测试通过。root随后在8898隔离卷验收战士/游侠，并以同一helper SHA核对云端法师回归；本子任务不部署、不新增云端角色。

## 下一真实边界（仅记录，不在本修复接入）

原静态目录、原学习记录和原装备/快捷槽内容是三种状态：

- 目录：原 `a0f968` 按职业建立主动/被动目录，不能据此授技能。
- 学习：原入站 `0x4b → 573b74` 的 `SMSG_SkillInit.learn_skills`，每项 `skill_proto_id/skill_rune` 交给 `a0ef3c`；index0..3对应实际学习字节。已有学习探针只证明这一消费，不证明当前角色学会目录中所有技能。
- 装备/快捷槽：同一原 `Skill.proto` 另有 `equip_skills`、shortcut、skill_page 状态，不能拿learn_skills或当前网页hotbar替代。原 `SkillSetting.onShow @399..428` 调用 `GetSkillIdByOpSlot(OPIT_SLOTSKILLITEM, _currSkillItem)`；`SkillPassive` 的 `_SkillSlot0/1` 也需要实际装备快照。`FreeBar`与这些回调的原缓存/页面/槽索引归一化、真实本服状态尚未接回，当前原模型/技能书可见不代表这一链已恢复。

相关冻结证据见 `CHARACTER_PROGRESSION.md`、`CHARACTER_LEARNING_STATE.md`、`CHARACTER_ATTRIBUTE_UPDATES.md`。本修复不调用这些原装备回调、不猜默认学习或装配，不把撤掉错职业三图报告为其它职业可施法。
