# 任务227鳄鱼：原骨架、相机附件和蒙皮

鳄鱼原模型没有缺骨。旧绑定检查工具因 `Bip01-node` 子树带有 `Camera01` 附件，跳过了整棵树。这是工具的范围限制，不能据此删掉源节点或填单位矩阵。

本批保留原37个节点及全部附件，实际执行原节点构造、27骨查找、属性setter、世界矩阵、调色板和1,266个顶点的位置运算。没有创建游戏怪物或GPU资源，没有修改共享读取器、游戏、存档或服务。原怪物出现、战斗、击杀、掉落和任务批准仍是独立问题。

## 原文件与实际调用

原模型为 `model/npc/creature/beast/crocodile/crocodile.bdae`，SHA256 `7fbf80b869a1b75a11cc29e8151a3cf4318567813d27bd84271c3cf5099593fd`。原动画为同目录 `anim/animations.bdae`，SHA256 `613cbe7a7fe3aaa5ece10e00f8b18280ac20da77f6cdd67ae9a450bc44d21f9b`。ARM64库SHA256 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

原模型相机表（section124）数量是0，但骨架中仍有 `Camera01-node` 及其 `#Camera01-camera` 引用。实际执行完整 `111dae0`，kind1由原表 `1f2ea94` 派发到 `111dffc`；`111e014`读取相机数量，`111e020/111e024`在数量小于1时转到 `1120978`。这个原分支保留并构造普通的Camera01变换节点，节点实际vptr与Bip01相同，均为 `2460890`。

明确提供的原资源工厂vptr `2416430` 的virtual150槽重定位到 `112b580`；原函数确实分配相机对象并调用 `1113fd4`。但本模型的相机表为空，实际未进入这个工厂，也未调用相机登记 `118455c`。本批不把“普通Camera01节点已构造”写成“相机资源已创建”，更不补成功返回。

原 `Bip01-node` 和 `Direct001.Target-node` 两根完整构造。独立的 `Object007-node` 含kind2网格附件，本批保留其原记录与附件，但不请求网格/GPU对象。绑定需要的27根骨骼全在已构造树内。原 `117c40c → 11985fc → 119c21c` 完成控制器解包及骨名查找，27个实际world指针均非零，逐个等于对应原节点地址加 `0x28`；原逆绑定矩阵逐值相同。

## 实际数值对照

复用[上一批原动画取样](ORDINARY_CROCODILE_ANIMATION.md)的44属性输出，不重做压缩取样器。选择原待机范围内三个既有时间点，实际调用每个属性对象的virtual98 setter（包括祖先Bip01和Camera01），随后执行原 `1362320` 更新世界矩阵、`11990b8..119912c` 调色板循环，以及原 `119bd7c` 位置散射。散射所需每骨影响列表由原关节和浮点权重明确转为宿主输入；没有把宿主顶点计算结果写回原CPU输出。

| 原绝对毫秒 | 27骨调色板最大误差 | 全1,266顶点位置最大误差 |
| --- | --- | --- |
| 34993 | 2.35744e-7 | 3.11024e-7 |
| 35123 | 2.17779e-7 | 3.45341e-7 |
| 36600 | 1.67161e-7 | 3.13080e-7 |

静止姿态调色板最大误差为1.88538e-7。比较阈值仍为0.002。每顶点原4个权重是float32，不是字节权重；导出后重新打包与原字节完全相同，4个关节编号也逐字节保留。没有归一化、重写逆矩阵、换姿势或改源动画范围。

## 可复用的数据和边界

忽略目录 `analysis/raw/ordinary-crocodile-binding-20261116/rig-final-v1/descriptor.json` 是入口：

- `source-model.json`：已有BDAE读取器的原结果，含原网格/材质引用，不添材质。
- `rig.json`：37个源节点、27个骨索引、原逆绑定/形状矩阵、1,266×4个原float权重及关节编号；四元数为XYZW，矩阵为列主序、Y向上。
- `finite-poses.json`：仅三个已核时间点的原44属性、原调色板和原位置输出，可供渲染接线作固定对照。它不是新插值器、连续动画片段或自动播放规则。

研究接口 `binding_type()` 返回独立原CPU探针；沿原 `prepare_animation(reader)`、`sample_case(absolute_ms)`、`apply_original_samples(case)` 可继续消费自己的原控制器与属性。需要传入固定原文件、原源时刻及现有明确资源/流/分配宿主接口，不内置怪物活动、游戏时钟或任务状态。本批固定对照只覆盖idle；walk范围虽已由上一批原时钟确认，整段取样及实际怪物动作请求仍未在本批验收。原GPU最终绘制、材质及实例变换也未在这里验收。

完整CPU报告为 `cpu-final-v1/binding-v1.json`，原节点/27骨指针与逆矩阵见同目录 `construction-v1.json`；相机静态派发及重定位见 `camera-source-final-v1/source-v1.json`。原ASM、源数据、旧失败记录及可校验资料包均只留忽略目录。公开仅新增本工具、检查和本文，不修改上一批工具。

早期独立尝试曾误要求相机工厂必须执行，后被原空相机表和实际控制流纠正；另一次名称判断失误进入网格路径后停止。失败记录保留，均不当原游戏失败，也不以补成功返回修过。

## 复核

```sh
PYTHONPATH=tools .venv/bin/python tools/ordinary_crocodile_binding_tests.py
PYTHONPATH=tools .venv/bin/python tools/ordinary_crocodile_binding_tests.py --public-only
```

本地8项通过；公开环境只运行导入边界检查，其余7项明确跳过。检查会独立比对原权重字节、节点附件、27骨指针/逆矩阵、三个原姿势的全部位置输出、错误证明拒绝以及旧文件SHA。有限CPU实际执行已在报告中记录，检查不重复原220次取样。

完整新CPU运行可用 `tools/ordinary_crocodile_binding_probe.py --output analysis/raw/ordinary-crocodile-binding-20261116/<新目录>`；已有目录拒绝覆盖。导出需 `--export-rig <新CPU报告路径> --output <新目录>`，不再次运行原CPU。原资料不齐时不生成替代骨架。
