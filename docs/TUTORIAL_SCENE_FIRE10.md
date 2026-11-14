# 新手地图：10 处原纯火焰

这是 92 条场景特效中的下一独立分支，接在 43 处火焰烟雾候选之后。10 条 `scene_fire.beff` 全部通过原 APK 默认准入；没有强行显示另外 27 条 level5 效果。

## 原文件与原指令

- 原 BEFF SHA256：`fafd102871041292cc12f8c836fa5e2ed2fe07e8b9c131308ab3c7c61105e5cf`。10 条原摆放分别从其 AITM 读出；原 `a61ae8` 专用对象构造、`a62958..a62a78` 请求参数段均实际执行，原模型名、位置、四元数和缩放逐项相等。
- 原 `bdaeConfig.xml` 给该模型 level2；原 APK 默认 `DeviceLayer=4`，原查表/准入结果是 10 条全部允许。各条 phase 字段都是 `ffffffff`，没有补服务器活动状态。
- 两张原图 `fire01_6x6.tga`、`fire03_xulie4x4.tga` 齐全，与第一组使用相同源图。两个原点发射器材质序号 `[6,6]`，对应原 `EfflibEffects.bdae` 的加色材质；原 `fogRate=0`，没有新增光源或全局雾。
- 原发射器形状/档位的早段消费 `eb3f58..eb3f84` 也已实际执行：形状写入 `[0,0]`，最低发射器档位写入 `[1,0]`。原 `GameOptions.json` 的默认 `EffectDetailLevel=2`，原库该档位全局初值也是 2。显式质量 0 的对照会阻止第一发射器更新，质量 2 会进入首发；不能只凭原图存在就跳过这一门。
- 两个发射器都是第 0 帧开始、时长 -1；原 `e8ed28 → e907a4` 的默认累计、首发和首发标志清除实际执行。对照增量 `16.9 / 16.9 / 33 / 100 / 2001` 得累计 `0 / 16 / 49 / 149 / 182`。复用前批已核的默认帧钟，不设周期重启。

原库仍固定为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。完整源表、坐标、材质引用、原字节 hash 和执行轨迹在私有 `fire10-candidate-v1/audit.json`。原粒子分配、完整 I/O/GPU、随机序列和音频播放不冒充已恢复。

这里的 level、DeviceLayer 和发射器档位是画质加载条件，**不是角色站在哪一层楼**。地图位置仍由原世界 TRS 决定。文件规律也分开：AITM 管摆放和请求，BEFF 管依赖、发射器与曲线，材质序号回到 Efflib 的原有顺序；无界发射时长、曲线自己的循环标志和资源重新启动是三件事。

## 独立运行与附加包

新 `source-scene-effect-fire10-runtime.js` 接收原 10 条数据，使用已有粒子模拟/着色器和冻结的默认时钟。原坐标仅减现有网页 origin；随既有 sourceArchiveWindow 按原 tile 显示，隐藏保留并暂停，再入继续；彻底卸载清自身对象，新加载从 0 开始。首窗尚未存在时等待。诊断最多每秒一次，明细只在检查接口请求时生成，不加游戏说明界面。

此模块与第一组分开，前批 13 个冻结文件不改。`source-scene-effect-fire10-overlay.mjs` 在第一组 overlay 之后追加 `stageFire10Entry`；后台资源计划追加 `stageFire10Plan`。原 critical/background 成员、战斗、移动、物理和存档不改。

部署准备副本的两处接线：

1. 显式复制新 `tools/preview/source-scene-effect-fire10-overlay.mjs` 到部署准备上下文，然后在原 43 处入口 overlay 后，仅当存在 `FIRE10_MANIFEST` 时调用 `stageFire10Entry(entrySource)`。
2. 资源计划已加原 43 处计划后，再调用 `stageFire10Plan(plan,texts)`。新增 6 份资料均为 background，运行 JS 通过正常 import 闭包预取。

`tutorial_scene_effects_fire10_delivery.py` 以冻结的 43 处完整私有候选 SHA `5301671ce7be5016e3b6e8205c3279599d98826d377a552b8e1609ffac15983e` 为底，追加 9 文件，2868 原成员逐项核对且不替换，原 127 身份保持。`audit.json` 不在 public 或运行迁移包里。

复跑：

```sh
.venv/bin/python tools/tutorial_scene_effects_fire10_tests.py -v
.venv/bin/python tools/tutorial_scene_effects_fire10_delivery.py --output analysis/raw/tutorial-scene-effects-20261114/new-fire10-append.tar.gz
.venv/bin/python tools/tutorial_scene_effects_fire10_delivery.py --output analysis/raw/tutorial-scene-effects-20261114/new-fire10-complete.tar.gz --complete
```

本分支是可供正式入口继续验收的原位置候选，不是整图完成。首批 43 与这批 10 共 53 条；余下可准入且严格解码完整的还有 9 条，另有 3 条明确解析缺口和 27 条原默认拒绝项。原服务器缺口、原随机序列与音频依然单列。没有修改生产、存档或自动任务 2。

实际浏览器使用新运行模块：先等 60 帧显示窗，随后原摆放 `684473416` 可见自动火焰，1 个着色器程序、20 次绘制，console warning/error 为 0。移出显示窗 3008 帧后累计仍为 90909 ms，重入继续到 91133 ms。该独立检查相机不作为游戏相机；记录和截图在 `fire10-browser-acceptance.json` / `fire10-browser.png`。正式 43 处入口再叠加本组已实际生成并通过语法核查，原职业热栏等代码保留；完整地图走动与双连接由父任务继续验收。
