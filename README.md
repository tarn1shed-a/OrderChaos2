# 《混沌与秩序2》客户端离线逆向研究

当前只分析用户提供的3.1.3a APK、原生库和资源文件，核对原始数据与代码的关系。没有原开发工程源码或原服务器源码。

**自写网页客户端、本地游戏服务器、玩法规则及启动/部署入口已从当前版本删除。** 旧原型及转换预览保存在忽略的本地备份和Git历史中；不再作为当前实现。原始资源、研究证据和私有存档保留，自动续跑保持暂停。

当前研究入口：[建筑模型怎样读取、进入场景和隐藏](docs/MESH_AND_SCENE.md)，接续[BRES重定位、节点矩阵与12项初始世界包围盒](docs/BRES_WORLD_BOUNDS.md)、[模型任务结果、显示槽与包围盒](docs/MODEL_COMPLETION_AND_BOUNDS.md)、[EntityConfig、模型槽与距离选择](docs/ENTITY_MODEL_LOADING.md)、[设备档位与实例过滤](docs/DEVICE_AND_INSTANCE_FILTERING.md)、[配置、phase与区块遮罩](docs/MAP_CONFIG_PHASE_MASK.md)及[地图请求与区块加载/卸载](docs/MAP_REQUEST_AND_STREAMING.md)；文件关联基线见[新手地图原始加载链与缺口](docs/ORIGINAL_MAP_LOADING.md)。全仓历史归因见[审计报告](docs/PROJECT_AUDIT.md)及[318文件基线清单](docs/PROJECT_AUDIT_FILES.json)。历史目录只供追溯，不自动触发后续实现。

## 保留内容

- `tools/`：本项目编写的只读格式解析、原生字节核对及隔离研究工具。它们不是原游戏源码；每个工具的适用范围和替代输入应单独审查。
- `analysis/`、`docs/`：证据、地址、样本身份及未知项说明。完整转储和源数据留在忽略的 `analysis/raw/`。
- `.github/workflows/check.yml`：研究工具检查。无私有原文件时相应测试会跳过，CI成功不表示原版等效。

原APK、原/解包资源、原生库、完整表格、截图、存档、备份均不上传GitHub。

## 复核本轮加载链

在具备原始输入及研究依赖的本地环境执行：

```sh
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
.venv/bin/python tools/scene_lightmaps.py --output analysis/raw/map-original-loader-20261108/lightmap-bindings.json
```

这些坐标仅复核此前研究区域，不是恢复出的原出生点或原驻留范围。工具输出文件关系和验证记录，不生成游戏、画面或服务器。

原文件没有给出、原代码尚未追清或原进程未观测的部分保持未知，不用自写玩法或显示配置填补。
