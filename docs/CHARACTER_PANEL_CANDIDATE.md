# 原人物/职业技能只读可见候选（2026-11-14）

本批把前三批核实的职业目录和属性消费接到独立原布局候选。尚未接生产或共享运行接口；没有读取、修改任何角色存档，也没有授予技能或经验。此前冻结的 10 文件保持原哈希。

可以直接看到的变化：五职业各自的主动/被动技能目录、原铭文图标及说明；人物姓名旁的原职业图标；原属性经验条的显示修复。独立 QA 使用显式临时对象，人物模型位置留空。整合时沿用现有 `renderAttributePreview` 回调读取当前角色模型。

## 入口和复跑

已构建的忽略目录：`analysis/raw/character-progression-20261114/panel-candidate-final/`。`public/` 为仅静态素材和只读模块，`SHA256.json` 校验全部输出。当前本机静态入口端口为 8894；不连接游戏服务器，不打开 WebSocket，不访问存档。

```sh
.venv/bin/python tools/character_panel_candidate_assets.py \
  --output analysis/raw/character-progression-20261114/panel-candidate-recheck
.venv/bin/python tools/character_panel_candidate_tests.py \
  --public analysis/raw/character-progression-20261114/panel-candidate-recheck/public -v
.venv/bin/python -m http.server 8894 --bind 127.0.0.1 \
  --directory analysis/raw/character-progression-20261114/panel-candidate-recheck/public
```

生成器要求输出位于忽略目录，且拒绝覆盖已存在目录。校验 9 个原 UI/字符串资源 SHA、已有成长表 SHA、审定 `source-ui-svg.js` SHA；重复资源必须字节相同，存在不同副本时拒绝自行决定挂载优先级。

浏览器入口：

- 属性、现有试玩进度显式夹具：[法师属性](http://127.0.0.1:8894/panel-candidate.html?profession=2&pane=attributes)。`30 / 60` 来自 QA 传入值；候选不执行 `%60`、升级或奖励计算。
- 技能目录：[战士](http://127.0.0.1:8894/panel-candidate.html?profession=1&pane=skills)、[法师](http://127.0.0.1:8894/panel-candidate.html?profession=2&pane=skills)、[游侠](http://127.0.0.1:8894/panel-candidate.html?profession=3&pane=skills)、[僧侣](http://127.0.0.1:8894/panel-candidate.html?profession=4&pane=skills)、[血骑士](http://127.0.0.1:8894/panel-candidate.html?profession=5&pane=skills)。左侧沿原 WindowStack 切主动/被动；原箭头查看后续条目，点击技能或铭文查看原说明。
- 明确的空学习协议夹具：[战士空学习](http://127.0.0.1:8894/panel-candidate.html?profession=1&pane=skills&state=known-empty)。仅此参数提供 `learning:[]`、原字段 `77:3,138:150,139:7455,145:2`，故显示 `0/9`、`0/27`、2 点及原等级门槛锁图。它不是任何用户的真实状态。

`C` 打开属性，`K` 打开技能；返回关闭。页面内 QA 对象 ID 固定以 `qa-panel-` 开头，仅存在内存。

## 原布局与素材

新增实现仅为下列 8 文件，未修改 `deploy/`、原 127 文件、共享构建代码或此前冻结 10 文件：

- `tools/character_panel_candidate_assets.py`：独立资源构建和原方法/字段证据清单。
- `tools/character_panel_candidate_svg.py`：原 SWF 显示列表导出，保留原矩阵、遮罩、颜色变换和文字样式。
- `tools/character_panel_candidate_tests.py`：5 项素材、消费和输入边界检查。
- `tools/preview/character-source-panels.mjs`、`character-source-state.mjs`、`character-source-panels.css`、`character-source-qa.mjs`：只读控制器、纯输入映射、原字体/窗口适配、显式 QA 对象。
- 本文档。

主体为原 `AttributePage`（root 106）、`SkillSetting`（原 `symWindowSkillSetting`）、`SkillPassive`（原 `symWindowSkillPassive`）、`WindowStack`（root 23）绘图。主动保留 7 个原列表模板位置，被动 4 个；没有重新排版为网页卡片。侧栏取 `interface_common_2.ini` 的原图标配置，`TabBoard.height=565` 取原 `WindowStack.init @296..302`。现阶段仅技能的两个侧栏标签可以切换，属性侧栏其它页面尚未接入。

89 个职业/技能/侧栏图标直接复制原 PNG 全文件。总计 96 份图标、原图集及锁图素材逐字节或逐像素校验。技能页对 `itempanellocked.png` 的外部引用未单独存在于包中：候选只接受原 library **同导出符号**、单矩形图集形状、相同尺寸/原点得到的 40×40 无损裁切；清单保存 library sprite/shape、图集 SHA、原矩形。没有按图像外观猜裁切位置。最终构建没有未关联的外部图片。

仍未执行 Flash 的 67 个滤镜栅格化操作；没有原冷却快照的两处 morph 倒计时留空。图形导出和浏览器文字折行是显式适配，不称为完整 Flash VM。原技能说明按原字符串显示，尚未恢复的实时伤害/消耗统计留空。

关键原 SWF SHA256（完整清单见生成器 `SOURCE_PINS` 和素材清单）：

| 资源 | SHA256 |
| --- | --- |
| AttributePage | `e7ad9fc9b9fd8c1749113c1ca2fa9e9ec00e1261bdaca282cae943a2d38bdc76` |
| SkillSetting | `3ffab64df48454250c71871c94796a4409af719ca72e6fc6afcc1e2d00ab12bc` |
| SkillPassive | `93d7ab055dbdd4ae4cd424023d06d0a46b5f5d8bd793cefcc69df68827f3af9d` |
| WindowStack | `39f53d816b06f9573e8cc0a6b107ac9428f239c7a80bcaaeb63626bc1803dd33` |

## 经验条的具体修复

原 `AttributePage.SetAttributeValueExp @290..301` 先调用 **父** `Exp.valueBar.gotoAndStop(totalFrames)`，随后 `@349..358` 把 **子** `exp` 与比例交给 `setMcToPercent`。原父 sprite 70 有 **60 帧**，子 sprite 69 仅 **1 帧**。原 `setMcToPercent @13..32` 执行 `gotoAndStop(totalFrames * ratio)` 与 `scaleX=ratio`，原 Exp 比例下限 2%、上限 100%。

现有 `recover_login_ui` 的输出保留了父第 1 帧；`deploy/attribute_ui.mjs` 仅缩放子图，父第一帧遮罩会把 `30 / 60` 也夹成细线。本候选独立导出父第 60 帧，再按原子比例消费；浏览器实际看到半条。没有修改这些共享文件。此前阶段口头提到“101 帧”不准确，已按实际 SWF 核正为父 60 / 子 1。

方法代码 SHA：

- `SetAttributeValueExp`：`a1871ececb03835c5e621a9ae2f96dd9edb1056e3a5d7dc747fbc9c8f936ef4f`。
- `setMcToPercent`：`af32fca550f9b58991690fcf507e154f635b505afa4d4cec215c50e202216777`。

## 输入边界

当前试玩等级/HP/护甲和匹配角色的原消息缓存是两组输入。原协议字段与写入/显示的原 CPU 证据见 `CHARACTER_ATTRIBUTE_UPDATES.md`，职业及学习原执行证据见前两批文档；本批新增测试不冒充原 CPU 或 AS VM 执行。

| 输入 | 候选消费 | 缺失时 |
| --- | --- | --- |
| 现有 role.name / level / hp / maxHp / stats.armor | 原姓名、等级、生命条、护甲位置 | 不重算基础属性 |
| role.profession | 已核实原编号 1战士/2法师/3游侠/4僧侣/5血骑士；五职业各 9 主动/5 被动目录 | 非 1..5 不显示目录 |
| source.roleId | 必须匹配当前 role.id；原职业字段127若提供也必须匹配 | 整个原快照不消费 |
| source.attributes[77/138/139] | 原等级/XP/upgradeXp；只在三字段都已知时显示原 XP；原55级显示分子取139 | 不把试玩总XP当原字段 |
| 显式 trialProgress.value/max | 沿用调用方现有进度条显示值，标记 `existing-trial-progress` | 没有原字段且未提供时，XP留空 |
| source.attributes[145] | 原技能点位置 | 留空 |
| source.learning = [[skill_proto_id, rune_index], …] | 仅当前职业目录的实际原学习记录；index为0..3，不是掩码 | `null/unknown`，不等同空数组 |

原等级门槛锁图仅由已知原字段77与原 unlock.needlevel 比较；不拿试玩等级证明原解锁。目录和铭文可选中查看原说明，选择框表示浏览条目。没有原真实学习/装备快照时，学习按钮、可学提示、已学计数、原技能槽/快捷方案状态留空或隐藏；不把目录项装进热键。

计数上限来自原 `SkillSetting.SKILL_COUNT` 的 ABC int pool **解析值 9**（trait.value=14 是池索引，不是14项），`onShow @123..144` 乘3得27。只有已知学习数组才计算9个主动本体与27枚铭文的原 learned byte计数；未知状态不显示0。

现有本服 `level=1+floor(totalXP/60)`、狼经验奖励、已有三招热键及法师施法门禁，本候选都没有改写。原 `player_xp` 表的服务授予/升级阈值语义仍有缺口，不能把 `xp_levelup` 静态行直接用作服务器公式。

## 最小整合建议（由主任务接线）

先把 final/public 中 `assets/character-source/` 与4个 `character-source-*` 模块/样式复制到隔离包；沿用已审定 `source-ui-svg.js`。`assets/ui` 三字体和 IGM frame/entry 原素材由生成器提供，可以按SHA去重。不要把 standalone QA 模块接入实际游戏入口。

```js
import {createCharacterSourcePanels} from '/character-source-panels.mjs';
const panels = createCharacterSourcePanels({
  stop, focusGame, beforeOpen: closeOtherGameWindows,
  preview: existingAttributePreviewCallback,
});
// 放在现有 hud.character(data) 之后；显示值来自现有进度条。
const xp = document.getElementById('field-xp');
panels.update(data, {
  source: null, // 直到确有当前角色原消息缓存；不是静态目录或试玩存档。
  trialProgress: xp ? {value: xp.value, max: xp.max} : null,
});
// 人物C/原属性入口 -> panels.openAttributes()
// 技能K/原技能入口 -> panels.openSkills()
// 退出角色 -> panels.update(null)
// 输入门禁合并 panels.isOpen；关闭 -> panels.close()
```

`preview` 签名与现有 `deploy/attribute_ui.mjs` 相同：`preview(structuredClone(role), {width,height}) -> {url}`；保留现有 `renderAttributePreview` 的 THREE、源模型、灯光及像素比参数。候选按角色外观/装备/尺寸缓存预览，避免每次属性更新重渲染。

属性和技能共用此候选的一个 dialog；`beforeOpen` 只关闭任务/背包/旧热键等其它窗口，不能调用候选自身 `close()`，否则会取消当次打开。旧 `skillBook` 初始化是固定 mage-only静态目录，需由主任务在隔离适配处替换 K/菜单路由和输入门禁，避免同时打开旧、新两个窗口；不要只改原 `skills.js` 的三招数组。

## 检查与余项

5 项检查通过：所有输出校验及审定SVG接口；原PNG/图集和无损裁切；五职业目录及未附学习状态；原经验父末帧/子缩放；显式JS夹具中的未知/空学习/孤立铭文、跨角色/职业、非原等级锁定及输入不变。完整包目前约25MB。

Chrome实际检查已看到五职业不同首招、铭文详情切换、主动/被动切换；默认源学习未知，显式空学习才显示0计数；原职业图标与半条经验显示已检查。独立 QA 没有用户角色模型，正式可见整合还须主任务以实际现有模型回调复跑：当前职业、换角色、关窗/输入门禁、刷新、同账号双连接；不能据此称整个人物系统或新手MVP已完成。

尚缺原真实学习/装备快照、完整学习服务及升级授予路径、原实时伤害/消耗统计、其余属性字段与窗口导航。本批不部署、不提交、不推送，也不改任何既有存档。
