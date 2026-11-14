# 选角背景两处花草：保留原模型自己的光照图

这批恢复两条 `whi_plant_flower005` 原摆放。关键结论是：它们虽然都有 selection DAT，**原代码会拒绝用地图图集替换模型里的 `texture/lightmap02.tga`**。不能为了接通旧通用材质，把这个名字改成 `lightmap.tga` 或直接套对象图集。

独立候选尚未部署，也没有进行本批浏览器/GPU 验收。冻结的 139 条基础、神殿内侧追加、六条石头追加、区域 211 环境、天空、部署和存档均没有修改。

## 原始依据

| 内容 | 原文件/原代码 | 核对结果 |
|---|---|---|
| 模型 | `model/scene/region_whisper_island/whi_plant_flower005.bdae`，SHA256 `5d08863bac80a932a54e9738696866d7da351e427e8b3897c1a181c142cd6b8d` | 8 顶点、4 三角、1 部件、1 材质；原顶点/索引/UV/节点矩阵不变 |
| 两条摆放 | `world/selection/items/-041_-001.itm`、`-040_-001.itm` | 对象 967639024、967638880，均 type2；实际原默认配置门允许加载，TRS 原样保留 |
| 原材质 | `flower_yellow`、`ut_lightmap_trans.bdae` | 主贴图 `texture/whi_botany_integration.tga`；光照 sampler 真实引用 `texture/lightmap02.tga`，请求字段没有覆盖 |
| 绘制状态 | 原 FX 两套 profile、原公共 shader，既核 alpha/culling 读取 | 双面、深度测试/写入、LessEqual，不混合；alpha 小于等于 0.5 丢弃，不添加风或其它动画 |
| 地图图集请求 | 两对象分别有原 `world/selection/lightmap/-41_-1.dat` / `-40_-1.dat` 的一条记录 | 都真实存在，但“有请求”不等于“最后使用了它”；记录作为证据保留，候选不应用其 atlas/UV 变换 |
| 原替换决策 | 原 `0x342194`，名字查找 `0x14006c4`、材质纹理 getter `0x13e4214`、原名字拷贝 `0x316c7c` | 非空且不等于 `texture/lightmap.tga`，原 owner `+0x179` 清为 0；不调用纹理替换 setter，不写入 DAT 的 UV 变换 |
| 原构造与缓存 | 原 `0x33db74` 和 `0x342194` | 新 owner 初始标记是 `(1,0)`；决策完成后成为 `(0,1)`。这里执行原构造器，没有把新 owner 初值猜成全零 |

原 `0x342194` 内部的名字比较、分支、缓存标记、材质纹理 getter、UV getter/setter 和 C++ 字符串拷贝均实际执行。运行时材质声明、被保留纹理的身份/2D 类型和名字 interning 是明确的 CPU 接口，不是已经构建原 GPU 的声称。对照测试里，原占位名字、空名字及空纹理允许替换；本模型实际的 `lightmap02` 不允许。旧已缓存 owner 的真实 Android 历史仍不据此补造。

## 原光照图与 UV 的处理

`texture/lightmap02.tga` 唯一来自 `res_t.bin`，SHA256 `822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b`。它是原来的 8×8 图片，逐像素核对全部为 RGBA `(130,130,130,255)`。候选解码并保留这张实际图片，既没有新画灰色图片，也没有按主观亮度挑图。

模型没有序列化 `uvTransform`。原 CPU 在显式零 UV 的接口案例中会重置为 `(0,0,1,1)`；在已有非零 UV 的对照中则保留。这个实验不能替代原设备的完整 UV 历史。网页材质直接使用模型原 UV1 采这张已核的恒定原图：任一有限 UV 都得到同一像素，因而不需要猜历史变换，也不会错误应用 selection DAT。该等价桥接已单独标明，不声称抓到了原 Android 当前 uniform。

环境仍由主任务提供区域 211 fresh-start 的已核输入；本模块不设置灯光、曝光、天气、天空或新颜色。图片解码、浏览器滤波/mip、精度和调度属于网页技术适配。

## 导出和接线

原决策工具为 [`selection_scene_flowers_probe.py`](../tools/selection_scene_flowers_probe.py)，导出工具为 [`selection_scene_flowers_candidate.py`](../tools/selection_scene_flowers_candidate.py)：

```sh
.venv/bin/python tools/selection_scene_flowers_candidate.py \
  --base analysis/raw/selection-scene-candidate-20261115/v4 \
  --output analysis/raw/selection-scene-flowers-20261115/v2
```

正式候选是 `analysis/raw/selection-scene-flowers-20261115/v2/`。早期 `v1` 和探测草稿不能用于合并。原资源、完整证据、CPU 轨迹、私有包和截图只留忽略目录，不上传 GitHub。

[`selection_scene_flowers_material.js`](../tools/preview/selection_scene_flowers_material.js) 提供：

```js
const append = await createSelectionFlowersAppend(THREE, overlay, {
  origin, lighting, json, texture,
});
scene.add(append.root);
// 卸载时 append.dispose()。
```

调用方使用与其它选角候选相同的原点和区域 211 环境，加载器能读取冻结基础与追加目录。主贴图复用冻结 PNG 并核对原编码 SHA、解码像素；`lightmap02` 是一张新解码原图。两实例只使用一份原网格，保持各自 ITM 的位置、旋转、缩放，不增加布景或碰撞。

[`selection_scene_flowers_tests.py`](../tools/selection_scene_flowers_tests.py) 核对原模型/材质、实际原替换决策与正对照、原恒定纹理全部像素、两条原 DAT 及默认门，并逐个 SHA 核对前三份冻结候选的载荷未变。[`selection_scene_flowers_tests.mjs`](../tools/selection_scene_flowers_tests.mjs) 使用实际 PNG 尺寸与区域 211 fresh-start 输入做 CPU 构造，检查两实例、原 TRS、原 cutout 状态、不应用 atlas/DAT 及卸载；它不渲染 GPU 或原始像素。

本批加上已有三个静态候选后，可提交主任务验收的数量是 **41 模型 / 148 条静态摆放**。仍余两条瀑布和一条缺对象 DAT 的草；活动特效、水分支、原实际驻留中心及完整原版帧仍是独立缺口。计数不代表选角画面已经最终完成。

可复用的规律是：**模型里非占位的 lightMap 引用有实际语义。** 原文件存在对象 DAT，并不能绕过材质替换门；必须继续追最后 setter 是否执行，不能看到表里有图集就绑定上去。
