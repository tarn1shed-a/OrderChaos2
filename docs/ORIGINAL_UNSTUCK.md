# 原“脱离卡死”界面与请求边界

本批仅原资源/原代码取证与只读隔离组件。没有改生产、存档、角色位置或规则；地图 5 的运输适配由主任务单独处理。NPC 已冻结的 85 个文件保持原 SHA。本批没有恢复原服目的地选择、活动传送点、服务器结果、冷却策略或移动/战斗资格。

## 已证实的入口与布局

原中文 `GENERAL_TIPS_MAP_3_113`（2062）给出的路径是“选项 > 信息 > 帮助”。实际入口是 `IGMBottomBar.swf` 的 `_settingBtn`，并非 IGM 网格的第 13 项：IGM 构造的 `InGameMenus` 仅 0..12，遗留 `IGM_BTN_SETTING=13` 常量不能据此新增网格按钮。

`IGMBottomBar.InitMembers` 为该按钮赋 `uiname=SettingHouse`，点击 `onIgmBtnTap` 调 `EventWindowContainerSwitch(SettingHouse)`。原配置中 SettingHouse 使用 WindowStack，子页依序为 Setting、LanguageSetting、SettingScreen、SettingInfo；信息是索引 3，原图标为 `ui/icons/userinterface/option_info.png`。`WindowStack.onItemSet` 设置 IconName、Selected、IsShowNewTag，没有在侧栏设置“信息”文字；信息/帮助文字是页面标题及原按钮字段。

SettingInfo 的 `m_MainPanel.m_Help` 注册到 `onTapHelp`，切换 HELP_PANEL。其 `m_HelpPanel.mc_content.m_BreakAway._GroupBtn._Button` 注册到 `onTapBreakAway`；按钮组的 `_Disable.visible` 为 false 且回调存在时，AS 调 `Setting_BreakAway`，无游戏参数。`GetBreakAwayInfo` 调 `Setting_CanBreakAway` 并读取 Map_GetMapInfo.mapType；原战场类型禁用按钮且不显示时间提示，返回分钟数大于 0 时禁用并显示原 `%d` 提示，否则启用。帮助页每 1000 ms 更新这个信息。没有原当前状态输入，不能从静态文字直接设实际按钮资格。

原窗口局部 authored 位置：帮助按钮 `(101.25,102.35)`，BreakAway 组 `(75.8,76)`，组按钮 `(309.65,143.65)`。最后一项只是 SWF 初始摆放，原 `InitHelpPanelPos` 会执行：

```text
detail.height = detail.textHeight
groupBtn.y = detail.y + detail.height
tip.y = groupBtn.y + groupBtn.height
```

`SettingBtn.SetTitle` 另设 label.height=textHeight+10，label.y=_Hit.y+(_Hit.height-label.height)*0.5。中文 Flash textHeight 未恢复，不手填最终 Y。DefineEditText 的 bounds/font/颜色/对齐/换行/行距/原 HTML/字体声明和全部矩阵保留在私有候选 fields.*.textStyle。正文是 22px Alegreya bold、白、左对齐、换行/多行；帮助和脱离按钮标签是 26px Alegreya bold、白、居中、不换行；页面标题是 36px League Gothic。全局字体替换及浏览器文字测量属于后续技术适配，不宣称 Flash 像素一致。

WindowContainerIGM 原式将 SettingHouse 置于 `x=(screenWidth-measuredScaledWidth)/2`、`y=(screenHeight-TopBar.height-measuredScaledHeight)/2+TopBar.height`。WindowStack 动态分支以首子页的 scale*880、scale*560 测量，子页完成后设 scale=config、x=0、y=0；Tabs 原起点 `(0,0)`，TabBoard.height=565，item_3 authored `(0,222.3)`。原背景 `new_big_bg` 在 SettingInfo 窗口内是 identity。设备缩放、列表位移与全局字体仍需输入，不新增居中或响应式重排。

齿轮在底栏局部原点 `(50.5,48.65)`；去掉未知通知节点后，实际图形在组件内 `[10,6,50,46]`，底栏内 `[60.5,54.65,100.5,94.65]`（xmin,ymin,xmax,ymax）。底栏自身由 IGMContainer 配置 relativepos=(1,1) 和实际窗口测量定位；onShow 创建、onHide 销毁，完整显示事件/通知状态尚缺，不能当常驻 HUD 固定坐标。桌面 Esc 打开原设置页可明确标作宿主输入适配。

## 原生请求、确认与时间写者

原登记 `0x64faa0..64fac4` 证明 Setting_BreakAway→`0x7197e4`，Setting_CanBreakAway→`0x719970`。在隔离 CPU 中执行原 ARM64 后确认：

| 输入分支 | 原结果 |
|---|---|
| 地图键 5 | 直接调用 `0x5a4540`，没有确认，也不查地图行 |
| 其他地图，查表成功且 mapType=2 | 显示 2207“您确定要退出副本吗？”，次按钮 237“退出”，回调 `0x7984d0` |
| 该确认 result=0 | 调同一个 `0x5a4540` |
| 确认 result 非 0 | 不发请求 |
| 其他 mapType/未找到行 | 同普通请求分支 |

`0x5a4540` 实际构造 opcode `0x284`（644）、零字节 payload 的原包。此处没有目的地、坐标或 spot_id；未恢复其原符号名，不改称 C2GS_TeleportRequest。发送仍受原 socket 存在、connected、抑制字节、socket+d8 条件控制；无网络时即使没有发送，调用者仍会设置 context+6c=1，因此该标记不是服务器成功。CPU 在运输边界捕获包，没有联网。

2257 `GENERAL_BREAK_AWAY_IN_DUNGEON` 虽存在于中文表（内容仍是英文），不是这条实际确认使用的 ID；不要替换 2207。静态 `CTO_BREAK_AWAY=4` 属 ChallengeTowerOption，也不能由词义套到普通脱出。

`0x719970` 没有地图 5 特例，统一读取原本地 `break_away` 键，用 `0x3f7c48` 时钟输入与键值计算剩余分钟，原常量 1800；缺键分支写 now-1800 并返回 0。原整数算式会在 elapsed=1 时返回 29，elapsed=1800 返回 0，不能改用自创向上取整或当倒计时恢复完整。本批只执行输入夹具，没有读取/改写真实用户键值。

点击不直接写这个时间键。普通分支/确认成功后置 context+6c=1；原地图路径 `0xa34f28` 中 `0xa35938..54` 检查这个标记，非 0 时调用 `0x48b858` 并清零。`0x48b858` 使用 time()/网络同步偏差检查，才写 break_away 并 flush。已执行这一窄前缀和时间写者：flag=0 无写，flag=1 写显式时钟夹具值并清标记。未执行完整地图加载或原服务器成功反馈，当前真实时间键未知。

原 4780 文本是“战斗中或移动时无法脱离卡死。”，但已执行的 AS 点击、7197e4、719970 与 5a4540 没有证明对应移动/战斗 guard。该字符串的已查原引用是通用本地化索引构建，不是资格生产者。本批保持原状态/接口未知，不据警告文字补检查。

普通 C2GS_TeleportRequest 的原描述含 spot_id、price；C2GS_Revive 含 option、teleport_spot_id；它们与本次按钮实际构造的空请求分开。中文说明所述“最近已激活点/未激活则地图起点”是原 UI 文本，不是已恢复的原服务端选点算法。用户授权的庭院试玩落点只能作为明确试玩适配。

## 可复跑与私有素材

```sh
.venv/bin/python tools/original_unstuck_probe.py --library analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so --output analysis/raw/original-unstuck-20261114/native-validated-v2.json
.venv/bin/python tools/original_unstuck_assets.py --output analysis/raw/original-unstuck-20261114/ui-candidate-v5
.venv/bin/python tools/original_unstuck_tests.py --library analysis/raw/ghidra-mcp-20261110/input/libOrderChaos2.so --candidate analysis/raw/original-unstuck-20261114/ui-candidate-v5
.venv/bin/python tools/original_unstuck_tests.py
```

原 native SHA 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。六个 SVG 只导出原组件图形，不输出替代文字或新游戏菜单；原纹理字节、矩阵/颜色/渐变保留，通知/选中状态无活动输入时不补。字体元数据和中文表映射另存 JSON。原资源、方法转储、截图和可校验包均留 ignored 目录。候选真实 Chrome 验收与 SHA 在私有 handoff.json；不等同生产上线或完整原脱出。
