# 新手任务正文候选：原输入目录、路径和覆盖边界

2026-11-15，继续原脚本来源专项，人物、通用地图及其它工作后置。前一批交接是 `d30e1d3`；本批没有补任务规则、创建任务状态、修改角色或更新Railway。

**原版怎样找到 InitialFeed.dat 的目录已经有具体Java和原生代码关联；当前正文仍未解开，也没有证据说明它就是任务程序。** 原始导出与项目文件一致，不能把失败说成迁入项目时改坏了文件。

## 原目录从哪里来

原 `309a8c` 通过JNI取得 `PackageUtils/AndroidUtils` 的几个目录字符串，保存到原全局COW字符串。原 `14f1890` 随后把其中三个目录交给路径管理器，原DEX生产者见 [副本与Java路径](TUTORIAL_SCRIPT_INITIALFEED_ORIGIN.md)：

| 原Java方法 | 原字符串位置 / getter | 原setter / 路径管理器字段 | 原Java生产者 |
| --- | --- | --- | --- |
| `RetrieveDataPath` | `2526fc0` / `2f8738` | `1541fe0` / `+8` | 读取 `MainActivityPrefs` 的 `SDFolder`；使用与默认空串的引用比较分支，否则取 `Context.getExternalFilesDir(null).getAbsolutePath()` |
| `RetrieveSavePath` | `2526fc8` / `2f8748` | `1542014` / `+10` | `Context.getFilesDir().getAbsolutePath()` |
| `RetrieveTempPath` | `2526fd0` / `2f8758` | `1542048` / `+18` | `Context.getCacheDir().getAbsolutePath()` |

Java的实际指令是字符串引用比较，不能简化为 `isEmpty` 或 `equals`。本批没有读取Android实际偏好、用户设备目录或伪造JNI结果。另一个原 `2f86b4` 可以复制同一组字符串，已与实际JNI填入分开记录。

`8e3864` 为 `InitialFeed.dat` 调用原 `15427d4`，明确输入flags0，因此选路径管理器 `+8` 的数据目录，不是保存角色的内部目录。原 `1541858` 构造时清零大小写标志；`15427d4` 在该标志置位时才把名字转为小写。其它目录、原映射表和实际会话输入仍需分别核对，不能用网页工程路径代替Android现场。

## 原路径控制实际执行到了哪

`tools/tutorial_script_path_source_probe.py` 执行三个原getter和setter，并执行完整原 `15427d4`，使用明确标出的 `/research-data`、`/research-save`、`/research-cache` 输入：

- 三个原getter返回正确字符串槽，原setter保存相同目录字节到对应字段。
- 原映射表为空、无额外目录别名的明确条件下，flags0产生 `/research-data/InitialFeed.dat`，返回flags0；将大小写标志置位则产生小写文件名。没有打开文件，没有修改或解码文件内容。
- COW字符串存储、可写缓冲和有界ASCII libc是具名宿主接口。这里没有执行完整Android启动、JNI或实际文件系统打开，不能把两条控制路径称为原模拟器实际打开的路径。

工厂入口也已收窄：原 `10f75d4` 只在 `25ba0e0` 为空时接受指针，已有指针时返回0并保持它。三组原指令控制核对了这个条件。此前笼统的“工厂可被覆盖”不准确，应称“可在未设置时注册”；没有得到实际替换的证据。原构造/默认getter另会安装默认工厂。

## 路径映射和直接调用的边界

原 `1542094` 确实会读取指定文件、按参数进行字节转换、检查原尾标记，再将记录放进路径映射树；它还处理 `.crc` 与 `.dyn.crc` 路径。这个函数的存在不是它在本次会话运行过的证据，也不能把该转换套到 `InitialFeed.dat`。当前源目录没有命名为这些后缀的散装文件；此检查不覆盖未知名字或未知外部目录。

为避免依赖Ghidra是否已经识别函数，本批直接检查原 `.text` 全部28,641,180字节中的对齐B/BL立即分支：任务getter `c99370` 仍为此前14处，scripts getter `c994c8` 无直接分支，skill-event getter `c993f8` 仍只有 `5b7e00`。`1542094` 和 `10f75d4` 也没有这种直接分支；三个目录setter各有 `14f1890` 中的一处调用。

这只闭合立即分支清单，不覆盖间接虚调用、函数指针、内联字段读取或其他模块。异常展开表引用仍不算调用，也不能因为Ghidra缺少函数定义就忽略原指令存在。

## 原副本、缓存和资源包覆盖

最初 `/Users/kevin/Public/com.gameloft.android.ANMP.GloftO2HM/files/InitialFeed.dat` 与项目当前文件是两个独立路径，均1084字节，逐字节一致，SHA256均为 `a794b8e66758bdfd0baa09dd472c31034a5c16360f7ac38d5441bf093f3e5c55`。原APK成员和现有GBMP索引没有同名候选；不能因此排除动态名字或未提供的外部内容。完整路径核查与原DEX复制过程留在私有origin证据中。

原默认FS需要分清：已打开流缓存、按组查找的挂载归档、最后的散装文件打开是不同来源。缓存命中不等于改名，也不能凭空创建一条成功流；具体缓存生产者及可选hotfix挂载见 [缓存和挂载入口](TUTORIAL_SCRIPT_STREAM_REGISTRATION.md)。尚未观察到 `InitialFeed.dat` 命中哪个活动归档或缓存，不能将候选覆盖顺序当成实际选中结果。

## 与完整主线之间的剩余缺口

原实际目录偏好、资源挂载与最终读入流仍未观察到；现有同一份磁盘字节在已知原头变换与校验分支中仍未产生有效正文。没有因此尝试其他密钥、编码或构造通过校验的任务内容。

这一批补齐了原输入的真实生产链，没有补出首次接取、NPC出现、升降台启动、取锤、目标完成或奖励。下一步应从实际流选中或另一个明确脚本消费者取证；若需要用户材料，应精确对应原目录/挂载缺口，不能泛称需要更多游戏资源。

复跑：`.venv/bin/python tools/tutorial_script_path_source_tests.py`。5项本地通过；不含原库的独立环境应执行1项分支解码检查，跳过4项原指令检查。原反编译、完整指令、路径控制和交接仅留 `analysis/raw/tutorial-script-path-source-20261115/`。
