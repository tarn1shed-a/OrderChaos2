# 《混沌与秩序 2》3.1.3a：资源加载流程静态分析

分析日期：2026-11-07（悉尼）。样本由用户提供。只读取 ZIP、AndroidManifest、DEX 指令和 ARM64 原生库字符串；未安装或执行 APK，未请求游戏服务器。

## 结论

这份 APK 包含 Android 启动层及 `libOrderChaos2.so`。它不是完整游戏数据包：`assets/` 只有 `GameOptions.json` 和 `crashlytics-build.properties`，APK 内没有 `.obb`。其余 PNG 等界面文件不能替代完整模型、地形、动画与音频。

原生库中明确存在两个与此构建版本一致的资源包文件名：

```text
main.31320.com.gameloft.android.ANMP.GloftO2HM.obb
patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb
```

这是后续寻找资源的具体线索。仅凭字符串不能证明两个文件都必需、内部格式是什么、读取优先级是什么，或任何下载服务器仍可用。此前把“没有内嵌 OBB”解释为“缺失部分资源”是合理判断，现在已补充了外置 OBB 的直接线索。

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
Android 启动 MainActivity
  ├─ onCreate → System.loadLibrary("OrderChaos2")
  ├─ e() → 创建 SurfaceView、注册 Surface 回调
  │        → SilentInstaller.Schedule(context)
  └─ onResume 的未初始化分支 → 启动 GameInstaller Activity
          └─ 存储目录选择、下载组件、资源包处理
          └─ startGame → M() → setResult(1)、finish()

MainActivity 初始化/返回处理
  ├─ c() → JNIBridge.NativeInit()
  └─ surfaceChanged → JNIBridge.NativeSurfaceChanged(surface, width, height)

原生层资源路径线索
  ├─ AndroidUtils.RetrieveDataPath()
  │    ├─ 优先读取 MainActivityPrefs / SDFolder
  │    └─ 回退到 Context.getExternalFilesDir(null)
  ├─ main.31320.…obb / patch.31320.…obb
  └─ 分段/DLC 下载相关字符串
```

上图表示已找到的静态关系，不表示所有设备必然按完全相同顺序走完每个分支。完整 NativeInit 调用条件、下载触发条件、OBB 挂载及增量覆盖顺序仍需继续分析原生函数或运行日志。

## 可以复核的证据位置

脚本输出 `analysis/raw/resource-flow.dalvik.txt`。下面的偏移是对应方法内的字节偏移，不是文件行号；脚本版本变化不会影响按方法名定位。

| 方法 / 来源 | 偏移或内容 | 能说明什么 |
|---|---|---|
| `MainActivity.onCreate(Bundle)` | `0x0094` 的 `OrderChaos2` 字符串；`0x0098` 调用 `System.loadLibrary` | 游戏通过 Android 原生库启动 |
| `MainActivity.e()` | 创建 `SurfaceView`；`0x007c` 调用 `SilentInstaller.Schedule` | 渲染表面交由原生层，存在静默安装/更新调度 |
| `MainActivity.onResume()` | `0x0044` 起构造 Intent；`0x006e` 调用 `startActivityForResult` | 未初始化分支进入资源安装器 |
| `MainActivity.c()` | `0x0000` 调用 `JNIBridge.NativeInit()` | Java 到原生初始化的桥接点 |
| `MainActivity.surfaceChanged(...)` | `0x000e` 调用 `NativeSurfaceChanged` | Android Surface 交给原生层 |
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

## 下一步应寻找哪些文件

优先在自己保留的安装包归档、旧 Android 设备或备份中寻找：

```text
Android/obb/com.gameloft.android.ANMP.GloftO2HM/
  main.31320.com.gameloft.android.ANMP.GloftO2HM.obb
  patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb

Android/data/com.gameloft.android.ANMP.GloftO2HM/files/
  （整个目录，包括 pack.info、索引、下载包和可能存在的 ui/Font/）
```

`ui/Font/` 出现在客户端路径常量中，但文件是否存在、是否包含中文字体，需拿到数据后验证。`SDFolder` 可能指向其他存储卷，因此上述路径是优先检查位置，不是穷尽列表。

拿到 OBB 后先记录哈希、检查文件头和目录，再决定解析器；不要直接假定扩展名对应 ZIP、Unity AssetBundle 或 Unreal PAK。拿到完整数据目录后先生成目录清单和扩展名分布，再挑单个模型、贴图做最小解析实验。

## 当前未完成的验证

- 尚未执行 APK，所以不能确认启动是否成功、缺资源时的实际日志和网络响应。
- 未验证资源服务器可用性，未猜测或请求下载接口。
- 未解析原生文件读取函数，不能确认 main / patch / DLC 的覆盖优先级或加密/压缩方式。
- 未恢复游戏通信协议、登录流程、战斗逻辑或原版服务端。
- 未确认样本是否包含可用的中文完整资源。

## 与网页原型的关系

`prototype/` 是独立协议和独立地图的联机原型：Canvas 2D 绘制、WebSocket 收发输入与快照、Node 服务端固定 20 Hz 计算移动。它验证的是浏览器多人基础，与原游戏资源解析是否成功无关，也不连接 Gameloft 服务。

后续可沿两个方向推进：一是找到完整数据并恢复一个模型/小场景；二是在现有服务端增加可保存角色、共同攻击的怪物和战斗结果同步。

## 工具与复现

提取器使用 Androguard 4.1.3 的 APK / DEX 接口，调用 `get_instructions_idx()` 保留方法内偏移。见 [Androguard DEX API](https://androguard.github.io/androguard/reference/androguard/core/dex/index.html)。结论以本地样本为依据，API 文档仅用于工具使用。

执行命令和环境说明见根目录 `README.md`。原 APK 未被修改。
