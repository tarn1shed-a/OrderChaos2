# 原选角、创角背景：独立静态候选

本批整理的是原包 `selection.bin` 中的 **map7 selection 场景**，不是把新手地图当作选角背景。候选尚未接入正式入口；没有改服务器、现有角色、原地图、光源或共享发布脚本。原资源和完整明细仅保存在忽略目录。

已有原文件和原代码依据的部分：

| 内容 | 原始依据 | 本批结果 |
|---|---|---|
| 地图与尺寸 | `world/selection.wld`，AWLD 配置 `[3,3,1]`；原 `0x8fd270–0x8fd298` 容器复制、`0xa61bdc` / `0xa612b4` 尺寸消费者 | 原网格跨度 64，未沿用 tutorial 容器 |
| 场景配置 | `conf/game.conf`、`game_a.conf`、`game_w.conf` 的 `[splash]` | 三份均指向 map7；`sceneCenter`、相机、角色配置分别保留，不将相机当作玩家出生点 |
| 地形与遮罩 | `world/selection/terrain/*.trn`、`layers/*.msk`；既有原 ATIL 读取与材质扫描工具 | 25 块原地形、原高度/法线/RGB565/五层索引/遮罩；未焊接、补面或改高度 |
| 建筑与草木 | `world/selection/items/*.itm`、原 BDAE 节点和几何 | 13 个 ITM 共 151 条静态摆放；其中 37 种模型、139 条摆放具备本批支持的原材质与图集绑定 |
| 配置选择 | 原 APK `GameOptions.json` 和原设备 getter / 实例门执行 | APK `DeviceLayer=5` 经原 getter **clamp 为 4**；静态 151 条均通过；12 条特效中 10 条通过、2 条 light_spot 被拒绝，拒绝项未强显 |
| 模型与图集 | 原槽0 filename、`world/selection/lightmap/*.dat`、`texture/lightmap/selection/lightmap/*.tga`；原部件局部引用与 `0x33faa0` 绑定顺序 | 不借 tutorial 的对象记录或图集；按原 **部件顺序** 绑定，非材质下标猜配 |
| 环境资料 | 原 `tables/zones.tbl` 区域 211 | 原字段和可推导的稳定目标保留为资料；实际环境、天空、天气和过渡队列没有凭空激活 |

本批复用了先前 32 份已核模型转换，但逐份重读原 BDAE，检查 SHA、几何、UV、原节点矩阵和材质一致后才复用。另补了五份通用材质模型：草、祭坛、主建筑、台阶和火盆。所有摆放仍来自 selection 自己的 ITM。

## 尚未接回的 12 条静态摆放

| 原模型或对象 | 数量 | 缺口 |
|---|---:|---|
| `whi_other_waterfall001` / `002` | 2 | 原 `water_fall.bdae` 的材质和时间输入尚未在此候选恢复，不用平面颜色替代 |
| `whi_plant_flower005` | 2 | 模型使用 `texture/lightmap02.tga`，不同于既核 `lightmap.tga` 占位分支；未擅自改成另一张图 |
| `wp_big_stone003` / `wp_small_stone001` | 6 | 原 `u2t_lightmap_solid.bdae` 第二贴图组合尚未接回 |
| `god_temple01_inside01` | 1 | 原多贴图/UV 动画材质；本场景记录是 **type2**，不能沿用 tutorial 的 type15 可见状态冒充原选择 |
| `whi_plant_unknowgrass006`，对象 `1014080736` | 1 | 槽0 DAT 文件存在但没有该对象记录；不借槽1或其它地图的记录 |

另有 12 条原特效声明保留为待恢复资料，其中 2 条已经被 APK 默认门拒绝；本批没有生成新的烟、光或播放规则。地形中 344 个原水标志区块保留待恢复状态，既有地表适配器跳过这些原水分支，未用新地板填补。因此 139 条可加载静态摆放不等于完整原画面。

`texture/tiles/default.tga` 在源包中缺失。只有地形层的这一条已核空请求分支使用既有工具执行原初始化、纹理描述和像素填充指令，保留其原 `glitch.texture-not-found-2d` 结果及证据；它不是新画的贴图，也不代表原 Android 缓存或 GPU 创建成功。其它模型/图集缺贴图一律拒绝替代。

## 范围与接线边界

候选 25 块是以原配置 `sceneCenter=(-2583,-124.5,-100)` 的 X/Z 算出的 5×5 **条件窗口**。原 `0x53b5c8` 把该配置解析到 splash 对象 `+0x68`，原 `0x539674` 则把 world `+0x164` 交给 streamer；两者中间写入者仍未闭合，不能称这 25 块是已观察的原驻留列表。若直接以原相机位置计算，会得到另一个窗口，候选清单同时记录了这一区别。

本批没有扩展到选角地图远处其它区域。原目录虽然有 90 个 TRN 文件，但不能因此把它们全放进同一原始画面。区域 211 的天空引用为原 whitepike 天空/远山，本批仍未激活；不会复用 tutorial 天空作为替代。

[`source-selection-scene.js`](../tools/preview/source-selection-scene.js) 仅提供 `createSelectionScene(THREE, manifest, {origin, lighting, json, texture})`：

- `origin` 只用于网页数值原点平移，模型世界 TRS、节点矩阵和地形采样不重排、不归一化或居中。
- `lighting` 必须由另行核对的原调用者提供，并声明 `sourceSelectionRegion=211`。本模块不建立相机、灯光、天气、雾参数或新界面；缺环境接线就拒绝构建。
- 保留 139 个实例自己的 DAT 绑定；按原 part 顺序分配图集和 UV 变换。
- 使用既有原材质的网页桥接，RGBA 解码及浏览器采样是技术适配，不称原 GPU/像素级还原。
- 返回 `root`、计数、待恢复资料与 `dispose()`；不连接游戏、不创建角色、不读写存档。

实际人物、原相机/投影、环境和正式入口由主任务统一接线后浏览器验收。当前仅通过原数据核查和 CPU 构建检查，没有把未渲染的检查称为进游戏验收。

## 文件结构与复用规律

1. `world/<world>.wld` 是入口；地形、ITM、DAT 路径跟随其内部世界名。**同模型可跨地图共用，ITM/DAT 不可跨地图借用。**
2. ITM 文件名用带零填充的 tile 坐标；对象 DAT/图集文件名用原非填充坐标，不能根据相似文件名替换。
3. 原 `EntityConfig.xml` 在 selection 中只有空 Item/Npc/Object，且没有本地 `bdaeInstanceConfig.xml`；tutorial 的替换、距离和实例配置不能带过来。
4. `partToMaterial` 可能不是 `[0,1,2…]`。DAT 第 n 条绑定给原第 n 个部件，不能直接当材质 n。
5. 原素材都在，并不代表原效果已支持。水瀑、第二贴图、UV 动画和活动可见状态需要各自的源代码链路；通用材质不强行接收它们。

工具为 [`selection_scene_candidate.py`](../tools/selection_scene_candidate.py)，原资源测试为 [`selection_scene_candidate_tests.py`](../tools/selection_scene_candidate_tests.py)，CPU 模块检查为 [`selection_scene_candidate_tests.mjs`](../tools/selection_scene_candidate_tests.mjs)。没有私有资源副本时，原资源测试明确跳过。

本批私有候选位于 `analysis/raw/selection-scene-candidate-20261115/v4/`，包含 `assets/source-selection-scene/manifest.json`、37 个模型、87 张解码纹理、原地形分层和遮罩、selection 专用图集绑定及独立审计。它不是生产部署，原始素材、完整表格、报告和候选包均不上传 GitHub。
