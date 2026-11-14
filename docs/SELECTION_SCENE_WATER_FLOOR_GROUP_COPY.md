# 选角水底材质：组代表复制纠正

2026-11-15。本篇纠正上一批floor-v4将“成员的合组后索引字段”直接视为最终材质的判断。v4原文件、载荷、工具和截图保留；本批只追加新命名空间，不覆盖旧文件，不改光照、几何、人物或存档。

## 漏掉的步骤

原 `355f28`建立分组后，较早加入的成员未必补满自身索引字段。随后 `3563dc`通过tile+`a0`成员顺序和+`a8`组边界找到组代表，对代表创建材质、请求五个贴图，再调用 `35127c`把材质绑定复制给其余成员。后者不写回成员的五个原索引字段。因此成员字段和实际绘制材质可以不同，不能靠字段是否相同判断最终绘制。

本批重新运行9个地块的原分组，直接读取原输出的成员顺序/边界，并执行 `35650c..356524`取得实际传给 `3509c4`的代表指针；不是猜“取第一个看起来相似的区块”。152个湿区成员逐一与实际代表核对水位、衰减、RGB、打包颜色和启用状态，全部相等，故不需要改水参数或颜色表。

| 原地块 / 成员区块 | 实际组代表 | v4成员索引 / 宏 | 实际材质索引 / 宏 |
| --- | --- | --- | --- |
| `[-39,-3] / [3,2]` | `[2,2]` | `[1,-1,-1,-1,-1]` / 1 | `[1,2,-1,-1,-1]` / 3 |
| `[-39,-3] / [4,2]` | `[2,2]` | `[1,-1,-1,-1,-1]` / 1 | `[1,2,-1,-1,-1]` / 3 |
| `[-40,-2] / [0,1]` | `[0,0]` | `[1,-1,3,-1,-1]` / 5 | `[1,2,3,-1,-1]` / 7 |

这两份原TRN中的材质1是 `whitepike/whitepike_soil08.tga`，材质2是 `cliffside/cliffside_snow01.tga`；后一地块的材质3为 `whitepike/whitepike_grass03.tga`。完整源路径与原CRC/SHA证据留在私有报告。所需PNG已经存在，不新增美术或贴图。

## 实际复制与执行边界

同一原ARM64样本SHA256仍为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

- `35127c`完整原CPU执行：复制effect指针+`68`、颜色表指针+`88`及五个绑定字节+`9c..a0`，原引用计数各从100增至101；成员索引+`50..58`保持。句柄和绑定编号是明确的受控CPU输入，不是原GPU加载成功或实际Android slot编号。
- `351690`静态消费原 `240dec0`指针表，顺序为 `texture1`至`texture5`，经原参数名查找调用材质纹理引用设置。原重定位后名字表重新读取核对；不声称完整加载器或GPU创建已执行。
- 原 `3563dc`的顺序是：按原列表选代表，`3509c4/350f6c`建立效果和水参数，循环五个原索引请求纹理、调用 `351690`，再经 `35127c`复制给组内其他成员。完整原函数仍依赖资源完成与GPU，未把本批有界CPU片段称为原完整帧。

既有网页factory按最终索引/宏和水参数建立材质，已能表达这次复制结果；相同颜色表URL在factory内共用同一个采样对象。因此本批只供应正确材质输入，保持旧factory与全部shader原样。复制所有权的原对象生命周期与网页对象管理继续明确区分。

## 验收与画面边界

5项Python检查通过，包含原组列表、152个水描述、完整复制、原uniform名表和旧213载荷逐SHA保持。Node使用未改factory分别构造v4与纠正profile，核对三个实际绘制组的宏/五个纹理URL、水参数、共享颜色表；9块的全部顶点属性、三角面集合和border保持。

实际Chrome/WebGL2仍组合原人物相机/TRS、211 fresh、151条摆放、192干地、152水面与湿区。三个材质所在绘制组均记录实际draw，运行时绑定为宏3/3/7及上述源PNG；console和页面错误均为空。原相机与三个源位置近景已保存，研究A/B比较显式固定特效时钟为0，正式游戏时钟没有改变。

本轮近景截图的旧/新像素没有可见差异：128水位两格当前遮罩及采样没有形成屏幕差异，135格研究机位被原建筑/树遮住。不能把材质来源纠正夸成明显画质改善，也没有隐藏原建筑来制造对照。这里的通过是源绑定与实际绘制一致；未证明每格无遮挡原客户端像素。原缺失天空、完整活动/驻留、动态LOD和原Android资源完成仍保留缺口。

两版候选卸载后GPU几何103→87、纹理163→144；研究页关闭，8924静态服务停止，没有Docker、游戏服务器连接或存档操作。

## 独立追加与正式接线

唯一新增载荷：`analysis/raw/selection-scene-water-floor-groups-20261115/v2/assets/source-selection-water-floor-groups/overlay.json`。其中shader、颜色表、地形、遮罩、原图集仍引用旧URL。

沿用原接口：

```js
const profile = await json('/assets/source-selection-water-floor-groups/overlay.json');
const wet = await createSelectionWaterFloorAppend(THREE, profile, {
  origin, lighting, json, text, texture
});
scene.add(wet.root);
```

profile保持旧factory格式，增加 `nativeGroupRepresentativeMaterials: true`、`priorFloorV4SHA256`、`correctedMaterialGroups`和`groupCopyEvidenceSHA256`。正式入口应由根代理用新manifest具名路由到它；旧v2 manifest与旧载荷保持。不要覆盖v4 namespace或修改shader，也不要把本次结果直接套到tutorial/map5。

复跑：

```sh
.venv/bin/python tools/selection_scene_water_floor_group_copy.py --output analysis/raw/selection-scene-water-floor-groups-20261115/NEW
.venv/bin/python tools/selection_scene_water_floor_group_copy_tests.py
```

Node检查参数依次为新候选、旧floor-v4、selection基础候选、已安装Three模块、211 fresh输入JSON。新素材包、逐文件SHA、GPU报告和交接均在专属raw根目录；完整源数据、GLSL、截图不上传GitHub。当前子代理未提交、推送或部署。
