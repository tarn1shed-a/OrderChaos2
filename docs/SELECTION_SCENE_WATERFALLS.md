# 选角背景的两条原版瀑布

这批恢复 map7 的两条原摆放、原网格、原材质及流水纹理动画。它们不是地图水面，也不使用通用地表光照材质。原文件有 selection DAT 请求，但原瀑布 shader 没有 `lightMap` 或 DAT 的 `uvTransform` 消费，不能把图集强行套上去。

候选独立追加，尚未接入正式入口或部署。冻结的 139 条基础、神殿内侧、石头、花草、区域 211 环境和天空均未修改；没有创建角色、连接游戏服务器或改存档。地图天空缺资源的黑色背景仍然保留，不能把两条瀑布验收当成完整原版帧验收。

## 原文件和代码依据

| 内容 | 原始来源 | 核对结果 |
|---|---|---|
| 模型 1 | `model/scene/region_whisper_island/whi_other_waterfall001.bdae`；SHA256 `9832bfae95860fdfbdf157cef9a0fe05713eba5d1adff29d2f0b20e5260fb79d` | 对象 404238120；42 顶点、60 三角、一个部件和材质；保留原节点矩阵、UV0、UV1 |
| 模型 2 | `model/scene/region_whisper_island/whi_other_waterfall002.bdae`；SHA256 `38bd80cf16116ac1d1e2571caa712149045f802b30efa17dac2ccd1886e1bab4` | 对象 404238408；同样 42 顶点、60 三角、一个部件和材质；没有复用模型 1 的变换 |
| 摆放和加载门 | `world/selection/items/-041_-003.itm`、APK 默认配置、原实例过滤 | 两条均为 type2，原默认门实际允许；ITM 位置、旋转、缩放原样保留 |
| 效果 | `water_fall.bdae`；SHA256 `d16c5a7b804040148ea936f3a763d2ce03b8d7acc7fdc3ad81ebeeb5f54a3192` | 两套 profile 均使用 tech0 和同一对原 shader，没有效果私有宏 |
| 原数值消费 | `0x1129190 → 0x13baac8 → 0x13daa40`，随后 `0x112920c / 0x13e0b30` | 实际执行原材质构造、20 字节默认块复制及模型 typed override；声明布局、interning 是明确 CPU 接口，不是假称 GPU 成功 |
| 原全局上下文 | `0x550f08..0x550f58`，实际初始全局字节 | 默认 blend override 字节为 1；带对象 DAT 的 fresh slot0 标志为 `0x887`，WATER 未开启；没有把原初始字节猜成 0 |
| 原绘制状态 | 原效果状态读取和原 GL 状态翻译 | 双面，深度测试开启、深度写入关闭、LessEqual；真实记录 `glBlendFunc(770,771)`、Add 方程 |
| 环境颜色 | 原区域 211 fresh-start；重跑 `0x34e53c` | 原 common RGB 为 `[1.2750000954, 1.2300001383, 1.1633332968]`，与冻结原环境一致；模块不新增灯光或手调颜色 |

两张原纹理为 `texture/whi_waterfall001_01.tga` 和 `texture/whi_waterfall002_01.tga`。它们实际都是 ZIP 内分离 `rgb.pvr` / `alpha.pvr` 的 256×256 ETC1 图片，各有 9 层源 mip。候选把每一份原 PVR 单独解码成 PNG，共四张，逐像素核对；不合成噪声、不新画遮罩，不把分离 alpha 丢掉。

## 原流水动画与材质规律

原 `water_fall_vs.glsl`（SHA256 `d79cf3b5b555e2b92089d72566f9e6e7817b5d3404506233c8a1e40f10c68144`）把 UV0 分别加上 `fract(uvSpeed1 * time)` 和 `fract(uvSpeed2 * time)`。遮罩使用原 UV1，和地表 lightmap UV 的用途不同。

原 `water_fall_fs.glsl`（SHA256 `d7b7b4d5dc2da58c64a509450923fa2dad5549d041698e59398cddefbf7e0d74`）从主纹理颜色取得扰动，两次采样再做 RGBA 乘积；随后执行原 mask alpha 修正、色调、`light_affected_rate` 颜色混合和雾。原文件保留私有目录；公开工具只存来源、校验与必要接线。

| 对象 | uvSpeed1 | uvSpeed2 | light_affected_rate |
|---|---|---|---|
| 404238120 | `[0, -0.20000000298]` | `[0, -0.40000000596]` | 模型显式覆盖为 0.5 |
| 404238408 | `[0, -0.25]` | `[0, -0.5]` | 模型未写，原效果默认块仍为 0.5 |

不能把模型没写的参数当成 0。数值工具用脏内存执行原复制链，证实模型 2 的 0.5 来自效果默认值。原时钟的微秒到秒换算也实际执行；浏览器传入明确的单调时钟。原 Android 暂停、旧世界重入、淡出及水下分支不在这次 fresh-start 验收范围内。

## 导出与接线

工具为 `tools/selection_scene_waterfalls_native.py`、`tools/selection_scene_waterfalls_candidate.py`。正式候选目录是 `analysis/raw/selection-scene-waterfalls-20261115/v2/`；早期失败的 v1 不用于合并。

```sh
.venv/bin/python tools/selection_scene_waterfalls_candidate.py \
  --base analysis/raw/selection-scene-candidate-20261115/v4 \
  --output analysis/raw/selection-scene-waterfalls-20261115/v2
```

运行模块 `tools/preview/selection_scene_waterfalls_material.js` 提供：

```js
const append = await createSelectionWaterfallsAppend(THREE, overlay, {
  origin, lighting, json, text, texture, clock,
});
scene.add(append.root);
// 卸载时 append.dispose()。
```

加载器需读取 `/assets/source-selection-waterfalls/` 的两份模型、四张图片、两个原 shader 和 overlay，共 9 个追加载荷；使用同一原点和冻结区域 211 fresh-start 环境。模块检查环境 common/model RGB 对应，不接受套 map5 的输入。

网页适配范围明确为：原 GLSL 语法传输到 WebGL2/GLSL3、矩阵和原参数提交、图片解码后的浏览器滤波/mip、透明排序以及显式时钟。保留原 shader 运算、图像、UV、摆放和混合状态；没有用另一套视觉材质替代。

## 实际验收及缺口

`tools/selection_scene_waterfalls_tests.py` 的五项原文件/CPU 检查通过：原网格和节点、默认值与覆盖、四份 PVR 解码像素、原上下文及状态、前 169 个冻结载荷 SHA。Node 检查构造、原 TRS、两条 UV、显式时间、矩阵、状态及卸载；Node 自身不编译 GPU。

随后在独立 GET-only 静态页实际用 Chrome WebGL2 验收。组合页沿用主任务的原选角相机、人物 TRS 和区域 211 fresh-start；25 地形、150 静态摆放正常提交，原瀑布 shader 实际编译，console error/warn 为空。分别通过研究页按钮查看两条瀑布近景：两次截图中原时间前进且水纹明显变化。近景相机只是验收工具，**不是原版相机的新设置**。完整原相机画面和各近景截图、时间、GPU 资源及 console 均留在本批 `browser-qa/`。

点击卸载花草和瀑布后，两组追加节点均移除；GPU 几何从 73 降至 70、纹理从 129 降至 124，未出现错误。临时页和端口 8924 已关闭，没有 Docker、游戏连接或角色写入。这里证明的是网页 GPU 成功执行该有据候选；模块中的 `originalGPUObserved: false` 仍准确表示没有原 Android GPU 抓帧。

静态候选合计达到 **43 模型、150 条摆放**，剩一条缺对象 DAT 的草；另有未闭合的活动特效、水分支、原驻留窗口及 region211 缺天空模型，不能用这个数目宣称完整选角场景已 1:1 完成。可复用规律是：先核效果默认块，再核模型覆盖；同样叫 UV1 和 DAT 的字段，也必须追到 shader 的实际消费，不能一律当 lightmap 绑定。
