# 《混沌与秩序 2》3.1.3a：资源加载流程静态分析

分析日期：2026-11-07（悉尼）。样本由用户提供。本次复核读取 APK、Manifest、DEX、ARM64 指令以及已导出的资源包；未安装或执行 APK，未请求游戏服务器。

## 结论

这份 APK 包含 Android 启动层及 `libOrderChaos2.so`。它不是完整游戏数据包：`assets/` 只有 `GameOptions.json` 和 `crashlytics-build.properties`，APK 内没有 `.obb`。其余 PNG 等界面文件不能替代完整模型、地形、动画与音频。

原生库中明确存在两个与此构建版本一致的资源包文件名：

```text
main.31320.com.gameloft.android.ANMP.GloftO2HM.obb
patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb
```

这是寻找资源的线索，不能据此认定两个文件都必需，或用户看到的 829 MB 就是 OBB。现在已拿到 `Android/data/…/files` 的导出目录，其中包含 DLC 清单、分段资源包和部分配套索引，应优先分析这些实际文件。

目前已确认启动层选择资源目录、原生初始化调用 Java 取回目录，并定位了原生包索引读取、名称查找和条目解压函数。本地读取器已实现相同的名称归一化、哈希和碰撞检查。各类包的完整挂载顺序及地图/角色运行时请求仍未全部接通。下文将静态调用证据、数据实验和未确认部分分开。

## 样本身份

| 项目 | 结果 |
|---|---|
| 原文件 | 用户本地下载的 `com.gameloft.android.anmp.glofto2hm.apk` |
| 字节数 | 56,639,416 |
| SHA-256 | `4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe` |
| Manifest 包名 | `com.gameloft.android.ANMP.GloftO2HM` |
| 版本 / versionCode | `3.1.3a` / `31320` |
| 入口 | `com.gameloft.android.ANMP.GloftO2HM.MainActivity` |
| 原生库架构 | `arm64-v8a`、`armeabi-v7a`、`x86` |
| ARM64 主库大小 | 38,892,376 字节 |

注意文件名用小写包名，而 Manifest 与内部路径使用上表中的大小写。搜索、提取和恢复 Android 目录时，应保留实际目录名称，避免在区分大小写的文件系统中找错路径。

本次没有将签名与可信官方样本比对，因此不作“官方未修改包”结论。

## 已确认的启动与加载关系

```text
Android 初始化 FrameworkApplication，随后启动 MainActivity
  ├─ onCreate → System.loadLibrary("OrderChaos2")
  ├─ e() → 创建 SurfaceView、注册 Surface 回调
  │        → SilentInstaller.Schedule(context)
  └─ onResume 的未初始化分支 → 启动 GameInstaller Activity
          └─ 选择目录，写 MainActivityPrefs / SDFolder
          └─ startGame → M() → setResult(1)、finish()

MainActivity.onActivityResult：请求码 100、结果码 1
  ├─ d() → b() + c() → JNIBridge.NativeInit()
  │    └─ 原生一次性初始化（正常 JNI 路径）
  │         └─ 调用 AndroidUtils.RetrieveDataPath()
  │              ├─ 读取 MainActivityPrefs / SDFolder
  │              └─ 回退分支：Context.getExternalFilesDir(null)

MainActivity 的 Surface 回调（独立于安装器返回处理）
  └─ surfaceChanged → JNIBridge.NativeSurfaceChanged(surface, width, height)

其他资源线索（不表示已连接为调用顺序）
  ├─ main.31320.…obb / patch.31320.…obb
  └─ DLC_Info.json、DLC_UniversalPack.json、preloadTextures.txt
```

上图表示静态关系，不表示已在雷电中观测到所有分支成功执行。原生目录调用存在一次性初始化保护，并依赖 JNI 环境、类与方法解析成功；下载触发条件、包挂载及增量覆盖顺序仍待分析。

## 本课：怎样找到线索，再验证

### 1. 从 Manifest 找入口，不靠猜类名

`analysis/raw/AndroidManifest.xml` 第 37–41 行显示，`MainActivity` 同时声明 `android.intent.action.MAIN` 与 `android.intent.category.LAUNCHER`。这比看到一个名字叫 Main 的类更强：启动入口有 Manifest 声明佐证。`application` 还声明了 `FrameworkApplication`，其初始化不能遗漏。

沿入口检查 DEX 指令，在 `MainActivity.onCreate` 内找到：

```text
0094 const-string v0, "OrderChaos2"
0098 invoke-static v0, Ljava/lang/System;->loadLibrary(Ljava/lang/String;)V
```

再检查 APK 的 ZIP 目录，确实存在 `lib/arm64-v8a/libOrderChaos2.so` 等架构版本。这是“代码引用”和“实际文件”两条证据。Java 的 `JNIBridge.NativeInit` 带 `public static native` 标志，因此没有 Java 函数体是正常的，需要继续查原生实现。

### 2. 搜索路径词，再找谁写、谁读

搜索 `SDFolder`、`getExternalFilesDir`、`/Android/data/`，找到两端：

- **写入端**：`GameInstaller.onCreate` 调 `L()` 选择目录，在方法偏移 `0x0126` 写入偏好项 `SDFolder`，并在 `0x0156` 设置 `DATA_PATH`。`L()` / `K()` 检查默认外部文件目录及其他存储卷；回退常量是 `/sdcard/Android/data/com.gameloft.android.ANMP.GloftO2HM/files`。
- **读取端**：`AndroidUtils.RetrieveDataPath` 在 `0x0008` 引用 `SDFolder`，读取同一偏好设置，并有 `getExternalFilesDir(null).getAbsolutePath()` 回退分支。

便于理解的概括是“安装器记住目录，游戏初始化取回目录”。这不是原 Java 源码的逐字还原；DEX 对空字符串的具体判断使用引用比较，尚未审计其健壮性。

用户导出的 `game-data/com.gameloft.android.ANMP.GloftO2HM/files/` 是电脑上的研究副本；原 APK 不认识这个 Mac 路径。它使用的是 Android 上的目录。两者末级目录和实际资源文件吻合，但没有导出的偏好设置或运行日志，不能确认那次安装的 `SDFolder` 最终值。

### 3. 原生库里有方法名，仍要验证它真的被调用

ARM64 库的 `RetrieveDataPath` 字符串在 ELF 虚拟地址 `0x1df7121`。单独出现这个字符串只算线索。本次继续跟踪指令，发现：

```text
导出 NativeInit @ 0x30c0c0
  0x30c0c8 → 0x309a5c
  首次初始化分支 → 0x309a8c
  0x309b90 / 0x309b94：加载 "RetrieveDataPath"
  0x309ba4：GetStaticMethodID，签名 ()Ljava/lang/String;
  0x309bb4：返回的方法 ID 存入 x21
  0x309cac：把 x21 作为调用参数
  0x309cb0 → 0x2ec844 → CallStaticObjectMethodV
  0x309cd0：GetStringUTFChars，读取返回的 Java 字符串
```

JNI 表偏移 `0x388 / 0x398 / 0x548` 在 64 位下分别对应索引 `113 / 115 / 169`，语义对照了 [Oracle JNI 函数规范](https://docs.oracle.com/en/java/javase/17/docs/specs/jni/functions.html)。方法 ID 的寄存器传递也连续吻合。因此可标为**已确认的静态调用路径**，而非仅凭名字推断。

本次截取的原生指令保存在本地 `analysis/raw/native-startup-evidence.txt`。这些地址属于该 SHA-256 样本的 ARM64 库，不能直接套到 x86 版或其他版本；它们也不同于 DEX 的方法内字节偏移。

### 4. 把 APK 中的名字与实际下载文件对应

| APK 原生库线索 | 导出目录中的实际文件 | 能确认什么 |
|---|---|---|
| `DLC_Info.json`，`0x1e3219b` | 同名 JSON，17 个 DLCpack，关联 worldname 和文件逻辑 ID | 有 DLC/世界分组清单；不等于包内字节索引 |
| `DLC_UniversalPack.json`，`0x1e324b7` | 同名 JSON，animation/model/sound 组合 | 存在跨世界的下载分组 |
| `preloadTextures.txt`，`0x1e04320`，代码引用在 `0x4d1a18` | 同名纹理路径列表 | 是继续追踪预加载调用的线索 |
| 分段下载日志文本 | `d_o_w_n_l_o_a_d_e_d.txt` 中有 494 条分片记录 | 支持分片下载解释；不能仅凭文本认定完成或证明读取此记录文件的调用点 |

导出目录现有 94 个文件、1,006,498,744 字节，包含辅助文件与子目录。它不是最初 829 MB 网络下载量的复测，也不能独立证明全部必需资源齐全或数据版本完全匹配。`InitialFeed.dat` 为 1,084 字节非明文数据，格式暂未解释。

### 5. 用一个模型验证“索引 → 偏移 → 解压 → 校验”

选取 `res_npc.bin` 内的 `model/npc/character/elf/female/oc2_elf_f_body_01.bdae`。配套原始 `res_npc_i.bin` 的头为 `01 49 4b 50`，随后是 32 位小端条目数；每条记录为 28 字节。

第 10 条记录（从 0 计数）位于索引偏移 `8 + 10 × 28 = 288`，按 7 个小端 uint32 读取为：

```text
[985527393, 156413, 380, 524371, 173381, 82240, 0]
```

先提出可检查的解释，再到包内验证：

| 字段解释 | 预测 | 实际验证 |
|---|---|---|
| 第 2 个整数是 local header 偏移 | 到 156413 应看到包内记录头 | 确实是 `GBMP`，并附目标模型路径 |
| 第 4 个整数的低 16 位是头总长 | `524371 = 0x00080053`，头长 83 | 数据从 `156413 + 83 = 156496` 开始 |
| 第 4 个整数的高 16 位是压缩方法 | 方法 8，尝试 raw DEFLATE | 成功解压 |
| 第 5 / 6 个整数是解压 / 压缩长度 | 82,240 字节解到 173,381 字节 | 长度一致 |
| 包内 header 的 CRC32 应匹配内容 | `6a576f24` | 重新计算仍为 `6a576f24` |

解出内容以 `PK 03 04` 开头，内部 ZIP 可读取，里面的模型数据以 `BRES` 开头。继续跟踪原生读取函数后，原来未知的第 1、3 个整数已分别确认为文件名哈希和名称表偏移；最后一个整数对应 ZIP flags，见后续原生复核。CRC 在这里校验解析结果的一致性，不验证发行来源。

然后把字段解释扩展到所有有配套索引的包：**27 包、35,924 条结构记录全部字段匹配**。这增强了字段解释的可信度，但没有重新解压这 35,924 个负载，也没有证明某次运行逐条使用了这些索引。其余 14 个 GBMP 包没有配套 `_i.bin`；原生代码存在无索引时读取包目录或扫描本地记录的回退分支。

`tutorial.bin` 就没有配套 `tutorial_i.bin`。另一个最小实验能顺序读出 `world/tutorial/terrain/-029_-005.trn`：144 字节解到 30,660 字节，CRC `1ad64054`，内容头为 `ATIL`、版本 9。没有索引时仍能解析记录，不代表原引擎也采用相同的顺序扫描策略。

### 6. 自己复现

在项目根目录执行；下面的资源检查工具仅使用 Python 标准库，不联网、不写资源：

```bash
# 一个地形条目：偏移、解压长度、CRC、ATIL 头
.venv/bin/python tools/inspect_resource_entry.py

# 一个模型的原始索引记录，以及全部配套索引的结构交叉验证
.venv/bin/python tools/inspect_resource_entry.py \
  --pack res_npc.bin \
  --entry model/npc/character/elf/female/oc2_elf_f_body_01.bdae \
  --verify-all-indexes

# 从原 APK 重新生成 Manifest 与 DEX 反汇编；需要 requirements-analysis.txt
.venv/bin/python tools/analyze_apk.py /path/to/game.apk
```

可先读 `tools/inspect_resource_entry.py` 的 `index_checks`：每一个布尔检查对应一个可被数据推翻的字段解释。不要先记住某个数字是偏移；先看这个解释如何预测读到什么，再核对实际字节。

## 原生资源读取复核与本地实现

本轮继续完成了以下静态定位。下列函数标签由本项目命名，原始库未保留这些源码名称；地址仅适用于上文样本的 ARM64 库。

| 地址 | 已确认行为 |
|---|---|
| `0x54cabc` | 构造配套 `_i.bin` 路径，打开并识别 `0x504b4901`；读取 ZIP 中央目录，有无效/缺失索引的回退分支，接受 `PK` 与 `GBMP` 本地头 |
| `0x54c604` | 去除开头一组 `./`，ASCII 大写转小写，反斜线转正斜线；计算名称哈希；按无符号哈希二分查找，同哈希候选再比较名称 |
| `0x556be0` | 调用名称查找函数，再调用条目读取函数；另有跨子包索引分支 |
| `0x54da70` | 用条目偏移与头长定位数据；分别处理方法 `0`、`8`、`14` |
| `0x5565f0` | 构造归档，调用 `0x54cabc` 并排序内存条目表 |
| `0x54bc84` | 先检查直接/缓存路径，再依次搜索多组归档；`this+0x98` 组命中时输出 patch archive 日志 |
| `0x8f8508` | 引用 `res_t.bin` 与 `res_t_upd%d.bin`；遍历版本号 10–15 并注册可用归档。完整搜索优先级仍需继续核实 |
| `0x7c1478` | 经重定位指针取得 `DLC_Info.json`，传给 `0x7c2144`；这也解释了为什么仅搜索直接字符串地址交叉引用会漏掉该调用 |

名称哈希的每步是 `h = (h * 13 + signedByte) & 0xffffffff`。名称表偏移按每个 UTF-8 名称的 `(byteLength + 4) & ~3` 累加；这是为 NUL 和四字节对齐预留空间。对全部 35,924 条记录验证了这两项新解释及 ZIP flags，没有不匹配。

`tools/resource_packs.py` 的 `ResourceArchive` 已实现恢复出的查找规则，按哈希定位后继续比较名称，避免哈希碰撞读错文件。缺少索引时解析本地记录；已有索引若与包内记录不一致，本地工具明确报错，不沿用原引擎的容错策略。尚未把多归档覆盖规则假定为“文件名排序”或“最后解包者优先”。

构建器已使用该读取器按资源名读取必需文件。加入角色骨骼和动作后，空目录重建当前场景仅需校验、提取 **57** 个源文件，生成 20 个模型、23 张贴图、39 个场景实例与 3×3 地形。生成模型的 `source` 使用包内路径，避免把开发机器的绝对路径写入可迁移资源。

原生指令可复现导出到忽略目录；工具会核对原生库 SHA-256，拒绝把这些地址用于其他构建：

```bash
.venv/bin/python -m pip install -r tools/requirements-native.txt
.venv/bin/python tools/analyze_native_resources.py /path/to/game.apk
```

输出为 `analysis/raw/native-loader/report.json` 和 9 个相关函数的反汇编。它只读取 APK，不运行 APK 或原生代码，不请求游戏服务。

## 可以复核的证据位置

脚本输出 `analysis/raw/resource-flow.dalvik.txt`。下面的偏移是对应方法内的字节偏移，不是文件行号；脚本版本变化不会影响按方法名定位。

| 方法 / 来源 | 偏移或内容 | 能说明什么 |
|---|---|---|
| `MainActivity.onCreate(Bundle)` | `0x0094` 的 `OrderChaos2` 字符串；`0x0098` 调用 `System.loadLibrary` | 游戏通过 Android 原生库启动 |
| `MainActivity.e()` | 创建 `SurfaceView`；`0x007c` 调用 `SilentInstaller.Schedule` | 渲染表面交由原生层，存在静默安装/更新调度 |
| `MainActivity.onResume()` | `0x0044` 起构造 Intent；`0x006e` 调用 `startActivityForResult` | 未初始化分支进入资源安装器 |
| `MainActivity.c()` | `0x0000` 调用 `JNIBridge.NativeInit()` | Java 到原生初始化的桥接点 |
| `MainActivity.surfaceChanged(...)` | `0x0010` 调用 `NativeSurfaceChanged` | Android Surface 交给原生层 |
| `AndroidUtils.RetrieveDataPath()` | `0x0008` 的 `SDFolder`；`0x002c` 的 `getExternalFilesDir` | 有保存的资源路径和默认外部文件路径 |
| `GameInstaller.<clinit>()` | `0x0018` 的 `MainActivityPrefs`；`0x0066` 的 `/Android/obb/` | 偏好项名称、外置 OBB 搜索目录 |
| `GameInstaller.<init>()` | `0x001e` 的 `/pack.info` | 安装器引用包信息文件，内容格式未解析 |
| `GameInstaller.L()` | 回退路径 `/sdcard/Android/data/com.gameloft.android.ANMP.GloftO2HM/files` | 外部文件目录是重点取证位置 |
| `GameInstaller.startGame()` / `M()` | `setResult(1)`、`finish()` | 安装器完成后返回 Activity |
| `DownloadComponent.a(boolean)` | `HttpURLConnection.connect()`、`Content-Length`、`.zip` | Java 中存在 HTTP 下载和 ZIP 包处理路径 |
| `GLUtils.ZipFile.unZip(...)` | `java.util.zip.ZipFile`、遍历 entry 和写文件 | 至少有一条 ZIP 解包路径；不等于所有 OBB 都是普通 ZIP |
| `JoinFiles.join(...)` | `joinedFile.zip` | 有分片合并相关实现 |
| ARM64 主库字符串 | 两个 `31320` 的 OBB 文件名 | 原生层识别与此构建相匹配的 OBB 名称 |
| ARM64 主库字符串 | `[oc2][sgmt download]`、`RequestDownloadDLCPack`、`RequestDownloadAllPacks` | 存在分段及 DLC 下载相关实现线索 |
| ARM64 主库字符串 | `GameOptions_saved.json`、`GameOptionsEtag.t`、`gameoptions.gameloft.com` | 设备选项配置具有保存和更新机制；该域名不应被误认成模型数据下载地址 |

ARM64 ELF 有 `.dynsym`（2,017 个符号表项），未见 `.symtab` 或 `.debug_info`。仍可利用导入/导出名称和字符串交叉引用继续定位函数，但不能期待恢复完整源码名、注释和原始工程。

## OBB 线索与其他目录

以下是 APK 中还存在的目录线索，不是要求重新下载的清单。已有 data/files 数据应先分析；仅在核查其他安装分支或备份时参考：

```text
Android/obb/com.gameloft.android.ANMP.GloftO2HM/
  main.31320.com.gameloft.android.ANMP.GloftO2HM.obb
  patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb

Android/data/com.gameloft.android.ANMP.GloftO2HM/files/
  （整个目录，包括 pack.info、索引、下载包和可能存在的 ui/Font/）
```

`ui/Font/` 出现在客户端路径常量中；是否有可用的完整中文字形仍须单独验证。`SDFolder` 可能指向其他存储卷，因此上述路径不是穷尽列表。

若后续拿到 OBB，仍须先检查哈希、文件头和目录，不能把当前 `.bin` 的格式结论直接套到 OBB 上。

## 当前未完成的验证

- 本次没有执行 APK；用户报告原客户端提示“无法连接服务器”，但尚未采集对应运行日志，不能据此认定为资源缺失或停服。
- 未验证资源服务器可用性，未猜测或请求下载接口。
- 已定位原生名称查找、索引和解压函数，尚未完整确认 main / patch / DLC 与所有其他归档组的覆盖优先级，也未实机观察各分支成功执行。
- 未恢复游戏通信协议、登录流程、战斗逻辑或原版服务端。
- 未确认样本是否包含可用的中文完整资源。

## 与网页原型的关系

`prototype/` 的网络、战斗和存档逻辑是独立实现，Node 服务端按目标 20 Hz 计算移动。它有无需原资源的 2D 页面，也有展示已转换地形和模型的 3D 页面；都不连接 Gameloft 服务。读取这套新代码属于框架学习，不代表已逆向出原版网络或战斗规则。

森林精灵节点、蒙皮与兼容原始行走/待机片段已接入网页，见资源接入报告。后续重点是跨包覆盖顺序、其他动作、地表材质和导航数据，并结合原客户端运行日志验证。已有网页功能不能充当原版协议和游戏规则的证据。

## 工具与复现

提取器使用 Androguard 4.1.3 的 APK / DEX 接口，调用 `get_instructions_idx()` 保留方法内偏移。见 [Androguard DEX API](https://androguard.github.io/androguard/reference/androguard/core/dex/index.html)。结论以本地样本为依据，API 文档仅用于工具使用。

执行命令和环境说明见根目录 `README.md`。原 APK 未被修改。
