# 重返营地

面向电脑键鼠操作的本地多人浏览器原型，以及《混沌与秩序 2》Android 3.1.3a 客户端和资源格式的研究工具。

**仓库不包含游戏资源、原版源码、账号数据或数据库。** 网页客户端、协议、服务端与转换工具为本项目编写，不连接原游戏服务器。

本项目以学习为优先目标：资源逆向沿“线索 → 假设 → 字节/调用证据 → 实验验证”推进；框架开发沿“输入 → 网络 → 服务端规则 → 存档 → 画面”理解。先读 [学习路线](docs/LEARNING.md)，区分原程序的证据与我们新写的实现。

## 第一版可玩循环

进入营地，靠近野狼，按 **空格 / F** 或地图内攻击按钮。野狼被攻击后追击并反击；参与击杀且仍存活、在线的角色各获得 **30 经验、10 金币、1 张狼皮**。累计每 60 经验升一级并恢复生命。野狼 8 秒后重新出现，倒下的玩家 4 秒后在出生点恢复。

二维营地和三维试炼都可完成此循环。服务器决定距离、冷却、伤害和奖励；客户端仅发送攻击目标，不计算掉落。

使用同一浏览器、同一服务器网址，输入原来的角色名，可恢复角色。服务器将进度写入被忽略的 `runtime/characters.json`，浏览器另存恢复凭据。离开、刷新或正常重启服务器后可以继续；不同名字是独立角色，同一角色不能同时登录两个窗口。

## 快速开始

需要 Node.js 22.13+、pnpm 11.25.0。仓库的 `.nvmrc` 和 `prototype/package.json` 声明了运行版本。

```sh
cd prototype
pnpm install --frozen-lockfile
pnpm start
```

打开 <http://localhost:8787>，两个浏览器窗口使用不同名字、相同营地编号即可测试同图移动。二维营地使用自制场景，克隆代码后无需另备资源即可运行。

安装依赖后，Mac 上也可以双击根目录的 `start.command`。端口和监听地址可通过根目录 `.env` 配置，模板见 [.env.example](.env.example)。

## 三维资源实验场

另行准备 `game-data/converted/` 后，打开 <http://localhost:8787/explore.html>。**只克隆 GitHub 仓库不会得到此目录**，资源未准备时页面会明确提示加载失败。

目前已验证的新手区域为 3×3 地块、192×192 世界单位，含39个场景摆放。可玩角色使用原版精灵女性玩家基体，支持三件现有装备换装、三款原发型及发色/肤色选择；与野狼都已接入恢复的骨骼、蒙皮和战斗片段。先前森林精灵NPC保留为本地研究资源；熊及人类男性基体仍使用静态源网格。

- WASD / 方向键移动，点击地面直线前进。
- 三维画面铺满浏览器窗口；右侧说明默认收起，按 **H** 或右上“营地”展开，Esc 收起。进入营地使用独立小窗口，背包可用 B / C 或右上按钮打开。打开面板时停止自己的移动输入，联机世界继续运行。
- 中央小地图以自己为中心、北向固定，显示队友和存活怪物，范围外点收在圆形边缘。底图由已转换高程与场景位置生成，是自制网页地图；不是恢复的原版地图美术或导航网格。
- 三维场景可右键拖动旋转镜头、滚轮缩放；屏幕不显示方向按钮，保留键盘 WASD / 方向键。
- 每房间最多 8 人，服务端同步移动；二维、三维使用独立房间空间。
- 当前有基础战斗、奖励、等级、本地角色存档，以及三维页背包和三类装备穿脱，尚无任务和完整账号系统。
- 房间与怪物是临时状态；服务器重启后怪物重置，角色进度与分场景位置保留。
- 三维角色按服务器位置变化切换行走/待机，其他玩家也能看见；每个角色独立维护骨架与动作。原始片段已按目标骨架适配，不是用整体摆动代替关节动作。
- 攻击和受击由服务器确认后播放，受击动作叠加到原攻击/移动上。死亡播放一次并保持末帧，服务器复活或重生后恢复待机；迟加入房间也能正确看到尸体。
- 三维场景按 **1** 施放火球术（30 伤害，冷却 3 秒），按 **2** 施放冰霜爆破（20 伤害，减速 2.5 秒，冷却 5 秒），也可点击地图内按钮。服务器校验目标、存活、射程与冷却，施法期间停步；伤害在确认命中时结算，目标倒地、施法者倒地或离线会中断。
- 火焰与冰霜使用原 BEFF 中的 15 个发射器、545 条曲线，恢复发射间隔/数量、寿命、颜色/透明度、UV、尺寸、旋转、速度、重力/阻尼及材质混合。按原生整数 30 FPS 曲线采样；技能数值、整体飞行路径和随机种子仍为本地实现。
- HDR 使用恢复的亮部提取、两轮水平/垂直模糊、Reinhardt 与原 LUT；雾按源区域优先级和指数公式计算。原设备质量覆盖、天气、完整光照与区域渐变尚未恢复，当前使用已验证的构造默认参数和原始区域表。
- 火球蓄力分别跟随左右手Dummy的完整变换，飞行终点与命中使用胸部挂点，冰霜使用地面+0.1挂点及原缩放。当前精灵玩家基体原生包含这些Dummy；旧森林精灵参考模型曾从该骨架适配挂点。完整原版玩家技能ID链尚未证明。
- 三维界面使用 9 张原版图集裁片、两张经技能表链确认的 96×96 原图标，以及原 Fontin / Alegreya 中文字体。两份完整字体各含 20,932 个基本汉字，当前界面汉字均已检查覆盖；稀有扩展和源字体缺字仍回退系统字体。西文数字继续使用原嵌入子集，布局与按钮行为由网页实现，不执行 SWF。美术与字体均只留在本地。
- 状态栏使用 `Gauges2` 原自身生命半弧的 50 帧掩模及加色；经验使用 `ExpBar` 原条与变换，冷却使用 40 帧原矢量扇形。战斗面板为底部左右各五槽，标注 1–0；1/2 为火球/冰霜，其余槽留空。每槽采用独立半透明圆角玻璃框，没有整条背景。中间为实时小地图，普通攻击 F/空格也可从右上按钮使用。原 `OperationPanel2` 布局保留为研究数据；新排布为网页设计。没有虚构 MP 数值或未实现的技能。
- 头像由当前玩家精灵/狼模型生成192px缩略图，不改战斗骨架；角色卡、同行者头像和装备页全身预览跟随装备更新，按装备与外观组合缓存，最多保留24组。角度、取景、灯光与头像用途均是网页适配。原PlayerGauges的Model3D槽属于选中玩家，自身Gauges2中心含小地图，原狼目标槽是精英状态图标，不能把这些冒称原版静态肖像绑定。
- 按 **B / C** 或角色卡的“背包与装备”打开窗口，Esc 关闭。使用原 `Bag` 的圆形物品槽、选中框、金币和原物品图标；桌面 8 列，手机 5 列重排。`EquipmentPage` 十个原数值槽的位置保留，三个槽适配本地主手、胸甲、鞋靴，其他槽为装饰；这不代表原版身体部位枚举已解码。
- 每个角色有三件本地新手装备：练习剑普攻 +4，布甲防御 +1/生命上限 +20，旅靴防御 +1；服务器决定穿脱、背包数量和属性。提高上限不会回血，卸下时生命最多保留到新上限；倒地或施法时不能更换。野狼伤害为 `max(1,6-防御)`，技能伤害不受练习剑影响。背包显示已有狼皮奖励；物品及装备即时存档，其他玩家收到装备/属性，但不收到背包或凭据。
- 练习剑、布甲（含原表关联的附属下装）和旅靴使用原版精灵女性装备模型、蒙皮与材质贴图，世界角色、其他玩家和装备预览随服务器穿脱结果变化；刷新、倒地和复活保留已穿装备。换装不重建骨架或重置动画；无衣甲时显示原基础内衣。身体遮挡和剑的挂载对齐为网页适配，原部位Flags与完整原引擎光照尚未恢复。原SWF行为、物品原数值/服务端协议、制作、分解、扩容及套装均未实现。40格为本地容量，原五个可见行不是原容量的证据。
- 背包中可预览三款原发型、六组发色色板与五组肤色色板，点击“保存外观”后世界角色、头像及其他玩家同步更新，刷新/重启保留。第六肤色记录为两个零值，暂不开放。两值色板的选值及 RGB24 高字节作红色为网页约定，原生色值字节顺序尚未证实。
- 玩家恢复原法线、遮罩、漫反射调色板、正反高光调色板、轮廓光与染色公式；头发使用原 0.5 alpha 裁剪阈值。原切线/副法线与蒙皮均保留。全局灯光默认值、贴图上传色彩空间尚未完整证明，网页阴影与 gamma 桥接为适配，不声称像素级复刻原作。
- 伤害、冷却、奖励与重生由服务端判定，不以动画画面计算命中。原版混合地表材质和建筑碰撞尚未恢复，可穿过场景物件。

资源单独复制到另一台 Mac、首次安装和局域网联机步骤见 [本地服务器指南](docs/LOCAL_SERVER.md)。服务器只开放转换后的资源，不开放原始导出目录或数据库。

## 目录

```text
prototype/              网页、Node 服务端、锁文件与自动测试
  game/                 角色存档层与服务端战斗规则
  public/               二维与三维客户端、自制占位场景
  test/                 WebSocket 联机与地形采样测试
tools/                  只读 APK 分析、解包、模型/地形/贴图转换工具
docs/                   GitHub 与本地服务器说明
analysis/               格式研究文字和验证结论
.github/workflows/      不依赖游戏素材的源码检查
start.command           Mac 启动入口
.env.example            可提交的配置模板
```

以下目录只在本地存在，均不上传：

```text
game-data/
  com.gameloft.android.ANMP.GloftO2HM/files/  用户提供的原始导出
  extracted/                               校验后按需解包
  converted/                               网页所需 JSON / PNG / WOFF
analysis/raw/                              完整反汇编、索引、验证输出
.venv/                                     Python 环境
runtime/                                   本地服务器角色存档，不随 Git 更新
```

## 检查代码

```sh
cd prototype
pnpm test
```

Python 工具建议使用 Python 3.12：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r tools/requirements-resources.txt
.venv/bin/python tools/resource_tests.py
.venv/bin/python tools/bdae_tests.py
.venv/bin/python tools/bdae_skin_tests.py
.venv/bin/python tools/bdae_animation_tests.py
.venv/bin/python tools/beff_effects_tests.py
.venv/bin/python tools/skill_attachments_tests.py
.venv/bin/python tools/scene_render_tests.py
.venv/bin/python tools/ui_assets_tests.py
.venv/bin/python tools/chinese_fonts_tests.py
.venv/bin/python tools/skill_icons_tests.py
.venv/bin/python tools/hud_assets_tests.py
.venv/bin/python tools/character_portraits_tests.py
.venv/bin/python tools/inventory_assets_tests.py
.venv/bin/python tools/item_icons_tests.py
.venv/bin/python tools/equipment_appearance_tests.py
.venv/bin/python tools/character_hair_tests.py
.venv/bin/python tools/character_materials_tests.py
python3 tools/art_library_tests.py
```

基础资源和动画格式测试包含自制数据，无需游戏文件；原始模型/动画集成测试在缺少本地素材时明确跳过。GitHub Actions 运行这些 Python 检查及 Node 联机、角色动画测试，不上传或下载游戏资源。

## 本地研究与转换

已获得对应本地文件时，可按需运行：

```sh
# 原始下载文件放在 game-data/com.gameloft.android.ANMP.GloftO2HM/files/
# 先只读检查一个资源条目的偏移、解压和 CRC
.venv/bin/python tools/inspect_resource_entry.py

.venv/bin/python tools/build_resource_preview.py
.venv/bin/python tools/verify_resource_preview.py
.venv/bin/python tools/terrain_convert.py --validate-all

# APK 分析额外依赖 Androguard
.venv/bin/python -m pip install -r tools/requirements-analysis.txt
.venv/bin/python tools/analyze_apk.py /path/to/game.apk

# 已确认构建的 ARM64 原生资源读取函数：静态反汇编，不执行 APK
.venv/bin/python -m pip install -r tools/requirements-native.txt
.venv/bin/python tools/analyze_native_resources.py /path/to/game.apk

# 同一构建的 BEFF 加载、曲线采样、粒子运动与材质选择证据
.venv/bin/python tools/analyze_native_effects.py /path/to/game.apk
```

转换入口按原索引提取194个包内源文件并校验长度/CRC，另按精确SHA256/长度读取两个松散原字体。生成21个模型、74张场景/特效/角色贴图、9张基础UI裁片、2张技能原图、13张HUD裁片、14张背包/装备裁片、4张物品原图、4个WOFF及各清单和地图。玩家 `models/elf-female.json` 合并23个原网格、22份蒙皮、10份材质，保留124节点与7段动作，内含 `oc2-equipment-appearance-v1`、`oc2-character-hair-v1`、`oc2-character-materials-v1`。完整中文字体来自原松散文件，不从系统字体替代转换。原始包不修改，产物留在忽略目录。当前要求 `oc2-combat-effects-v3`、`oc2-scene-render-v1` 和 `oc2-original-ui-v6`，请整体重建或同步匹配版本的 `converted/` 后刷新页面。

## 美术素材复用与同步

运行资源构建后，可打开 <http://localhost:8787/assets/library/index.html>。素材按界面、技能图标、字体、贴图、模型、地图、特效和光影分组，保留原图下载、用途引用、来源、尺寸、SHA256 与资源版本。目录位于 `game-data/converted/library/`，随整套转换资源复制，原始导出仍保留在原位置。

下列同步工具只用 Python 标准库，朋友的服务器不需要安装逆向环境：

```sh
# 开发机：整理并生成独立素材 ZIP，默认写入 game-data/transfers/
python3 tools/art_library.py export

# 目标机：git pull 后停止服务，先检查再导入；文件名替换为实际收到的 ZIP
python3 tools/art_library.py verify /path/to/oc2-assets.zip
python3 tools/art_library.py import /path/to/oc2-assets.zip
```

导入先核对每个文件的长度、SHA256、路径和清单版本，再替换 `game-data/converted/`；旧目录自动保留为相邻 `converted.backup-…`。素材包只包含转换产物，不含 APK、原资源包、原 TTF 或 `runtime/` 存档。当前整包为152个内容文件与3个素材库文件，共155个文件。GitHub 同步目录生成器、导出/导入工具与代码，素材 ZIP 和备份继续留在 Git 忽略目录。

## 文档与当前验证

- [上传 GitHub 的约定](docs/GITHUB.md)
- [学习路线：资源逆向证据与框架数据流](docs/LEARNING.md)
- [另一台 Mac 的安装与资源迁移](docs/LOCAL_SERVER.md)
- [APK 资源加载分析](analysis/APK资源加载分析.md)
- [资源解包与网页接入结果](analysis/资源解包与网页接入.md)
- [Vercel 架构调研与准备](analysis/Vercel部署准备.md)（当前以本地开服为主，尚未部署）

测试覆盖联机、服务端攻击/技能判定、延迟命中与中断、协作奖励、特效去重与释放、角色身份、重启恢复、损坏存档和写盘失败处理。三维双窗口实测施法、火球命中、冰霜减速与混合击杀奖励；真实重启本地服务后，角色经验、金币、狼皮和位置成功恢复。尚未在朋友的 Mac Pro、两台物理设备或跨公网环境验证。

当前没有附加代码许可证；仓库公开或代码再分发前需另行确定。第三方依赖和研究参考保留各自的许可与归属，原作资源不随仓库提供。
