# 全部原角色选择与实际入图恢复

2026-11-15，新一批。完整目标是原客户端可选择的全部身体/职业都能正确创建、保存、进入地图、活动和恢复，不缩成只支持人类男性。本批先交全范围的原选择与玩家加载证据、统一身份链，以及最完整的人类男性实际工厂。**45项身份通过，不等于45项身体和战斗均已可玩。** 共享入口、用户存档、生产和自动续跑2均未修改。

## 原版选择范围

原 `CharacterChooseRace.swf` 的 `Window_ChooseRace.seleteCharacter`：UI种族4隐藏两个性别按钮，并调用 `Character_Race(4,0)`；其余四种族保留男女选择。原职业列表顺序与已核 native 回调为 `[1,3,2,5,4]`，分别是战士、游侠、法师、血骑士、僧侣。原中文种族名依当前原字库为人类、蒙德尔、精灵、兽人、龙人；`kartan` 是龙人的既有资源/接口键，不另造种族。

本批逐项实际执行原 `542da4 → 53d3e8`，覆盖9种身体的选种族阶段及全部45项的选职业、外观编辑阶段。阶段1的职业展示模型与阶段2的编辑 display 分开记录，未把展示服当成实际入图装备。

| 原中文种族 | UI编号 | 内部avatar编号 | 男Model | 女Model | 职业选择数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 人类 | 0 | 0 | 1 | 32 | 各5 |
| 蒙德尔 | 1 | 5 | 34 | 31 | 各5 |
| 精灵 | 2 | 1 | 33 | 2 | 各5 |
| 兽人 | 3 | 2 | 28 | 30 | 各5 |
| 龙人 | 4 | 4 | 29 | 原UI无女选项 | 5 |

这是当前构建的客户端可达选择；原账号、解锁或创建批准的真实会话仍未取得，不把静态UI选择称为原服批准。网页身份采用用户已授权的兼容接线。

## 各组合实际选择哪些资源

`tools/player_choice_matrix.py` 固定原库和原SWF，复用既有原AS方法导出，生成独立私有 `matrix-source-v1.json`。原库SHA仍为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

`tools/player_choice_world_source.py` 将每项原编辑草稿作为显式字段，沿真正玩家 `900234 → 9d4c48 → 9d64e8` 执行，并实际运行 `9d3dc8` 颜色转换。45项都返回各自身体Model；空装备输入没有带入展示衣物，所有非空部件模型唯一存在。这里的空装备、kind属性和已装载包装器是明确的兼容/研究输入，未宣称原服务器初装或GPU完成。

`tools/player_choice_inventory.py` 逐原文件检查9份身体、9份自己的动画文件、8份实际头发模型及材质真实引用。身体、头发和所引采样图均唯一存在；没有用精灵素材或NPC装备补另一个种族。该检查不等于所有新骨架/权重、动作采样和状态转换已通过。

| 身体 | 原动画范围数 | 当前资料与实际准入 |
| --- | ---: | --- |
| 人类男 | 511 | 已有原115动作、完整135属性/31皮肤骨骼组合；本批接精确五职业草稿及1992B姿势消费 |
| 人类女 | 426 | 已有独立world与最终时钟候选；原文件没有`jumplandrun`，不得借男性片段；本批未新增完整可玩准入 |
| 蒙德尔男 / 女 | 445 / 445 | 真实身体、部件、材质、自己动画范围已核；逐骨架和状态消费待接 |
| 精灵男 | 418 | 已有独立world候选；战士原草稿hair2与原hair1夹具不同，不能直接把旧候选当全部五职业 |
| 精灵女 | 441 | 现有旧地图角色仍走旧工厂；其旧外观、存档和职业技能不因此自动变成全部原状态 |
| 兽人男 / 女 | 427 / 418 | 男已有独立world候选，但原草稿hair0与旧hair1夹具不同；女仍需逐骨架/动作接线 |
| 龙人 | 414 | 真实Model29、原body/material/动画已核；逐骨架和状态消费待接 |

`run/idle/跳跃/落地/游泳`名称存在只是资源依据。缺失、重名、未通过源CPU或尚未接真实队列的动作继续拒绝，不用名称列表冒充可玩。

## 统一创建、读取、存档与快照

新独立模块 `deploy/player_choice_registry.mjs`：

```js
const registry = createPlayerChoiceRegistry(privateProfile);
registry.draft({race: uiRace, gender, profession});
registry.check(storedAvatar, profession);
createPlayerChoiceStore(ReviewedStore, registry);
playerChoiceView(record, reviewedView, registry);
```

私有 `registry-v1.json` 给出全45项精确原整数。调用方不能提交任意Model、外观、资源URL或捏造的已学技能。草稿、保存字段、职业和快照一致；旧记录没有`sourceAvatar`时不推定种族或迁移。早期人类男显式记录仍兼容原manifest SHA。

`deploy/player_choice_server.mjs` 提供 `createPlayerChoiceManager`、`stagePlayerChoiceServer`、`stagePlayerChoiceRead`、`stagePlayerChoiceStoreSource`。`admit`能力门必须由集成者显式提供；目录里有一项不代表地图可以实际使用它。服务器、角色读取和存档生成副本使用同一受信registry，不能只替换创建接口。

真实重启测试暴露并修正了旧原型约束：旧 `CharacterStore.validate` 要求每件演示装备恰好持有1件，所以新空背包直接保存会在下次启动失败。新记录首次落盘附加 `sourceInventoryPolicy='empty-compatible-container-v1'`；只对该明确标记、严格registry有效的记录允许空背包和全null装备。原基础store SHA固定为 `49a9f84c2ec5d4a0708932d2e77cc1296077e3b988d5614ef7e840e95de16eba`，生成副本的局部改动才生效。旧无标记角色仍保留原验证和物品，未修改旧文件。

空容器是网页兼容存储选择，**原初始背包未知**，不是恢复了原初装。原型基础生命/等级/经验字段的既有宿主意义也没有变成原属性。本批不授展示服、演示练习装备、职业技能或技能点。

## 人类男地图工厂

新 `tools/preview/player_choice_human.mjs`：

```js
const create = createPlayerChoiceHumanFactory({
  THREE, manifest, draftData, bodyData, binding,
  createCharacterFactory, characterAnimationState, createMaterials,
});
const actor = await create(snapshot);
actor.body; actor.apply(nextSnapshot); actor.inspect(); actor.dispose();
```

原材料分别来自冻结的 `character-human-creation-defaults-20261115/candidate-v1`、`character-human-combat-20261115/candidate-v1` 和 `character-human-queue-fast-20261115/fast-evidence-v3.json.originalBinding`。rig、mesh、材料和115动作逐项等值；依用户所选职业应用真正的发型、颜色和原部位可见性。空装备才可使用，不把职业展示服当实际衣服。

动画只消费自己演员的原CPU完整1992B/135属性包，直接写自己骨骼，不再调用旧精灵`updateCharacterAnimation`或Three混合。错误演员、错误职业、改变外观、非空装备和不完整姿势拒绝。材料由调用方注入，实例之间不可共用可变Material；未参与材质或原世界光选择。

集成仍须逐角色分派工厂，移除`quest_world.mjs`的“所有sourceAvatar都拒绝”分支，并将真实worker的species、forward、sourceAnimation和sourceHumanPose接到各快照。当前旧人类worker的空中/方向守卫保持；本批没有删掉它们，也不把地面成功称完整走跳/战斗成功。

## 已完成的隔离检查

- 45项原UI草稿与45项原玩家刷新/部件/颜色执行，9身体和8头发材质引用检查。
- 45次真实HTTP创建、读回，两个真实WS的职业/种族快照一致；关闭服务器后45份记录重新加载，两个WS恢复成功。
- 同一隔离库中的2份既有网页记录（无sourceAvatar、旧人类含演示库存）逐字段不变；3种错误空库存/策略/源avatar记录拒绝。测试没有访问用户存档。
- 人类男五职业5个独立工厂，交错应用33个冻结原CPU姿势包：135属性逐值一致，31根皮肤骨骼最大世界矩阵差约`3.81e-7`，阈值仍`.002`。这些包是原CPU夹具，未冒充该测试实时网络状态。
- Node五项检查全部通过，无跳过；Python源工具语法检查通过。
- NPC专线负责独立真实worker/地图/浏览器联验。本代理已只读独立查看其人类男与原NPC/原MissionDialog同场截图，确为人类身体，未抢其浏览器操作。完整任务、刷新和角色切换结果由该专线单列交接，不能将其单个人类浏览器结果扩大成45身体已验收。

原表、原模型、完整源输出、registry、QA角色和截图只在忽略目录 `analysis/raw/player-choice-recovery-20261115/` 及协作专线 `player-quest-interop-20261115/`，不上传GitHub。本批不连接生产、不推Git或部署；root负责共享入口整合与发布。

## 后续保持完整范围

统一身份层可承载45项，但每种自己的身体、头发、原材质、骨架、基本移动/跳游、武器/施法和技能真实状态仍需逐批实际准入。先沿本批精确草稿补人类女、精灵男与兽人男的既有候选，再补蒙德尔男女、兽人女和龙人；精灵女旧角色保持不迁移，另接显式原草稿路线。学习、装备、快捷栏是独立状态，不按等级或职业目录推定已学，也不借法师技能填空。

主线和地图工作继续并行；本批完成只表示上述证据和接口可审阅，完整“所有原允许角色都可用”目标尚未完成。
