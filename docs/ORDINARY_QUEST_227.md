# 普通支线227：原来源与独立资源审阅

227《抓鳄鱼》是地图1的一条独立普通支线，不是461后继。本批只取证和准备私有资源审阅；没有新任务执行器、活动演员、战斗、掉物、地图接线或GPU验收。

原 quests 的 Type2/map1 只有225、226、227、461。四者 RequiredQuest 均为字符串`0`，RequiredOneOfQuest 为空；全原表这两种前置引用没有指向或来自四者的边。表中没有 NextQuest 列。227的 RemoveQuests=`186`原样保留，不解释为前置、不执行移除。没有据此放行202或208。

## 原内容和数据边

227的 MinLevel=1、questlevel=4、RequiredRaces/Class=0、script为空、quest_filter=50；这些是原字段，filter与原批准尚未恢复。接取者是Creature872，交回者是StaticObject218。第一个目标 obj_type2/count4 对应物品50051《鳄鱼肉》，takeback/count4/type2/takeback_all1；第二目标 obj_type6/value0。原logic同时指向638/zone285，另有50051物品行。不能将logic英文旧名`Crab meat`改作执行规则。

掉物关联完整存在：loot88 的 VictimID638/VictimType1 → LootFilter63（parent51）→ Feature74 → loot_feature_items89/50051，原 Chance=1.0、CountMin/Max=1、BoxValue=1.0。本批没有运行对应过滤、随机、击杀批准或掉物生产者，不能把数值直接宣布为100%保证。原奖励只有金币15、XP1075、Favor6，无物品奖励。完整原行、中文、父链及SHA/CRC位于私有 source inventory。

## 三组原资源

| 原类型 | 默认资源与摆放 | 本批边界 |
| --- | --- | --- |
| 872 | display852→Model32/Flags4→Extra720；spawn2535，phase/phasing/manual均0；`[-15.7177,1.69369,-207.116]` | 原parts/idle CPU消费；116节点、12个base mesh；Face1/Hair1/Chest100009/Boots100012。未构造实际活动演员。 |
| 638 | display630→Model49/Flags1，crocodile.bdae；11条map1原摆放 | 1266顶点、37节点、1skin严格原float权重通过；不套人类模型或动作。 |
| 218 | hum_other_tombstone001.bdae；spawn783/phasing0，与1795/phasing2分开 | 原Type6/spell0/script空/display_filter221；display.scale0与spawn783.scaleXYZ1.40258分别保存，不当作运行期缩放已恢复。 |

7个模型/部位的几何和30张原纹理解码已完成，全部 `renderAdmitted=false`。NPC872胸衣descriptor原值是贴图短名；v2已实际执行325ce0/325e5c构造`texture/oc2_human_f_npc_villager_chest_d.tga`，该图唯一存在。原compiled sampler reflection仍未知，源sampler名是明确研究输入，未制造成功材质回调。

Model32的旧静态rest-equals-bind诊断拒绝仍保存。它不是新的原模型错误：已核与既有 female-v4-final 的同SHA body/animation、116节点TRS及12个base mesh几何完全一致，逐项复用其原CPU controller/palette/vertex证明和原float皮肤；未复制玩家衣服、外观或活动状态。四个本NPC原部件分别通过严格绑定。

墓碑原BDAE的lightMap声明为`texture/lightmap.tga`。两包选择使用既有真实res_t fresh初始化/54bc84查询，顺序upd10..15、base，首次命中upd10；cold cache/其它provider空/归档流接口均明确，不称观察到Android现场，也不套AITM实例图集。

鳄鱼的原idle请求已证，但严格动画读器拒绝：44通道中的Camera01两通道有未支持的valueType0；原ranges也不满足旧完整包读器。完整原字节和拒绝记录保持，未跳过、补动作或放宽守卫。父级另负责这条具体原格式分支。

## 当前不能放行的项目

- 原活动GUID、运行位置/属性、相位/filter/演员出现、击杀及掉物批准没有在本批补造。原script为空也不等于全部规则已恢复。
- resource-review不是完整角色合成、默认可见性、原材质完成或GPU通过。
- 独立路线代理已发现墓碑前原坡度门；其原CPU路线收据由父级另行交接，不能用当前四格矩形覆盖宣称通行。
- 227尚不能接成完整可玩支线。下一具体资源门是鳄鱼Camera01/range原格式；下一路线门是墓碑原通行路径。已交父级，不重复同一动画研究或广扫任务脚本。

## 复核入口

私有目录：`analysis/raw/ordinary-quest-neighbors-20261116/`。权威数据为`candidate-v2/source-v1.json`与`resource-review-v4/profile.json`；中间v1、review-v1/v3失败及review-v2诊断均保留，不当最终候选。

```sh
PYTHONPATH=tools .venv/bin/python tools/ordinary_quest_227_tests.py
PYTHONPATH=tools .venv/bin/python tools/ordinary_quest_227_tests.py --public-only
PYTHONPATH=tools .venv/bin/python tools/ordinary_quest_227_probe.py --output analysis/raw/ordinary-quest-neighbors-20261116/new-source-review
PYTHONPATH=tools .venv/bin/python tools/ordinary_quest_227_assets.py --source analysis/raw/ordinary-quest-neighbors-20261116/candidate-v2/source-v1.json --output analysis/raw/ordinary-quest-neighbors-20261116/new-resource-review
```

15本地检查通过；无私有来源时2通过/13跳过。复跑必须使用新目录，不能覆盖旧收据。本批没有操作浏览器、服务、Docker、存档、Git提交或部署；原数据、PNG和转换结果只在忽略目录。
