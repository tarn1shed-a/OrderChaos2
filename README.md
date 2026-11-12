# 《混沌与秩序2》客户端离线逆向研究

研究对象为用户提供的 3.1.3a APK、原生库和资源文件，重点核对原始数据与代码的关系。解析与适配工具由本项目编写，没有原开发工程源码或原服务器源码。

自写网页客户端、服务器及玩法主体仍保存在忽略的本地历史预览，未冒充原开发工程或原服务器源码。原始资源、研究证据和私有存档保留，自动续跑保持暂停。

2026-11-13：按用户新的 MVP 授权，增加[独立本地试玩入口](docs/LOCAL_MVP.md)，复用已核对的历史预览，支持单人进入、当前两人展示、可配置人数及独立存档。原版资料和现有本地规则逐项区分；[精灵内衣叠穿修正](docs/DEFAULT_UNDERWEAR_RECOVERY.md)已通过本地与对应 CI。原资源/运行资料另供，不是 clone 后即有完整游戏。

2026-11-11 补充：按用户最新要求，已将[新手地图两个原配置条件分支](docs/TUTORIAL_ASSET_SELECTION.md)接到忽略目录中的隔离历史预览，并实际进入核对。受控仓库没有恢复旧游戏代码；雷电实际选档尚未取得，旧显示/玩法适配不当作原版恢复。新增工具只导出有原依据的资料绑定，缺失项不补，自动续跑仍暂停。

最新基准改为[原 APK 默认材质与光照](docs/DEFAULT_MAP_MATERIAL_LIGHTING.md)，不依赖设备选档。已核对原模型/UV/颜色图，纠正旧预览误用的 HDR/LUT 并接入原普通后处理着色文件；当前偏暗的主要阶段已定位，原环境状态及同位置画面对照尚未闭合，不宣称已根治。

当前研究入口：[纹理加载、上传与材质绑定](docs/TEXTURE_LOADING_AND_UPLOAD.md)。经GhidraMCP接上所查文件识别/读取、加载和补传任务、GLES上传/错误清理及材质引用消费；34份样本候选保留原压缩格式，同名光照图未代选。原任务结束、上传返回和纹理可用分别核对，实际显卡结果及原版画面仍未取得。MCP独立工程现有269个研究入口，原GUI工程保持；[手动启动研究服务](tools/start_ghidra_mcp.command)。前轮见[完成与绘制前检查](docs/RESOURCE_COMPLETION_AND_BINDING.md)、[配置与GPU条件](docs/RENDER_READINESS.md)、[帧呈现证据](docs/FRAME_PRESENTATION.md)，加载总览见[Ghidra工程](docs/GHIDRA_MAP_FLOW.md)。

前轮证据：[原效果文件的读取、材质生成与部件更新](docs/EFFECT_RESOURCE_AND_MATERIAL.md)，接续[材质列表建立与重建](docs/MATERIAL_LIST_AND_REBUILD.md)、[显示前的材质调整](docs/MATERIAL_ADJUSTMENT.md)、[建筑模型怎样读取、进入场景和隐藏](docs/MESH_AND_SCENE.md)、[BRES重定位、节点矩阵与12项初始世界包围盒](docs/BRES_WORLD_BOUNDS.md)、[模型任务结果、显示槽与包围盒](docs/MODEL_COMPLETION_AND_BOUNDS.md)、[EntityConfig、模型槽与距离选择](docs/ENTITY_MODEL_LOADING.md)、[设备档位与实例过滤](docs/DEVICE_AND_INSTANCE_FILTERING.md)、[配置、phase与区块遮罩](docs/MAP_CONFIG_PHASE_MASK.md)及[地图请求与区块加载/卸载](docs/MAP_REQUEST_AND_STREAMING.md)；文件关联基线见[新手地图原始加载链与缺口](docs/ORIGINAL_MAP_LOADING.md)。全仓历史归因见[审计报告](docs/PROJECT_AUDIT.md)及[318文件基线清单](docs/PROJECT_AUDIT_FILES.json)。历史目录只供追溯，不自动触发后续实现。

## 保留内容

- `tools/`：本项目编写的只读格式解析、原生字节核对及隔离研究工具。它们不是原游戏源码；每个工具的适用范围和替代输入应单独审查。
- `analysis/`、`docs/`：证据、地址、样本身份及未知项说明。完整转储和源数据留在忽略的 `analysis/raw/`。
- `.github/workflows/check.yml`：研究工具检查。无私有原文件时相应测试会跳过，CI成功不表示原版等效。

原APK、原/解包资源、原生库、完整表格、截图、存档、备份均不上传GitHub。

## 复核本轮加载链

在具备原始输入及研究依赖的本地环境执行：

```sh
.venv/bin/python tools/frame_present_evidence.py
.venv/bin/python tools/render_readiness_evidence.py
.venv/bin/python tools/resource_binding_evidence.py
.venv/bin/python tools/resource_binding_evidence_tests.py
.venv/bin/python tools/texture_loading_evidence.py
.venv/bin/python tools/texture_loading_evidence_tests.py
.venv/bin/python tools/map_loading_evidence.py --world tutorial --tile-x -43 --tile-z 2 --side 3
.venv/bin/python tools/map_loading_evidence_tests.py
.venv/bin/python tools/map_selection_evidence.py --probe
.venv/bin/python tools/map_selection_evidence_tests.py
.venv/bin/python tools/device_instance_evidence.py --probe
.venv/bin/python tools/device_instance_evidence_tests.py
.venv/bin/python tools/entity_model_evidence.py --probe
.venv/bin/python tools/entity_model_evidence_tests.py
.venv/bin/python tools/model_completion_evidence.py
.venv/bin/python tools/model_completion_evidence_tests.py
.venv/bin/python tools/bres_world_bounds_evidence.py
.venv/bin/python tools/bres_world_bounds_evidence_tests.py
.venv/bin/python tools/mesh_scene_evidence.py
.venv/bin/python tools/mesh_scene_evidence_tests.py
.venv/bin/python tools/material_adjustment_evidence.py
.venv/bin/python tools/material_adjustment_evidence_tests.py
.venv/bin/python tools/material_list_evidence.py
.venv/bin/python tools/material_list_evidence_tests.py
.venv/bin/python tools/effect_material_evidence.py
.venv/bin/python tools/effect_material_evidence_tests.py
.venv/bin/python tools/scene_lightmaps.py --output analysis/raw/map-original-loader-20261108/lightmap-bindings.json
```

这些坐标仅复核此前研究区域，不是恢复出的原出生点或原驻留范围。工具输出文件关系和验证记录，不生成游戏、画面或服务器。

原文件没有给出、原代码尚未追清或原进程未观测的部分保持未知，不用自写玩法或显示配置填补。
