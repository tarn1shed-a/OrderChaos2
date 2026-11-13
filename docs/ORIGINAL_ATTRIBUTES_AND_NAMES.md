# 原角色属性页与头顶名字

2026-11-13，基线 `13e9c17`。本轮恢复能直接指回原文件的属性页二维部分；头顶名字仍未恢复完整显示。没有重新加入旧“营地与冒险”卡片、测试场入口、研究说明或自选名牌。自动任务 2 保持暂停。

## 属性页的原文件与代码

- `ui/Flash/AttributePage.swf` SHA256 `e7ad9fc9b9fd8c1749113c1ca2fa9e9ec00e1261bdaca282cae943a2d38bdc76`。`onCreate` 创建 `Window_AttributePageInfo`（106），调用 `subInit/initString/InitCombatScore`，默认显示人物属性区，隐藏战力区；`refreshState` 负责两区切换。
- 原配置链为 `AttributePage → BaseInfo/WindowStack.swf → IGMContainer/WindowContainerIGM.swf`。供应的非动态加载分支测量 BaseInfo 各子页，父页尺寸约 `879.7467 × 571.8526`。原 ScrollPane 遮罩、内容尺寸、偏移与内部每次 0.1 的滚动规则均从显示树和方法读取，不另画一套列表。
- `InitAttribute/SetAttribute` 给属性行设置中文表标签和 `PROPERTY_BAR_ICON_*` 帧号。ABC trait 的整数是常量池索引，必须解引用，不能直接当帧号；核对后生命图标为第 5 帧，护甲为第 4 帧。导出检查逐项验证所有标签确实指向原文本节点。
- `SetAttributeValueHp` 使用原 60 帧生命条，比例至少 2%；最大生命为 0 或当前值大于最大值时比例为 1。`SetAttributeValueExp/setMcToPercent` 另有缩放逻辑。数值格式调用 `numberWithCommas`。战力标签由 `SetAttrCombatScoreString` 写 `_TxtDesc`，不是属性行的 `title_name`；浏览器切页核查发现并修正了这一区别。
- 上述图形、原矢量颜色、布局、图标、中文标签和帧数据来自原 SWF/共享库/中文表。没有手调配色、替换背景美术或加入自行设计的角色卡片；Flash 滤镜栅格化和实际运行 DPI 尚不能称为像素一致。

可重放读取器：[attribute_page.py](../tools/attribute_page.py)、[login_ui_assets.py](../tools/login_ui_assets.py)。原共享库 SHA256 `d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89`。

## 人物预览与数值的边界

原 `ModelRefresh` 先卸载模型，再取 `Hero_GetHeroInfo.SelfGuid` 调 `Model3D.initWithGuid`，并调用 `UIObjMgr_GetCameraInfo` 设置相机和目标位置。原 ARM64 的 `0x61aac8` 将这个接口注册到 `0x61d870`；`0x62217c` 明确加载 `ui/Config/character.ini`。该配置包含按种族和性别区分的相机，例如 `Elf_0/Elf_1` 的 camera 为 `[0,1,3.4]`、target 为 `[0,1,0]`。这证明参数存在，尚不能证明网页已执行原 Model3D 的投影、渲染目标、灯光和 GUID 模型接线。因此本轮不摆一个猜测角度的人像填空。

网页只读绑定现有角色姓名、等级、HP、经验与护甲；这些数值来自当前试玩服务器，**不是恢复了原服属性公式**。物理强度不借用网页 `attack` 冒充；原能量、活力、战力、其他属性没有数据就留空。未闭合的动态图标和活力购买控件不显示占位图、不执行购买。

入口沿用已有网页 C 键，B 仍打开背包；C 是键鼠适配，不宣称是原手游快捷键。没有新增可见菜单按钮：原 IGMEntrance 在 map 5 的隐藏条件仍保留。完整 WindowStack 导航未接回。窗口打开期间停止当前移动并阻止游戏输入，关闭后恢复焦点，不发送角色修改或存档请求。

## 头顶名字的实际证据和缺口

原库 SHA256 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`，通过 GhidraMCP 和原 ELF 指令交叉核对：

| 原位置 | 已确认的用途 | 不能据此补出的部分 |
| --- | --- | --- |
| `0x8fe804 → 0x91088c` | 名字绘制入口有 actor `+0x5a0` 位条件与选择/关系分支 | 当前网页没有这些原 actor 状态，不能默认全部显示 |
| `0x91088c → 0xa94798` | 姓名、`[%s]` 公会名、称号分别绘制；此调用点姓名字号参数 16、公会名 14 | 不能把参数直接当作浏览器 CSS 像素；原投影/缩放尚需核对 |
| `0xa94798 → 0x3aa394 → 0x36a83c` | 原 3D 文字/字形图集构建链，存在 name_board 资源引用 | 通用资源出现不等于所有玩家均有一块背景卡片 |
| `0x91088c` 内关系虚调用、位置和称号字段 | 颜色、位置、标题依赖原 actor 关系、模型位置和相机；公会名还读取显示偏好 | 不给网页角色擅自指定绿色/白色、固定高度、“·你”后缀或 HP 方框 |

当前头顶原型卡片继续隐藏。不是删除角色姓名或改存档，也不把查到函数入口写成名字系统已完成。后续须补齐实际玩家类型的调用条件、字号到屏幕的变换和颜色/可见输入，再接回显示。

## 验证与资料

原 SWF、完整方法指令、GhidraMCP 响应、ELF 汇编、截图、测试角色和可校验素材包仅留忽略目录 `analysis/raw/source-attribute-name-20261113/` 与 `backups/deployment/`。Git 只包含读取器、适配代码和说明；既有登录/创角 SVG 与 PNG 逐字节保持，新增两个属性相关 SVG 和配置字段。

发布包不含存档。只在隔离 Linux 测试卷测试界面、实际按键移动和第二连接；生产更新前后另作只读备份/对比，不导入本地测试角色。最终发布提交、CI、界面截图、线上存档核对和未决项以本轮私有交接记录为准。
