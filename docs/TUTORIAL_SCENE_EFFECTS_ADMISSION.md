# 默认地图应加载哪些场景特效

不能把原包内 92 条场景特效一律显示。按用户指定的原 APK 默认配置，实际执行原查表和准入后，65 条准入，27 条被原分支拒绝。本轮未修改画面。

原 `bdaeConfig.xml` 给 `scene_fog003`、`scene_sun_light_line_purple`、`scene_cold_light_spot` 和 `scene_crystal_blue` 四组配置 level 5，共 27 条。原 APK 默认 `DeviceLayer=4`；原 `4cb934` 查表，再在 `a61abc..a61ac0` 比较，5 大于 4，于是跳到拒绝分支。虽然这些效果的原文件、贴图完整，也不能强行接回默认地图。

已有 43 条 `scene_fire_smoke` 属于准入组。剩余 49 条可分为：

| 范围 | 数量 | 接下来怎么处理 |
| --- | ---: | --- |
| 原默认分支拒绝 | 27 | 保留原资料，不强制显示 |
| 准入且严格解码完整 | 19 | 按组继续恢复，先做 10 条 `scene_fire` |
| 准入但解析有明确缺口 | 3 | 2 条 torch 的 JPG 依赖、1 条 sunshine001 的 timing，继续留缺口 |

这些结果不是来自效果名字猜测。`tutorial_scene_effects_admission.py` 从原 APK 取配置，通过原配置更新/层级钳制、原 level 查表和 92 次原摆放准入核查，与之前审定选择逐项相同。原 JSON/XML 的解析结果作为明确输入；原解析器、工厂成功和 GPU 没有执行。真实 Android 会话、保存设置与下载覆盖仍未观察，因此只称原 APK 默认条件分支。

完整原表、每条位置、源文件 SHA 和执行结果留在 `analysis/raw/tutorial-scene-effects-20261114/admission-v1/`，不上传 GitHub。原 43 条候选、存档、共享部署和生产服务保持不动。自动任务 2 仍暂停。
