# 新手 NPC 第二批：747 与 970

2026-11-14。750首批8文件及私有包保持冻结。本批只交付两种不同于750的原单体模型独立可见候选，未创建活动NPC、静态刷地图、接取任务或修改存档；自动任务2继续PAUSED。

## 选取与原表链

在map5的22个entry里，优先比较原任务关联与资源完整性。747、970均有唯一基础模型、同目录原动画、材质/贴图、可严格绑定的原骨骼。867、971在现有严格rest/inverse-bind检查中失败，未放松阈值选入；触发器mark也未冒充角色。

| 原entry/名字 | 原默认链 | 原任务资料关联 | 本批资源 |
| --- | --- | --- | --- |
| 747 冰霜巨兽 | appearance747 → display738 → model52 | 202的obj_idx7 / step9 | `ice_elemental_king.bdae`、原动画、1材质、1网格/蒙皮、33节点 |
| 970 神庙守卫 | appearance970 → display949 → model55 | 202的obj_idx9 / step2 | `armor_skeleton_02/armor_skeleton_01.bdae`、原动画、1材质、1网格/蒙皮、42节点 |

目标关联由当前原 `quest_objective_logic` 的 quest/obj_idx/entry 与 `quest_objective` 联结得到，保留step与obj_idx的区别；这不是服务端达成条件。名字分别取原简中ID783、1023，没有补译或改名。

747有1条静态出生、manual_spawn=1；970有8条、manual_spawn=2。两者静态phase/phasing_id均0。没有将这些值解释成活动出现、战斗姿态或实时GUID。

## 原默认模型与动作分支

复用750已冻结的原表/字符串宿主接口，额外探针在原ARM64库上执行。库SHA256仍为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

- 原 `9dd5fc` 对747/970分别得到 +f20查询键747/970、名称ID783/1023、默认display738/949。显式属性覆盖夹具仍能选择别的display，默认来源没有变成活动状态。
- 两者原Model Flags都为1。实际执行 `9d40cc` 后到 `9d5104` 的单体模型请求，不进入750使用的 `9d4c48` / 37部位流程。单体原网格完整保留，没有套用人类身体隐藏表、删掉装甲或添加衣甲。
- 原 `9e95a4` 对两者均发出 `idle`、参数1、engineFlags1。执行停在请求边界；没有伪造资源完成、原模型就绪或目标资格。
- 747原idle为35000–39000毫秒，4秒；970为47000–49000毫秒，2秒。全部34/51条原通道绑定原模型节点，不改原轨道值、补动作或重新设计循环。

747原extra=0，当前原分支也未请求额外武器。970原extra1485记录MainHand200010、AlwaysArmed1。原单体分支后续实际请求 `9d54dc(200010,0,1)`；再执行其物品分类，得到两个 `9d89b8` 请求 `[200010,0,1]`、`[0,1,1]`。这证明请求，尚不证明挂接/收拔姿态或现场动作。

200010原资料指向模型257的罗马剑。其500三角形、11节点和原材质已单独转换进私有包，**没有猜一个手部变换把它挂上970**。当前970画面只核查原基础单体模型，因此不称完整装备外观已恢复。

## 材质、蒙皮与可见验收

747原效果为 `lt_cull_pal_normal_trans`：原两个profile均引用相同pal-normal shader，带ALPHA_TEST/RIM_LIGHT、alpha阈值0.5、背面剔除、写深度，没有开启alpha混合。970原 `lt_cull_pal_normal_solid` 带RIM_LIGHT。读取器逐一核对原FX、shader SHA、标量、6个原采样器与色板，不通过改效果名字绕过750读取器的范围限制。

747有2574个三角形，rest-bind最大误差约 `1.74e-6`；970有794个，最大约 `1.33e-5`，均小于原严格读取器阈值0.002。没有生成切线、替换骨骼或丢弃未绑定动作通道。两模型加未挂接剑共使用14张去重的原采样图。

浏览器WebGL蒙皮、原材质公式重写、纹理采样配置、镜头/中性光、构图及idle审阅时钟/重复播放属于网页适配，不是原Android完整渲染器或像素级原场景。原display中的Scale80/120、Opacity1/255保留原值；未把它们直接当当前世界变换或网页alpha，更未虚构活动属性快照。

最终候选为 `candidate-v2`。Chrome实际显示两者，分别转视角检查，切换后仍保持各自原网格与动作；刷新后重新加载并可再次选择。动作骨骼确有变化，新一轮warning/error为0。候选没有登录、游戏状态、网络广播或角色存档。首版与最终版的三份转换模型JSON逐字节一致；v2补齐了任务原表联结证据。

## 文件、校验与交接边界

新增公共范围仅为 `tools/tutorial_npc_additional_*`、`tools/preview/source-npc-additional-*` 和本文。冻结750工具只读复用，8文件SHA核对保持；用户两份既有草稿也保持。未改共享deploy、原审定文件、存档、GitHub或Railway。

本地8项检查通过；无原资料公共副本为2项通过、6项明确跳过。检查覆盖原默认/属性覆盖、单体分支、idle参数、武器请求/挂接分离、原材质/骨骼/任务表联结、旧750冻结SHA、文件校验，以及额外文件/改字节/重复覆盖拒绝。私有归档已逐成员解档核对。

私有包 `analysis/raw/tutorial-npc-additional-20261114/npc747-970-source-candidate-v2-20261114.tar.gz`：26文件、2,867,201字节，SHA256 `ec13001586c19c69a4333695611d47f25cb80d9fc66762b9b3709202f175a4de`。原数据、转换资产、完整行、报告、截图及归档都留忽略目录，不上传GitHub，也不将包含证据报告的审阅根当生产资产目录直接挂载。

复跑：

```sh
.venv/bin/python tools/tutorial_npc_additional_probe.py --output analysis/raw/NEW/native.json
.venv/bin/python tools/tutorial_npc_additional_candidate.py --three ORIGINAL_LOCAL_THREE_DIRECTORY --output analysis/raw/NEW/candidate
.venv/bin/python tools/tutorial_npc_additional_tests.py -v
.venv/bin/python tools/tutorial_npc_additional_package.py --candidate analysis/raw/NEW/candidate --output analysis/raw/NEW/npcs.tar.gz
```

与quest_flow交换了原默认查询键、单体模型分支、武器请求，以及原模型 `Dummy_Name` 节点来源。747的该节点是非根节点，970是独立根；这些资产局部坐标没有写成最终actor名字偏移或屏幕坐标。没有修改其冻结接口、令v+B0/模型完成门为true，或推导任务可接标记。

真实出现/卸载、活动GUID、ObjectCreate完整属性、世界位置/缩放、display/name覆盖、模型异步完成、970武器姿态、目标资格和任务状态继续未知。独立模型可见不等于战斗或新手任务链完成。
