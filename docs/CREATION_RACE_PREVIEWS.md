# 原种族页的八种人物预览

截图中“只有人类有模型”有一个直接原因：网页的预览准入表只包含人类男、女；选择其他种族时，旧代码连背景画布一起隐藏了。本批按原创建控制器实际请求，补入六套各自的原种族展示服、脸发、骨架、材质和 idle。没有拿世界裸体或人类展示服填充。**目前是八种身体的种族页预览，不能称为原版完整创角流程已经恢复。**

八体已经由主代理在原 SVG 界面逐个点击、实际绘制检查；对应 display 为 2038、2045、2048、2049、2047、2050、2051、2052，控制台没有 warning/error。截图与逐体记录保留在忽略目录 `analysis/raw/creation-race-preview-20261115/browser-parent-v1/`。本专线只做离线原代码、资源与构造检查，没有控制用户浏览器，没有更改角色存档或发布生产。

## 原选择与装配

原库 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。冻结的 45 组合矩阵先实际执行原 `542da4 → 53d3e8`，取出种族页的 stage 0 请求。本批继续执行原 `9d40cc`，参数为 `3,0,"idle",1,0`，再以每个身体自己的模型路径执行 `9d64e8` 的部位描述符请求；原材质覆盖请求通过 `325ce0/325e5c` 到纹理请求边界核对。

| UI 身体 | 原种族页 display / model | 原展示服条目 | 本批新增原 CPU 对比 |
|---|---|---|---|
| 人类男、女 | 2038/1、2045/32 | 沿用已核的原独立候选，未替换 | 旧交接保持 |
| 蒙德尔男 | 2048/34 | 胸 100316、腿 100245、脚 100127 | 20 个控制器、80 组 |
| 蒙德尔女 | 2049/31 | 胸 100316、腿 100245、脚 100127 | 18 个控制器、72 组 |
| 精灵女 | 2047/2 | 胸 100342、脚 100354 | 18 个控制器、72 组 |
| 兽人男 | 2050/28 | 胸 100398、脚 100401 | 18 个控制器、72 组 |
| 兽人女 | 2051/30 | 胸 100398、脚 100401 | 16 个控制器、64 组 |
| 龙人 | 2052/29 | 肩 100381、胸 100382、脚 100385 | 17 个控制器、68 组 |

表中的原条目按 `itemmodeldata.tbl` 再解析为各自种族、性别的 BDAE。它们仅表示这一页的展示服，不向游戏角色授予装备。龙人原 UI 只有 gender 0；没有新增一个龙人女性。

六套新增候选共执行 428 组自身 idle 的原采样、骨骼矩阵和顶点计算对比；误差都不超过既有的 `.002`。所有源逆绑定、姿态、浮点权重保留，没有归一化或修补模型。网页实际使用同一生产骨架工厂、原 `lt_pal_normal` 顶点/片元程序、原材质宏、原采样寻址和调色板输入。Three 构造、材质构造和骨架更新另做 CPU 检查；这不伪称观察了原 Android GPU。

人物位置、旋转、整数大小 5、原相机和 SVG 布局沿用 [已有阶段核查](CREATION_STAGE_TRANSFORMS.md)。本批没有重新摆镜头、缩放按钮、换背景或调颜色。

## 已处理的具体边界

- 蒙德尔的脚覆盖请求最终确实指向 `texture/oc2_human_m_tramp_feet_d.tga`，该资源存在。原描述符保存的是不带目录、扩展名的 stem；不能直接把 stem 当成文件路径报缺图，也不能仅凭 `human` 名字擅自改成别的图。
- 蒙德尔女性原 foot 控制器声明 1768 字节，147 个完整顶点记录消费 1764 字节。只对已单独核实的原模型、ordinal 4 复用原 CPU 消费证据；1768 字节原流没有截断，尾部四字节仍未分类，通用精确长度检查没有放宽。
- 龙人的 `horn` 由原槽 5 管理；`the_tail` 不在装备槽映射里。原命名绑定和遮挡查询保留其源节点挂接，不因不在槽表就删除尾巴。
- 原 `53d3e8` 成功切换时，将旧 wrapper 隐藏、新 wrapper 显示；不是销毁整张 selection 场景。四组有界 CPU 测试核实了成功、有无旧 wrapper、显式空构造边界及无效 display。构造边界没有伪造模型完成或资源加载成功；显式 cache miss 也不等于已执行真实纹理失败。
- 网页尚无准入候选时，只保留已核背景、移除旧种族模型，避免把人类假充其他身体。该保护属于网页的资源拒绝处理，不冒充原资源失败时的最终画面，不新增提示面板。

## 尚未准入与后续复用

精灵男性 stage 0 是 display 2046/model 33，胸 100342 真实请求 `texture/oc2_human_m_light_sunken_chest_brown_d.tga`，现有包中缺失。本批八体版本仍拒绝它。原覆盖失败是否保留 BDAE 原图由另一条原代码调查负责；只有明确核实原分支后才单独扩展，不能因看到模型自身 `_d` 就自行当成 brown。

职业页 stage 1、外观页 stage 2、已存角色选角预览各有独立 display、装备和相机调用。此处恢复的舞台服不自动适用于那些页面，也不代表职业技能、原账号服务或原服角色创建已经接通。原 selection 天空缺文件等既有边界保持，不以新美术填补。

可复用的核查顺序是：当前页面选择的 display → 原表对应的 model/extra → 原部位消费者 → 原槽位遮挡 → 原材质覆盖消费者 → 自己的骨架/idle → 原 shader/采样 → 原 UI 实际绘制。不要把身体资源存在、世界可玩、种族展示服正确混为同一项完成证明。

## 文件与验证

本地取证工具为 `tools/creation_race_source.py`、`creation_race_candidate.py`、`creation_race_switch_probe.py` 和 `creation_race_delivery.py`。它们依赖的历史原 CPU/BDAE 辅助代码已整理成忽略目录里的 `source-replay-tools-v1.tar.gz`，随包附逐文件 SHA 和导入闭包清单；原文件、私有取证输入、素材和存档不在源码包内，重放仍须提供对应的原始输入。本批 Git 只审查运行接线、公开测试、只读界面 QA 工具与文档，不宣称整棵本地历史工具已经公开。

网页接线限于 `deploy/creation_preview.mjs` 与 `tools/preview/character_creation_preview_proposal.mjs`。后者在新私有运行包中以 **`/character_creation_race_preview_v1.mjs`** 的新名称追加；既有 `/character_creation_preview_proposal.mjs` 的载荷逐字节保留。v1/v2/v3 使用原两人体工厂和本地安全校验，不依赖新模块；只有 v4 才动态请求新增模块。

私有最新运行交接在 `analysis/raw/creation-race-preview-20261115/handoff-eight-v3.json`：逐体模型、脸发、服装路径、覆盖和原 CPU 误差见 `summary-v1.json`；原请求见 `source-v2.json`；原切换记录见 `switch-v1.json`。原文件、完整表、转储、候选模型、纹理与截图全留忽略目录。v1/v2 历史交接与早期 QA 静态包保留，不原地覆盖。

`eight-body-append-v2.tar.gz` 只包含模型/纹理闭包、新 v4 配置及新命名工厂。SHA256 为 `f835af0d41ebcdc607ecbaf5a2f2b68ff05eee3665b3bfc96b5a8d359da69d17`，5,313,497 字节。旧 v1/v3 仍只接受原先两套人类；v4 显式列出新增六体，`allNineRacePreviewsRestored` 为 false。原静态场景、两个人类候选、地形、光照、SVG和存档均不替换。v2 修正了实际加载路径的规范性、先核身份再请求资源，以及 manifest 与模型 `sourceCreation` 的对应；包括编码路径逃逸和模型混用的回归检查。

```sh
.venv/bin/python tools/creation_race_switch_probe.py --output analysis/raw/NEW-REVIEW/switch.json
node --test tools/creation_preview_tests.mjs tools/character_creation_preview_proposal_tests.mjs tools/creation_race_preview_tests.mjs
```

原 SVG 的轻量验收工具只安装现有身份只读接口，读取一份不存在的隔离存档路径，所有创建、删除、复位和进入世界请求均拒绝，不启动 WebSocket 或物理工作进程。由主代理决定启动新的 QA 会话、浏览器验收及最终发布，自动续跑保持暂停。
