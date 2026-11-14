# 入图调用者的朝向和相机后续

2026-11-14，承接已冻结 [重新入场状态核对](TUTORIAL_REENTRY_RESET.md)。本批另增独立探针/检查/本文，未修改上一批文件、共享运行、存档、原 127、地图或线上服务，自动任务 2 仍暂停。

**原入图在设置 XYZ 后还会处理朝向和相机。但这两段改的是面向方向、相机水平角，没有清运动速度，不能把它们误叫作“清下落”。** 仍没有收到真实原服入图/脱出包。

## 原来源和实际执行

原库 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。复用已有 `a34f28` 原 GS2C_EnterMap 调用者指令，不重做整段入图。

| 原范围 | 本批核对 |
| --- | --- |
| Hero 原虚表 `24228a8 + 40` | ELF relocation 确认实际目标 `a2b7d8`；不是移动向量 setter `a2ba0c`。 |
| `a356d0..a3571c` | 实际读取解码 location.direction，再经该虚表调用。记录真实消费入口收到 W2=`0xffffffff`、W3=0；执行完整 `a2b7d8`。 |
| `a2b7d8` | 536 字节，原字节 SHA `3d0c3eddfda0beb7a61ca8ec3417d2f3f34b4d0581fe0180378d60145d5bc9da`。更新 actor+140 / +174 朝向向量及 +188 / +18c 朝向角；运动 direction 在 motion+0c，二者不同。 |
| `a3574c..a35814` | 读取同一 direction，原数学代码生成相机 yaw，写 camera+68 / +18c dirty / +2a9；停止在后续 UI 调用前。没有手算角度再写回代替原代码。 |

两段是**分别执行的原片段**。中间 e20 特殊状态清理、UI/配置以及条件 `a0de1c` 未执行，不把它们拼称完整帧。输入 direction、已加载静态容器和正常 Hero 是显式夹具；`atan2/atan2f` 仅用标准 libc ABI 宿主数学接口。没有伪造协议解析成功、活动状态或相机完整构建。

## 三组原 CPU 结果

仍使用 139 份原 PHY / 2827 形状。先实际执行神殿下落或原潜水，再完整调用 `9037d4` 将位置改为已授权网页 w7，最后执行上述两段。

| 显式 direction | 原朝向归一化后 | 原相机 yaw | 相机 pitch |
| --- | --- | --- | --- |
| `(0,0,-1)`，实际下落中 | `(0,0,-1)` | `0°` | 保持 `355°` |
| `(1,0,0)`，实际潜水后 | `(1,0,0)` | `-90°` | 保持 `315°` |
| `(3,0,4)`，实际潜水后 | 约 `(0.6,0,0.8)` | 约 `-143.130096°` | 保持 `315°` |

各组 motion 方向、speed、加速度与竖直速度在这些调用前后逐字段相同。下落组仍约 `-17.675`，潜水组仍约 `-3.394113`。这支持上一批区分：原朝向/相机处理不是网页 worker 的缓存实体复位；完整 EnterMap 其它分支是否进一步处理仍需单独取证。

它也不意味着脱出应强制套用某个消息 direction 或重置玩家镜头。实际 direction 尚无原服包；不能用本批三个测试向量写入游戏。父任务现有重连运输方案仍需真实浏览器检查，原逃生目的地/回执仍未知。

## 复跑和范围

```sh
.venv/bin/python tools/tutorial_reentry_reset_caller_probe.py \
  --output analysis/raw/tutorial-reentry-reset-20261114/caller-unique.json
PYTHONPATH=tools .venv/bin/python -m unittest tutorial_reentry_reset_caller_tests -v
```

4 项原 CPU 检查：真实虚表消费/速度保持、原相机 yaw/pitch、片段边界与声明、源指令和碰撞集身份。无分析依赖的干净环境导入不需要 NativeImage，私有 4 项明确 skip。

完整指令、源哈希和报告留忽略目录 `analysis/raw/tutorial-reentry-reset-20261114/`，不上传原资料。没有新界面、动作规则、假地板、假传送、存档操作或发布；不是整图/原脱出完成。
