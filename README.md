# 重返营地

以原版手机操作界面还原为目标、保留键鼠测试操作的本地多人浏览器原型，以及《混沌与秩序 2》Android 3.1.3a 客户端和资源格式的研究工具。

**仓库不包含游戏资源、原版源码、账号数据或数据库。** 网页客户端、协议、服务端与转换工具为本项目编写，不连接原游戏服务器。

本项目以学习为优先目标：资源逆向沿“线索 → 假设 → 字节/调用证据 → 实验验证”推进；框架开发沿“输入 → 网络 → 服务端规则 → 存档 → 画面”理解。当前按 [逆向目录与执行记录](docs/REVERSE_ROADMAP.md) 连续分析、接入、检查并同步；学习材料另见 [学习路线](docs/LEARNING.md)。

## 第一版可玩循环

进入营地，靠近野狼，按 **空格 / F** 或地图内攻击按钮。野狼被攻击后追击并反击；参与击杀且仍存活、在线的角色各获得 **30 经验、10 金币、1 张狼皮**。累计每 60 经验升一级并恢复生命。野狼 8 秒后重新出现，倒下的玩家 4 秒后在出生点恢复。

二维营地和三维试炼都可完成此循环。服务器决定距离、冷却、伤害和奖励；客户端仅发送攻击目标，不计算掉落。

使用同一浏览器、同一服务器网址，输入原来的角色名，可恢复角色。服务器将进度、外观与技能栏写入被忽略的 `runtime/characters.json`，浏览器另存恢复凭据。换设备时，先在三维页“营地 → 换设备继续这个角色”复制恢复码并退出，再在新设备进入窗口选择“已有角色？使用恢复码继续”。只有名字不能识别另一台设备上的原角色；同一角色不能同时登录两个窗口。恢复必须连接同一服务器，或已经迁入对应角色存档的服务器。

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

目前已验证的新手区域为 3×3 地块、192×192 世界单位，含39个场景摆放。可玩角色使用原版精灵女性玩家基体，支持五件现有装备换装、三款原发型及发色/肤色选择；与野狼都已接入恢复的骨骼、蒙皮和战斗片段。先前森林精灵NPC保留为本地研究资源；熊及人类男性基体仍使用静态源网格。

- 在左侧四分之一、下半屏区域按住拖动，浮动摇杆在第三个移动事件出现，超过原半径后移动，松手停止并隐藏；键盘 WASD / 方向键仍可使用，点击地面可直线前进。摇杆在取消触控、丢失捕获、窗口失焦、页面隐藏、窗口尺寸变化及打开面板时归零。
- 三维画面铺满浏览器窗口；右侧说明默认收起，按 **H** 或右上“营地”展开，Esc 收起。进入营地使用独立小窗口，背包可用 B / C 或右上按钮打开。打开面板时停止自己的移动输入，联机世界继续运行。
- 小地图移回左上 Gauges2 状态环内，以自己为中心、北向固定，显示队友和存活怪物，范围外点收在圆形边缘。底图由已转换高程与场景位置生成，是自制网页地图；不是恢复的原版地图美术或导航网格。
- 三维场景可在空白处触摸拖动、或右键拖动旋转镜头，滚轮缩放；摇杆与视角分别捕获自己的指针。
- 每房间最多 8 人，服务端同步移动；二维、三维使用独立房间空间。
- 当前有基础战斗、奖励、等级、本地角色存档，以及三维页背包和三类装备穿脱，尚无任务和完整账号系统。
- 房间与怪物是临时状态；服务器重启后怪物重置，角色进度与分场景位置保留。
- 三维角色按服务器位置变化切换行走/待机，其他玩家也能看见；每个角色独立维护骨架与动作。原始片段已按目标骨架适配，不是用整体摆动代替关节动作。
- 攻击和受击由服务器确认后播放，受击动作叠加到原攻击/移动上。死亡播放一次并保持末帧，服务器复活或重生后恢复待机；迟加入房间也能正确看到尸体。
- 三维法术使用原玩家链：炎爆术17/rune68（吟唱1500ms、独立CD0/公共CD600ms）、霜爆术94/rune376（无吟唱、CD20000ms/公共CD700ms），新增奥术飞弹90/rune360（引导1500ms、间隔300ms、CD4000ms）。新角色默认1/2/3，旧角色保留所有槽位和键位并将新技能放入首个空槽。三种法术目前限法师，尚无原版技能学习或MP规则。炎爆与奥术按源阶段位在移动时中断，Esc可取消；引导收招与未命中飞弹分开同步。原服确认由本地服务器代行，炎爆30伤害/350ms飞行、奥术每发8伤害/250ms命中延迟与首发在300ms的调度、射程、霜爆减速仍为明确本地规则。
- 特效包保留四个研究样例，并增加六个玩家特效，合计47个发射器和两个原半球网格节点；恢复发射间隔/数量、寿命、颜色/透明度、UV、尺寸、旋转、速度、重力/阻尼及材质混合。按原生整数 30 FPS 曲线采样；技能数值、整体飞行路径和随机种子仍为本地实现。
- HDR 使用恢复的亮部提取、两轮水平/垂直模糊、Reinhardt 与原 LUT；雾按源区域优先级和指数公式计算。原设备质量覆盖、天气、完整光照与区域渐变尚未恢复，当前使用已验证的构造默认参数和原始区域表。
- 火球蓄力分别跟随左右手Dummy的完整变换，飞行终点与命中使用胸部挂点，冰霜使用地面+0.1挂点及原缩放。当前精灵玩家基体原生包含这些Dummy；旧森林精灵参考模型曾从该骨架适配挂点。当前三种玩家技能的proto/rune/动作/可用特效链已核对。炎爆命中组0x90000023的27号地面爆炸已接入，但39号引用在现有表与APK中缺失，不能称所有命中层完全恢复。奥术手部/连线/胸部命中按130/128/131状态绑定；网页连线基向量和飞行轨迹仍为适配。
- 三维界面使用 9 张原版图集裁片、三张经技能表链确认的 96×96 原图标，以及原 Fontin / Alegreya 中文字体。两份完整字体各含 20,932 个基本汉字，当前界面汉字均已检查覆盖；稀有扩展和源字体缺字仍回退系统字体。西文数字继续使用原嵌入子集，布局与按钮行为由网页实现，不执行 SWF。美术与字体均只留在本地。
- 状态栏使用 `Gauges2` 生命半弧50帧掩模、左上实时小地图、`ExpBar` 经验条和40帧冷却扇形；右下按 `OperationPanel2` 原坐标放置普攻、四个技能槽与跳跃槽。手机摇杆保留源48px圆盘、24px半径、启动区和第三个移动事件门槛；键鼠仍用于测试。完整原触控相机分区、MP和情境交互尚未恢复。
- 默认跳跃从原生普通地面分支恢复起跳速度10、分段重力和“先位置、后速度、再切下帧重力”的顺序。服务器以50ms步长维护世界高度、墙体/天花板和触地，两端及晚加入者共享状态；松开不取消运动，走出高台会下落。移动跳接源 start/air/drop，落地接300ms `jumplandrun`。核对全部9个玩家动画包均缺少 `jump_in_place`，静止跳按原生可用性检查保留当前动作，不能声称缺失动作已恢复。原生帧长、完整碰撞标志/坡度、水中、骑乘和飞行仍未复现。
- 普攻从 `skill_combo` 普通攻击库及职业/主副手过滤恢复，接 `proto → rune → visual_state → c_animationdata → BDAE`，不再统一使用NPC权杖动作。当前空手4/5、法师持杖84起、武僧持杖424起、战士/血骑士持大剑66起，服务端选择连击分支和超时重置，其他玩家收到相同动作与技能ID。旧练习剑属于已废弃的单手类别，没有已核实的普通库入口，三维页提示卸下/换武器，不猜测双剑技能。已闭合普通步行库的换装→武器打包→当前槽→按压→执行换段→超时/UI更新链；执行中的动作和已准备的下一段槽位分开同步。按压只触发一次，未恢复按住自动普攻。全部原技能执行分支、专有网络协议及骑乘/召唤等分支仍未恢复；当前伤害、射程、700ms普攻间隔及职业创建流程保留本地玩法。
- 右上“技能”打开按原 SWF 命名显示列表恢复的法师技能资料面板：主动/被动页签，顶部横排技能，左侧说明，右侧三个铭文或两个被动槽。包含原表9主动/5被动、27铭文的中文说明、原96px图标、等级/技能点要求及基础施法数据。可翻页或用左右键选择，Esc关闭；打开时不发送移动/施法输入。当前是资料预览，学习和装配按钮不可用，不改变角色进度或现有三种战斗技能。标题栏、分页、文本排版和桌面缩放为网页适配。
- 右上“键位”打开电脑快捷键设置：点击按键后输入数字/字母，可加Shift；冲突会提示，WASD、方向键、F/空格与B/C/H保留。Esc取消改键或关闭窗口，设置自动保存到角色。当前手机界面固定按原版弧形位置摆放，暂停拖拽换位；已有十格逻辑布局和键位数据保留，炎爆/霜爆/奥术无论原先在哪一格都显示在三个已接入的手机技能槽中，继续使用各自已保存的键位。
- 技能栏布局与键位随角色自动保存到服务器，刷新、换房间、服务器重启，以及新设备恢复同一角色后会载入；当前固定的手机显示位置不受旧十格位置影响。旧版本机偏好仅在服务器尚无记录时导入一次；之后以服务器为准，旧缓存不会覆盖新设置。界面收到写盘成功回执才显示“已保存”，超时可重试；快速连续修改会依次确认并保存最新结果。它们仅发给本角色，不广播给队友，也不进入 Git。
- 头像由当前玩家精灵/狼模型生成192px缩略图，不改战斗骨架；角色卡、同行者头像和装备页全身预览跟随装备更新，按装备与外观组合缓存，最多保留24组。角度、取景、灯光与头像用途均是网页适配。原PlayerGauges的Model3D槽属于选中玩家，自身Gauges2中心含小地图（当前已移回此处，自身HUD不再用网页肖像占据地图中心），原狼目标槽是精英状态图标，不能把这些冒称原版静态肖像绑定。
- 按 **B / C** 或角色卡的“背包与装备”打开窗口，Esc 关闭。使用原 `Bag` 的圆形物品槽、选中框、金币和原物品图标；桌面 8 列，手机 5 列重排。`EquipmentPage` 十个原数值槽的位置保留，三个槽适配本地主手、胸甲、鞋靴，其他槽为装饰；这不代表原版身体部位枚举已解码。
- 每个角色有五件本地练习装备：旧练习剑、新增法杖和大剑、布甲、旅靴。法杖限法师/武僧，大剑限战士/血骑士，普攻 +4；布甲防御 +1/生命上限 +20，旅靴防御 +1；服务器决定穿脱、背包数量和属性。提高上限不会回血，卸下时生命最多保留到新上限；倒地或施法时不能更换。野狼伤害为 `max(1,6-防御)`，技能伤害不受练习剑影响。背包显示已有狼皮奖励；物品及装备即时存档，其他玩家收到装备/属性，但不收到背包或凭据。
- 练习剑、布甲（含原表关联的附属下装）和旅靴使用原版精灵女性装备模型、蒙皮与材质贴图，世界角色、其他玩家和装备预览随服务器穿脱结果变化；刷新、倒地和复活保留已穿装备。换装不重建骨架或重置动画；无衣甲时显示原基础内衣。身体遮挡和剑的挂载对齐为网页适配，原部位Flags与完整原引擎光照尚未恢复。原SWF行为、物品原数值/服务端协议、制作、分解、扩容及套装均未实现。40格为本地容量，原五个可见行不是原容量的证据。
- 背包中可预览三款原发型、六组发色色板与五组肤色色板，点击“保存外观”后世界角色、头像及其他玩家同步更新，刷新/重启保留。第六肤色记录为两个零值，暂不开放。两值色板的选值及 RGB24 高字节作红色为网页约定，原生色值字节顺序尚未证实。
- 玩家恢复原法线、遮罩、漫反射调色板、正反高光调色板、轮廓光与染色公式；头发使用原 0.5 alpha 裁剪阈值。原切线/副法线与蒙皮均保留。全局灯光默认值、贴图上传色彩空间尚未完整证明，网页阴影与 gamma 桥接为适配，不声称像素级复刻原作。
- 39个场景摆放接入16个原PHY文件的138个盒体/圆柱/多面体碰撞形状。建筑网格使用明确的BDAE几何节点绑定和完整父子变换，与碰撞保持同一世界坐标；原生前向余量0.31、抬步上限0.5用于网页静态射线/滑动判定。运行时几何注册/更新/移除、自身排除和禁用过滤已接入；完整形状标志、vehicle、原导航与混合地表材质尚未恢复；当前静态求交只是有界重建，尚非完整1:1物理引擎。伤害、冷却、奖励与重生仍由服务端判定。

动态碰撞可从“营地”中的“动态碰撞验证场”入口测试（`?room=DYNAMIC-01&lab=collision`）：两人共享原门模型及PHY，关门阻挡、开门通行。门的摆放、9单位/800ms升降与门下拒关规则为本地试验，不冒充原场景轨迹。各房间几何独立，普通场景不额外放门，试验位置不写回常规角色位置；尚未恢复移动平台载人、推挤/挤压和所有演员的原注册路径。

角色存档当前为 **v6**，读取 v1/v2/v3/v4/v5 后先保留精确原字节备份，再原子写入新格式。v4及更早角色沿用法师原型，职业设为2并新增一次法杖/大剑；v5职业与物品保持原样。旧装备、生命、外观、进度及原有技能位置/键位保留；v5升v6只在首个空槽加入奥术飞弹，旧浏览器缓存也支持同样升级。新建三维角色可选择五种职业；尚不是完整的原版职业/创建系统。恢复码沿用现有私有恢复凭据，可登录角色，请自行保管；不会放入邀请链接、素材包或 Git。

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
.venv/bin/python tools/scene_collision_tests.py
.venv/bin/python tools/native_gameplay_tests.py
.venv/bin/python tools/native_cast_tests.py
.venv/bin/python tools/native_combat_tests.py
.venv/bin/python tools/native_interaction_tests.py
.venv/bin/python tools/quest_assets_tests.py
.venv/bin/python tools/swf_ui_graphics_tests.py
.venv/bin/python tools/terrain_materials_tests.py
.venv/bin/python tools/navmesh_tests.py
.venv/bin/python tools/player_spell_effects_tests.py
.venv/bin/python tools/ui_assets_tests.py
.venv/bin/python tools/chinese_fonts_tests.py
.venv/bin/python tools/skill_icons_tests.py
.venv/bin/python tools/skill_ui_assets_tests.py
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

转换入口按原索引提取358个包内源文件并校验长度/CRC，另按精确SHA256/长度读取两个松散原字体。生成22个模型、112张场景/特效/角色/地表贴图、9张基础UI裁片、3张战斗技能原图、18张技能目录原图、4张技能面板裁片、15张HUD裁片、14张背包/装备裁片、6张物品原图、5张操作原图、4张任务状态原图、2张IGM原始完整图集、4张状态原图、61张普攻原图、4个WOFF及各清单、地图和9块源导航。玩家 `models/elf-female.json` 合并25个原网格、22份蒙皮、12份材质，保留124节点与76段动作（含55段不同普攻片段），内含 `oc2-equipment-appearance-v1`、`oc2-character-hair-v1`、`oc2-character-materials-v1`。完整中文字体来自原松散文件，不从系统字体替代转换。原始包不修改，产物留在忽略目录。当前要求 `oc2-combat-effects-v4`、`oc2-scene-render-v1` 和 `oc2-original-ui-v19`、`oc2-native-gameplay-v9` 和 `oc2-scene-collision-v2`、`oc2-source-navigation-v1`，请整体重建或同步匹配版本的 `converted/` 后刷新页面。

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

导入先核对每个文件的长度、SHA256、路径和清单版本，再替换 `game-data/converted/`；旧目录自动保留为相邻 `converted.backup-…`。素材包只包含转换产物，不含 APK、原资源包、原 TTF 或 `runtime/` 存档。整包文件数、字节数及SHA256以每次 export 输出为准；当前版本同时包含玩法和碰撞清单。GitHub 同步目录生成器、导出/导入工具与代码，素材 ZIP 和备份继续留在 Git 忽略目录。

## 文档与当前验证

- [上传 GitHub 的约定](docs/GITHUB.md)
- [学习路线：资源逆向证据与框架数据流](docs/LEARNING.md)
- [另一台 Mac 的安装与资源迁移](docs/LOCAL_SERVER.md)
- [APK 资源加载分析](analysis/APK资源加载分析.md)
- [资源解包与网页接入结果](analysis/资源解包与网页接入.md)
- [Vercel 架构调研与准备](analysis/Vercel部署准备.md)（当前以本地开服为主，尚未部署）

测试覆盖联机、服务端攻击/技能判定、延迟命中与中断、协作奖励、特效去重与释放、角色身份、重启恢复、损坏存档和写盘失败处理。三维双窗口实测施法、火球命中、冰霜减速与混合击杀奖励；真实重启本地服务后，角色经验、金币、狼皮和位置成功恢复。尚未在朋友的 Mac Pro、两台物理设备或跨公网环境验证。

当前没有附加代码许可证；仓库公开或代码再分发前需另行确定。第三方依赖和研究参考保留各自的许可与归属，原作资源不随仓库提供。


以1:1还原为目标，不自行增加玩法、界面布局或美术。右上“任务”目前仅启用源QuestListHero已核对的空列表分支：服务器明确没有已接取任务时显示原文“无可用任务！”，隐藏列表/奖励/操作区。静态任务资料和对象检查不再放入正常游戏界面。原任务接取/完成/发奖、对象动态字段和WindowContainerIGM完整外框仍待恢复，不把现有本地适配称为原版。UI19 / gameplay9需要整体更新素材包，原图/原文/表格/存档不随Git分发。

原地图地表当前还需 `maps/terrain-materials.json`（`oc2-terrain-materials-v1`）及其原纹理/遮罩；每块64个区块、9块共576个源区块绑定，网页合为12组材质绘制。此批只恢复基础贴图与UV/当前G遮罩，不称原光照贴图、建筑全材质或整图已1:1。
