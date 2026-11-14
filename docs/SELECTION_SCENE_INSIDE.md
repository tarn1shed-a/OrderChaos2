# 选角背景的一处神殿内侧模型

这批把选角地图原先未接的 `god_temple01_inside01.bdae` 整理成独立追加候选。它是一处完整原模型和一条原摆放，没有新补墙面、换模型、移动建筑或修改光源。冻结的 139 条静态候选仍原样保留；合并本批后才是 140 条，另 11 条缺口仍待核对。候选尚未部署，最终画面由主任务统一接线、进浏览器验收。

## 原文件和原代码核对结果

| 核对内容 | 原始依据 | 结果 |
|---|---|---|
| 选择和摆放 | `world/selection/items/-041_-002.itm`，原实例配置查询和 APK 默认门 | 对象 `684990760` 是 **type2**，默认设备门允许加载；不是 tutorial 的 type15 室内对象 |
| 模型结构 | `model/scene_generator_temple_000/god_temple01_inside01.bdae`，SHA256 `a7d5ab9ec74318feaf1c518d8b4b5a94e3e847996c67c9a34e84ee34c3c23192` | 11817 个顶点、7900 个三角形、21 个部件；原索引、节点矩阵、ITM 位置/旋转/缩放全部保留 |
| 材质与绘制状态 | 模型 21 条材质、三个原 FX 和 `ut_common_vs/fs.glsl`；既有原状态扫描 | 18 条 solid、2 条第二贴图发光、1 条 UV 动画。只有材质 0、1、3 做 `alpha <= 0.5` 丢弃；全部双面、深度测试/写入、LessEqual，无混合 |
| 第二贴图坐标 | 原 BDAE 顶点声明/primitive binding，原 `0x12db438` / `0x12db478` 与 texcoord 名表 | 原 UV2、UV3 分别用于第二贴图和遮罩；不是复制主 UV。原源语义 6/7 对应运行时 3/4 |
| 材质数值 | 原模型 typed property，实际执行原 `0x13e0b30` 写入 | 两项第二贴图滚动速度、颜色、强度及一项主 UV 滚动速度均按原 float 值导出；未手调 |
| 光照图 | `world/selection/lightmap/-41_-2.dat` 和 selection 自己的图集；原 `0x33faa0` 部件绑定循环 | 该对象只有一条 DAT。原循环确实让 21 个部件共用第 0 条；不能借 tutorial 的多条记录 |
| 时间 | 既核原计时器的毫秒转秒指令 | 1000 毫秒得到 1 秒；网页显式提供同一单调时钟适配，不猜循环长度或另设动画速度 |

三个原效果为 `ut_lightmap_solid.bdae`、`u2t_lightmap_trans_uv_lumin.bdae`、`ut_lightmap_trans_uv.bdae`。导出器同时验证 FX 两套原 profile、sampler 声明、shader defines、原 shader SHA 和原材质属性类型。所有实际需要的纹理都在原包中。本模型用的是 **`texture/hum_portal005_01.tga`**；另一个模型缺失的 `hum_portal005.tga` 不能混为同一引用。

第二贴图使用原 UV2 加原速度与时间的 `fract` 偏移，遮罩使用原 UV3。第二贴图 RGB 乘原颜色、原强度、第二贴图 alpha 与遮罩 alpha，叠加在基础光照结果之后、雾之前。主 UV 动画只用于材质 3。底层状态从原 FX 读取，网页 shader 是按已核运算独立编写的桥接，不能把浏览器滤波、精度和调度称为原 GPU。

## 独立接线

[`selection_scene_inside_candidate.py`](../tools/selection_scene_inside_candidate.py) 只读冻结目录并输出新目录：

```sh
.venv/bin/python tools/selection_scene_inside_candidate.py \
  --base analysis/raw/selection-scene-candidate-20261115/v4 \
  --output analysis/raw/selection-scene-inside-20261115/v1
```

候选 `assets/source-selection-inside/overlay.json` 指向一份模型和 24 个所需纹理引用：13 个复用冻结候选且核对原编码 SHA 与解码像素；11 个新解码 PNG 只进入追加目录。原文件、完整材质/原生核查和包清单全部留在忽略目录，不能提交 GitHub。

[`selection_scene_inside_material.js`](../tools/preview/selection_scene_inside_material.js) 提供：

```js
const append = await createSelectionInsideAppend(THREE, overlay, {
  origin, lighting, json, texture, clock,
});
scene.add(append.root);
// 卸载时调用 append.dispose()。
```

`origin` 必须与冻结场景相同，只做网页数值原点平移；不重新居中模型。`lighting` 接主任务已核的区域 211 fresh-start 输入，模块不创建任何灯光/环境。`json` 和 `texture` 同时能读取冻结目录和追加目录；共享纹理缓存不会被模块修改或销毁。`clock.value()` 显式返回既核时钟的秒值，调用方负责逐帧更新。

模块拒绝把对象改成 type15、混用其它地图图集、缺 UV、缺实际纹理、缺原材质参数或缺已核环境/时钟。它不设置室内相机/碰撞显示门，不请求 `_inside` 伴随模型，不改角色或存档。原 Android 暂停/重入历史、原 GPU 成功和最终活动特效仍未据此恢复。

## 已做与待做的验收

[`selection_scene_inside_tests.py`](../tools/selection_scene_inside_tests.py) 已通过 6 项原资源检查：重新解原顶点/索引/UV/矩阵、材质与 sampler、原部件绑定执行、type2 摆放、时钟与绘制状态，以及冻结基础包 146 个载荷逐个 SHA 未变。

[`selection_scene_inside_tests.mjs`](../tools/selection_scene_inside_tests.mjs) 使用真实 PNG 尺寸与区域 211 fresh-start 数据做 CPU 构造：1 实例、21 材质、7900 三角、3 动画材质、21 部件共用一条原图集绑定；核对原 TRS、UV、叠加顺序、显式时钟和卸载。测试不执行 GPU，也不把纹理尺寸夹具说成已经看到原像素。

主任务仍需把这个追加模块与原相机、角色预览和区域 211 环境合在同一浏览器里看图。本批没有新开 Docker，没有修改冻结场景、天空、发布脚本、现有存档或线上服务。

规律是：**同一个模型路径可能在不同地图里有不同对象类型和图集绑定。** 复用几何/材质解析器前，必须重新核对该地图 ITM 的类型与自己的 DAT，不能把 tutorial 的室内显示规则和图集一起复制进选角地图。
