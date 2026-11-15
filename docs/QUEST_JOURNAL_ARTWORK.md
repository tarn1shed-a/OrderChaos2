# 原任务手册与放弃确认框美术

本批恢复的是 `QuestListHero`（已接任务手册）和 `MessageBox` 的原绘图资料，以及明确指定的原按钮帧。它们不同于已经上线的 NPC 接取、交回窗口 `MissionDialog`。新增导出工具不建立任务、角色、库存或网络会话，不修改游戏入口；隔离浏览器审阅也没有连接角色存档。**这批不是已接任务手册的完整上线验收。**

原资料与审阅记录位于忽略目录 `analysis/raw/ordinary-quest-journal-art-20261116/`，权威美术导出为 `export-v4/`。完整表格、原 SWF、图页、SVG、字体与截图不上传 GitHub。

## 来源与绘制资料

|原文件|SHA256|用途|
|---|---|---|
|`ui/Flash/QuestListHero.swf`|`bd5c5a2d392dd63b872104148a74e075f8ec05c887a246015490ed16c95bf851`|根99、任务分组/行、正文/目标区、奖励列表和按钮。|
|`ui/Flash/MessageBox.swf`|`a4e85f3e7677caf292ab0f5d404f153d46d4886220c078e3667b568893b5e9c0`|原问号、正文及确定/取消按钮。|
|`ui/Flash/library.swf`|`d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89`|共享按钮、物品槽、冷却遮罩及图页绑定。|
|`ui/Flash/mainUI.swf`|`e18152cbddf51f335ad764fd57c928a990cb0846de05b2628968050e1dcbc0ac`|原 Icon/ItemSlot 构造、WindowManager 定位和 List 消费方法。|

导出保留原层级、放置矩阵、颜色变换、矢量/图页填充和裁剪路径。17份 PNG 均为原字节，包括任务目标、问号、货币、经验及20028奖励图。金币存在多个原包候选，复用此前执行过的 UI 注册、合并、查找收据，选择 `ui_icons_upd14.bin`；没有按包名或版本号自行排序。

另导出6份独立原状态片段：任务追踪提示第5帧、三个任务按钮及确认框 Yes/No 按钮第11帧。它们只是原帧的绘图资料，**导出本身不会选择游戏中的状态**。任务追踪第5帧来自 `UpdateSelAll` 的明确调用；按钮是否禁用仍须当前任务状态及原消费者决定，不能用 CSS 手工变灰代替原图。

## 冷却遮罩不是缺资源

旧绘图读取器没有收录 tag46，导致原 library 的486号记录被当成不存在。原文件实际包含71字节 `DefineMorphShape`。新增严格读取器只支持本批用到的 solid/round-line、ratio=0；不猜非零进度、另一种形态记录或缺失的插值。

原 `ItemSlot` 构造调用 `Cooldown.SetProgress(0)`，进度条因此选择第一帧。该帧保留一条原黑色底边，原范围 `[0,1699,1730,1830]` twips；不能把“0”理解成整层透明而删掉。导出将这条原路径用于裁剪，未用矩形替代源图。格式依据是 Adobe 的 SWF19 文档，链接见读取器说明。

## 浏览器审阅核对了什么

- 原放弃、确定、取消的有界 AS 分支产生对应调用意图；取消没有放弃意图，确定只记录461的放弃意图。审阅没有发送游戏协议或执行任务删除。
- 完整20028奖励槽使用本批已执行的原本地表和 ActionID 查询结果；13项原 CPU 检查由父级再次通过。这个研究实例生成的16只在该实例内有效，不能作为生产角色身份或稳定物品编号保存。
- `GetActionIDInfo` 此分支返回 `Quality=0`，不能拿源 items 的另一个字段 `quality=3` 给奖励槽染色。原20028图标、数量1及9金币/512经验/5 Favor未被省略或改写。
- 原列表包含 `item_pre0` 和 `item_post0` 备用页。直接显示全部第一帧会露出未初始化的锁、宝石及提示图案。原 `List.setItem` 根据索引是否在资料范围内设置 visible；本单页审阅的明确输入为 pre=-1、main=0、post=1、dataLength=1，备用页因此隐藏。没有删原对象或换美术。
- 原字体复用既有私有包。浏览器字体、SVG栅格化与 Flash 滤镜仍不等于原 Android 同位置像素；没有新增阴影、布局或装饰补差异。

## 尚未通过的接线门

当前审阅采用显式原 CPU 控制资料，不是在线角色的任务手册。未接通的部分包括完整初始化、长正文展开/折叠及滚动、列表选中标记绑定、原 MessageBox 完整根尺寸测量和模态事件传递，以及兼容任务账本到这些消费者的会话接线。私有确认框居中仍是审阅宿主，不能拿它当原定位已恢复。

原 `UpdateSelAll` 使用的 `CItemList.symCurrSel` 未在当前第一帧命名树中找到；不会猜匿名节点47或49就是它。原 `IsNew` 输出与 AS `isNew` 读取的大小写差异仍由独立状态批记录，未擅自改名。1/12是该客户端的显示形式，不能推出服务端可接任务数量或玩家人数上限。

这些缺口不影响已有461完整兼容流程的发布结果，也不替代208/202尚缺的原主线批准、对白和脚本效果。未将静态任务资料冒充已接取任务，未增加自编 NPC 或剧情。

## 复跑与文件规律

```sh
PYTHONPATH=tools .venv/bin/python tools/quest_journal_art.py --output analysis/raw/ordinary-quest-journal-art-20261116/new-export
PYTHONPATH=tools .venv/bin/python tools/quest_journal_art_tests.py
PYTHONPATH=tools .venv/bin/python tools/quest_journal_art_tests.py --public-only
```

新导出目录必须在忽略的 `analysis/raw` 内且不存在，工具不会覆盖旧证据。无原资源的检查为2通过/8明确跳过；本机10项通过，覆盖原图字节、原遮罩、具体状态帧、损坏偏移/未知进度拒绝及不携带任务/角色状态。

复用时依次区分：SWF authored 帧提供几何和原摆放；AS初始化决定可见、别名和滚动范围；native回调提供当前任务字段；兼容服务器持有实际任务状态。仅导出第一帧不能代替后三层。原完整目录、每个方法/资产SHA和本地截图分开保存在交接中。
