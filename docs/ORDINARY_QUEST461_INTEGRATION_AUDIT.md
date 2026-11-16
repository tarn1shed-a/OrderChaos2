# 461原演出接线的独立只读审查

本批只审PR6工作树的真实 `quest_gather_server`、`quest_gather_presenter`、`quest_world`、`quest_transport`、`quest_server_overlay`，没有改这些模块，没有操作服务器、Docker、浏览器、生产或角色存档。使用实际兼容collection/ledger、冻结无SO原动作队列库与实际presenter/世界函数控制流；研究任务行、时钟和异步target/HTTP/Timer端口明确属于隔离控制，不是原服状态、原活动演员或GPU证据。

## 当前结果

权威报告是忽略目录 `analysis/raw/ordinary-quest461-integration-audit-20261116/audit-v6.json`，**11组通过，findings为空**。此前负例、混合过渡版本与精确9文件基线均保留；`audit-v1.json`为原始快照/房间阻塞复现，`audit-v4-old-world.json`为精确旧world中断负例，不会把有findings的旧审查说成修复通过。

已复现并由父级修复：

1. 原event helper的snapshotRoom以已发布tick标记，却携带HTTP之后未随tick发布的init/begin或success。下一WS重复该序列，实际receiver拒绝并进入重放。PR6新副本的publishedLength现在只在tickRoom完整drain后更新；快照仅给已发布前缀，保留原receiver重复/错序拒绝。
2. 原presenter用全房间allReady与wanted队列，一个失败目标会让另一个ready角色在丢包后永远不能恢复。新版按actor分离target/inbox/wanted/queued/cooldown，HTTP重放请求仍可合并。失败身体继续严格隐藏，未用空对象或替代模型充ready。
3. 原world收到当前self/scope的可信interrupt后，仍等到1500ms再发旧finish；错误回执invalidate把原1000ms中断画面截短。精确旧world控制复现：中断300ms后发旧finish，显示被清掉。新版仅针对已收到的匹配interrupt取消并wake旧waiter，live拒旧finish；中断画面保留到1000ms。不新增移动取消触发规则。

## 已核边界

- 实际wrapper的pending finish不发success，wrong cancel返回快照不变成interrupt。正确当前cancel才发interrupt；真实active owner替换后旧源停止。明确装备、移动、空中或sourceAvatar不满足本批legacy ElfF合同则拒绝演出，不改变已授权461执行器。
- 同一房间50ms tick在按接收者send循环之前调用一次，所有self/peer共享同一包；真实WSclose向tape释放owner。没有按接收者独立推进时钟。
- 目标尚未ready时不apply假姿势；ready后按已发布快照完整重放，与独立原receiver逐姿势一致，再连续接下一tick。
- 迟到target在invalidate后被释放；已经在飞的旧replay返回也不能恢复旧actor。实际world API在角色、generation或connected变化时拒绝旧state写回。
- 失败peer不阻塞ready actor恢复，保留原scope/序列/房间/当前body门。重复dispose/旧连接释放只管演出，不能声称取消已获授权的服务端A角色提交。

本批不称已完成真实双端HTTP/WS/GPU任务验收；该部分由父级执行。UI结束不是任务批准，原服演员状态仍未知。461限既有授权兼容执行；208不简化，227不补击杀/掉落/资格批准。

## 复跑与冻结

`node tools/ordinary_quest461_integration_audit.mjs --report=analysis/raw/ordinary-quest461-integration-audit-20261116/parent-new.json --expect-fixed`

工具支持独立 `--worktree=`、`--events-module=`、`--presenter-module=`、`--world-module=`，只读输入。`baseline-v1`和`fixed-v6`保存各自9文件原字节；实际函数私有副本只改import解析，target和HTTP端口有明确标签。`source-layout-port`只是两个已核source/binding的只读符号链接，用来执行实际server工厂的资源构造，不启动服务，不包含SO或存档。

按用户最新要求，本次回归和交接冻结后暂停，不再开启新的NPC/任务分支。
