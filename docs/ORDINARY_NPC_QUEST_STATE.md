# 普通任务461的NPC状态与窗口会话

2026-11-15开始，11-16收口。本批只审已授权按原数据兼容执行的461/NPC2079，没有改共享游戏、账本、运输层、角色档案或部署；没有启动服务器、浏览器或Docker。202/208的原批准与剧情仍未补齐，本批不改变其准入。

发现并离线复现一个窗口生命周期问题：`quest_world.clearConnection()`调用`questUI.close()`，但`createQuestController.close()`在`pending`时返回false。角色A按“确定”后等待重查或操作，断线换B，旧请求失败会让`pressOK.catch`再次调用`open(old.questId)`，从当前B身份重查并打开461。既有API晚回包守卫已阻止A的state写到B，但没有使旧窗口VM失效。本批证明的是旧异步操作引起新角色窗口重开，**没有证明跨角色领奖**。

`tools/ordinary_npc_quest_lifecycle.mjs`提供最小源码候选生成器，只返回新字符串，不写共享源码：

- 新增无网络`invalidate()`：无论是否正在加载或pending，都递增epoch、清空current/VM/pending并隐藏窗口。
- 已失效的open/pressOK错误不再重开窗口或报告为新会话错误；旧action成功不向新会话返回`sent:true`。
- 正常关闭仍使用`close()`，仍是兼容取消意图，不放弃任务。正常原AS接取/两次交回分支不变。

父级已把最小修正合入实际`quest_ui.mjs`，`quest_world.clearConnection()`改为同步调用`questUI?.invalidate()`，本分支没有写共享文件。普通Esc/取消仍使用close。`open`和确认页消费draw完成后的epoch结果；fresh-state重新open后也核新epoch，过期时返回null。**invalidate不撤销已发送的服务端action**：A已经获授权的动作仍可能提交，修复的是旧回包不能重开或影响B的窗口，不能宣称回滚了A的任务。

## 原消费者与兼容映射

原`0x2b→571ce4→a4383c→49dee8`写查询缓存，实际挂起查询/记录数等条件选择详情或ListCommon；`65c458 Hero_GetQuestListNPC`从查询缓存输出标题、状态、ID及实际NPCGuid。ListCommon点行产生`EventQuestDetail(id,true,false)`，不是接取。既有证据见`TUTORIAL_NPC_INTERACTION_UI.md`与私有原profile。

| 兼容账本阶段 | 详情Status | 原列表图标 | 原详情按钮消费 |
| --- | --- | --- | --- |
| available | 6 | quest_available.png | 一次OK产生接取意图 |
| accepted | 4 | quest_unfinished.png | 原未完成正文，OK不可用 |
| ready | 9 | quest_complete.png | 先交回50125×4页，第一次OK切原完成正文/奖励页，第二次才产生complete意图 |
| completed | 0 | 不画行 | **0是兼容内部隐藏值，不宣称原QMGR完成枚举**；由completedQuestIds禁止再次打开 |

目前普通世界直接打开这一条MissionDialog，没有安装原NPCInteraction轮盘或ListCommon。不能把“单任务可操作”写成“原轮盘/列表均已接”。`quest_ui.render`会隐藏原灰按钮图；Status4逻辑确实拒绝OK，但灰按钮local bitmap13的原资源解析仍是已知显示缺口，不能补CSS假图。

头顶标记也不能直接套用列表图标。原Creature`9eb668`先调用`91ac9c`基础图标消费者，再按真实v480/自定义图/交互向量等条件处理；`af5`可覆盖为tutorial_target，`af8`索引交互记录后调用`9eb924`。后者读取的是`QuestInteractiveInfo.quest_type/quest_interact_type`，不是MissionDialog的Status。原opcode0x22活动交互消息生产者尚未恢复。新私有报告只保存这五个原函数和前沿，未制造活动GUID、头标资格或任务批准；后续若做兼容头标，必须明确为新账本呈现适配，并另核原图/布局/生命周期。

## 账本、运输及隔离核对

现有461使用原MinLevel=0、无RequiredQuest；questlevel2不是接取门。NPC2079与静态467的近距3/2是已明确的网页守卫。服务端上下文只取当前凭据对应的权威连接、地图、位置、生命和巡查标志。取消不改进度；收集四处不同源摆放后才ready；扣回与原数值奖励9/512/5及20028×1一次原子提交。物品type3/class100采用获授权的固定一次奖励兼容策略，未说原服保证算法已恢复。

本批用真实`OrdinaryQuestLedger`、`questContext`及已钉原AS程序，执行双角色内存对照：远距、死者、巡查、旧revision、重复采集/提交拒绝；另一角色可独立收集同一源摆放，进度和奖励不串；活动连接移除后拒绝上下文，恢复后状态保持。写出函数只接内存字符串，再经真实role validator重放，**不是本批实际文件重启、浏览器接近或重连验收**。此前male461实际完整路线证据仍按原交接单列，不能归功于本批。

```sh
node tools/ordinary_npc_quest_lifecycle_tests.mjs --report --baseline-replay
node tools/ordinary_npc_quest_state_tests.mjs --report
node tools/ordinary_npc_quest_lifecycle_tests.mjs --public-only
node tools/ordinary_npc_quest_state_tests.mjs --public-only
```

私有证据在`analysis/raw/ordinary-npc-quest-20261115/`。旧候选66断言/7场景及状态57断言已保存`checkpoint-v1`，不覆盖旧基线。新测试**直接import实际deploy控制器**，不再对修好的源码二次stage：公共模式以明确的host lifecycle VM fixture执行108断言/11场景，不冒称原AS；有原程序时再执行相同场景，并可重放旧基线的两个竞态，共224断言。初次查询/验证查询/操作成功与失败/初次绘制/确认页绘制/错误恢复绘制/fresh-state重查和绘制都覆盖会话切换。render/fonts等待是可控Promise接口，不是浏览器字体或DOM实测。原数据状态测试直接接实际控制器，57断言/4阶段；公开缺原表时明确跳过。没有本批浏览器、服务器、Android/Flash现场或正式发布声明。

## 父级实际路线与发布集成（2026-11-16）

父级已在独立本地原地图中用一次性龙人角色走完461：实际移动到四处不同原齿轮摆放，追踪切换为“与工程师交谈”，返回原NPC；第一确认仅显示原完成正文与9/512/5奖励，账本仍ready且奖励为0；第二确认后才扣回四件并记入原数值与20028×1。刷新、经原登录/滚动选角列表重进后仍completed，未重复发奖。其余八个一次性角色任务为空、奖励为0；没有操作现有玩家存档。画面/控制台/独立账本核对保存在忽略的`analysis/raw/player-choice-delivery-20261115/browser-parent-v2/`，其中角色素材路线是未发布候选，不能因此宣称九身体已正式可玩。一次早期旧进程断线原因未证实，后续带只读观察的完整路线通过；不把该断线归因于本生命周期缺陷。

公开CI直接检查真实`deploy/quest_ui.mjs`的108条host生命周期断言。私有原AS存在时，相同11场景另运行一次，合计216条；原任务状态另57条。旧基线回放为可选附加8条，不混入未执行的统计。私有状态检查需要原列表reader；公开缺原资料时明确跳过，不制造原表。此次产品改动只让断线/换角使旧窗口和异步回调失效；不改变任务规则、画面、原AS确认顺序或已提交动作。原主线208/202缺口与自动续跑暂停保持。Linux、Git、CI和Railway最终发布情况以本批忽略目录的收据为准，不能把源码提交当作上线完成。
