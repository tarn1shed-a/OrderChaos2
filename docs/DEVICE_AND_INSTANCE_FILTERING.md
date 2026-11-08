# 设备档位、配置覆盖与新手地图实例过滤

2026年11月9日，基线108338e。只继续原文件和原指令研究，没有增加游戏功能、界面或地图。自动续跑保持暂停。

本轮已执行原GPU条件判断、档位选择/调整及参数更新顺序的限定实验，并将新手地图全部1,354条AITM记录送入原创建前过滤片段。**可以给出指定原配置输入下的通过清单；实际雷电选档、下游模型加载/裁剪和最终可见清单仍未取得。** 全部计数均注明发生在哪个入口，不以资源存在或通过一个检查冒充加载完成。

## 原输入与新增代码依据

原ARM64库SHA256仍为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`，APK及其assets/GameOptions.json身份沿用[上轮报告](MAP_CONFIG_PHASE_MASK.md)。JSON的file_version=73；未观测当前进程是否使用此基线、保存配置或调试配置。

| 原文件 | 来源、大小、CRC | SHA256 |
| --- | --- | --- |
| bdaeConfig.xml | res.bin，86,176字节，d25b4dc7 | `516f8a072907387bd61f019cfe4253113e5484a260b86fd1a1e6d128314aad8e` |
| world/tutorial/bdaeInstanceConfig.xml | tutorial.bin，106字节，6c3fcd00 | `c967562ce3062578eea1e95418b9666afd3be4124fe12006251d9fc347f1c1b0` |
| world/tutorial/EntityConfig.xml | tutorial.bin，2,359字节，0e86a180 | `7f7601ae265a5fa1368a6e2f9cacc479cb14661b7a09bdcdfbb0e5aae31b3100` |

新增固定27段原函数身份、15条调用和两处GOT关系。完整输入、反汇编、每条实例的结果及限定实验清单只保存在忽略目录，不上传GitHub。

## 设备条件与GPU档位选择

原0xc5b854按顺序识别 `<=`、`>=`、`<`、`>`、`!=`、`=`、`!$`、`$$`。前六种进入对应的原类型比较方法；`$$`/`!$`检查字符串包含/不包含。实验验证了大小写敏感、缺失属性不命中、数值边界和字符串属性与数值属性的区别。设备属性的实际采集没有执行，输入类型和值必须明确给出。

原0xc48524遍历selection，调用上述判断；本轮通过原指令确认其嵌套组合：外层候选按数组顺序尝试；一个候选可有多个替代组；组内各条件子组都需通过，子组内多个表达式满足其一即可。先匹配的候选进入0xc49834，后者再读取priority和保存/传入的调整值。不能把GPU名字包含数字、或者GFX_Profile整数，直接解释成最终GPU档名。

原APK中GPU_6候选为 `[[]]`，构成后备匹配。原选择器对明确的未列型号字符串会得到GPU_6，不能因为没命中特定型号就断言“没有档位配置”。

本轮使用原APK的GPU配置，得到以下**显式输入实验**：

| 输入GPU字符串；其他属性未提供 | 调整值夹具 | 原选择器输出 | TerrainTileSight | ModelDetailLevel | DeviceLayer原值→原限制后 |
| --- | --- | --- | --- | --- | --- |
| PowerVR SGX 530 | 0 | GPU_0M | 1 | 2 | 1→1 |
| PowerVR SGX 530 | 1 | GPU_0 | 2 | 2 | 1→1 |
| Adreno (TM) 330 | 0 | GPU_4 | 2 | 0 | 3→3 |
| Unlisted GPU | 0 | GPU_6 | 2 | 0 | 5→4 |

这四行不是雷电设备检测结果。调整值1在本例转到GPU_0，不代表该整数就是GPU档名后缀，也没有将它解释成可任意叠加的等级步数。完整priority调整的原控制流已进入实验，但全部设备组合、存档值和实时改档路径没有穷尽验证。

## 配置覆盖顺序与真正的消费字段

0xc441fc先调用0xc48ba8读取当前分组defaults数组的第0项/Default，再调用0xc48e68读取选中档位的overrides。原循环顺序已执行；在0xc4a6d4参数写入边界逐项记录，覆盖顺序没有用自写设备选择器替代。

例如GPU_0M：先出现Default的TerrainTileSight=2、DeviceLayer=5，再出现其覆盖值1、1。GPU_0不覆盖TerrainTileSight，因此保留2；GPU_0M关闭ShowModelLightMap，GPU_0未覆盖它而保留Default的true。不是从上一次GPU_0M状态增量切换而来。这里只核对一次初始化更新顺序，没有模拟实时改档的全部清理和重载。

核对CPU、ColorCorrection、MEM、Specific各组后，当前关心的六个键（TerrainTileSight、ModelDetailLevel、DeviceLayer、ForceModelLodLevel、ShowModelLightMap、ShowTerrainLightMap）在该APK JSON中只由GPU组写入。这缩小了此版本的跨组覆盖疑问，不覆盖下载后配置。

参数写入边界后的关键原消费：

| 参数/位置 | 原指令证据 | 含义范围 |
| --- | --- | --- |
| ModelDetailLevel→config+0xc | 0x3bb96c–0x3bb990 | 读取同名整数，缺键参数0 |
| config+0xc→全局0x2532f08 | 0x4d19e4–0x4d19f0 | 后续创建与碰撞路径经GOT0x2505ca0读取此字，不等同于DeviceLayer |
| DeviceLayer→config+0x54 | 0x3bc1a8–0x3bc1f0 | 缺键参数4；读入值若不小于5，写成4。原APK默认5在这里变为4；本段没有新增下限规则 |
| ForceModelLodLevel→config+0x28 | 上轮已核对0x33ebf8等消费 | 影响模型槽请求；实例通过过滤不保证其base或_l模型已经载入 |

本轮参数更新实验在0xc4a6d4处记录调用，不执行整个原参数注册表的类型存储和客户端初始化；DeviceLayer上限片段另行执行原指令。来源选择仍保留上轮的GameOptions.json、有效保存JSON与调试JSON分支，不能因APK基线可读就替进程选择来源。

## 建筑/场景记录进入工厂前怎样过滤

原0xa6196c在分配类型对象和进入虚工厂前依次检查：

1. **记录+0x3c字。** 值在1..999时，必须出现在全局0x2528e10所指对象+0x10的整数向量中；否则跳过。其余数值绕过该向量检查。本轮仍称它为dynamicWord，不把它直接命名为上一轮地形phase或某种任务状态。
2. **细节字段。** 原0xa61a54取记录+0x38的低两位；若全局0x2532f08以无符号比较大于该值，跳过。
3. **XML等级。** 从上下文+0x1b8取得配置对象；空指针会跳过。非空时以模型字符串、实例ID调用0x4cb934；若返回值以有符号比较大于config+0x54，跳过。
4. 上述通过后才在0xa61acc起分派类型2、8、15、16等，构造对象并调用原工厂；未识别类型还有跳过分支。

碰撞路径0xa61030也读取细节字段，并在0xa611ac调用同一等级查询；本轮没有因此声称碰撞实例、注册成功数量和显示实例完全相同。

### XML等级先按实例，再按模型

世界加载器0x8fcb90调用0x4cac98读取全局bdaeConfig.xml；0x8fcdac调用0x4cb1a4读取当前世界的bdaeInstanceConfig.xml，二者放入上下文+0x1b8关联的配置对象。

0x4cb934先将输入实例ID格式化为十进制字符串，在世界实例覆盖列表中按字符串查找；命中则返回对应level。未命中再按完整模型字符串找全局模型项，使用首个匹配项。原方法还检查该模型的嵌套字符串列表：命中则返回0；没有模型项也返回0。本轮没有把嵌套字符串擅自改成另一种ID类型；0x4cae7c起的原读取代码使用父Item的name，当前源文件中的这些字符串是模型路径。

全局文件有929条模型等级项。tutorial实例覆盖只有一条：ID250436944、level=1，对应原ITM `-039_-001.itm` 中的 `hum_other_ballista001_broken.bdae`。`EntityConfig.xml`是另一个对象和读取流程，不能把其device数值当成这里的level。

## 全新手地图和旧研究区域的条件清单

本地57份ITM共1,354条记录：类型2有1,258条，类型8有92条，类型15有4条。它们不是1,354座建筑，也不是全图同时可见模型数。

全部记录+0x38低两位为3、+0x3c为0xffffffff；因此，在原APK常见ModelDetailLevel=0..2输入下，上述细节/编号检查不会区分这些源记录。按原XML查询，等级分布为：0级404条、1级109条、2级658条、3级145条、4级11条、5级27条。

以下结果将每条原记录送入创建前的原片段，输入明确为ModelDetailLevel=2、非空且按源XML构造的配置列表、当前记录有效；在类型分派前停止。

| 明确DeviceLayer输入 | 通过上述入口检查 | 被此入口排除 |
| --- | --- | --- |
| 0 | 404 | 950 |
| 1 | 513 | 841 |
| 2 | 1,171 | 183 |
| 3 | 1,316 | 38 |
| 4 | 1,327 | 27 |

这些是**遍历全部源区块的条件筛选总量**，不是驻留窗口。本轮完整JSON包含每条ID/模型/所属区块、查询等级和各输入下的结果，可逐条审查。

旧研究中心明确取(−42,3)时，范围和等级组合进一步得到：

| 位置/配置夹具 | 范围内原记录 | 通过创建前检查 |
| --- | --- | --- |
| R=1，DeviceLayer=1（GPU_0M实验值） | 39 | 30 |
| R=2，DeviceLayer=1（GPU_0实验值） | 217 | 82 |
| R=2，DeviceLayer=3（GPU_4实验值） | 217 | 217 |
| R=2，DeviceLayer=4（GPU_6实验值经原限制） | 217 | 217 |

这里沿用上轮phase 0和已知初始化mask条件，不把中心坐标当作原出生点。此后还需要原类型工厂、模型槽载入、EntityConfig和裁剪等；未完成的任务也不能按这些数当作已成功加载。

## 下游具体缺口

0x8fce2c→0x4c975c读取world/tutorial/EntityConfig.xml，属于上下文+0x1b0的另一个对象。其6个模型键、12个显式实例ID均能与本地图源记录关联。当前已确认文件关系和原读取入口，**尚未闭合device=6、culldistance、lodlevel、cullmode等字段到具体对象/裁剪器的消费与优先级**；不把6解释成这里的DeviceLayer阈值，也不凭文字另写过滤。

实际最终集合还缺：当前配置来源/版本、设备属性类型和值、持久调整值，原map/位置/缓存与任务完成状态，EntityConfig下游、模型槽请求/载入、相机裁剪和动态实体。没有这些现场，就保留条件清单，不选一个夹具充当雷电的真实结果。原现场材料仍为上轮列出的保存配置、档位/设备日志与进场状态，本轮不重复要求上传。

## 核验与交接

[device_instance_evidence.py](../tools/device_instance_evidence.py)重读原APK、XML和ITM并生成可审查清单；[native_device_instance_probe.py](../tools/native_device_instance_probe.py)执行原条件、等级查询片段和创建前过滤；[native_device_selection_probe.py](../tools/native_device_selection_probe.py)执行原GPU选择/priority与更新顺序。

实验中的设备属性、已解析JSON树和XML列表是明确输入；字符串、C库转换、部分JSON值访问/复制、容器存储、分配/释放和日志由适配回调提供。JSON迭代和树遍历所列原函数、原专用选择/过滤分支实际执行；没有执行JSON/XML解析器、设备采集、完整配置初始化、任务队列、工厂或渲染。参数写入只记录边界，未写入任何实际游戏状态。

```sh
.venv/bin/python tools/device_instance_evidence.py --probe
.venv/bin/python tools/device_instance_evidence_tests.py
```

新增8项检查覆盖原指纹、八种条件运算、嵌套/先匹配/后备选择、默认后覆盖顺序、原上限、查询优先级和缺项、三道过滤正负分支、原文件全量条件结果。原材料缺失时CI会明确跳过相应实验，CI绿色不表示原进程等效。

本地连同加载链、区块选择、资源读取和光照表的相关回归共38项通过，0失败、0跳过。41份原包SHA和私有角色存档字节与审计/备份基线一致；未重建prototype或转换预览。

下一有界入口：0x4c975c的EntityConfig字段写入及其对象查询/裁剪消费者，再接原模型槽和实际资源请求；继续保留真实设备现场缺口。全部本地输出和交接在analysis/raw/device-instance-20261109/，自动续跑继续暂停。
