# 任务227鳄鱼动画：原取样器与旧读取器的差别

本批核《抓鳄鱼》原目标638的动画资源，不创建任务或怪物，不改存档、碰撞、画面或服务器。原接取、杀怪批准、掉落及交回条件仍须分别核对。没有把原型野狼的战斗规则套到鳄鱼上。

原模型为 `model/npc/creature/beast/crocodile/crocodile.bdae`，外层SHA256为 `7fbf80b869a1b75a11cc29e8151a3cf4318567813d27bd84271c3cf5099593fd`。同目录 `anim/animations.bdae` 的外层SHA256为 `613cbe7a7fe3aaa5ece10e00f8b18280ac20da77f6cdd67ae9a450bc44d21f9b`。原ARM64库SHA256为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。原文件与完整报告只在忽略目录。

## 这次确认的内容

原属性管理器 `1103d9c → 1106f94 → 110749c` 选择44条属性。在待机的5个明确时间点，实际进入原 `1109aec` 共220次，所有输出为有限数。40条属性直接属于原skin的27个骨节点，另有2条Bip01祖先属性及2条Camera01属性。Bip01虽不在skin调色板名单中，仍是骨架祖先，不能随相机一起裁掉。

Camera01原值描述符的valueType为0、源分量数为3。原位置属性实际调用 `116243c/1162568`，原旋转属性调用 `115c894/115c95c`，分别经过原插值和复制路径。`1162568` 原指令读取有符号字节，再乘源缩放并加源偏移；不能把它当float流、无符号归一化流或直接套到四元数上。原旋转路径自行产生4分量结果。本批没有另写压缩解码器。

原 `1195f3c → 1196824 → 1196570` 实际读取原时段：

| 动作 | 原范围三个字的含义边界 | 原时钟实际起止 |
| --- | --- | --- |
| idle | 原字为34993、36600、35000；第三字保留，未改成起点 | 34993～36600毫秒 |
| walk_forward | 第一字位型为0xfffffff9，原时钟实际解释为-7 | -7～1333毫秒 |

这两个新鲜时钟的循环字节为1、速度为1；这只核时钟构造及绑定，不等于活动怪物已请求或自动播放该动作。待机在34993、35000、35123、35796.5、36600毫秒的原取样全部执行。首段覆盖的边界与源关键帧并不要求重合，不能为了旧30FPS读取器通过而修改范围。

## 旧工具为什么拒绝

冻结的 `bdae_animation.py` 仍限定已核的float值流、无负起点的范围及分段。本资源分别触发其channels、ranges、segments三处拒绝：两个Camera01值流不是float6，walk范围和第一分段的起始位型是0xfffffff9。旧拒绝不证明原文件损坏或游戏缺少动画。

本探针只选覆盖idle的正数分段并交给原取样器，没有重新解释第一分段的负数位型，也没有更改共享读取器。行走范围仅执行原时钟，未宣称行走整段取样已完成。

## 尚未接回游戏的部分

原模型的Camera01是骨架子树里的相机附件。旧独立绑定探针会跳过含附件的整个根，因而没有构造Bip01子树；这不是原骨缺失。本批绕开该探针，仅核原属性输出，没有伪造附件完成、节点setter、世界矩阵、调色板或GPU成功。下一步应单独核原相机附件的构造和骨架绑定，不能通过删源节点、放宽bind检查或补单位矩阵解决。

因此本批不作“鳄鱼已上线”或“227可完成”的验收。交回墓碑路线、原交互输入和掉落批准也是各自独立的未决项。

## 重跑

使用本机既有原资源目录和虚拟环境：

```sh
.venv/bin/python tools/ordinary_crocodile_animation_probe.py \
  --resources analysis/raw/ordinary-quest-neighbors-20261116/candidate-v2/original-resources \
  --output analysis/raw/quest227-parent-20261116/croc-native-review-new
.venv/bin/python tools/ordinary_crocodile_animation_tests.py
.venv/bin/python tools/ordinary_crocodile_animation_tests.py --public-only
```

输出限定在忽略的 `analysis/raw`，已有evidence不覆盖。7项本地检查实际通过；公开环境只执行不依赖原文件的导入检查，6项原资源核查明确跳过。分配、源字节流、字符串、锁及libm是已说明的宿主接口，属性选择、取样和时钟执行原指令；这不是运行原Android会话。
