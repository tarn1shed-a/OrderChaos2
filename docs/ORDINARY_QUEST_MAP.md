# 普通任务 461 的原地图上下文

本批服务于用户已授权的普通任务兼容执行层，不把自建执行规则称为原服务器源码。地图数据与兼容任务规则分开。

## 原地图对应

- 原 `map_info` 的地图 1 名称是 **Heaven Landing**，文件为 `world/dawnwatch.wld`。地图 2 名称才是 Dawnwatch，指向当前资源缺失的 `world/dawnwatch_2.wld`。不能根据目录名把这两张地图混为一张。
- 地图 1 原 `ori_teleport_spot=20`，关联 `teleport_spot` 的 `origin_heaven_landing `，坐标约 `(-234, 2.43, 40.8)`。这是原表入口参考，不等于已核清首次创角出生条件。它不在本批四块范围内，本批没有据此修改任何角色。
- 任务 461《第一印象》所用 NPC 2079 的原摆放为 6598，位置约 `(-6.34581, 1.20355, -226.035)`。原物件 467 在地图 1 有 11 条 phasing 0 摆放、另有 3 条 phasing 2 摆放。普通任务上下文采用前者，保留后者条件，不混入。

## 本批范围与工具

`tools/ordinary_quest_map.py` 只导出原四块：X 为 `-1, 0`，Z 为 `-5, -4`。覆盖任务 NPC 和全部 11 条普通齿轮摆放。这里是显式四格兼容窗口，不声称原客户端同时驻留范围。全地图、原出生流程、剧情任务 202 不属于本批。

导出器复用原 ATIL/AITM/BDAE/PHY 读取器，原地形遮罩消费与完整 `355f28` 合组、`35650c` 组代表选择，以及已实跑 `35127c` 材质复制契约。最终 sampler 与宏取组代表，不能只拿剪枝后的 effectiveIndices 代替最终材质。所有图集记录、模型、纹理都来自 dawnwatch 自身请求；未借用 tutorial 或 selection 的资源。

本批原 `EntityConfig.xml` 的 Item 与 Object 为空，Npc 有自己的记录。`bdaeInstanceConfig.xml` 的原一条 ID 档位覆盖及全局 `bdaeConfig.xml` 送入既有原 CPU admission。模型节点矩阵、材质剔除和 alpha 保留原消费，解码 PNG 与 Three 材质是浏览器技术接口。

```sh
.venv/bin/python tools/ordinary_quest_map.py --output analysis/raw/自选新目录
.venv/bin/python tools/ordinary_quest_map_probe.py --candidate analysis/raw/自选新目录 --output analysis/raw/自选新目录/native-movement-verified.json
```

原素材与完整数据只写忽略目录。公开工具不包含模型、纹理、完整原表或存档。

## 可接接口

候选目录中的 `assets/source-ordinary-quest-map1/manifest.json` 引用独立 terrain、terrain-materials、terrain-lighting、collision、environment 与模型/纹理载荷。

`tools/preview/ordinary-quest-scene.mjs` 导出：

```js
const world = await createOrdinaryScene(THREE, {
  scene, renderer, json, texture, origin,
  manifest: '/assets/source-ordinary-quest-map1/manifest.json'
});
// world.root / world.lighting / world.instances / world.update() / world.dispose()
```

json 和 texture 是现有资源读取接口；origin 是宿主坐标桥，不改原世界坐标。模块不创建角色、任务规则、账号、网络连接、存档或调试 UI。任务 NPC 和物件由独立人物/任务模块接入，可共用返回的 lighting。

collision 的 `sourceFiles` 将原 PHY 路径映射到候选目录下私有文件及 SHA256。可直接供 `SourcePhysics.load_world` 的 `read_source` 回调使用。其 terrainLighting 的 runtimeFlags 取该地图原 TRN，不能借 tutorial 的水标志。现有宿主逻辑坐标 frame 可由上层在独立配置副本提供，不属于原地图或出生点证据。

## 光照界限

区域 3 是地图 1 的原基础区，任务核心位于原子区域 9 的矩形范围内。environment 只采用原 3/9 表值、原强度回退规则和真实 `TempleAmbientProbe` RGB 生产者输出；额外 RGB 项显式为零。它是兼容层初始化到原静态目标，不声称恢复原启动时钟、实时天气、全地图 polygon 区域选择或完整原帧。没有另建灯、手调亮度或套用神殿/选角参数。

## 实际核查与缺口

当前候选四块共有 540 条原摆放，其中 530 条 type2 静态、10 条 type8 效果；70 个静态模型全部可解几何。现有材质消费者可实际绘制 56 模型、371 摆放、469 个材质部件。其他 14 类材质保留具体缺口，不用通用材质顶替。

38 份原 PHY、113 个摆放、155 个 shape 已装入原 CPU 查询。NPC 与全部 11 个齿轮位置均在可用干地格，实际执行原支撑查询，并从 NPC 附近连续向南走 30 步约 4.8 米。支撑高度是检查结果，不回写原摆放 Y，不更新用户角色。

原四块另有以下明确缺口：

- `texture/tiles/textures/grass03.tga` 在 `(0,-4)` 的 24 个干地 chunk 被最终材质实际引用，但当前资料缺该文件。
- `gravel01.tga` 在 `(0,-5)` 的 4 个水区 chunk 实际引用，当前资料缺文件。缺失的 grass04/mud02 等原索引在本批已被原遮罩剪掉，不应全部误报为实际画面缺纹理。
- 110 个原水区 chunk 的水面/水底没有在本批接入；10 条效果、14 类特殊装饰材质及天空也没有冒称完成。

缺必需贴图的 chunk 只略过绘制，独立列出 sourceResourcePending；原 nativeFlags、碰撞和地形数据保持。NPC 与 11 条普通齿轮所在 chunk 均不属于上述缺纹理块。外围蓝色空洞仍是已知未完成内容，不能把截图或任务核心可行走称为整张地图完成。

独立 Chrome 静态页已实际编译绘制 8 个 WebGL program，检查 NPC 区与齿轮区两种明确 QA 镜头，console error/warn 为空；随后执行卸载并关闭页及 8946 服务。QA 画面与说明只留忽略目录，不进正式游戏界面。本批未执行生产部署、未改变任何存档。
