# 选角背景的六条双贴图石头

本批核对并导出 map7 selection 中六条原石头摆放，使用两份原模型、原材质、原第二套 UV 和每个对象自己的 selection 光照图记录。它是独立追加候选；没有替换冻结的 139 条静态候选或神殿内侧追加，也没有改光源、地形、存档或发布脚本。

## 已确认的原始内容

| 原模型 | 摆放数 | 原顶点 / 三角形 / 部件 | 原第二贴图 |
|---|---:|---|---|
| `wp_stone/wp_big_stone003.bdae` | 3 | 419 / 282 / 2 | 两个材质分别为 `wp_big_stone001.tga`、`wp_big_stone002.tga` |
| `wp_stone/wp_small_stone001.bdae` | 3 | 77 / 62 / 1 | `wp_big_stone003.tga` |

两份模型完整路径均在 `model/scene/region_whitepike/` 下，主贴图均为原 `texture/rock_07.tga`。文件名中“大石头”和“小石头”不是纹理选择依据：小模型的真实第二贴图就叫 `wp_big_stone003.tga`，导出按原 sampler 引用，而不按名字猜。

原 `u2t_lightmap_solid.bdae` 两个 profile 都声明 `LIGHTMAP + TWO_TEXTURE`，没有 `TEX_BLEND`、`TEX_LUMIN_WITH_MASK`、`ALPHA_TEST` 或 UV 动画。原 `ut_common_fs.glsl` 这条分支会让两次采样的 **RGBA 逐分量相乘**，再乘光照图、顶点环境光并处理雾。它不是 alpha 插值，也不是把第二张图当作发光层。原 `ut_common_vs.glsl` 将 `TexCoord2` 独立传给第二贴图；这两份模型的原 UV2 确实不同于主 UV。

核查了原 FX 外层归档 SHA256 `75bad7fe12152d853ae44206a5d2a2f6bfadc5c01414bae71815277604fffd03`，以及解包后的 BRES SHA256 `172b30438e12a0fe18610fe66e145e9f87372987c2699034a5490dd5b1f3d547`。它们是不同层的数据，不能把归档 SHA 用作 BRES 校验。

原模型的三个 sampler 是 `texture`、`lightMap`、`texture2`。模型请求未覆盖采样字段；原 FX 两套 profile 对三个 sampler 都声明 Repeat U/V，过滤字段为空。实际纹理均存在，全部读取原引用，没有纯色或相似文件替代。RGBA 解码、浏览器滤波/mip 和精度仍明确属于网页适配。

原 FX 两个 profile 的绘制状态一致：双面、深度测试/写入、LessEqual，不混合、不做 alpha-test。原顶点/索引、法线、主 UV、光照 UV、第二 UV 和节点矩阵原样保留；没有生成新几何。

## 原摆放、门和光照图

六条记录都在 `world/selection/items/-041_-003.itm`，类型是 2。重新执行原配置查询与 APK 默认设备门，六条均允许进入原类型工厂前的分支；不是强行显示被拒绝对象。原设备层 getter clamp 和 selection 无本地实例覆盖的结论仍与冻结候选一致。

六个对象分别使用 `world/selection/lightmap/-41_-3.dat` 自己的一条记录、原 `texture/lightmap/selection/lightmap/-41_-3.tga`。它们的 UV 变换各不相同。原部件引用与 `0x33faa0` 绑定循环重新执行：三块大石头各两个部件、三块小石头各一个，共九次绑定；大石头的第二部件沿原回退规则共用该对象第 0 条 DAT。没有借用 tutorial 图集、借其它对象变换或把材质下标当绑定顺序。

UV2 读取复用既核原顶点声明和 primitive binding；原 `0x12db438`、`0x12db478` 及 texcoord 名表核对源语义 6 对应运行时 3。工具复用了 UV2 读取函数，没有给石头添加植被摇动或风参数。

## 候选接口和验收边界

导出工具为 [`selection_scene_stones_candidate.py`](../tools/selection_scene_stones_candidate.py)：

```sh
.venv/bin/python tools/selection_scene_stones_candidate.py \
  --base analysis/raw/selection-scene-candidate-20261115/v4 \
  --output analysis/raw/selection-scene-stones-20261115/v4
```

正式候选目录为 `analysis/raw/selection-scene-stones-20261115/v4/`。早期失败输出仍只在忽略目录，不可误用。候选有两份模型、四张新解码 PNG 和一份 overlay；光照图复用冻结候选，且核对原编码 SHA 与解码像素。原资源、完整表格、原代码、报告及私有包不上传 GitHub。

[`selection_scene_stones_material.js`](../tools/preview/selection_scene_stones_material.js) 导出：

```js
const append = await createSelectionStonesAppend(THREE, overlay, {
  origin, lighting, json, texture,
});
scene.add(append.root);
// 卸载时 append.dispose()。
```

调用方提供与冻结场景相同的 `origin`、已核区域 211 fresh-start 环境，以及可读取冻结和追加目录的资源加载器。不建立新相机/灯光/天气/计时器。六个实例各自保留原 ITM TRS 和节点矩阵；两份原网格供三个实例分别使用。模块创建九个按对象绑定的材质，不改共享纹理缓存。

[`selection_scene_stones_tests.py`](../tools/selection_scene_stones_tests.py) 核对原几何/UV/材质、真实 FX 状态与默认 sampler、六条 ITM 和 DAT、实际原部件绑定，以及冻结基础包和内侧追加全部载荷 SHA。原资源缺失时明确跳过。

[`selection_scene_stones_tests.mjs`](../tools/selection_scene_stones_tests.mjs) 使用真实 PNG 尺寸和已核区域 211 fresh-start 数据做 CPU 构造：两份网格、六个实例、九个材质、共 1032 个实例三角形；核对第二 UV、RGBA 相乘位置、各对象 DAT、TRS、无灯光、缺 UV/外地图集拒绝及卸载。没有把尺寸夹具说成已渲染像素，实际 GPU 和浏览器验图留给主任务统一进行。

仅加本批时，冻结基础候选变为 39 模型 / 145 条静态摆放；再合并独立神殿内侧追加，才是 40 模型 / 146 条，仍剩两条瀑布、两条花草的不同 lightMap 分支和一条缺对象 DAT 的草，共五条静态缺口。水面、活动特效、真实 streamer 中心和完整原始帧仍需单独核对，不能把 146 条理解为整个原场景已经完成。

可复用的规律是：原 `TWO_TEXTURE` 只是打开第二采样，不一定表示混合。必须继续检查具体组合宏、源 UV 语义和原 shader 分支，才能决定相乘、插值、发光还是其它处理；原图集仍按每个地图对象和部件绑定，不能随模型一起跨地图复制。
