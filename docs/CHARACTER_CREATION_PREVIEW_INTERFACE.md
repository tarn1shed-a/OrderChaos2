# 原创角人物预览：最小接线接口

2026-11-14。独立提案模块是 `tools/preview/character_creation_preview_proposal.mjs`。不自动修改 `deploy/entry_ui.mjs`、服务器创建检查、角色列表或游戏存档。

## 可接入的范围

当前 `entry_ui.mjs` 的 `race()` / `update()` 已有网页草稿 `draft.race`、`draft.gender`，人类为 0，男为 0、女为 1。仅在原选种族界面用这两个字段选择已验收的私有候选；**这不是新的可玩角色支持开关**。`entry_manage.mjs` 对实际创建是否已支持的校验必须保持，不能仅因预览有模型而放行创建。

当前接口只识别人类男/女。其他组合返回 `null`，原有精灵女性游戏加载路径继续由主线单独管理，不把此候选列表当作全部已支持角色种族表。

原 male display2038 与 female display2045 来自原创建控制器的选种族阶段。它们不能被当作已有角色的保存外观，也不能在进入职业、外观编辑或游戏时继续假称为这些阶段的原显示。职业、外观阶段的原 display 已另行记录，尚需各自组装和验收。

## 调用方式

主线提供已存在的 Three.js、原材质承载函数以及私有素材目录，随后把模型加入自己的原选角场景：

```js
import {loadCreationRacePreview} from './character_creation_preview_proposal.mjs';
// createNPCMaterial 来自已有 source-npc-material.js；名称不决定角色是 NPC。
const preview = await loadCreationRacePreview({
  THREE, createMaterial: createNPCMaterial,
  baseURL: '/assets/source-creation-human-male/',
  race: draft.race, gender: draft.gender,
  signal: abortController.signal,
});
if (preview) originalCreationScene.add(preview.root);
// 原预览显示期间，每帧调用；没有原服务器时钟假回包。
preview?.update(deltaSeconds);
// 切换种族/性别、离开该界面时：
preview?.dispose();
```

`baseURL` 必须以 `/` 结尾。目录中保持候选 `manifest.json`、`assets/character.json`、哈希 PNG 的相对关系。候选原路径 `/assets/...` 会相对这个目录解析，避免错误请求正式游戏的另一个 `/assets` 根。已有资源前缀若不同，主线可只改 `baseURL`，不修改角色 JSON 或原纹理。

调用者应在每次 `race.update()` / 性别变化时取消上一加载，销毁旧模型，确认仍在相同种族/性别再挂入场景。模块识别 `AbortSignal`，但 Three.js 图片下载本身没有被伪称为能撤销；迟到的纹理会被销毁而不绑定到旧角色。

模块不创建 DOM、CSS、相机、背景、图形按钮或文字，不决定模型在页面的位置、大小。主线沿原场景节点、原镜头和原 UI 的叠放关系承载，不另造创角布局。中性灯光及审阅相机不能因此冒充已恢复的原选角场景。

## 依赖和索引

- 三维数据是既有 `bdae946-character-v1`，包含 `meshes/materials/rig/clips`，骨骼来自各自原种族性别，不能用男性骨架替换女性。
- manifest 的 `materials` 只包含实际显示材质，`entry.index` 是模型原材质索引。接口创建长度等于 `data.materials.length` 的稀疏数组，**不按 manifest 数组下标重新编号**。所有 `groups[].material` 原值保留。
- `createMaterial(THREE, entry, samplerMap, manifest.colors)` 复用既有原调色板公式承载。每个 sampler 都有独立寻址状态；纹理保持 `flipY=false`、原数据色域承载。相同纹理冲突寻址会拒绝，不默默覆盖。
- `visibleMeshIndices` 已由原部位替换和双计数遮挡消费产生；接口不再猜身体遮挡，不给模型补衣服。
- 原 idle 的轨道值和节点绑定保持；浏览器时钟/Three.js 蒙皮是明确承载边界，没有原 GPU、模型完成回调、账号或服务器属性的成功假值。

`checkedCreationPreview` 校验格式、race/gender、`createdRole=false`、`initialServerAttributes=null` 和不重复的材质索引。返回 scope 固定 `createsPlayableRole=false`、`grantsEquipment=false`、`writesCharacter=false`，供主线防止把可见候选当作创建授权。

接口检查在真正的 Three.js CPU 场景中组装原候选、按原材质索引建网格、推进原 idle 并核对实际骨骼变化；另检查不支持种族、错格式、创建/属性伪状态和重复材质索引均拒绝。完整 WebGL 画面仍由各候选的实际浏览器验收覆盖，不能把 CPU 组装测试称为 GPU 像素等效。
