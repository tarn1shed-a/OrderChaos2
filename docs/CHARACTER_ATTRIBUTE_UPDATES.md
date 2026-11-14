# 原角色属性消息、经验与升级显示

2026-11-14，角色专责第三独立批次。新增 `tools/character_attribute_updates.py`、`tools/character_attribute_updates_tests.py` 与本文；前两批7文件保持冻结。所有原表、原代码、协议夹具和完整报告只留忽略目录 `analysis/raw/character-progression-20261114/`。未读写任何角色存档，未改原127运行文件、共享部署接口、数据库或Railway。

本批闭合的是：原网络属性字段如何落入演员属性，再被原经验显示读取。没有恢复服务端经验发放、升级资格或成长曲线。

## 真实注册与消费

| 输入 | 原注册 | 已实际执行的路径 |
| --- | --- | --- |
| ObjectCreate | 消息6，580f4c..580f5c → 589dd8 | a3f8b8构造/解析GS2C_ObjectCreate；在演员创建边界改用显式准备演员，再执行a3700c内a37958..a37af8顺序属性写入片段 |
| ObjectUpdate | 消息8，581a50..581a60 → 58b3bc | a40760原构造/解析GS2C_ObjectUpdate，按GUID找演员；a4086c复制update_values，a390a4逐mask处理属性 |

ObjectCreate.values 是 GS2C_FullObjectValue；ObjectUpdate.update_values 是 GS2C_ObjectValueUpdate。完整值按原数组下标写入，增量按原bit_masks逐位扫描、对置位项依次消费values。没有把值数组本身当成连续属性编号。

原增量消费的实际整数属性编号如下，和原UI getter的字节偏移逐项吻合：

| 属性 | 原索引 | 属性容器偏移 | 原显示/消费证据 |
| --- | --- | --- | --- |
| level | 77 / 0x4d | +0x268 | Hero_GetHeroInfo、原升级显示分支 |
| profession | 127 / 0x7f | +0x3f8 | 玩家职业显示与skill_unlock过滤 |
| xp | 138 / 0x8a | +0x450 | Hero_GetHeroInfo.xp、经验条 |
| upgradeXp | 139 / 0x8b | +0x458 | Hero_GetHeroInfo.upgradeXp、经验条分母 |
| skillPoints | 145 / 0x91 | +0x488 | Spell_GetSkillNumInfo技能点 |

a390a4使用 `actor+0x18+index*8` 访问属性；原a999d4相等检查、a9995c双副本XOR写入、a996a0整数读取都实际执行，没有用Python字典替代原属性存储。进程XOR键明确作为隔离进程夹具提供，不声称恢复了原Android进程启动状态。协议中的values为int32，原UI的整数转浮点也按有符号值消费；负值夹具没有被擅自改成经验0。

完整值片段先从GUID高32位写属性0，并跳过values[0]，之后顺序处理1..N-1。显式完整值夹具中把values[0]改为777777，原属性0仍保持该GUID高位0x120a。这里只证明所执行片段的行为，不把这一准备演员夹具称作已运行真实演员工厂或完整对象初始化。

`bit_count` 名称没有被直接解释为最高属性编号。原循环同时受mask数组长度、该字段和消费值数量约束；本批对仅更新138号属性的夹具实测bit_count为0、1、4均不写到它，5才写到。该观察不是允许网页产生任意原包的规则；运行接入仍须先取得真实原服务消息。

## 经验分母来源已经闭合到消息

接收完原属性写入后，工具再次执行668778..668810的原显示切片，读取**刚更新后的真实隔离属性单元**；不再由getter钩子代答XP数值。由此闭合：

`ObjectCreate.values[139] / ObjectUpdate的139号置位值 → 属性+0x458 → 原upgradeXp → 原经验显示分母`。

原客户端这条接收/显示路径使用消息中的原值，没有从 `player_xp.xp_levelup` 在这里重算阈值。例如：

- 只给138号属性下发99999时，XP变99999，等级仍1、upgradeXp仍2403；不会按本地60或表值自动升级。
- 只给139号属性下发12345时，原显示分母直接变12345，XP仍0，等级仍1。
- 同时下发77=2、138=17、139=4802、145=1时，四项分别落入对应单元，原经验显示为17/4802。
- 55级时原显示切片仍会把分子换成upgradeXp；原138号属性的123本身没有被改写成4567。这继续证明原显示分支和经验授予/重置是两回事。

以上都是明确消息夹具，不代表这些数值是原服应该发给某个角色的值。`player_xp` 的108行保留为原资料；本批没有证明 `xp_levelup/xp_levelupold` 是单级、累计或原服务实际阈值，也没有确定服务端升级后的XP重置规则。任务回执RewXP/完成展示同样不能代替这里的角色属性消息。

## 升级通知的真实边界

77号属性值发生变化时，a390a4原核心设置levelChanged标志；后续原分支包含升级表现、`sfx_ui_level_up`、角色虚调用和界面通知。145号属性变化另设置技能点变化标志，经验/等级字段还请求gauges脏更新。工具实际核对这些核心标志，但在表现尾部之前停止，没有为隔离演员制造原模型/菜单/音频系统。

另有旧GameServerOld.proto描述 GS2C_PlayerLevelUp（202a934，70字节），字段仅guid、level、required skill_point，没有XP/upgradeXp。它的**专用传输注册与消费handler仍未成立**。本批复跑了原构造/复制/新实例/解析/序列化的直接分支搜索，以及0x24e3340虚表地址序列搜索；所见引用均在生成的protobuf基础设施，另记录0x269ba68缺省实例的原引用。未把这些静态阴性记录升级成“证明消息绝不会使用”，也未给它杜撰消息ID。

目前已经定位并执行的真实等级属性接收是消息8的ObjectUpdate链。不能因为旧描述名叫PlayerLevelUp，就再写一个客户端发经验、扣点或升级handler。其skill_point是总量还是增量也不能按名称猜，更不能直接接成145号属性。

## 给父任务的只读UI接线建议

当前审定 `recovered-hud.js` 仍做 `xp % 60` 并把DOM `field-xp.max`设为60；`explore-map.js`也保留该演示值。当前 `deploy/attribute_ui.mjs` 再从这个DOM进度读取经验。因此不能只替换一个表或分母，随后把演示累计XP冒充原xp。

建议在父任务复核后使用独立、临时的原属性快照输入，保持既有角色记录不变：

1. 原网络输入先按GUID和原属性索引进入独立状态；只有真实收到的字段才已知。缺快照/缺字段分别保持unknown，不能默认等级1、XP0或阈值60。
2. `source_attribute_view(snapshot)` 提供只读投影，接受原索引/int32快照；不会接收现有试玩的字符串字段角色对象，也不做累计XP换算、经验发放或存档迁移。
3. 原经验显示消费已知的138/139及原显示分支；55级需保持上述分子规则。属性页不要再反读由演示HUD写出的 `field-xp` DOM值。原技能点显示只消费已知145号属性，学习/装备另接前批状态。
4. 当前无真实原属性输入时，原状态继续unknown；不要把本批测试消息当作当前角色初始值或奖励。可见接线由父任务另做实际浏览器、双连接、刷新验收，本批没有提前宣称通过。

这些建议没有执行到共享代码；现有角色等级、经验、技能、热键和原界面布局均保持。

## 复跑与冻结

```sh
.venv/bin/python tools/character_attribute_updates.py --library analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so --output analysis/raw/character-progression-20261114/attribute-batch3
.venv/bin/python tools/character_attribute_updates_tests.py
PYTHONPATH=tools .venv/bin/python -m unittest character_attribute_updates_tests.AttributeBoundaryTests
```

8项通过（5原资源/CPU、3纯边界）。覆盖原完整/增量解析、跨mask字的原索引、GUID不符、相同值不重复写、bit_count边界、原双副本属性读写、原显示切片、无本地升级、55级显示、未知投影与旧LevelUp描述的有界检索。前三批共23项，不代表完整人物系统、原服或新手任务MVP已经完成。

完整原输出与SHA清单留 `analysis/raw/character-progression-20261114/attribute-batch3/`；`SHA256.json` 同时核对前两批文件保持。仍缺原服务真实角色输入、经验授予/重置和技能成长规则、旧LevelUp专用注册、完整对象创建/表现尾部及可见接线验收。
