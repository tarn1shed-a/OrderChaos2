# 角色等级、经验与职业技能恢复

2026-11-14，独立首批候选。新增 `tools/character_progression_evidence.py`、`tools/character_skill_progression.py` 和 `tools/character_progression_tests.py`；未接公共运行接口，未改变任何角色、存档、数据库、原资源或部署。完整原表、ABC、反编译、原指令和测试输出只留忽略目录 `analysis/raw/character-progression-20261114/`。不把本批核查完成写成角色系统或新手任务 MVP 已完成。

## 当前试玩与原数据的区别

审定运行副本 `analysis/raw/showcase-20261110/running-preview` 按 `tools/local_mvp_runtime.json` 校验身份，保持只读。

| 当前宿主 | 已确认行为 | 原版边界 |
| --- | --- | --- |
| `character-store.mjs` | 强制 `level = 1 + floor(xp/60)`；新建角色等级1、累计经验0 | 这是演示存档约束，不等于原角色字段 |
| `combat.mjs` | 演示野狼每次经验30；按上述公式升级并回血 | 不是原击杀、任务经验、成长或原服升级规则 |
| `public/skills.js` | 全局固定三招；接原动作时仍从该集合生成 | 不是五职业已学习/已装备列表 |
| 法术服务器入口 | 已有仅法师可使用当前原法术的门禁 | 门禁不补其他职业招式，也不证明法师已学会三招 |
| `public/skill-book.js` | 旧候选目录只导出法师资料 | 当前静态页面不能作为原学习状态 |

没有修改这些约束，也没有用原表数字重写旧角色。现有累计 `xp`、等级、HP 与原 `xp/upgradeXp` 是否同义尚未成立，不能迁移后再倒推原公式。

## 原职业编号已与网页逐项核对

原 `mainUI.swf` 的 `Common::ASDefines` 常量与原 `AttributePage.setAttributePlayerClass` 对应如下。网页的数值通过审定 `public/professions.js` 身份和当前 `deploy/entry_ui.mjs` 创建适配再核对。

| 原玩家常量 | 原数值 | 原属性页图标 | 网页 profession |
| --- | --- | --- | --- |
| WARRIOR | 1 | warrior | 1，战士 |
| MAGE | 2 | mage | 2，法师 |
| HUNTER | 3 | ranger | 3，游侠 |
| PRIEST | 4 | monk | 4，网页旧标签“武僧” |
| DEMON_SLAYER | 5 | demonslayer | 5，血骑士 |

原创角 `Window_ChooseClass` 构造的五个图标/中文标题顺序为战士、游侠、法师、血骑士、**僧侣**；“僧侣”是本构建中文表原值，不把网页旧标签“武僧”冒充该原文。`seleteCharacter` 直接将0起始索引交给 `Character_Class`。注册 `64edc0 → 6fd340` 的原分支实际执行后得到 **[1,3,2,5,4]**，与网页创建适配一致；并非将列表索引直接加一。

原 `Hero_GetHeroInfo` 在 `6684a8..6684b4` 读取演员属性容器的 `+0x3f8`，输出 `playerClass`；原职业目录 `a0f968` 使用同一属性值匹配 `skill_unlock.needprofession`。因此这里建立的是玩家职业编号对应。没有把 NPC 的其他 class 字段或模型/种族编号接成玩家职业。静态资料仍含第6类和 ALL=7；当前五职业入口未因此扩成六职业。

原创角三个 SWF 使用压缩 CWS/标准 DoABC tag82，与大部分运行 SWF 的重排 tag300 不同。只在本批 evidence 文件内增加独立有界读取函数，读取完整方法、签名、traits 与范围；未读取或修改用户草稿 `tools/standard_abc.py`、`tools/native_character_entry.py`。

## 原目录、等级锁与学习分开

完整 `skill_unlock` 有246行，六类各41行。当前五职业各有9主动、5被动；静态第6类含空名称，未导成可玩职业。

不仅按表名称连接：本批实际执行原 `a0f968` 的目录构造、原 `1dcb628` 树迭代、稳定等级排序、等级锁和铭文需求写入。原代码按 `needprofession` 过滤，先选 `rune_id==0` 基础项，再写1至3号铭文；主动/被动使用 `skill_proto.attributes & 0x100`，不是把全部 category=0 当主动。`rune_id` 是序号，需再经 `skill_proto.runeN` 取得真正 `skill_runes.id`。

原代码的容量为9主动/5被动；同等级项保留原 unlock 行ID遍历顺序。实际五职业执行结果与独立连接器逐项对照，技能ID、顺序、四项等级和技能点要求一致。游侠有 `reqProfession=0` 的技能，部分被动也为0；只按 proto 职业字段会漏分，不能忽略 unlock 的职业约束。

等级9/10边界：原法师94的基础等级锁在10级解除，但本批新建隔离演员的四个学习字节仍全为0；其他职业与铭文也不由表值自动变成已学习。缺失原 proto 缓存时，原构造确实跳过该技能，未用同一招式补位。新建隔离演员是明确内存夹具，不代表原服务器创建角色时的默认学习状态。

`a0f0f8` 实际按缓存中非零基础字节计已学主动技能、另外按三个铭文字节计铭文；它不通过等级重新计算已学数量。独立 `inspect_skill` 仅作为待复核的数据边界：缺学习状态为 unknown，显式空夹具为未学；职业不符、未知技能、未学基础、未学铭文均不能通过。该夹具接口尚不是原消息归一化器，也不是可施法/可扣点/已装备判定。

## 原经验显示及技能槽消费

`playerinfo.tbl` 90行只有基础属性/战力，无XP字段；真正 `player_xp.tbl` 有108行、124字节步长，包含 `xp_levelup`、`xp_levelupold`、技能槽/技能点等资料。表中名称和数字不证明它是单级、累计或实际服务升级阈值。

原 `ExpBar.refresh` 消费 `Hero_GetHeroInfo` 的 `xp / upgradeXp`。原属性页另消费 `player_field_xp / player_field_upgrade_xp`；这两种UI字段命名不能与网页累计经验直接混用。`668778..668810` 的原指令切片从属性容器 `+0x450/+0x458` 读取 XP/upgradeXp，另读 `+0x268` 等级；54/55/56级的显式夹具确证仅55级把显示分子换成upgradeXp。它是显示分支，不证明满级、升级、发奖或经验重置规则。

另找到并实际执行 `a0f510`：它按当前等级查 `player_xp`，读行内 `+0x34/+0x38`（skillslot_num/passiveskillslot_num）到演员槽位字段；但结尾原指令又**无条件覆盖为4主动/2被动槽**。等级1、10、108及表中无109行时均核对；未直接把原表第一行3/2接成运行槽数，也未据此改现有热键或设计新技能栏。

当前仍未闭合 `xp_levelup/xp_levelupold` 的阈值消费者、角色属性网络更新与原服务升级重置；原表所有经验/点数都仅保留为证据。任务提交回执的xp展示字段也不是角色属性授予的证明。

## 原学习请求的执行边界

原 `SkillSetting.MessageBoxLearnSkill` 经确认后发 `Spell_LearnRune(skillId,0)`；铭文确认发所选序号。原 `6a60e4` 回调、`1d50204` 构造和 `1d50798` 数组序列化均实际执行；在传输边界记录到消息 **0x8b CMSG_LearnSkill** 的 `skill_proto_id` 和 `skill_rune`，请求不包含可选 `is_success`。

原代码拒绝缺参数和错误Flash类型，但未知技能ID/铭文99仍产生请求；true 返回只说明发送分支执行，不能当作学习成功。`Skill.proto` 另明确区分 `SMSG_SkillInit.learn_skills`、`equip_skills`、shortcut与skill_page；学会、装备、铭文选择和快捷栏不是同一状态。原接收消费者和服务端资格/扣点结果尚未接回，未从描述文本补学技能。

原 `Skill.proto` 完整描述位于 `2040bf3`、长度 `0x163d`，SHA256 `db6c1fd1ca8dfee6ce6838022db5d8f4a2b78e4591b9f1556ef460da2298189f`；所有原例程也按字节SHA固定。详见工具常量与忽略目录的完整报告。

## 复跑与冻结批次

```sh
.venv/bin/python tools/character_progression_evidence.py --library analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so --runtime analysis/raw/showcase-20261110/running-preview --output analysis/raw/character-progression-20261114/frozen-batch1
.venv/bin/python tools/character_skill_progression.py --library analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so --evidence analysis/raw/character-progression-20261114/frozen-batch1/evidence.json --output analysis/raw/character-progression-20261114/frozen-batch1
.venv/bin/python tools/character_progression_tests.py
PYTHONPATH=tools .venv/bin/python -m unittest character_progression_tests.ProgressionBoundaryTests
```

9项检查通过，其中5项使用原资源/原指令，4项可不带原资源运行。覆盖职业映射、同级排序、未知与未学区分、缺失原型、9/10级边界、55级显示分支、108/109表边界、槽数覆盖、原学习请求与错误参数；不以这些检查代替实际浏览器、双连接、刷新和完整新手路线验收。

原运行接口没有接回，所以本批没有可见界面变化或网页验收结论。主任务复核本批后再决定可见接线；下一独立分支追 `SMSG_SkillInit` 与 `CMSG_LearnSkill.is_success` 的原接收/缓存消费，再追角色XP/升级属性消息。缺原服务状态时继续保持 unknown，不默认发经验或满技能。首批SHA清单留 `analysis/raw/character-progression-20261114/frozen-batch1/SHA256.json`，供主任务独立复跑。
