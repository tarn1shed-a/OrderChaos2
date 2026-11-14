# 43 处火焰、烟雾：完成门和自动帧钟

本阶段继续第一组场景特效，不代表整图完成。独立验收模块与正式宿主接线分开：前批 `source-scene-effect-preview.js` 的 600000 ms 上限只是资源审阅保护；新运行模块不调用它的 `update()`，也不通过周期重启绕过上限。

## 原代码实际核查

`tutorial_scene_effects_lifecycle_probe.py` 实际执行固定 ARM64 库中的以下片段：

- 原基础变换初始化到 `1343154`，原效果局部初始化、原发射器构造到 `e8d244`，以及原 `eb40b4..eb4228` 对源文件 80 字节头的消费。全局驱动登记没有执行。三发射器原默认 `+294=0`、`+4c0=1`、`+38a=1`、`+200=0`、时长 `+374=-1`。基础变换标志本身来自原构造，不是手填“可见”。
- 原 `eb5104` 从原 BEFF 读取三个档位的发射量曲线，再由原 `e8b9dc` 采样；没有为首发写一个假的常量曲线。
- 原 `e8ed28` 接收帧浮点毫秒数，乘 root `+23c`（原默认 1），截断成整数；大于 2000 ms 的步长改成 33。第一次因 `+38a` 将累计保持 0，之后在发射器 `+200` 累加。原 `e907a4` 首次请求点粒子后清除 `+38a`。
- 三发射器逐一输入 `16.9 / 16.9 / 33 / 100 / 2001`，原累计都是 `0 / 16 / 49 / 149 / 182`；显式暂停输入下再过 500 ms 保持 182，恢复后 33 ms 到 215。首次确实进入原点粒子请求。几何缓冲、实际粒子分配和后续粒子几何仍是明确停止边界，未伪装成功。
- 数值边界另外实际执行：接近和超过 `2^32`、以及 `1e20` 的正帧增量，原 `FCVTZU W` 饱和到 `ffffffff`，随后原检查将步长改为 33；运行模块先比较再转换累计整数，不能先用 JS `>>>0` 把大步回绕。2000.9 的原截断结果仍为 2000。
- 原完成回调 `a5e5cc` 在条件已加载资源输入上实际执行：未取消时写完成标志并依次调用原位置、旋转、缩放 setter；取消时不调用 setter，并清 owner 的节点引用。setter 内部传播、资源 I/O 和原引擎 GPU 创建没有执行，因此这不是“原 Android 完整加载成功”。

更正前批研究键名：`time250` 只记录过 root `+250` 的初始数值 0，**它不是帧钟**。原析构 `eaf5f4..eaf60c` 会把该字段作为回调参数并清零。当前明确分开 root `+250` 回调参数、root `+23c` 时间比例、emitter `+200` 毫秒累计和 emitter `+294` 暂停门。前批文件保持冻结，不能据旧键名推断播放。

## 正式入口候选的接线

新运行模块 `source-scene-effect-runtime.js` 复用已有粒子模拟和材质着色器；三贴图、原发射器参数和 43 条原 TRS 全来自第一批私有候选。原坐标不重写，仅在外层 Group 减去现有网页 origin。

`source-scene-effect-clock.mjs` 只移植上述实际执行的默认时钟分支，不加入循环、天气或开关界面。宿主解码资源和贴图完成后，使用 `requestAnimationFrame` 的单调帧增量。此帧源属于浏览器适配，不冒充原 Android 的全局帧时间戳。原文件时长 -1 持续发射，不设置新的重启周期。

`source-scene-effect-overlay.mjs` 只接受已经使用 `sceneStages.present(windowChange)` 的现有入口；把新 Group 按原 tile 登记到同一 `archiveObjects`，并用当前 `sourceArchiveWindow` 的 resident 集合显示。原人物、战斗、物理和存档不改。

当前宿主保留隐藏的地图对象；本候选也保留隐藏特效并暂停累计，再入该显示窗时继续同一对象和时间，不重建或归零。完整资源卸载调用 `dispose()`，移除自身 Group、archive 登记和图形资源；新加载会从原默认 0 开始。这是与现有宿主缓存一致的适配，不能说原异步任务取消/销毁调度也已经完整恢复。

启动顺序检查实际执行现有 `createSceneStages`：没有 display 时 `present(null)` 返回 false；有完整窗时先写 resident 再返回 true。新模块也对异步素材先完成、resident 尚未存在的情况保留等待保护，第一帧有效显示仍从 0 开始。浏览器实际先观察 60 帧等待，再自动显示烟火，无错误。

部署入口的精确钩子：

1. 在 `stageEntry → stageInsideEntry → stageCharacterPanelsEntry / stageCharacterHotbarEntry` 之后按需调用 `stageSceneEffectsEntry(entrySource)`。
2. 该函数只在现有 `requestAnimationFrame(draw);sceneStages.start();` 前启动独立资源 Promise，不阻止进入地图；在原 `sourceWater?.update(now);` 前，用现有显示窗更新特效。其他帧函数保持。
3. 在原计划生成后调用 `stageSceneEffectsPlan(plan,texts)`，只把新增 7 份资源放入 background。原 critical、background 成员保留；运行 JS 随正常 import 闭包预取。
4. 运行素材路径 `/assets/source-scene-effects/`；3 份新 public 模块在站点根。证据报告、原表、反汇编和截图不进入 public 或游戏界面。

新 overlay 只提供候选，不修改共享 `deploy/prepare_delivery.mjs`。父任务需要在自己的部署准备副本加上述两处调用，完成正式入口、双连接及存档保全验收后再发布。

正式钩子每帧继续更新粒子，隐藏诊断快照最多每秒写一次，默认快照不分配 43 条明细。一次 Node CPU 测量（不含 GPU）中，原单 tile 200 次更新 p50 约 0.17 ms / p95 约 0.39 ms；强制全部 43 处可见的上界 p95 约 6.67 ms。因此保留当前真实显示窗门，不能用测试用“全可见”代替正式区块准入。完整地图帧耗时还须父任务正式入口复测。

## 私有包与核查范围

`tutorial_scene_effects_delivery.py` 只读基底 `oc2-runtime-character-panels-20261114.tar.gz`，固定 SHA256 `f1dc28154f890f3e3eccd39e927130e51daa693f215d8cd0936bbc4c063d4569`。2857 个原成员逐项校验；新增 11 文件，无原成员替换，原 127 文件身份保持。完整包仍是私有迁移素材，不提交 GitHub，也没有现有角色存档。

可复跑：

```sh
.venv/bin/python tools/tutorial_scene_effects_lifecycle_tests.py -v
.venv/bin/python tools/tutorial_scene_effects_delivery.py --output analysis/raw/tutorial-scene-effects-20261114/new-append.tar.gz
.venv/bin/python tools/tutorial_scene_effects_delivery.py --output analysis/raw/tutorial-scene-effects-20261114/new-complete.tar.gz --complete
```

检查涵盖原三发射器时钟/完成/取消、43 条原姿态、显示窗隐藏与重入、卸载和重新加载、超过 10 分钟的累计不抛错/不循环，以及追加包不替换旧文件。无 capstone/unicorn 的独立公开副本也需通过，原资源组在公开环境按明确条件跳过。

正式地图 43 处画面、原资源完整 I/O、原随机序列、原音频和完整原异步 manager 仍分别记录验收范围；不能把本阶段称为它们全部完成。余下 49 条、13 个 BEFF 组继续按独立分支排队。

本阶段已用实际自动帧在独立浏览器运行新运行模块：同一原摆放可见火焰烟雾，1 个着色器程序、35 次绘制；移出显示窗后绘制为 0，观察 3104 帧后累计仍保持 11836 ms，重入后继续到 12061 ms，未归零。总观察 4530 帧，console warning/error 均为 0。`runtime-browser-acceptance.json`、`runtime-fire-smoke-browser.png` 留在私有目录。该验收页的相机和检查按钮没有进入游戏。完整 f1dc28 基底的正式入口经过原有三层 overlay 后，也已实际应用新钩子并通过 JS 语法核查；正式场景走动、双连接和保存保全由父任务继续验收。
