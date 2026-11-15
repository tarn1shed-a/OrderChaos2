# 872原默认人物资源候选

本批已将872的原Model32默认组合整理为可直接加载的独立资产：**116节点、16网格，其中原代码选出11个可见网格/1878三角形；5份完整材质、23张原贴图、原idle**。没有活动GUID、摆放、任务资格或服务器状态；浏览器/GPU由父级验收，本批未运行UI或服务。

## 原组合与复用边界

原链为appearance872→display852→Model32/Extra720，Face1、Hair1、Chest100009、Boots100012，其余已核部位/武器槽为0。四个原部件分别来自：

- `face_human_female_001.bdae`
- `hair_human_female_001_001.bdae`（内部原网格名仍为`hair_human_female_000_001-mesh`，未按文件名改写）
- `oc2_human_f_npc_villager_chest.bdae`
- `oc2_human_f_light_1_faith_feet.bdae`

复用前批同SHA Model32的12个base skin原CPU证明，116节点TRS、base几何、原逆矩阵和float权重逐值匹配；未复制旧玩家服饰。四个本NPC部件使用前批严格原skin结果。`merge_piece`只重定位mesh/material索引；遮挡重新执行原`CatalogVisibilityProbe`的部位绑定、feature替换和item Flags0/Flags1消费，未手填隐藏部位。

原可见索引为`[0,1,2,4,6,7,10,12,13,14,15]`。原代码仍保留base chest等网格，不因衣服外形推测遮挡再删面。

5份原材质均有完整六标量，无稀疏材质回退或新参数。Chest的原覆盖请求只改diffuse至`texture/oc2_human_f_npc_villager_chest_d.tga`，原normal/mask/palette保持；其原材质自带diffuse为elf_f路径，保留在来源记录中。原sampler寻址、FX双profile、宏、透明测试/剔除状态和两GLSL的SHA均核对。源声明sampler的覆盖应用用于网页资产候选，Android compiled reflection/异步cache时序仍未观察。

原idle为同SHA human-female动画束中的131 tracks、4.266666666666667秒，并复用旧原CPU证明。新接口只接受明确采样时间，不增加巡逻、转身、战斗、循环或交互动作政策。真实模型任务的异步完成未由本批产生。

SC Creature925原名为“卢西安哪”，任务正文写“露西娜”；原差异保留。profile.name是原本地化源串，未把它称为已执行872动态替换/最终演员名字发布。

## 可调用接口

权威候选：`analysis/raw/ordinary-npc872-candidate-20261116/candidate-v2/`。无需新建页面。其资源都在`/assets/source-ordinary-npc872/`，profile为该目录的`profile.json`。

现有2079 loader硬校验461/2079，不能伪装身份直接传872。因此本批新增一个872专用薄factory，复用已有NPC Three骨骼/网格适配方式，**材质builder由调用方注入**，不增加灯或重写公式：

```js
import {loadNPC872Assets} from './source-ordinary-npc872.mjs';
import {finalPairMaterial} from './source-npc-final-pair-material.js';

const assets = await loadNPC872Assets(THREE);
const npc = assets.createNPC872({
  materialFactory: ({THREE, record, textures, colors}) =>
    finalPairMaterial(THREE, record, textures, colors, 'source')
});
scene.add(npc.root);
npc.sampleIdle(0.5); // 明确审阅采样，范围0..idleDuration
// 最终：assets.dispose(); // 包含全部实例、材质、几何和纹理
```

也可注入父级现有原NPC材质builder；参数是`{THREE,record,textures,colors}`，需返回每实例独占Material。返回实例包含`root,bones,meshes,materials,geometries,sampleIdle,inspect,dispose`；多实例骨骼/材质独立，纹理采样克隆由assets统一拥有。重复释放安全，错误尺寸纹理/共享Material/释放后调用会拒绝。默认显示与世界落点、原演员可见资格相互独立，调用方不得由factory成功补出任务状态。

继续使用旧NPC审阅材质时保持其既有linear输出/NoToneMapping等查看器设置；该光照/Three渲染属于明确宿主适配，不是原Android现场。原位姿/颜色/贴图没有据此调色、补光或手调偏移。

## 核查与剩余

```sh
PYTHONPATH=tools .venv/bin/python tools/ordinary_npc872_tests.py
PYTHONPATH=tools .venv/bin/python tools/ordinary_npc872_tests.py --public-only
node tools/ordinary_npc872_tests.mjs --output analysis/raw/ordinary-npc872-candidate-20261116/new-three-check.json
node tools/ordinary_npc872_tests.mjs --public-only
```

12个Python来源检查通过；无私有资源时1通过/11跳过。重新导出全部候选成员逐字节一致。真实Three CPU宿主426断言通过：两个独立实例、4个idle时点，世界矩阵最大差约4.13e-7、palette约2.87e-7；错误纹理清理、共享材质拒绝、重复释放均通过。这不是GL编译、浏览器或实际演员验收。

下一步仅需父级用现有NPC查看器/场景相机实际核GPU图像、正反面、材质和释放。任务227仍有原活动/filter/掉物/查询批准与墓碑路线边界，本批资产不放行任务，不改游戏、存档、服务、Git或部署。
