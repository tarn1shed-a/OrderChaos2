# 原登录与角色选择：有依据的界面与试玩接线

2026-11-13，基线 c1b27e5。用户确认：原界面连接现有试玩角色，网页身份接线明确作为适配，原账号登录不可用。自动任务 2 保持暂停。神殿下层、原出生位置和地图缺口不因本次界面工作而解决，不移动原有角色。

## 原文件和代码

| 部分 | 原始依据 | 本轮边界 |
|---|---|---|
| 登录面板 | ui.bin 中 `ui/Flash/QuickLogin.swf`，SHA 955ba936c5e98073b0ad740570683b09ded75c30a4ef7dca89fd58d70cb5034b；`Window_QuickLoginInfo` 18 | 原图形、文字字段、按钮位置、中文标题及 logo；不是恢复 Gameloft 账号服务 |
| 选角 | `CharacterChooseCharacter.swf`，SHA 3e055b2c07f6098664fadab44be0498aebcedf17d7520805d1948130c89db587；`Window_ChooseCharacter` 35、列表 15/14 | 原列表模板和开始按钮；只接已有试玩角色，不编造原服角色列表/购买槽位 |
| 共享美术 | `library.swf`，SHA d984e35a35e455d9fa15a64ee4abdd169c2db005cf8d143f4fcbf5a26f613f89 | 原矢量、渐变、图集、透明度变换和遮罩；新增 Shape2/中途样式数组读取，旧有界读器默认仍拒绝该扩展 |
| 位置 | conf.bin 的 `interface_common_2.ini`；mainUI 的 `WindowManager.resetUI`，方法 SHA 09e6cd50d37111dd0ea42b6c9e51cccea9a521ac28dc39d04f891e4812b84544 | x=relativeX×(stageWidth−windowWidth)+offsetX，y 同理；选角 InitPos 把列表靠右，不能只照设计文件的初始坐标放置 |
| 文案 | `String_General_.tbl` 的符号 ID 对应 `String_General_zh.tbl` SC 值 | 例如原开始按钮是“开始”，没有自写宣传文字；原中文 logo、字体继续来自原资料 |
| 选择和动作 | `character_list_mc.Update/onCharacterListSet/SelectChar/onNextClick`，`CheckBox.Selected` setter | 原字段包括角色名、职业图标、等级；开始调用 Character_ChooseCharStart，选择框切换原 SelectedEff 图形 |

`QuickLogin.onCreate` 绑定快速登录、Game Center、Facebook 和 Google 回调。该原包 mainUI 的 `ASDefines.isPUB` 方法直接返回 false，因此这一脚本默认分支隐藏 Google、保留 Game Center；不凭 Android 常识改成另一个分支。原账号按钮在网页保持不可用，未调用任何社交账号或 SDK。自动登录勾选状态、原运行版本响应没有取得实际会话值，未伪造。

原 ARM64 SHA 77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4 中，字符串与原注册段把 `LoginFlow_QuickLoginClick` 连到 0x746bd4、`LoginFlow_GoogleClick` 连到 0x7631d8、`Character_ChooseCharInfo` 连到 0x6ff020、`Character_ChooseCharSwitch` 连到 0x700470。这是静态注册关系，不能等同原账号认证、列表回包或入图已恢复。GhidraMCP 对 0x746bd4 未找到现有函数定义；保留错误并用原 ELF 指令核对注册段，没有把反编译失败猜成成功。

## 网页适配及保留缺口

`deploy/entry_read.mjs` 仅验证当前浏览器已有 ID/恢复凭据，按既有角色文件的 SHA256 tokenHash 规则返回名字、职业、等级；不公开其他角色、不返回凭据/位置/背包，不实例化会迁移/写入的 CharacterStore。读取页面不创建、登录或 touch 角色。选中并按“开始”后，才沿原试玩 WebSocket 接线恢复同一个 ID，继续使用其原存档位置。原始账号认证没有被网页恢复码冒充。

`deploy/entry_ui.mjs` 将原绘图与原定位规则显示为 SVG；保留原列表的五个可见模板。未恢复超过五项的原列表滚动、选角三维背景、完整角色展示、创角、买槽、删角和转服。没有凭习惯增加空角色槽、默认职业、背景画或人物镜头。SVG/Flash 的字体基线、滤镜及浏览器缩放尚未证明像素等效，不称完整 1:1。

此前的地图直达路径保留。新浏览器没有既有凭据时，原服角色列表本来无法获取，网页显示空列表且开始禁用；维护/恢复仍可在地图链接加 `entry=legacy` 使用原有试玩恢复入口。该入口只作兼容，不作为默认界面；原始创角流程尚未完成，不能承诺新设备在原界面上创建角色。

导出原资源在 `analysis/raw/login-selection-20261113/assets/`，随单独校验的私有资料包发送至指定 Railway 服务，不上传 GitHub。原运行文本、原素材和存档原位保留。包工具允许追加这一封闭目录，拒绝多余文件、符号链接和路径重名，并补齐私有构建上下文缺失的部署模块清单。

本轮实际本地/云端结果以本节后续验收和私有交接为准，不能将源码检查当作画面验收。

## 本地实际验收与可见差异

38 项 Node 检查、8 项部署边界检查、3 项原资源读取检查通过。Linux 新私有包 2716 份载荷，原 2697 份文件及 52 份 Python 宿主身份均保持，仅新增 19 份原界面导出文件。原资料包和转换前素材未覆盖。

实际浏览器完成原登录→两个已有角色列表→选择乙→开始→移动→另一窗口选择甲→同图双连接→刷新重选乙。乙刷新前后均为同名、相同位置，双端无 warning/error。浏览登录/选角页期间，隔离测试存档全字节保持；只有按开始进入并真实移动后的验收角色正常保存。绿色设计占位已按 Picture 构造器的 ImageContains 隐藏规则处理；SVG 裁剪组导致列表全隐藏的问题已通过保留原路径和矩阵、展开为直接 clipPath 几何修好，随后实际列表截图通过。没有移动源控件来掩盖裁剪错误。

| 仍然可见的问题 | 真实状态 |
|---|---|
| 旧“重返营地”和五职业下拉 | 自写原型，退出默认入口；仅在明确 legacy 兼容路径保留恢复能力，不称原款式 |
| 不同职业却共用三招 | 当前宿主 public/skills.js 定义全局三招，服务端 skill 消息使用这一演示技能集合；没有完整职业技能分配。新入口不再提供自写职业创建下拉，也不迁移已有角色职业，职业技能仍待按原资料恢复 |
| 选角背景和人物预览缺失 | 尚未把原 selection 世界和完整展示调用接通，保持空白，不用新背景/人物镜头填补；这不是完整选角画面 |
| 神殿底部、悬空/缺面观感 | 原入场位置/楼层问题仍未解决；本次不更改地图、用户坐标或镜头 |
| SVG 字体、阴影等细节 | 采用原字形/源字体尺寸与源图形，Flash 滤镜和所有栅格化细节未核实，仍不能宣称像素 1:1 |

本轮只交付已经核对的入口部分，不把“可以选择职业”或“用了原图标”算作职业已完整恢复。后续仍需按具体问题逐项取证；自动续跑不恢复。

原 League Gothic 子集不包含所有中文。浏览器接线显式回退到同包已核对的完整 Fontin，避免登录等中文标签落到系统字形；Alegreya 亦使用原完整字体。此为原字形的网页承载，仍不冒充 Flash 字体滤镜的像素等效。
