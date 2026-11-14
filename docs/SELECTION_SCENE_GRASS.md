# 选角背景最后一条缺 DAT 的草木

对象 `1014080736` 不缺模型，也不是原版主动隐藏：原 APK 默认实例门允许加载，原槽 0 DAT 没有它的记录，原代码会跳过图集替换，保留模型自己的默认光照纹理。基础候选为了避免猜测而遗漏了这条；这次按原空记录分支补回，不能借另一对象或槽 1 的 DAT。

候选独立追加，尚未改正式入口或部署。它复用已冻结模型，只追加一条原 ITM 变换及真实默认图片，没有新造网格、地面、灯光或坐标。原区域 211 天空资源、活动效果等缺口不因此消失。

## 依据和实际分支

| 内容 | 来源及结果 |
|---|---|
| 模型 | `model/scene/region_whisper_island/whi_plant_unknowgrass006.bdae`，SHA256 `af7e764074b378199e115d8b1d20743d8c7a7717d5ea6193c0b98547877a0fc5`；227 顶点、165 三角、一个部件；已冻结基础中同模型另有 3 条摆放 |
| 摆放 | `world/selection/items/-042_-001.itm`，type2，位置 `[-2635.7963867,142.4558258,-37.4527969]`；原旋转、缩放和节点矩阵保留；实际 APK 默认门为 admittedBeforeTypeFactory |
| 原材质 | `_4_-_Default`，`ut_lightmap_trans.bdae`；主图 `texture/whi_botany_integration.tga`，lightMap 引用 `texture/lightmap.tga`；源采样请求无覆盖；双面、深度测试/写入、alpha ≤ 0.5 丢弃 |
| 缺记录 | `world/selection/lightmap/-42_-1.dat` 存在但没有该对象；原 `0x3293a8` 实跑返回空记录 |
| 原处理 | 新 owner 用原 `0x33db74` 构造；原 `0x33ee00` 在空记录时保持 owner 不变；给出明确已载模型指针后，原 `0x33faa0` 因空 atlas 提前返回，不遍历或替换材质 |
| 默认图片选择 | 复用已核 `MissingRecordProbe`，实际执行 `0x8f8508` 挂载和 `0x54bc84` 冷缓存查找；实际本地包条件下，选择 `res_t_upd10.bin` 的原默认图片 |

原 `texture/lightmap.tga` 在 base 包里是 `(200,200,200,255)`，在 `res_t_upd10.bin` 中是 `(130,130,130,255)`。候选使用后者的真实 8×8 图片，SHA256 `822acc1f548307aeeb52e8f3ac4d376d9e6c5250043d4eb2235e88690f04a26b`，逐像素核对。它虽然与花草的 `lightmap02` 图片内容相同，语义仍是本模型原占位名字经原包顺序选中的默认图片，没有改名或借用别人的 DAT。

CPU 接口边界是文件存在、归档句柄、stream 查找、冷名字缓存、锁和已载模型指针；没有伪造纹理解码或 GPU 成功。新启动冷缓存分支已闭合，原热缓存、其它文件系统 provider、旧世界历史和原设备 GPU 仍未观测。图片所有像素恒定，因此直接使用原 UV1 与任意有限源 UV 变换像素等价；候选不猜运行中的旧 UV uniform。

## 候选与核查

`tools/selection_scene_grass_candidate.py` 导出 `analysis/raw/selection-scene-grass-20261115/v1/`，只新增 overlay 和一张原 PNG，模型和主图继续读取冻结基础 URL。

```sh
.venv/bin/python tools/selection_scene_grass_candidate.py \
  --base analysis/raw/selection-scene-candidate-20261115/v4 \
  --output analysis/raw/selection-scene-grass-20261115/v1
```

`tools/preview/selection_scene_grass_material.js` 提供 `createSelectionGrassAppend(THREE, overlay, {origin, lighting, json, texture})`；使用同一选角原点和区域 211 fresh-start 环境，卸载调用返回值的 `dispose()`。没有重写冻结基础清单或消除其原缺口记录；合并入口须显式接这个追加并防止重复实例。

四项 Python 检查通过：实际原空记录处理、原模型/ITM、原挂载与图片像素，以及前 178 个冻结载荷的 SHA。Node 检查一条实例的原 TRS、alpha/depth/culling、默认图、不套 DAT 和资源释放，通过；Node 本身不渲染 GPU。

随后用独立 GET-only 研究页实际验图：同一原相机、人物 TRS、区域 211 fresh 环境，组合 151 条静态摆放；研究页按钮切近景可见该原草木及正确透明裁切，console error/warn 为空。近景仅验收相机，不改变正式原相机。卸载后根节点移除，GPU 几何 74→73、纹理 130→129，无错误。原相机、近景、卸载截图和记录在本批 `browser-qa/`。临时 Chrome 页与端口 8924 已关闭，没有 Docker、游戏连接或存档写入。

六份候选合起来可提交验收的静态计数为 **43 模型 / 151 摆放**，覆盖这个明确的 25 地形窗口内所有原 type2 记录；这不是全地图、原真实驻留窗口、活动效果或最终原版整帧完成的声明。可复用规律是：**缺对象 lightmap 记录不等于缺模型，更不等于应删除模型。** 必须继续追原空记录 guard 和模型默认纹理的实际包选择。
