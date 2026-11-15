# 任务227鳄鱼638：完整待机与行走动画

本批已导出原待机、行走的连续数据，保留全部44条属性、原相机轨道、分段、重复关键时间及其不同数值。不是将上一批三个有限姿势插值成动画。原压缩数值全部由原代码复制/解码，没有另写byte codec，没有修改旧parser或上一批有限姿势。

对象仍是原目标638的资源审阅，不创建游戏怪物，不决定何时待机/行走，不补战斗、掉落或任务批准。没有运行浏览器、服务或修改存档。

## 原文件和新的实际差别

原动画 `model/npc/creature/beast/crocodile/anim/animations.bdae` SHA256为 `613cbe7a7fe3aaa5ece10e00f8b18280ac20da77f6cdd67ae9a450bc44d21f9b`。沿用[已核原模型、27骨及权重](ORDINARY_CROCODILE_BINDING.md)，未改骨架或逆矩阵。原ARM64库仍为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

旧读取器在这份文件上还有限定之外的重复关键时间，例如第一段frame40连续两条，后段frame1098连续两条；许多重复时间对应不同原数值。因此不能按frame放进字典合并，也不能删除重复项后给Three普通keyframe插值。

原 `118a72c → 118a544 → 1109188 → 1108b74 → 1108354` 提供分段选择入口。本批只实际执行 `1108354` 中 `11083b0..1108438` 的原分段表查找片段，输入真实重定位资源表，停在引用计数/缓存/provider创建之前。这里的 `CMP/GT` 是有符号比较，原第一段起点 `0xfffffff9` 作为-7保留，不能按unsigned坏数据丢掉。

实际缓存时间还先经过原 `118a6a8` 的FCVTZU及 `118a6c8..118a6e8` 的有符号CMP/LT限幅。本批直接执行这两个原片段及原 `1112e0c` 读取真实range。负的行走起始时间对应缓存键0、分段0；属性取样仍使用原-7毫秒。缓存键和动作取样时间不是同一个值。早期适配器曾误读后段LT为unsigned，已按原寄存器结果纠正；该误读没有改变本批分段0的姿势输出。

原 `117c40c` 实际解包所选段。44条轨道的全部原时间键与相应数值顺序保留，其中Camera位置和旋转源描述仍是valueType0、3源分量。11,432次原virtual60调用取得原键值：Camera位置走 `1162568`，旋转走 `115c95c → 115cd58`，旋转得到原4分量，不在网页里猜编码或补四元数。

## 时钟、查键与实际检查

原 `1195f3c → 1196824` 的新鲜时钟，以及 `11962c0` 的推进/循环实际运行：

| 动作 | 原起止毫秒 | 时长 | 本批使用的原分段 |
| --- | --- | --- | --- |
| idle | 34993～36600 | 1.607秒 | 4、5 |
| walk_forward | -7～1333 | 1.34秒 | 0 |

range第三字原样保留：idle为35000，walk为0，没有改为新起点。原新鲜时钟速度1、循环字节1；本批真实检查其外部回调及事件接口为空，不推广到带回调/反播的活动控制器。恰好到end时保留end，下一次越界tick才回环，不能先用普通取模把end换成start。

源uint16帧使用原float32常量 `0x42055555` 转毫秒并取整，选键使用 `0x3cf5c290`；原四元数分支阈值为 `0x3d4ccccd`。`114afcc` 的缓存索引查找和 `114a61c` 的复制/插值分支已按这份数据机械转写，重复键不去重。Camera位置按原 `116243c` 的两边加权顺序，旋转沿原 `11dd664`；没有改用Three默认epsilon或额外归一化复制值。

25个原边界、中间、分段交界及循环时间，执行原44属性取样共1,100次，再执行真实setter/world/27骨调色板。另10个冷缓存、倒序和返回起点的边界执行440次原属性取样。JS独立模块按同顺序重放35个原CPU样本，全部通过。原重复键之外的片段也完整保存在数据中，播放接口只准这两个已核动作范围。

| 最大误差 | idle | walk_forward |
| --- | --- | --- |
| 属性 | 2.98024e-8 | 1.49012e-8 |
| 27骨调色板 | 2.38894e-7 | 2.80022e-7 |
| 全1,266顶点位置（各3次） | 3.13080e-7 | 2.90764e-7 |

容差仍为0.002，未放宽。两个JS实例交错取样不共用缓存，原源数组不被修改，错误来源、缺Camera、重复目标、未知插值调用及越界时间保持拒绝。

## 最小接入

权威数据入口是忽略目录 `analysis/raw/ordinary-638-animation-complete-20261116/cpu-final-v1/animation-v1.json`。只需新模块 `tools/preview/ordinary_638_animation_complete.mjs` 与该JSON，模块没有任何import依赖；模型/rig/六贴图沿用上一批父级已有资源，不替换旧文件。

```js
const clip = animation.clips.find(c => c.name === 'idle');
const sampler = create638ClipSampler(animation, 'idle');
const clock = create638FreshClock(clip);
const frame = sampler.sampleAbsolute(clock.tick(deltaMs).absoluteMs);
// frame.samples: 原44条 { node, type: 'position'|'quaternion', value }
```

调用者按原节点名将值写到既有骨架，再更新世界矩阵。`sampler.reset()`只清独立插值索引；每个审阅实例应拥有自己的sampler/clock。输入时间单位是毫秒。这里的新鲜时钟只用于明确的原资源审阅；实际NPC动作选择和世界时钟归后续原活动接线，不由该模块生成批准。

不要将44轨换成Three普通KeyframeTrack，不删除Camera轨道，也不再次normalize原复制的四元数。保留原37节点/27骨/原float权重，按既有rig的矩阵及四元数约定消费。此批没有GPU验收，不能单凭CPU通过就称原游戏已播放或任务已完成。

## 重跑与交接

```sh
PYTHONPATH=tools .venv/bin/python tools/ordinary_638_animation_complete_tests.py
node --test tools/ordinary_638_animation_complete_tests.mjs
PYTHONPATH=tools .venv/bin/python tools/ordinary_638_animation_complete_tests.py --public-only
PUBLIC_ONLY=1 node --test tools/ordinary_638_animation_complete_tests.mjs
```

本地Python8项、Node7项通过；公开Python1过7跳过、Node3过4跳过。检查重放原证明，不重新复制11,432个原值。

完整新原CPU运行：`tools/ordinary_638_animation_complete_probe.py --output analysis/raw/ordinary-638-animation-complete-20261116/<新目录>`。冷/热边界补件：同工具追加 `--edge-controls <本批animation-v1.json> --output <新目录>`，不再次复制所有键。已有目录拒绝覆盖。

全部原代码、数据、早期失败及可校验包只留忽略目录；以本批 `handoff.json` 和 `freeze-manifest-v1.json` 为准。此前已冻绑定/有限样本及原源文件共55个保护文件SHA保持。公开仅新增本工具、独立模块、两类检查与本文，未改共享运行或父级原采样工具。
