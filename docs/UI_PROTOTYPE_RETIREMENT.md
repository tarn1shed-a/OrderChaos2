# 撤下混入正式页面的原型侧栏与测试入口

2026-11-13，基线 `9d83d07`。用户指出“营地”侧栏、角色卡片与头顶名称不像原版，并误入动态碰撞验证场。本轮先撤下无原版依据的可见界面，**没有把删掉旧界面写成已还原完整角色面板或名字系统**。自动续跑保持暂停。

## 原文件核对

- 原 `ui/Flash/IGMEntrance.swf` SHA256 为 `8b97da95ba21ce835dd2833a290fe0d35a6c4b480ae7fbe4438de285f0aad051`。优化 ABC 的 `IGMEntrance.onShow`（30 字节，SHA256 `df3b257b933a91860487f8488a10286d0d7a21914b6c6348b41024ca7594e57b`）读取 `Map_GetHeroMapId`，map=5 时调用 `setShow(false)`。这是原菜单入口的隐藏条件，不能据此泛称全部角色界面在任何新手阶段都禁止。
- 原 `interface_common_2.ini` 的角色页路径是 `AttributePage.swf → BaseInfo/WindowStack.swf → IGMContainer/WindowContainerIGM.swf`。`AttributePage.swf` SHA256 为 `e7ad9fc9b9fd8c1749113c1ca2fa9e9ec00e1261bdaca282cae943a2d38bdc76`，实际创建 `Window_AttributePageInfo`（106）；含 `player_name`、`player_level`、`CharacterDisplay`、属性区与战力区。
- 原 `AttributePage.onCreate` 创建上述对象，默认进入 `STATE_CHARACTOR` 分支；切换时隐藏战力区、显示属性区。它不是“营地与冒险/击杀/狼皮/试验场/技能说明”拼接卡片。
- 原头顶名称尚未闭合。`TTFBillboardTexture` 连到通用字形图集管理器，不等于找到角色名称的完整样式；`[player_name]` 连到通用占位文本处理，也不能当字体/颜色证据。没有凭这些名字决定原字号、颜色、背景或自名显示条件。

读取器与重放：`tools/role_ui_evidence.py`、`tools/role_ui_evidence_tests.py`。完整原布局、方法指令、GhidraMCP 响应只留 `analysis/raw/role-ui-audit-20261113/`，不上传 GitHub。

## 本次正式入口的改变

- 移除“进入动态碰撞验证场”链接。旧 `/explore.html` 或带 `lab` 的地图地址跳回当前原资源登录/选角入口，不再加载旧临时表单。
- 部署服务拒绝所有 `lab` 连接请求，发生在角色创建或存档读取之前。旧缓存页面也不能借此进入测试场；无需补上传本地门、墙或测试摆放素材。
- 撤下旧“营地”按钮和整块原型侧栏，H 键不再打开它。为保持已核对脚本的 DOM 绑定，旧支持节点留在隐藏、inert 区域；不是一个可见的替代角色页。
- 暂停显示未核实的玩家/怪物头顶原型卡片，包括方框、HP 数字和“·你”后缀；原名字渲染未完成前，不换另一套自选 CSS 冒充。角色真实姓名、身份、HP 与存档不改，原目标 HUD 仍保留现有接线。

原始资源、127 份私有运行文件和角色存档不改。部署层只生成单独的页面/脚本适配；本地碰撞测试工具和资源仍留研究目录，不混入游戏入口。原角色菜单、头顶名称、完整窗口导航与原显示条件继续列为待恢复。

## 本地验收

- 53 项 Node 检查通过；8 项部署边界检查、2 项原文件证据检查通过。
- 隔离 Linux 容器实测旧地址及编码别名均返回正式入口；旧缓存的 `lab` WebSocket 请求被拒绝，拒绝前后测试存档逐字节一致。
- 浏览器实际快速登录、选角、进入地图、按 H、移动；原型侧栏不再打开，头顶卡片不可见，目标 HUD 及移动仍工作，无浏览器警告或错误。第二连接收到实际浏览器移动；原存档和原始运行目录均未作为测试环境写入目标。
- 画面、完整双连接帧与私有核查结果留在 `analysis/raw/role-ui-audit-20261113/`，不上传 GitHub。上线沿用既有可校验素材包，无需新增测试场资源。
