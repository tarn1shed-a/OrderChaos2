# 新手地图的配置、phase与区块跳过遮罩

2026年11月9日，基线7c1c63d。本轮只核对原APK、原资源和固定ARM64库，执行有限原指令片段；没有恢复网页、服务器、地图显示或自写选择器。自动任务2保持暂停。

**结论：Android APK自带配置的地形半径默认2，GPU_0M覆盖为1；原phasing_area表没有tutorial的map_id=5；已找到的20条区块跳过遮罩常量全部属于map_id=1。** 因此，新手地图在本轮核对的表选择分支中使用phase 0，不能把其他地图的特殊遮罩套过来。实际设备选中配置、位置、缓存历史和实例过滤仍未观测，不能给出一个伪称原会话“最终可见”的对象清单。

## 原始输入身份

ARM64库SHA256仍为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。下列地址只对应这一版本，不证明雷电所用ABI与进程现场相同。

| 原输入 | 本轮核对 | SHA256 |
| --- | --- | --- |
| 3.1.3a APK | 56,639,416字节 | `4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe` |
| APK内assets/GameOptions.json | 82,986字节；header file_version=73、format_version=1、library_version=1 | `7284c94676d704bad084e1f685afdd77a70f27a96a88b4ddb36ad60eb14aa355` |
| tables.bin内tables/phasing_area.tbl | 20,675字节，CRC57385bc1；15行、205列 | `53ae6f6d3076a0dcfa6baa33300de64a55705846a37b45dfe747577a7747f2ab` |
| tables.bin内tables/map_info.tbl | 17,249字节，CRC8a5b18eb；map_id=5→world/tutorial.wld | `7107a73d63faf44961554205ac8720cb466e7c6fa7e43d174f1e009b0608ab8f` |

原完整JSON、表行、文件/实例清单和反汇编均留在忽略目录。Git仅保存研究工具、核查和结论。

## TerrainTileSight到底怎么选

上轮只核对了资源包中的GO_ios.json；本轮补查APK，找到了Android自身的同名配置候选，不能再只用iPad配置说明Android的半径来源。

| 阶段 | 原代码证据 | 已确认与边界 |
| --- | --- | --- |
| 请求配置内容 | 0x3b99b4–0x3b99d0 | 使用字面量GameOptions.json，经0x2f9200请求内容，再交给初始化。APK有assets/GameOptions.json；未在原进程观测虚文件系统最终命中哪个来源 |
| 初始化与持久档位 | 0x3b9934 | 读取GFX_Profile_Must_Restore、GFX_Profile，构造GPU档位输入，经0xc425b8尾跳0xc42c9c；不是简单读一个常数 |
| 配置来源分支 | 0xc42c9c | 存在调试JSON、USER_FOLDER下GameOptions_saved.json、传入资源内容的选择；核对GameVersion及header/library_version=1。0xc43500/0xc43634调用JSON解析0xc44104，0xc4366c进入0xc441fc。调试路径、保存文件和原进程所走分支未观测 |
| 分组和设备条件 | 0xc441fc→0xc48524 | 读取profiles和selection，条件求值调用0xc5b854，匹配后还调用0xc49834。设备资料字符串由0xc5c55c拼出，包括GPU、MODEL、MANUF、CORES、CPUFMAX等。完整条件表达式与档位调整语义未全部执行核对，不另写求值器代替 |
| 写默认/覆盖参数 | 0xc44440→0xc48ba8；0xc4445c→0xc48e68 | 前者读defaults/Default，后者读overrides下选中档位；均向同一个+0x198参数对象调用0xc4a6d4。整数分支0xc4a724–0xc4a738进入0xc62510；没有把参数原文直接当成最终设备值 |
| 半径消费 | 0x3bbcf0–0x3bbd14；0xc62564；0x35b1a0 | 用TerrainTileSight取整数，缺键传入2；写config+0x38，再生成原偏移表与循环缓存尺寸 |

APK JSON中GPU/defaults/Default的数组记录明确给出TerrainTileSight=2；全部overrides中只有GPU/GPU_0M将其覆盖为1。GPU_0M的selection原文包括旧GPU型号及部分CPU/设备组合条件；这些原表达式已保存供继续逐项核对。JSON的注释提到“2×R+2”，原指令证明这是缓存边长；**候选偏移数量仍是(2×R+1)²**，不能拿注释替代代码。

因此，在该APK基线中，默认半径产生25个候选偏移，GPU_0M的半径产生9个。保存/调试配置可能不同；没有实际设备资料和选中档位，不能说雷电现在必定是哪一个。资源包里旧GPU_Options.xml的Broad View文字没有被证明接到这条TerrainTileSight调用链，不据此增加另一个配置开关。iOS覆盖也不用于Android。

## phase的表和角色输入

0xc99268从表管理器+0x70取表指针。原表读取例程0xcacacc构造tables/phasing_area.tbl路径；其类型串位于0x1f00cb8，与源表205字符的physicalTypes完全一致：id、name、map_id、color、tile_count，以及100组x/z。0xcadd14使用同一串解码记录。

0x366ed4读取全局对象0x2528df8所指对象+0x68下的+0x14e0位字，按bit 1..31产生活动phase候选。另一端的0x58ae2c会从输入缓冲读取一个32位字，检查剩余长度后写到同一+0x14e0位置；短输入写0，游标仍前进4。**目前没有确认该输入的消息名、opcode和完整分派，不给它编造协议字段。** 0x9ec7c8内也有+0x14e0清零，但不把构造时清零当作实际登录会话的值。

区块选择0x367144–0x367208对活动ID逐个查表，并且同时要求：

1. 表中有这个phase ID；
2. 记录map_id等于当前上下文+0x278；
3. 候选地块X/Z出现在该记录的tile_count坐标中。

第一条满足这些条件的候选决定传给0x367684的phase；全部不匹配则0x367200明确将w3置0。原表15行的map_id为0、1、2、3、4、8、9、10、12、30，没有5。因此，在这份表和这条分支下，tutorial不会因角色phase位不同而选择非零phase。这个结论不覆盖后续下载/测试表、其他直接加载入口或未观测的数据替换。

本轮用原指令执行该查找片段：输入全部1..31活动ID，新手地图三个明确坐标都返回0；另用真实表中其他地图坐标得到对应非零ID，并检查错误地图、错误坐标和非活动ID均不命中。树节点布局和活动ID向量是实验夹具，未执行完整原表管理器/网络。

## 区块遮罩不是地表MSK

原0x35b1a0在生成偏移表后尾跳0x357b2c。后者向全局对象0x25282e0的+0x290 map写入20条**原指令常量**；没有读取TRN或MSK。原map树头为0x2528578，根指针位于0x2528580。

0x3520e0–0x352178用以下四个低16位组成64位键，查询节点+0x20的key，命中后把节点+0x28值复制到地形对象+0x14：

```text
高位 [ mapId:16 | phase:16 | tileX:16 | tileZ:16 ] 低位
```

地形对象之前的memset清零了+0x14，所以未命中时保持0。原0x367104–0x367114检查该值，对−2..2外圈中对应bit非零的偏移跳过请求。它用于区块请求筛选；原0x354fec读layers/*.msk并交0x359ad0的流程用于地形层资料，两者不能混叫同一张遮罩。

执行原0x357b2c，捕获20次map写入：全部map_id=1，其中phase 0/2各10条，坐标集相同。例：(map=1,phase=0,x=0,z=−5)→0x7fc；phase=2同值。再执行原0x3520e0查询片段，20条全部查回对应值；改成map=5则全部未命中，返回0。这里仅替换map operator[]的存储分配为收集器；键和值由原指令产生，查询运行原指令。

**准确边界：已闭合这一处初始化生产者到消费者；没有穷尽排除全部别名写入或原进程后续修改。** 所以结论是“这批原初始化常量不为新手地图跳过区块”，不是“已证明整个原进程永远不存在tutorial特殊遮罩”。

## 能列出哪些地形和建筑

当前原包索引中tutorial/terrain有251个TRN，均为普通坐标文件名；tutorial/items有57个普通坐标ITM。全部57份ITM经原包长度/CRC核对并按v5读取，含1,354条静态实例、176种模型引用；完整ID、模型、变换、类型和所属区块列在本地证据JSON。

更正上一份加载文档的表述：这251个TRN没有查到phasing目录或LOD后缀，不能继续称其中已包含LOD变体。原加载代码确有相关路径分支，分支存在与本地文件实际存在须分别陈述。

依本轮表选择分支，tutorial使用phase 0：原0x354de4的基础地形路径为world/tutorial/terrain/<坐标>.trn，原0xa60b4c的基础建筑路径为world/tutorial/items/<坐标>.itm。地形还受+0x170级别后缀分支影响，建筑有_1f分支；本轮没有把它们强制为0或移除。建筑任务仍接在地形发布后，随后还有XML、device、记录类型、模型slot、光照和裁剪过滤。

为与旧研究区域对照，下面只给**显式中心(−42,3)、已找到初始化遮罩表、phase 0、基础文件名**的条件例子。中心、半径、LOD均不是实测原会话值；偏移来自原0x35b204。

| 明确输入 | 原候选偏移数 | 本地基础TRN存在 | 这些坐标有ITM的区块数 | ITM静态记录数 |
| --- | --- | --- | --- | --- |
| R=1，X=−43..−41，Z=2..4 | 9 | 9 | 3 | 39 |
| R=2，X=−44..−40，Z=1..5 | 25 | 25 | 8 | 217 |

R=1的3个建筑资料区块为(−41,2)、(−41,3)、(−41,4)，分别35/3/1条记录。R=2还包含(−42,1)、(−41,1)、(−40,1)、(−40,2)、(−40,3)，分别1/90/79/7/1条。没有ITM候选不代表原异步读完；有记录也不代表全部实例最终显示。

缓存还可能保留之前中心的外圈，任务可能未完成或被取消，因此“新请求候选”“驻留区块”“读入的ITM记录”“最终可见模型”是四个不同集合。此前9块/39条是一个条件研究区域，不能称整个原新手地图已还原或原会话只加载这些。

## 复核、缺口与下一入口

[map_selection_evidence.py](../tools/map_selection_evidence.py)额外固定15段原函数身份和17条调用/尾跳转，重读APK配置、phase表及57份ITM；[native_map_selection_probe.py](../tools/native_map_selection_probe.py)执行上述限定mask/phase/输入字片段。全部范围与替代输入写进输出，不构建游戏。

```sh
.venv/bin/python tools/map_selection_evidence.py --probe
.venv/bin/python tools/map_selection_evidence_tests.py
```

本轮新增7项检查通过，覆盖原字节变更拒绝、原mask写入与查询、phase正/负分支、短输入、原表/清单与Android APK配置。没有原APK/资源/库的CI明确跳过相应检查，不能以CI绿色证明实际设备状态。

连同地图加载/流转、资源读取与光照表的相关回归，本地共30项通过，0失败、0跳过。41份原包SHA与审计基线一致，角色存档与删除原型前的备份逐字节一致；prototype与game-data/converted均未重建。

还需要的现场材料一次列明：原应用数据中的GameOptions_saved.json（若存在）、GameOptionsEtag.t、dyanmicSpecs.t及GFX_Profile相关保存值；设备规格/档位选择日志；原进程当前map ID、位置、tile级别和加载/取消现场。APK内基线配置已经取得，不再把它列为缺失。没有这些现场时，可以继续追条件解释器、虚文件来源和字段写入；不能替原设备挑profile，也不能给出唯一最终对象集合。phase输入的消息分派、表动态替换、mask其他写入与实例过滤仍保留缺口。

本地原始输出、完整清单与交接：analysis/raw/map-selection-20261108/。本轮没有画面或运行玩法修改，不做不存在的浏览器/双连接验收；原资源、私有角色存档保持原样。
