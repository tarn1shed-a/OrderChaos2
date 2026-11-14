# 新手 NPC：750 首批原资源候选

2026-11-14。本批交付是 **NPC 750 的原默认外观独立可见候选**，还不是地图里的活动 NPC，也不表示任务 202 可以接取。未改共享部署、Railway、角色存档、原地图/任务/人物冻结文件；自动任务 2 继续 PAUSED。

## 已证实的范围

原 `creature_spawns` 的 map5 有 67 条记录，涉及 22 个 entry。所有静态 `phase/phasing_id` 都为 0；`manual_spawn` 原值分布为 0：36 条、1：11 条、2：20 条。这里只清点并保留原值，没有把 0 翻译为“无条件出现”，也没有自行解释 1/2 的活动时序。完整坐标、表行、原资源身份与缺口只在忽略目录。

任务 202 的 StartGiverID=750，与 map5 的 spawn2482 同 entry 关联；739 是另外的升降台，未混入角色。750 的原表链为：

| 环节 | 原证据 |
| --- | --- |
| 原名 | appearance750 的 name=786；`String_Creature_zh` 选中行是“烈焰骑士治疗师” |
| 默认外观 | appearance750 → creaturedisplayinfo741 → creaturemodeldata1 |
| 基础模型 | 人类男 `oc2_human_m_body_01.bdae`；原 Flags=4 |
| 附加信息 | display741 的 ExtraDisplayInformation=608 |
| 原特征 | face=2、hair=2、beard=1 |
| 胸甲/靴子 | extra608 → itemdisplay100037/100038 → 人类男模型146/147 |
| 武器资料 | extra608 的 MainHand=200069 → 模型371 水晶杖；本候选没有擅自挂在手里或背上 |

源名字表含一条与本批选择无关的无效 UTF-8。读取器严格校验全部物理 ID/字符串跨度和终止符，只对需要的选中 ID 解码；选中无效文本会拒绝，没有替换字节或换语言补名。当前只确认默认名称来源，实际 ObjectCreature 的 `name_id` 覆盖仍须活动输入。

## 实际执行的原选择链

原库 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。探针在独立 ARM64 执行环境运行原指令；原表查找/拷贝、C++ 字符串、场景句柄及挂接接口是明确宿主边界，没有声称原 Android 进程或 GPU 成功。

- `9dd5fc` 用输入键查 `c992d0 → creature_appearance`，缓存到 actor+d2c；同键查 `c99280 → creature_proto` 到 actor+dc8。显式键750得到 +f20=750、名称ID786、默认 display741。显式属性 `+280=742` 则选择742，默认741保持。因此默认表外观不能盖过未知活动属性。
- `9d40cc` 的无 actor owner 默认分支，实际产生37个部位输入。本批非零为 face2、hair2、beard1、槽11=100037、槽14=100038；武器另走后续链，不能从此处的零值推断活动 NPC 无武器。
- `9d75e8` 从原基础模型路径得到 race/gender=0/0；`9d88b0` 实际生成 face/hair/beard 的原文件名，均有唯一包内资源。
- `9e95a4` 在显式 entry750/display741 夹具中实际发出 `idle` 请求、参数1、引擎 flags3。执行停在请求边界，没有伪造模型完成回调或完整两层动画系统。
- `32023c` 的部位名字循环把原身体节点映射到原部位编号；`32165c` 的替换段将 face 替换基础 head。`9d64e8` 的原 Flags 重排交给 `321350` 的双通道计数，原胸甲遮住身体覆盖区及胡须，靴子遮住小腿/脚；原手、颈保持。未沿用旧网页的猜测遮挡。

部位替换执行在 `321abc` 前停止，后续材质/资源完成仍是边界。计数器的场景 attach/detach 使用记录接口，浏览器按其结果选择可见网格，不能把这一接口称为原场景树/GPU已经运行。

## 独立可见候选

私有候选共39文件：18个原网格、18份原蒙皮、130个节点、6种原材质和28张原采样图；原规则得6个可见网格、1922个三角形。所有部件均通过同一基础骨骼的 rest/inverse-bind 检查，最大误差约 `2.13e-6`，没有补骨骼、画材质或生成替代切线。

胸甲与其余部件的顶点布局不同：多一组 UV，原切线/副切线在64字节步幅的40/52偏移。导出器按 primitive 的原语义22/18取流，保持 UV1，未按其他部件56字节布局硬读。材质的 FX、shader身份、标量、原采样器和色板都保留并校验；网页通过原公式重写做可见审阅。镜头、光照、WebGL蒙皮、RGB输出和播放时钟/循环是审阅适配，未称原场景完整画面。

唯一导出的动作是人类男原 `idle`，源范围456000–460000毫秒，4秒。骨骼通道和值直接绑定同一原基础模型，未自行改剧情动作。浏览器实际显示、拖动看背面并刷新，三次快照显示集合保持 `[4,8,13,14,16,17]`，动作时间和9个采样骨骼有变化；刷新后新一轮 warning/error 为0。没有角色登录、联机状态或存档写入。

首个审阅版本因胸甲切线流遗漏而拒绝加载，已更正；当前冻结的是 `candidate-v3`，不把失败版本算入验收。静态模型审阅不适用双连接任务状态验收，生产接线仍须主任务用正式入口另验。

## 交付与检查

公共新增只含 `tools/tutorial_npc_*`、`tools/preview/source-npc-*` 与本文。未使用或复制用户的 `native_character_entry.py`、`standard_abc.py` 未跟踪草稿；其 SHA 保持。原文件、完整行、反编译、转换资产、原生探针输出、截图和私有包全部留 `analysis/raw/tutorial-npc-recovery-20261114/`，不加入 GitHub。

本地8项检查通过；无原文件的公共副本为2项通过、6项明确跳过。检查涵盖选中名字严格解码、默认/属性覆盖分开、原部位和idle请求、原文件名、身体替换/计数、静态活动未知、包内SHA及蒙皮/切线绑定。私有包已逐文件解档校验。

私有包：`analysis/raw/tutorial-npc-recovery-20261114/npc750-source-candidate-20261114.tar.gz`，SHA256 `7c3990e23ea2caea02e71696ed029adf50b8e503b3b99457fa642be1a7968870`。它是独立审阅包，没有部署或创建运行角色的入口；主任务可据 `manifest.json`、`package-files.json` 与交接JSON审查资产接线边界。

复跑入口：

```sh
.venv/bin/python tools/tutorial_npc_inventory.py --output analysis/raw/NEW/inventory.json
.venv/bin/python tools/tutorial_npc_native_probe.py --output analysis/raw/NEW/native.json
.venv/bin/python tools/tutorial_npc_tests.py -v
.venv/bin/python tools/tutorial_npc_candidate.py --three ORIGINAL_LOCAL_THREE_DIRECTORY --output analysis/raw/NEW/candidate
.venv/bin/python tools/tutorial_npc_package.py --candidate analysis/raw/NEW/candidate --output analysis/raw/NEW/npc750.tar.gz
```

## 仍未闭合

实际出现/卸载条件、服务端 ObjectCreate/属性快照、实时GUID、`name_id/display_id`覆盖、世界变换与缩放、武器收拔及完整异步加载仍未知。静态 spawn 只是资料，独立候选只使用资产审阅变换；未把它放到地图或制造活动消息。

与 `quest_flow` 的交接保持这些字段分开：真实 actor GUID、原查询键、quest_status、quest_type、interactives、目标选择/投影，以及任务202窗口请求。默认外观和可见模型都不能自动令目标资格门为 true；没有可接任务图标、任务已接/完成状态或奖励。本批没有接成生产 NPC，也未完成整条新手任务链。
