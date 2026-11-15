# 普通任务：原 MissionDialog 接兼容执行层

新增 `deploy/quest_ui.mjs`。这是用户已授权的兼容执行层窗口，不是原服务器源码或原生协议接收器。原标题、正文、目标、道具图、窗口、字体、布局和确认分支继续复用；不在游戏窗口内写 DTO、研究说明或调试控件。本模块不发奖励、不改角色存档，不强绑任务 202 或 461。

## 可集成接口

```js
import {createQuestUI} from './quest_ui.mjs';
import {createMissionProgramRuntime} from './mission_program.mjs';

const ui = await createQuestUI({
  host: gameHost,
  profile: questUIProfile,
  optionalProfile: missionOptionalProfile,
  program: originalMissionProgram,
  programFactory: createMissionProgramRuntime,
  assetBaseURL: location.href,
  optionalBaseURL: new URL('/assets/source-mission-optional/', location.href),
  fontBaseURL: '/assets/ui/',
  itemAssets,
  qualityFrames,
  query: questId => compatibleServer.queryQuest(questId),
  action: command => compatibleServer.questAction(command),
  onError: existingErrorHandler,
});
await ui.open(questId); // 从已有 NPC/任务入口调用，不创建独立营地或资料入口。
// ui.pressOK(), ui.close(), ui.dispose()
```

`programFactory` 是既有 `tools/tutorial_npc_mission_bridge_program.mjs` 的 `createMissionProgramRuntime`。它执行限定的原 AS 分支，不是完整 Flash VM；兼容层把 DTO 注入该有限解释器的具名宿主接口，不声称获得了 `Hero_GetQuestInfoNPC` 原消息。原 callback 名称只用于识别原按钮意图，真正发给兼容服务的是下面的新命令。

`query(id)` 必须返回独立玩家的规范数据：

```js
{
  origin: 'compatible-quest-layer', questId, revision,
  Status, Title, Detail, Objective, Incomplete, Completion,
  hasReward, NumGold, NumXp, NumFever, NumAdvExp,
  NumItem, NumItemOp: 0, NumItemTb, HasCollectedTbItem,
  IsFailed: false, IsInTuto: false,
  fixedItems: [{id, count, icon, quality, isGem:false, hasPromo:false, restricted:false}],
  returnItems: [{id, count, icon, quality, isGem:false, hasPromo:false, restricted:false}],
}
```

所有布尔值、数量和文本均须明确提供，不能靠缺字段生成可领取状态。`NumItem / NumItemTb` 是槽条目数；本候选各为 **1**，`count` 分别是奖励 **1** 与交回 **4**，不能把 4 填成四个槽。图标是由宿主校验的 `itemAssets[原路径] = {file或url,...来源}`；不会把物品 ID 编成假的原 ActionID。固定奖励只支持最多四条普通非宝石、非促销、无装备限制的显示候选；没有实现可选奖励、背包拖放、原 ActionID 引用注册或使用物品技能。

`action` 收到 `{type:'accept'|'complete'|'cancel',questId,revision,origin:'compatible-quest-layer'}`；接受／完成须返回 `{ok:true}`，拒绝可返回 `{ok:false,error}`。`cancel` 是兼容层关闭意图，不是原 `EventListCommon`，服务端不应因此改任务或角色。每次确定先重新查询；revision 或规范内容改变就重开新数据，不发旧动作。重复点、晚到查询、关闭／释放后结果均有生命周期守卫。服务器仍必须验证玩家、NPC、距离、任务条件、物品和幂等性；UI 不能替代这些校验。

## 原流程和实际支持范围

原 `MissionDialog` SWF SHA256：`1ca086266a17e5a12a46bcc6b5a37f1e3714dae6f66772f71256ea8161ca1236`。沿用已核的 `onEventQuestOpen / ShowQuestInfo / onOkClick / onCloseClick` 有限解释器；原 `RePosReward` 方法 SHA256 `e901c4f3ac55ed114a78e04e318ac21f28368af41858edbffb0f2c9d598a981e`，按原几何执行布局。

- 可接 5/6：原绿色“确定”，一次输出兼容 `accept`，成功才关闭。
- 原 9 且有交回条目：先显示 `Incomplete`、“需要”及原 Part3 道具槽。第一下确定只执行原 `_statusFinished` 切换，显示 `Completion`、数字奖励及 Part2 固定奖励槽；第二下才输出兼容 `complete`。无交回条目时原程序已置完成确认，不强制多点一次。
- 未完成 4：显示原未完成正文及交回条目，没有完成入口。原灰按钮图片当前缺失，不借绿色按钮或 CSS 灰图替代；保留桌面 Esc 关闭。1/2 同样不造可接按钮。
- 8/9 的原成功／失败 watermark 使用已导出的原 Icon。普通任务明确 `IsInTuto:false`；本模块拒绝教程专用控件，不扩 QTE。

标题、摘要、正文可视高、奖励板位置均用原字段和 `RePosDetail/RePosReward` 关系。中文测量、滚动、DOM 输入、原字体的浏览器栅格仍是网页技术适配，不声称 Flash 像素一致。没有增加提示卡片或改原窗口位置、大小。

## 道具槽原依据与兼容边界

`RewardBoard.svg` 已含原 `Part2.item0..3` 和 `Part3.itemOp0..3` 的 slotBG、DisplayIcon、Stack 及其矩阵。原 `ItemSlot.DataUpdate` 读取 `GetActionIDInfo.Icon → IconName`、`num → stackNum`；原 stackNum setter 在 `<=1` 时隐藏数字，`>1` 时显示。原 Quality setter 选择 `quality+1` 帧：本候选 quality1 → 原 library480 frame2（空），quality3 → frame4 → sprite472 → shape471（原蓝框）。蓝框只做原 atlas 的无损裁片，在原 1920×1920 twips 范围绘制；不手调颜色。

本轮候选 461 的原文本、物品和数字来自 NPC 代理的 `plain-quest-feasibility-20261115/candidate-manifest-v1.json`：50125 为机械齿轮×4、quality1；20028 为培训手册×1、quality3；金币9、经验512、Favor5。图标 `service_part.png / red_skull_plan.png` 是同键原 `itemdisplayinfo` 的原图。**零 displayid 的原 native fallback 未闭合，因此这项图标绑定明确是兼容适配。** 奖励行 type3/class100 的原服务器保证算法仍未知；父级本轮明确把该原表行按兼容固定一次奖励执行，不声称原算法已恢复。培训手册本模块只显示，不自动增加技能点。

## 资源闭包与验收

可直接取用的私有闭包：`analysis/raw/quest-ui-compatible-20261115/qa-v1/`，包含：

- `quest_ui.mjs`、`mission_program.mjs`、`program-v1.json`。
- `assets/source-quest/` 原 MissionDialog SVG、七份 PNG、窗口 profile；不使用 profile 内静态202作为任务状态。
- `assets/source-mission-optional/` 原 RewardBoard SVG、原数字／watermark 图及 optional profile。
- `assets/ui/` 三份原字体，`assets/source-mission-extra/` 两个原道具图与蓝框裁片，`item-assets.json / quality-frames.json`。

**正式集成排除** `index.html / qa.js / compatible-fixture.json`。它们仅是隔离验收控件和作者输入，不能成为真实任务状态。完整原 AS、图片、截图和闭包只留忽略目录，不上传 GitHub。

`tools/quest_ui_tests.mjs` 55项断言通过，含原两阶段、一次接取、并发重复点、revision竞态、晚到查询／释放、无交回直接提交、可选奖励和缺字段拒绝。实际 Chrome 依次看过接取、交回4件、第一次确认无请求、奖励确认、第二次提交关闭、未完成无提交、Esc取消；没有 console warning/error。截图位于同一私有目录的 `offer-final.png / return-items.png / reward-confirmation.png / progress.png`。浏览器发现的奖励数字越过隐藏 Part1、未完成交回分支误选已修正并实际复测。

没有真实角色、存档或服务器变更；没有部署、Docker 或自动续跑操作。父级负责兼容服务端完整执行链和最终正式场景／联机验收，这份 UI 的隔离结果不等于整条任务已可玩。
