# 选角地图的原水面批处理

接续 `SELECTION_SCENE_WATER.md`：192 块干地追加继续冻结，本批为其余 **9 个 selection tile、152 个 type0 湿块**提供独立原水面候选。水位、反射引用、深度图和批处理顶点都来自 selection 自己的 TRN。没有借 tutorial 地图参数、改水位或新画水面美术。

实际 Chrome WebGL2 已编译并显示原水面 shader，在外侧原水域可见原水纹流动；水下地表、补色 border 和原天空缺口仍保留。候选没有部署，不代表完整选角场景或原 Android 整帧已恢复。

## 原批处理能力与显示分支

上一批已核 `3758b8` 按 `2509330` 分派：0 用 `360b48`，1 用 `3624cc`。本批继续找到原能力生产者 **`13b7ad0`**：driver `+1b5` bit5 是能力字 `+1b0` 的 bit45；原 GL 版本 ≥ 300 或相应扩展条件可设置它。地形管理器 `35bb00` 仍会据这个位保留/清除原水批处理开关。

`selection_scene_water_batch_native.py` 实际执行完整原能力生产者，在明确的 GLES 类 backend、空扩展、版本 200/300 输入对照中，bit45 分别为 false/true。backend、版本、vendor、limits 是声明的 CPU 环境接口，不是冒称观测到了原手机。实际验收浏览器返回 **`WebGL 2.0 (OpenGL ES 3.0 Chromium)`**；网页候选显式使用这一 GLES300 类传输分支，没有把原全局强制改为旧 0 分支。

map7 通过原水面 show/map 排除入口门；排除的是 map43。这里选定 type0、水上 `default`、淡入完成的显示范围。原真实驻留队列、GPU 资源完成及 Android 淡入时相仍未闭合，网页直接提交已核原资源是技术接线，不伪造原完成回调。

## 原顶点、原深度和原贴图

原 `35459c` 在批处理路径中统计水面位、申请/映射缓冲，再从 **`354878..354a08`** 写顶点和索引。本批执行这个原写入循环，停止在 unmap/upload 之前，得到：

- 152 块 × 4 个顶点，共 **608 原顶点**；32 字节源步长，保留原位置、UV 和颜色字节。
- 每块 6 个原索引，共 **304 三角**；逐块核对 `0,2,1,1,2,3` 加该块顶点基址。
- 每一块世界位置均与 selection 原 tile/区块坐标、水位逐值对应；不是由网页另画任意四边形。

原 `356fac..357024` 的水深输入准备也实际执行，密度 5 和无水块 `-100` 哨兵来自原指令；随后执行 `357030..35724c` 产生 9 份 128×128 A8 缓冲。PNG 只无损保存实际 alpha 字节，没有新画岸线。

三种反射引用逐 tile 从原 TRN 索引/字符串表取出，分别是 `texture/tiles/textures/water.tga`、`texture/tiles/textures/reflection_r.tga`、`texture/tiles/water.tga`。波纹和菲涅耳使用原全局请求 `Waterbump_normal.tga` / `water_fresnel.png`。五张源图逐像素核对解码结果，全部保留原 alpha。

原 `CustomEffects.bdae` 的效果31 `Terrain_Water`，两个 profile 的 `default` 均引用原 `water_vs.glsl` / `water_fs.glsl`，无效果私有宏。状态为 SrcAlpha/OneMinusSrcAlpha Add（含 alpha）、双面、LEQUAL、深度测试、不写深度。水下技术不混用。

水面 RGB 是区域 **211** 原生产结果 `[3.375,3.2558825016,3.0794117451]`。本批没有创建灯光、改曝光、雾或环境。原波纹时间的双精度乘法、floor、float32 转换继续与原指令在 0/1/1000/123456/uint32 上界对照；网页单调时钟起点和淡入完成常量属于明确适配。

## 候选接口和验收

正式独立目录为 `analysis/raw/selection-scene-water-20261115/surface-v1/`；基础 `v1` 是上一批 192 干地追加，不能互相覆盖。原 shader、原图片、完整批次缓冲、Ghidra 响应和截图留在忽略目录。

`tools/preview/selection_scene_water_surface.js` 提供：

```js
const water = await createSelectionWaterSurfaceAppend(THREE, overlay, {
  origin, lighting, json, text, texture, clock,
});
scene.add(water.root);
// 卸载时 water.dispose()。
```

`clock.value()` 返回明确的非负秒数。模块做原 GLSL 到 GLSL3 的语法传输，按相同 scene origin 提交原位置/世界矩阵、原图片、原雾和原 RGB；不重新设计波纹。PNG 基级滤波/mip、透明排序、矩阵原点及 WebGL2 驱动属于网页技术适配。原水下地表和 border 不由这个模块打开。

四项 Python 源测试通过：全部原批处理/深度字节、五张源图与 shader、原能力生产者和 211 RGB、前 181 个冻结载荷 SHA。Node 核原矩阵/UV/索引、608 顶点/304 三角、原状态和时间、卸载，通过；Node 自身不渲染 GPU。

实际静态研究页沿用原选角相机/人物 TRS/211 fresh，151 摆放及 192 干地保持。原 shader 在 Chrome WebGL2 成功编译；外侧原水域 `(-43,0)` 的两次近景图中水纹明显变化，原时间偏移同步变化。研究相机不改正式相机。池面近景被原建筑/树干遮挡，没有把这一视点算作画面通过，也没有为验收挪开源物体。

研究页早期有一次资源完成前点击相机按钮，产生 QA 控件未就绪错误；已给这张研究页加就绪禁用门，并保留原诊断。最终页面的 error 数组为空；开发日志里先前 reload 的历史记录仍保留，不能混称为 shader 错误或抹掉。最终原相机、外侧 a/b、水面卸载及各诊断存于 `surface-browser-qa/`。卸载后追加根移除，已上传 GPU 几何 87→81、纹理 145→135，无新错误。

临时页与 8924 已关闭，无 Docker、游戏连接、角色写入或正式部署。下一缺口是 152 块的原水下地表与 border，其中 `(-41,-3)/(2,7)` 需要核对基础层被 mask 剪枝的原宏选择；同时真实驻留、活动、原天空和原 Android 完整帧继续单列。
