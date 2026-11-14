# 原技能学习消息与缓存消费

2026-11-14，角色成长第二独立批次；承接 [首批核查](CHARACTER_PROGRESSION.md)。首批四个文件保持冻结，新增 `tools/character_learning_state.py`、`tools/character_learning_state_tests.py` 与本文。未接公共运行、未读写角色存档、未发送网络包、未部署或提交Git。

本批补上首批所记的“原入站学习消息如何归一化”这一缺口；仍没有原服务器给当前角色下发的真实学习记录。下面的原指令均在新建隔离演员及显式消息夹具上执行，不代表已经知道用户角色学过什么。

## 原入站与出站分开

| 环节 | 原消息/ID | 已核查的原入口 |
| --- | --- | --- |
| 发学习请求 | 出站0x8b，CMSG_LearnSkill | 首批6a60e4、原构造与数组序列化 |
| 初始化学习/装备状态 | 入站0x4b，SMSG_SkillInit | 注册5723b4..5723c4 → 573b74 |
| 学习结果回执 | 入站0xa7，CMSG_LearnSkill | 注册573610..573620 → 5780fc |

同一个protobuf消息名不表示相同方向或相同消息ID。原学习回执没有误写成出站0x8b。注册函数572370、原接收例程及关键依赖均固定字节SHA；原库仍为SHA256 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

## 原初始化记录不是位掩码

本批实际执行573b74的长度前缀读取、原1ab7060 protobuf ParseFromArray及其原生成解析器、嵌套group复制、原职业目录/锁定构造、a0ef3c缓存写入及a0f0f8计数。没有用Python解析结果代替原protobuf解析过程。

`SMSG_SkillInit.learn_skills` 是重复group。每条含 `skill_proto_id` 和 `skill_rune`，原接收器逐条把两者交给a0ef3c；后者将 `skill_rune` 直接作为0..3的字节索引。比如原解析夹具 `(90,0),(90,2)` 得到学习字节 `[1,0,1,0]`，并非将2翻译成某个铭文位掩码。

原写入器仅搜索当前职业目录。跨职业/未知ID会被遍历跳过；重复记录写同一字节，不增加计数。主动项四字节与被动项单字节分开；主动基础/铭文计数不把被动项混入。技能页字段另经a115ec存到演员+0x17b4；本批未把它等同于已恢复装备方案。

状态之间仍然独立：

- 1级夹具收到94的学习记录后，原学习字节为1，原10级等级锁仍为1；原客户端接收器不据等级丢掉服务记录。
- 只收到90的铭文2记录时，原基础字节仍为0，计数为0基础/1铭文；不能替服务自动补学基础项。
- 收到404被动基础记录时，被动字节变为1，但原已学主动数量不增加。
- 没有原消息时状态继续unknown；只有显式收到空初始化快照时才可说“已知为空”。

## 学习结果必须来自入站回执

5780fc原构造/解析后读取可选 `is_success` 字节；缺省或false均跳过a0ef3c，保留既有学习夹具。只有true进入缓存写入。例如初始仅有90基础项时，true回执 `(90,1)` 才追加铭文1；false/缺省均不追加。即使成功回执引用其他职业或未知ID，写入器仍因当前目录无项而不改变缓存。

接收器信任服务器的成功结果；没有在这一写入分支重做等级、技能点或学习资格判断。原后续还有界面事件、表现及用于展示的点数计算，本批在已完成写入/失败跳过后停止，未冒称这些分支已恢复，也没有据此扣点。技能等级/升阶、铭文装配和原服务学习规则不从描述文本或 `reqLevel` 字段补造。

## 显式适配点与候选接口

宿主提供原FTABLE内容构建的隔离容器、原proto缓存查询接口、演员属性返回夹具、内存分配和libc。原树迭代、目录构造、锁定、protobuf解析和缓存写入均执行原指令。原目录/计数函数完成核心后跳到各自原epilogue，只跳过UI副作用；原缓存写入的UI刷新调用接记录出口。初始化在学习计数完成后停止，未执行后面的装备/shortcut恢复。学习回执在成功写入或失败跳过后停止，未执行后续UI表现。

`project_learning_records(catalog, records)` 是可供父任务复核的纯投影候选，支持unknown/已知空、逐条铭文索引、职业目录过滤和去重；不授技能、不发请求、不推断已装备或可施法。它还在宿主入口拒绝越界铭文和无依据的被动铭文编号。这个范围检查是适配边界：原a0ef3c本身直接使用服务器索引，不能把原代码缺少范围判断变成允许网页客户端传任意索引。

原协议、原服务器、网页JSON WebSocket与现有存档并未因此互通。当前网页现有角色没有来源完整的原学习快照，继续unknown；不能把本批用于检查的消息夹具当作初始化奖励或默认满技能。

## 复跑和验收

```sh
.venv/bin/python tools/character_learning_state.py --library analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so --evidence analysis/raw/character-progression-20261114/frozen-batch1/evidence.json --output analysis/raw/character-progression-20261114/learning-batch2
.venv/bin/python tools/character_learning_state_tests.py
PYTHONPATH=tools .venv/bin/python -m unittest character_learning_state_tests.LearningBoundaryTests
```

6项通过（3原资源/CPU、3纯边界检查）。覆盖原group解析、铭文序号、等级锁与学习独立、基础缺失、被动计数、跨职业/未知、重复记录、缺省/失败/成功回执和安全投影。连同首批9项共15项，但没有网页可见变化或浏览器验收结论，也不代表角色成长或完整MVP已完成。

完整输出在忽略目录 `analysis/raw/character-progression-20261114/learning-batch2/`；SHA清单 `SHA256.json` 同时核对首批保持。后续仍需原XP/升级属性更新与经验阈值/重置消费，以及原服务真实学习/技能点状态；装备槽和快捷栏接收、技能等级/升阶、战斗执行和五职业原资源接界面须另行核查。没有这些输入时，不以本地演示规则填补。
