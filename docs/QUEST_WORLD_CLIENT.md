# 普通任务实际地图客户端

2026-11-15。入口模块为 `deploy/quest_world.mjs`，父级交付层将它挂到 `/quests.html`。这是用户批准的按原数据重建的网页任务执行层，不是原服源码，也不是已恢复的新手主线202。

## 原资料与网页接线

| 内容 | 来源与使用边界 |
| --- | --- |
| 登录、选角、创建 | 现有 `createSourceEntry` 与当前生产完整原入口资源；不再使用临时营地表单。网页身份仍连接现有兼容服务器，停服账号登录保持不可用。 |
| 任务窗口 | `quest_ui.mjs`、原 MissionDialog 程序及资源，见 `QUEST_UI_COMPATIBLE.md`。接取、交回、奖励确认分别由原分支控制；HTTP 命令是明确的兼容接线。 |
| 地图 | `source-ordinary-quest-map1/manifest.json` 与 `createOrdinaryScene`，保留已核四块原地图、模型、材质和摆放，不渲染 tutorial 地图。见 `ORDINARY_QUEST_MAP.md`。 |
| NPC与收集对象 | actors-v4 原 NPC2079/spawn6598、原 static467 的11条 phase0/phasing0/manual0候选，沿原资源工厂加载。模型、骨架、纹理和节点来自原文件；Three 根朝向、原坐标到宿主场景的转换是网页适配。见 `ORDINARY_QUEST_EXECUTION.md`。 |
| 玩家 | 仅复用现有精灵女性原资源与已有动画工厂、外观/装备输入接口。尚不支持的 `sourceAvatar` 或种族/性别通过原错误窗口拒绝，不换成精灵显示。 |
| 操作 | 键盘、摇杆、鼠标取点、接近互动、拖动/滚轮相机、50ms输入与WS/HTTP绑定均是网页宿主实现，不称为原客户端最终相机、自动寻路或原协议。 |

宿主只显示已有原生命、等级、跳跃与任务控件。未接通的攻击、职业技能和背包入口隐藏；不挂通用法师三招，不混入资料、试验场或调试面板。普通任务奖励保存在独立 ledger，未送入旧的 `XP % 60` 显示，也未改写角色等级或旧经验。

## 交互和状态边界

资源入口包括 `/assets/ordinary-quests/profile.json`、`/assets/source-ordinary-quest-actors/profile.json`、`/assets/source-ordinary-quest-map1/manifest.json` 和 `/assets/source-temple-sampling/manifest.json` 的 `player` 字段。原 MissionDialog 的 program、item、quality资源复用上一批固定闭包；不在此复制或修改。

`/__quests/query`、`state`、`action` 使用当前角色凭据。接取、收集、交回必须经过服务端校验；浏览器不直接发任务状态或奖励。只在本角色 active 状态显示未收集的目标，ready/completed 不再显示目标。已完成任务禁用任务控件和NPC任务入口，不把原窗口不支持的 Status0 打开为错误页。

响应按当前角色和连接代次隔离，低 revision 不覆盖新状态。切换连接清除旧角色任务状态。原窗口操作前还会重新查询，避免旧窗口或重复点击重复领奖。点击对象只产生行走方向，抵达后才提交收集；没有传送、穿碰撞、保存坐标修改或本地加物品。

本批任务461《第一印象》使用原标题、正文、目标、对象和数字奖励；固定一次发放20028×1、同key图标映射等是父级已说明的兼容政策，不宣称原 type3/class100 保证奖励算法或原 ActionID 已恢复。培训手册的使用/技能点效果不在本批执行。

## 实际验收

隔离本地目录 `ordinary-quest-integration-20261115/local-v4`，没有导入现有用户存档。实际 Chrome 用原入口创建测试角色“任务界面甲”，在真实WS和原CPU碰撞/物理下执行：

1. 点击NPC查询并接取。
2. 点击原可见对象，真实走近并依次收集6865、6859、6863、6854。
3. 绕过中央岩石返回NPC；原交回确认后进入奖励确认，再确认完成。
4. 只读核对 ledger：completed、revision6、四条收集记录、交回库存空，奖励 XP512/钱9/Favor5/20028×1；旧等级1、旧XP0。
5. 刷新后由原快速登录/选角再次进入：位置恢复、任务按钮禁用、收集对象仍隐藏、revision及奖励不变。浏览器 warning/error 均0。

`node --check deploy/quest_world.mjs` 通过。父级另负责独立双WS、原CPU路线、持久化重启和Linux/部署验收。本批真实浏览器记录、截图与最终日志保留在忽略目录 `analysis/raw/quest-world-client-20261115/`，不上传GitHub。

## 尚未恢复

- 本范围只有四块港口地图和这一条兼容普通任务；远处原水面等未准入绘制仍可能形成可见缺口，不用新美术填补。
- 玩家/NPC沿现有材质适配器，最终原世界照明未在本客户端重新恢复；没有为本批另加灯或调亮材质。
- 视角、点击接近、拖拽、滚轮、输入传输和任务DTO是兼容宿主，不冒称原完整客户端流程。点击行走没有自动绕障路径规划，遇实体阻挡需玩家选择可行路线。
- 单独目标计数追踪器、成长系统、奖励道具使用、其他职业技能、其他种族实际入图、主线202仍不属于本批已完成内容。

本批不提交或部署，不改共享服务器、原资源、现有角色、自动续跑状态。主代理审阅后负责同步。
