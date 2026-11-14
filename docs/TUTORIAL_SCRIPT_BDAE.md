# 新手脚本：BDAE 的 ZIP 内层审计

本批核对了当前原文件索引中全部 10,224 条 BDAE，优先检查新手地图与任务资料明确引用的 179 个路径。没有找到新的任务脚本正文，没有重新搜索所有 39,665 份外层文件正文，也没有改游戏、地图、存档或服务。

## 原代码入口

原 ARM64 SHA256 为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

- 原 `127b640` 保存流位置、读取 4 字节、恢复位置，实际比较 `0x04034b50`，即 ZIP 本地头 `PK\x03\x04`。
- 原 `117f010` 在原 ZIP 开关允许且上述检查通过时构造 `127a350`；按原 `+4b` 先请求 `little_endian_not_quantized.bdae` 或 `little_endian_quantized.bdae`，取不到时尝试另一种。
- `version.nfo`、`metadata.xml`、`thumbnail.txt` 没有在这个原模型选择分支中被请求。不能因此证明它们从来没有其他消费者；本批仍实际检查额外内容，而不是凭名字排除脚本。

原反编译、调用锚点和程序 SHA 保留在 `analysis/raw/tutorial-script-bdae-20261115/`，没有将原代码转储放进公开目录。

## 当前目录的完整矩阵

| 原外层格式 | 数量 | 处理方式 |
| --- | ---: | --- |
| 裸 BRES | 44 | 原 GBMP 解压后已经是直接的模型字节；核对 BRES 头与声明长度，不重复搜索正文 |
| 真实 ZIP | 10,180 | 核对内层中央目录与本地头 |

全部 34,579 个内层成员的 ZIP method 均为 0，即直接存放。没有 Deflate/LZMA 等第二层 ZIP 压缩，也没有发现加密分支、ZIP64、非空 ZIP 注释、成员注释、额外字段或未引用的中央目录前空隙。

| 内层实际内容 | 数量 | 核对结果 |
| --- | ---: | --- |
| 原名、原 BRES 头与长度一致的模型 | 10,180 | 不凭 `.bdae` 扩展名认定；核对实际 BRES 头 |
| `version.nfo` | 10,180 | 内层 CRC/长度通过，内容全部为原版本 `0,0,0,946` |
| `metadata.xml` | 9,683 | 内层 CRC/长度通过，全部同一个 SHA；51 字节空 `metadata` 元素 |
| `thumbnail.txt` | 4,536 | 内层 CRC/长度通过，全部同一个 SHA；11 字节缩略图文件名 `generic.png` |

所有中央目录与本地头的名字、方法、标志、长度、CRC 字段及压缩范围相符，无成员重叠。外层 BDAE 的 GBMP 解压长度和 CRC 全部通过。额外成员及版本文本共 24,399 个实际读取并验证了内层 CRC；没有把另外 10,180 个普通模型的“CRC 字段相符”冒称为再次执行了其内层 CRC 全检。

对额外成员与版本文本检查 6 个目标名的 ASCII、UTF-16LE、UTF-16BE：`tutorial_quest202`、`tutorial_npc972_ai`、`tutorial_obj188_trigger`、`tutorial_obj190_khalin_hammer`、`Skill240_OnSkillHit`、`Skill228_OnSkillHit`，均无命中。没有发现 Lua/LuaJIT 魔数或新的内层 ZIP/SWF 容器。

## 新手引用与覆盖边界

优先集合来自当前正式新手地图 manifest 与冻结原任务资料中的明确 BDAE 字符串，179 个路径全部在现有索引解析成功。它只是有来源的检查优先级，不能当成已还原了全部活动 NPC、显示选择或原服任务规则。

随后按原索引穷尽了其余 BDAE 记录，逐包数量、物理记录位置、成员类型/方法矩阵、额外内容 SHA 均保留私有报告。没有按文件名将未知内容跳过；若遇不支持的加密、ZIP64 或格式错误，工具会明确报告错误，不试猜解码。

这项结论是：**当前这些模型 ZIP 中，没有藏着一份遗漏的独立脚本文件或第二层 ZIP 压缩内容。** 它不证明原 BRES 中所有未知数据字段都没有未命名或混淆行为，更不证明任务脚本一定只在服务器。InitialFeed、OF_PP 的实际生产者/解码，以及未观测的 Android 挂载目录，仍沿上一批明确缺口继续。

## 复跑

```sh
.venv/bin/python tools/tutorial_script_bdae_audit.py
.venv/bin/python tools/tutorial_script_bdae_tests.py
```

当前本地 10 项检查通过。9 项 ZIP/格式边界检查可在没有原资源的公开环境运行；实际原资料报告用例在缺私有报告时明确跳过，不生成假的成功报告。没有浏览器/GPU或完整 Android 运行验收，因为本批不改变游戏画面和运行行为。
