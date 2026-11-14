# 新手地图场景特效：第一组火焰、烟雾

这是地图恢复中的一个有界分支。92 条原 type8 摆放已盘点；当前只交付其中 43 条共用的 `scene_fire_smoke.beff` 独立可见候选。没有把它们作为普通模型补进地图，也不表示整张地图或完整任务路线已验收。自动续跑仍暂停。

## 原文件范围

原 `world/tutorial/items/*.itm` 中共有 92 条 type8，分为 14 组。完整摆放、表项、贴图引用、CRC 和 SHA256 留在忽略目录 `analysis/raw/tutorial-scene-effects-20261114/`，不提交原资源。

| 原效果资源 | 摆放数 | 本轮状态 |
| --- | ---: | --- |
| scene_fire_smoke.beff | 43 | 参数核对、独立浏览器可见候选 |
| scene_fog003.beff | 12 | 严格解码通过，未接画面 |
| scene_fire.beff | 10 | 严格解码通过，未接画面 |
| scene_sun_light_line_purple.beff | 9 | 严格解码通过，未接画面 |
| scene_firesmoke.beff | 4 | 严格解码通过，未接画面 |
| scene_cold_light_spot.beff | 4 | 严格解码通过，未接画面 |
| scene_torch001.beff | 2 | 解码遇到 `test_UV.JPG` 依赖；未改扩展名强行读取 |
| scene_crystal_blue.beff | 2 | 严格解码通过，未接画面 |
| scene_firesmoke_02.beff | 1 | 严格解码通过，未接画面 |
| scene_sunshine001.beff | 1 | 原数据 timing 不满足当前严格解码器；未猜数或钳制 |
| scene_sunshine002.beff | 1 | 严格解码通过，未接画面 |
| scene_frostcliff_tree_lightpot01.beff | 1 | 严格解码通过，未接画面 |
| scene_sun_light_fireworm_blue.beff | 1 | 严格解码通过，未接画面 |
| scene_cold_air.beff | 1 | 严格解码通过，未接画面 |

## 加载和播放的证据

固定原 ARM64 库 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

- `a6196c` 从 AITM 读取摆放并检查质量、phase 和名字过滤。type8 在 `a61ae8` 建立专用 48 字节对象，原虚表为 `2423de8`，随后跳到 `a61ec0`；它走独立特效分支。
- 43 条火焰/烟雾的原 phase 字段均为 `ffffffff`，原质量字段低两位均为 3；本轮逐项对比已核对的 `APK_Default / phase0` 选择结果，它们都在工厂前准入。没有用未知服务器 phase 造活动状态。
- 主线程 `a62508` 的 `a62958..a62a78` 计算原模型名和世界 TRS，再调用 `a5cfb8`。本轮实际执行上述构造和参数段，43 条位置、四元数、缩放与原摆放逐项相等。
- 原 `25071b8 → 25093a0` 字节初值 1 选择异步请求；显式对照 0 会进入 `325234` 同步请求。它不是“隐藏特效”的开关。
- `a5cfb8` 建立原效果节点、资源任务和 manager 登记。原完成回调 `a5e5cc` 清任务状态、写完成标志，再把原位置、旋转、缩放应用到节点；取消标志为真时清理。本轮读到这些指令，但没有把资源任务边界伪装成原引擎完成或 GPU 成功。
- 原构造器的局部初始化 `eaf068..eaf19c` 已实际执行：`218=0, 219=1, 21a=1, 21b=0, time250=0`。基础节点、驱动登记没有执行，因此这些字段不冒充完整的已加载对象。
- 原 manager `378fd8` 在 `37946c..379564` 根据相机距离及对象状态调用 `eb21c0` 切换显示；后续按 `230/219/218/22e` 等字段及 `eb6458` 的发射器完成判断决定保留或清理。独立预览没有声称恢复了整套 manager。资源自身为无界发射时长，不等于按某个固定周期重启整个效果。

这组原资源没有缺贴图，3 个发射器均从第 0 帧开始，时长字段为 -1；材质序号为 `[6, 6, 0]`，来自原 `EfflibEffects.bdae` 的有序材质表，前两项加色，第三项透明混合。原 `fogRate=0`，因此本候选不增加雾或光源。

原 BEFF SHA256：`3f5c397bcad07580513ddb50adcb5abcd95fb6c6b55919d886470857e233510a`。原有序材质库 SHA256：`056844f95f5edde8677dde5acceaea51c0e22c86226fc2daf21d3e2652e7e38f`。三张原贴图为 `fire01_6x6.tga`、`fire03_xulie4x4.tga`、`fire_cir02.tga`；每张转换 PNG 与源文件校验都在私有 audit 中。

## 网页接入边界

新增适配模块 `tools/preview/source-scene-effect-preview.js` 只接受这组已校验数据。它复用当前预览的粒子模拟和材质着色器，不创建默认场景、不读写角色、不自行启动计时器、不自动重启。

父任务的最小接入方式：

1. 校验私有包后，把 `public/source-scene-effects/` 的 6 份运行文件和 `public/source-scene-effect-preview.js` 放进独立候选。`private-evidence/` 不作为网页素材发布。
2. 只为当前实际准入、已加载的原 ITM 摆放建立实例；不要把整个候选当作所有区域同时可见的列表。
3. 调用 `createSourceSceneEffect(THREE, {definition, instance, textures, camera})`。`textures` 是按 manifest 文件名索引的已解码贴图 Map。模块仍依赖已有 `particle-renderer.js`、`particle-simulation.js` 和 `procedural-effects.js`。
4. 由宿主明确决定加入哪个场景及传入经过的毫秒数 `update(ms)`，卸载时调用 `dispose()`。此接口不代替原资源完成/取消和距离 manager；不得据此标成完整原版播放流程。

网页随机序列、时间零点和相机朝向属于技术适配。原曲线、分布、贴图帧和材质参数已读取，但不能声称随机粒子逐像素 1:1。原声音元数据 `audioEff-2-sfx_fire_%s_loop` 保留，声音播放没有恢复。不增加碰撞，不修改光照、既有地图、存档或生产服务。

## 实际核查

`tools/tutorial_scene_effects_tests.py` 核查 92 条清单、两项命名缺口、43 条原参数执行、同步/异步分流、原局部构造状态、校验失败拒绝与独立适配器。`tools/tutorial_scene_effects_package.py` 校验运行文件后生成确定性私有 tar；输出只能位于忽略目录且拒绝覆盖。

本轮在独立本地 HTTP 页面实际运行 WebGL，选择原摆放 `357183064`：位置 `(-2463.7056, 104.7792, -40.5311)`、原单位旋转、缩放约 `14.9820`。这只是资源查看位置，不是原出生点。显式时钟 0 ms 有 3 个粒子，5000 ms 有 35 个粒子，1 个着色器程序实际编译；观察 1562 帧，浏览器 warning/error 均为 0。画面中可见原火焰和烟雾。检查相机、背景和时间滑块只存在私有验收页，不加入游戏界面。

截图与报告：`analysis/raw/tutorial-scene-effects-20261114/fire-smoke-browser-5000.png`、`browser-acceptance.json`。这项验证的是单组独立可见候选；正式地图集成、43 条按区块出入以及完整路线尚未验收。
