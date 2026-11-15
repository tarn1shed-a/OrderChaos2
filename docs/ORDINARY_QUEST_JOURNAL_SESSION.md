# 任务簿原分支与网页会话联动审查

`tools/quest_journal_state_source_tests.mjs` 只读调用父级 `deploy/quest_journal_state.mjs`，并用冻结的 WebCrypto 原指令控制器执行 onAbandon、MessageBox 按钮和 MessageBoxYesNo。accepted state、query、action、会话与通知都是明确的内存运输端口，没有 HTTP 服务器、浏览器、真实账本或角色存档。

源程序 SHA 固定 `fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a`。getQuestList/displayCurrQuest 本批仅静态指令对照，没有冒称它们或完整原窗口已经执行。原方法、实际输入 profile/正文的 SHA 和关键指令范围保存在忽略目录 `analysis/raw/ordinary-quest-journal-session-20261116/source-contract-v1.json`。

## 对照结果

原 getQuestList 读取 native numQuest/currQuestIndex，并可能使用 Adv_GetQuestIndex；原负索引分支清 currSel=-1并隐藏内容/按钮。当前兼容控制器只允许已授权且实际 accepted 的461，唯一行即当前行；空列表/已完成列表不查详情、不造确认。这是限定单任务投影，不是一般原任务选择器恢复。

原 displayCurrQuest 调 Hero_GetQuestInfoHero，消费 Title、Objective、Detail、子目标及进程内 ActionID。网页用当前同 revision 的兼容详情承接原文字/4和9目标，固定物品按已核 type9 Quality0显示，不传研究 ActionID16。显示等级2来自原 questlevel 的明确兼容映射，不使用 MinLevel0冒充。

原 MessageBoxYesNo 只在 YES=0读取当时 `_arrayQuestList[currSel].questId` 并调用 Hero_AbandonQuest；NO=1不调用。网页每次为当前唯一461创建独立原分支 VM，并用 character/epoch/revision 取消过期问题。这个固定问题目标与失效处理属于网页会话安全适配，没有改原 AS 回调。实际原模态是否阻止背后改选仍未知，不能凭显式控制称原游戏会误删别的任务。

正常原 YES 意图进入现有 `{type:'abandon',questId:461,revision,origin:'compatible-quest-layer'}` 命令端口一次；cancel 和关闭不发送放弃。已授权给A的动作可能提交，之后换角只应丢弃旧显示/返回，不是撤销该服务器动作。

## 发现与修复复验

修前 controller SHA `314cb788dc06b1b1076dd445a09b1e9d9ac884d7b8127f4f716c96d88302e12c` 存在三个宿主控制缺口，`controller-audit-v3.json` 保存12通过/3失败：

1. 确认前 readState 延迟期间收到 completed revision5，再收到旧 revision1，内部 loadDetail 未挡低 revision，列表回退为 accepted。
2. state-changed 分支 await 详情期间换角，旧 answer 返回 `{sent:false,reason:'state-changed'}`，没有返回 null。
3. 成功动作刷新通知使会话失效后，旧 answer 仍返回 A 的 `{sent:true,result}`。A动作已经授权，测试没有要求取消它，也没有向B发动作。

父级修复统一 loadDetail 低 revision 门，并在两处 awaited refresh 后复核窗口 lifetime、会话和有效性；本代理未改该共享模块。修后 SHA `d06df6047b609c4b485624777f43ab7ebcfbd0239d9f9eba41f850495a9f9a52` 的独立复跑 `controller-success-v4.json` 为15/15通过；包括真实原 YES/NO、4/9、空列表、完成、旧查询、hash准备期间换角、进度刷新、旧 revision 和两处刷新换角。公开 `--public-only` 只运行1项错误源拒绝，私有14项不运行。v1早期控制曾在空列表取 fixture status 失败，仅保留开发记录，权威修前对照为v3。

## 静态测量边界

`measurement-review-v1.json` 核对 profile 的 panel/steps 来自各命名 mc_bounds 的原局部矩形乘末级矩阵。panel height≈106.0876、maskHeight1=106，没有重复乘外层 panel 缩放；这不是 Flash 根尺寸。MessageBox 的 authoredBoundsTwips 已明确标为首帧几何/编辑文本矩形，不是初始化后根对象尺寸。导出 art 的1136×640只是 SVG参考 viewport。

原 WindowConfig 的 MessageBox isModal=1、level=0，与 ShowMsg 的用户数据5分开。实际模态可达性、字体动态测量和 renderer/GPU不在本次检查内。没有扩展202/208批准、对白或任务规则。
