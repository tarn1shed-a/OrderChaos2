# 网页脱出接线与发布边界（2026-11-14）

本批新增 `tools/unstuck_state_tests.mjs`、`tools/unstuck_delivery_tests.py` 与本文；只读核对主任务的UI/state/打包实现，没有改共享部署、原127、真实存档或执行发布。测试及SHA收据留忽略目录 `analysis/raw/character-position-restore-20261114/`。此前运输与entry串联测试的v2收据保留旧快照，位置审计见 `docs/CHARACTER_POSITION_RESTORE.md`。

## 可见入口与原版证据

桌面 **Esc是网页键鼠适配**，不声称原APK用Esc打开设置。没有新增常驻gear或挪动原底栏。打开条件由现有当前连接、其它原面板/施法窗口与UI资格提供；UI busy只控制重复点击，不能反过来把已经开始的运输操作判为原资格失败。

可见帮助与“脱离卡死”使用原SettingInfo组件、原文字、原 `m_MainPanel.m_Help` 与帮助页 `m_BreakAway` 路径。HTML定位用导出的pixel值，SVG内部坐标/文字使用twips；动态文本高度使用浏览器字体测量，不称Flash像素级排版或完整原VM。四个tab的图形不等于其它设置功能已经恢复。

原AS/ARM64边界见 `docs/ORIGINAL_UNSTUCK.md`：客户端构造0x284空payload请求，原map5与其它地图分支、确认框、剩余分钟计算已有证据。**原服务器的移动/战斗资格与脱出目的地仍未恢复**；警告文字不产生资格规则，静态地图type也不是服务端允许证明。当前网页复用用户授权的cinematic7试玩庭院目标，不冒充原首次出生/原脱出目的地。

## 时间状态与完成时点

`sourceBreakAwayMinutes`复用原719970所核整数结果。额外原CPU输入检查固定如下：

| 已过秒数 | 原返回分钟 |
| --- | --- |
| 0 | 30 |
| 1、59、60 | 29 |
| 61 | 28 |
| 1739、1740 | 1 |
| 1741、1799、1800、1801 | 0 |

缺键分支返回0并写now-1800；所核未来键+1/+59/+60/+1800均返回30，不写新值。不能改为ceil，也不能把“直到满1800秒才可点”加入这条原分钟显示逻辑。浏览器实现限定安全整数秒数域，其浏览器存储字符串验证不冒称完整原atoll解析。

当前键 `oc2.break-away.client.v1`、Date时钟与无存储时的实例内存回退，均为明确网页输入，不是找回原账号偏好或原服务冷却。存储可用时重新创建clock实例能恢复；读/写抛错时只承诺该实例内回退，不伪造跨刷新持久化。打开界面或请求发出不写返回时间。

**必须同时有已校验HTTP重置成功、匹配重连socket/generation/UUID的welcome，才调用UI.returned()。** HTTP成功本身、错误UUID、迟到旧socket、失败请求后的同身份恢复welcome均不触发时间写入；重复welcome只触发一次。31项运输/entry检查包含真实createUnstuckReturn、EventTarget异步close链与真实browserBreakAwayClock串联，存储仍是明确内存fixture。

## 位置操作与失败恢复

运输只发送当前捕获身份，目标固定cinematic7；无任意UUID/坐标输入口。原有POST `/__entry/return`继续做ID/token所有权、角色离线、完整record备份、仅替换positions.resources及flush失败回滚。指定角色的位置操作必须先备份再改，等级/经验/技能/装备/物品与其它角色不因该操作改变；全局savedAt和随后正常join的updatedAt应与位置修改本身分开验收。

浏览器先只释放捕获socket并等实际close/reset；仅对现有精确“角色仍在线”HTTP400做短暂有限重试。关闭未确认不发POST，切角/页面退出不误重连；旧socket迟到close也不能自动弹回选角或安排重连。失败只尝试一次同身份恢复，并说明请求结果可能未确认，不声称位置一定未变。

主任务已报告本地实际验收：同UUID由下层保存高度约132.35返回庭院约135.73，备份完整，非位置字段和其它角色保持，重新入场可行走，并显示原29分钟禁用提示。这是本地具体入口结果，不等于云端已发布、原服务器脱出已恢复或整图物理通过；线上发布与指定原用户角色操作仍由主任务负责。

## 样式、字体与失败边界

UI按需加载；全局localStorage getter异常在构造边界捕获，不应令正常入图失败。异步open有取消epoch，切角/退出期间close能阻止迟到showModal；部分init失败清理未完成dialog。CSS等待load/error后才打开，404只提示，不拦住地图；字体也等待load后测量。

原_Detail.leading=-6是额外段落间距，不能把字号22直接减6当作总行距16。当前包从既有原 `chineseDisplay.woff` 的head/hhea读取unitsPerEm/ascent/descent/lineGap，随公开元数据附 `browserFontMetrics`。该字体22px基线advance=30.25，再加原leading=-6得到24.25。明确保留为 **浏览器字体适配**：原引擎究竟选hhea或OS/2的完整字体布局路径未闭合，没有改变原字号、文本框、图形或字体字节。

## 打包保护与检查

`tools/unstuck_delivery.py`固定原追加基底SHA和原UI profile SHA。新增成员仅在converted/source-unstuck前缀，允许SVG/PNG与裁剪后的unstuck.json；与旧manifest成员相撞即拒绝。原127身份、旧成员内容、旧字体及其它素材保持。不是重导/替换地图或原审定运行代码。

新增公开元数据不包含完整methods、configs、igmInitializer、sourceProofs、warnings/limits等研究正文，文本字段去initialHTML/variable；保留的是当前绘图/布局/字符串/字体度量所需资料。私有基底本来所需的原CPU/运行载荷并未因“源码剥离”被删除，也不因此变成可公开的完整原代码转储。

原PNG字节不变。SVG仅把原位图的相对href改为同源 `/assets/source-unstuck/` 路径；几何、矩阵、颜色和源图形不改。测试对真实原payload逐份核对，同时验证新元数据不把全AS方法带入运行资源。

```sh
node --test tools/unstuck_state_tests.mjs
.venv/bin/python tools/unstuck_delivery_tests.py -v
node --test tools/unstuck_return_tests.mjs tools/unstuck_entry_tests.mjs
```

状态9项检查涵盖精确分钟/未来键/缺键/浏览器字符串、get/set或属性getter抛错、reload，以及真实lazy UI在全局localStorage getter失败时不触发资源/DOM加载。

打包8项检查中6项使用微小显式tar和字体解析接口夹具，验证旧成员逐字保持、manifest只追加、冲突/篡改/路径/已有输出拒绝、源码裁剪；2项可选私有检查只读核原素材、真WOFF head/hhea、基底SHA和127身份。没有为测试重打正式完整包，也没有读取角色存档。无私有资料时这2项明确skip，公共夹具不依赖原文件或字体解析包。

UI布局、真实socket/角色状态与Linux/云端运行验收仍需主任务独立完成；这些检查不把运输fixture当真实服务器授权，不把浏览器字体测量当Flash渲染，也不填缺失的原技能/成长/脱出规则。自动任务2仍PAUSED。


主任务补充（禁用层最终候选）：原_GroupBtn._Disable并非不存在，v5首批组件导出明确省略该运行状态层。独立工具`tools/original_unstuck_disabled.py`核原cid25→cid24→shape23、两级矩阵和alpha77/256，复现同viewBox的独立SVG；不改旧v5。最终包新增14份载荷（含该层），已有2877份载荷/127审定文件/53物理宿主不变。覆盖层跟随原剩余分钟/战场限制显示，HTTP请求处理中防重复点击属于网页接线。打包测试续更为9项，本地全部通过，公开7项通过/2私有跳过；旧8项快照仍在私有收据中。
