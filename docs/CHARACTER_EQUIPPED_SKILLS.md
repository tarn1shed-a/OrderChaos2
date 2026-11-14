# 原技能装配槽首批实证（2026-11-14）

本批继续已上线热栏职业门禁之后的原状态研究，不改真实游戏、存档、服务器、原127或此前冻结文件。新文件仅 `tools/character_equipped_evidence.py`、`character_equipped_probe.py`、`character_equipped_tests.py`、`tools/preview/source-equipped-state.mjs` 和本文。完整原配置/原指令/方法/协议/执行结果留在忽略目录 `analysis/raw/character-equipped-20261114/`。

已完成：原 `GetSkillIdByOpSlot` 回调与槽 getter、原 `SkillInit` 的学习后装备续段、原装备回执、原装备/页面请求序列化均在独立内存夹具中执行。原CPU缓存输出已实际送进只读映射候选。尚未恢复完整 FreeBar/装配服务或把其它职业技能放到本服热栏。

## 三层必须分开

| 层 | 本批核对的原入口 | 实际含义 |
| --- | --- | --- |
| 静态职业目录/选中条目 | `a0f968`；`GetSkillIdByOpSlot(type=5,index)` | 选中目录中的skill ID，不是装备或学习状态 |
| 已学 | `0x4b→573b74` 的 `learn_skills`，写 `a0ef3c` | 四个真实学习字节；不由目录或装备推断 |
| 实际装配缓存 | `equip_skills` / `0xa8→578798`；`type=4`实际槽 getter | 原槽内ID与当前铭文选择，仍不证明服务施法权限 |

AS原常量解析值：`SkillSetting` 与 `SkillPassive` 的 `OPIT_SLOTSKILLSLOT=4`、`OPIT_SLOTSKILLITEM=5`、`OPIT_SLOTRUNEITEM=6`；SkillSetting另有quick-deck类型24。数值由原ABC int pool解析，不把trait的池索引当枚举。

`5f6d24..5f6d34` 将字符串 `GetSkillIdByOpSlot` 注册到 `6270ec`。回调检查两个数值参数，以(type,index)查原OpSlot对象；原 `63fd84` 容器搜索实际执行：

- type5直接读选中条目的 `+0x30`；同一index的夹具可返回目录ID90。
- type4经 `7b80e8→5ae560(0)→5b2998` 读取bank0实际槽；同一index另一个夹具返回槽内94。两者不能互代。
- 原 `5b2998` 仅接受槽1..5；值-1走原普攻链表解析，空链表返回0。本批不填入猜测的武器/普攻ID。

回调全函数执行，AS数值转换/结果写回和OpSlot虚接口的kind/index/group是明确宿主边界；没有执行完整AS VM，也没有创建实际原客户端OpSlot界面。

## 原协议与写入

原 `Skill.proto`：

| 消息/组 | 字段 |
| --- | --- |
| SMSG_SkillInit | learn_skills组1、equip_skills组4、shortcut_infos组8、必选int32 skill_page13 |
| Learn_skills | skill_proto_id2、skill_rune3 |
| Equip_skills | skill_proto_id5、skill_rune6、slot7 |
| Shortcut_infos | slot9、type10、object11、rune12 |
| CMSG_EquipSkill | skill_proto_id1、skill_rune2、slot3，optional is_success4 |
| CMSG_EquipPage | page1，optional is_success2 |

`0x4b→573b74` 在学习计数后继续执行原装备段，具体结果：

- 原init使用 `5ae560(0)`，清空/写入operation bank0。外层slot1..10进入 `5bfb64`，但writer本身只接受1..5；6..10不写。
- slot11..20经 `a100f0` 写 actor `+0x16ec` 的10个uint32；其它slot不写。本批只保留这一缓存范围，不把10格全部命名为已恢复的被动/快捷槽。
- 原 `SkillPassive.onBtnSkillSlot` 将界面索引加11；`onShow`通过 `GetSkillItemByOpSlot(type4, index+11)`取原ItemSlot对象。其显示对象后续消费仍待闭合，不能拿上面的数值getter1..5范围替代。
- `skill_rune>0`时，init按技能目录索引调用 `a10034` 写当前选择铭文字节 `active entry +0xc`；这和entry开头的四个学习字节是不同位置。
- `skill_page`经 `a115ec(...,true)`只存actor `+0x17b4`。operation-manager的bank selector在另一全局结构 `+0x30`，本批没有原依据使两者同义。夹具原消息page2仍写bank0，即使独立manager selector夹具为3。

`0xa8`在 `5736cc..5736dc` 注册到 `578798`，完整原回执解析/更新执行到返回：slot≤10走当前operation bank的 `5bfb64`，slot>10走 `a100f0`。原handler没有检查optional `is_success`；缺省/false/true三个显式夹具均写相同槽值。这只是原客户端消费事实，不代表服务会授权失败的请求。它也不验证学习或职业，跨职业ID243在法师夹具仍可进入原缓存；候选保留raw值并标记不在该职业目录，不能据此显示该职业图标或放行施法。

本批执行原请求核心与原数组serializer，拦截为记录出口、没有网络发送：

- `5c01bc`：已显式准备的槽2含90时，输出0x47 `CMSG_EquipSkill={skill_proto_id:90,skill_rune:0,slot:2}`。这是槽请求核心，不冒充完整DoAction/AS操作链或服务器许可；槽6无请求。
- `a115ec(...,false)`：输出0xac `CMSG_EquipPage={page:2}`，actor已存页面仍为0。发请求不等于页面已变更。专用入站页面回执消费者尚未建立，不能凭schema或相邻消息号补一个。

## 显式空装备组的原本地回退

原 `573f2c` 在 **已进入原SkillInit消费者且equip组数为0** 时调用 `a0f6b0`。它查询 `[test]/NumOfSkillToShow`，调用点传缺省参数6；随后原代码放入slot1=-1普攻哨兵，顺序取职业目录ID，writer最多实际写到slot5。没有把四个学习字节置为已学。

这不能在本服看到 `character.hotbar:null` 时触发。网页hotbar空配置、未接原消息的unknown、真实原SkillInit的空equip组，是三种不同输入。

配置选择已追到原启动 `4cd210 / 4cd488`：构造全局 `02528e28` 的配置manager并调用 `a78964` 加载字面路径 **`conf/game_a.conf`**。原下载包中：

- `game_a.conf`、`game.conf`没有 `NumOfSkillToShow`。
- 只有 `game_w.conf`有 `NumOfSkillToShow = 4`。它的存在不能证明Android现场选择4。
- 后续配置覆盖/实际运行环境尚未完全审定；本批配置解析/加载只静态取证，执行器将配置返回值作为显式宿主输入，分别验证4与6，不把任一样本当成现场快照。

Num=4和Num=6的原CPU夹具结果相同：`[-1, 职业前4个目录ID]`，原学习字节全0。Num=1时只有第一个技能，其余置0。五职业均复跑；这证明存在原客户端显示回退路径，**没有证明职业初始学习授予或某用户实际初始装备**。没有修改当前热栏，也没有为其它职业发图标。

## 只读映射候选

`tools/preview/source-equipped-state.mjs` 的 `projectSourceEquipped(role,catalog,snapshot)` 无DOM、存储、网络、默认装配或学习写入。它接受未来由原客户端缓存采集器提供的 `oc2-original-equipped-cache-v1`，而非网页hotbar配置：

```js
{
  format:'oc2-original-equipped-cache-v1',
  roleId, profession,
  operationBank,       // 必须显式已知，绝不由skillPage推导。
  operationBanks,      // 原manager5个bank，各自5个int32槽值。
  actorSlots11To20,    // 原actor缓存10个uint32。
  skillPage,           // 原actor原始页面字段，单独保留。
  learningRecords,     // 未知为null，已知空才是[]；(skillId,runeIndex)。
  selectedRunes,       // (skillId,当前选择铭文index)，不代替学习字节。
}
```

缺快照、角色/职业不匹配、bank未知时返回unknown且不生成槽。0保留为空，-1保留为未解析的普攻哨兵；其它raw装备ID保留，同时分别给出目录是否匹配、基础技能是否已学、所选铭文是否已学。无论这些字段为何，`castPermission`仍是null。本模块不返回/填充任何图标，不把未学装备记录删成“没有装备”。

生成证据的 `mappingSnapshot` 来自本批原CPU实际缓存，明确 `fixture:true`、私有测试role ID；测试已把它实际送入候选：90/rune2已学，404虽在11槽仍未学，page2与bank0保持独立。没有接到生产接口；当前真实用户原快照仍缺失。

## 复跑和余项

```sh
.venv/bin/python tools/character_equipped_evidence.py \
  --output analysis/raw/character-equipped-20261114/recheck
.venv/bin/python tools/character_equipped_tests.py -v
```

输出路径必须为新的指定忽略子目录。10项检查通过：3个source-free只读映射负例，7个原资源/CPU/真实输出接映射检查；涉及5职业空组、真实getter类型差异、init字段/bank分离、无效槽、未学/跨职业回执、成功flag未消费、原请求序列化、配置选择与实际原缓存映射。原资源不存在时原CPU组明确skip，不能称已执行通过。

主任务公开环境复核：原生分析依赖仅在原CPU组内导入；无原文件、无capstone/unicorn的独立Python环境实际执行3项映射检查，另7项明确跳过。首轮CI暴露的顶层原生导入错误已修正，未调整原指令探针或映射语义；旧冻结校验留档，修正后的检查文件另存主任务校验。

原执行边界：原protobuf解析、目录/学习消费、OpSlot迭代、槽写入、当前铭文map、原serializer执行。显式宿主接口包括AS数值/结果、OpSlot虚identity、已装载manager容器、配置返回值、UI对象/通知，以及 `a1314c` 后续重算。init停在573f34，**未执行其后的shortcut重建**；不称完整SkillInit恢复。

下一阶段仍缺：shortcut_infos完整消费者与类型24/QuickDeck的槽对应；SkillPassive 11/12显示对象的原消费；skill_page的原切换操作/专用回执或属性更新链；后续配置覆盖；真实原服务学习/装配快照和资格。继续取证前不接真实热栏、不把本地回退当已装备/已学发给角色。原角色、原127、共享部署、自动任务2（PAUSED）均未动。
