# 原天空候选：正式接线与私有增量回放

本批接在已上线 `8b0993c` 管理员巡图代码之后，只做天空候选的正式发布准备。没有提交、推送或更新Railway；未重开Docker，也没有启动游戏服务器或读取角色存档。原天空的源证据、画面验收及仍未恢复的设备/GPU分支见 `TUTORIAL_SKY_CANDIDATE.md`。旧神殿下层的结构开口仍未修复，不能用天空遮盖这一结论。

## 正式准备流程的改动

`deploy/prepare_delivery.mjs` 只增加6行：导入已有天空overlay，已验证包内存在天空manifest时检查桥接模块并接入entry，最后检查实际critical闭包。没有改原 `stageEntry`、管理员巡图控制、角色接线、地形、材质、环境光、天气或HDR。

未附带天空资产的旧包继续走原准备流程；不会仅因新代码存在就生成天空。附带manifest但缺桥接模块、缺任一天空关键资源或引用了其他地图格式时明确拒绝。接线继续保留 `wholeMapAccepted=false` 与 `skyGPUQueue=browser-adaptation`，不把网页渲染接线标成原GPU队列复原。

## 基于已缓存底包的增量

| 内容 | 载荷数 | 身份 |
| --- | ---: | --- |
| 已缓存完整底包 | 2857 | `f1dc28154f890f3e3eccd39e927130e51daa693f215d8cd0936bbc4c063d4569` |
| 当前线上所用完整素材 | 2891 | `17742ea08a704ac504156e7da4a7be19592eff96619c8886df73586bafbc155e` |
| 天空完整候选 | 2899 | `e946b9f1a17967de274487dbbe801ae22f047f2996acf9923a7fe7ffa42ed50a` |

新增量不是只发天空8份文件：它相对缓存底包包含线上已有34份追加内容，以及天空8份新增内容，共42份载荷，另附完整manifest及base引用。原线上2891份载荷逐项保持，127份审定运行文件、53份Python宿主的身份与内容均保持。原34份追加中包含两份已上线的场景效果JS overlay；它们没有被重写，也不是新增Python宿主。

私有包：`analysis/raw/tutorial-sky-release-20261115/oc2-runtime-tutorial-sky-delta-v1.tar.gz`。

- 字节数：5,422,390。
- SHA256：`175a7d4b5e3347351221f468b2f1a73739ff246c98ed5c3184207f6dec155b28`。
- 仍依赖缓存中的 `f1dc…4569.tar.gz` 完整底包，不要求重新上传整份148MB底包。
- 没有原角色存档、凭据或新原生输入；原美术、转换材质及完整资源清单都只在忽略目录和私有包内，不进入GitHub。

打包脚本只留在同一忽略目录。它重新验证三份输入归档的SHA及逐文件内容；使用正式 `deploy/bootstrap.py` 的 `extract_verified` 在隔离目录真实回放增量，随后核对全部2899份重建文件的长度/SHA，而非只检查压缩包能打开。全过程不运行bootstrap的服务器入口、不访问 `/data` 或用户存档。

## 正式prepare的实际回放

使用同一份 `8b0993c` 后的部署代码，先用原2891项清单生成基线，再恢复天空完整manifest生成候选；已有资源文件完全复用。只从停止中的验收容器读出两份缓存Three.js文件供prepare登记，未启动容器。

| 项目 | 原包基线 | 天空候选 |
| --- | ---: | ---: |
| 公开白名单 | 2743 | 2751 |
| critical资源 | 1081 | 1089 |
| background资源 | 450 | 450 |

原有公开资源中只改变了 `/explore-map.js` 的守卫式初始化/帧接线，其余2742项字节身份相同；新增8个URL全部进入实际critical闭包。原源地图窗口、模型清单、碰撞输入及角色逻辑保持。管理员巡图入口与相机控制仍在；临时只读观察器不在候选包或正式staged入口里。

基线delivery revision：`12dd9d7b9ea103ce0accbd47d0f6728c9a8b1c4e327e0dc4d007137ad9ab0ef8`。

候选delivery revision：`dd6affb3a0acec79ddfd00bbf49dee36fd0e3b80ef7d88d342a4b779f9ca1ba8`。

这两项是本地正式prepare的重放身份。主任务随后使用同一正式源码/私有增量建立最终 Linux 镜像，组合验收已通过：实际浏览器进入管理员巡图、升高至149.33、转动视角看到原天空与山体，横移跨过地图窗口 `[-41,-1]` 至 `[-40,-1]`，再返回庭院135.73；加载完成，零warning/error。两名隔离普通角色与该浏览器同时在线，双方能收到彼此位置；普通移动仍执行原CPU相机/物理，未获取管理员权限。新增8个公开资源均经实际HTTP下载和SHA核对。没有将独立观测器或新灯光加入正式入口。

最终QA容器 `oc2-sky-final-20261115` 已在验收后停止，保留独立测试卷；没有导入用户本地存档。真实协议与画面记录留在同目录 `final-linux-acceptance.json` 和 `final-linux-browser.png`。生产发布结果以本目录后续发布收据为准；天空接回不等于神殿下层结构、原出生点或整图1:1已经完成。

## 复核

```sh
.venv/bin/python tools/tutorial_sky_delivery_tests.py -v
.venv/bin/python tools/tutorial_sky_candidate_tests.py -v
```

增量/接线6项通过，其中3项需私有回放资料，缺资料时明确跳过；天空11项继续通过。新增检查针对完整8资源计划、逐项缺资源拒绝、地图格式拒绝、增量实际成员/身份、原在线载荷保留，以及正式prepare仍保留管理员接线。初次检查把原34份追加中已有的两份JS overlay误算成新增宿主，已改为核对它们与旧线上manifest身份相同；发布数据未因该检查修正而改变。

完整收据分别为同目录的 `receipt.json`、`prepare-receipt.json`；基线与候选索引、原始日志留在该私有目录。没有修改共享逆向路线图、自动续跑状态或任何角色位置。
