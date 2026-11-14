# InitialFeed 原副本、Java 路径与复制边界

找到了最初 Public 导出目录里仍保留的副本，和项目当前文件逐字节一致。没有发现支持“移入项目时改变了这份文件”的证据；也没有找到另一份不同字节的内置副本用于解码。**这仍不证明原 Android 文件系统交给 `8e3864` 的逻辑流就是当前磁盘字节，更不证明文件包含任务脚本。**

本批仅新增 `tools/tutorial_script_initialfeed_origin_probe.py`。来源目录和字节记录留在忽略目录 `analysis/raw/tutorial-script-initialfeed-origin-20261115/`，未改原文件、存档、服务或部署，没有连接外服。

## 两份实际文件

| 来源 | 路径 |
| --- | --- |
| 原 Public 导出副本 | `/Users/kevin/Public/com.gameloft.android.ANMP.GloftO2HM/files/InitialFeed.dat` |
| 当前项目副本 | `game-data/com.gameloft.android.ANMP.GloftO2HM/files/InitialFeed.dat` |

两者均为 1084 B，SHA256 都是 `a794b8e66758bdfd0baa09dd472c31034a5c16360f7ac38d5441bf093f3e5c55`；逐字节相等。它们不是同一 inode，Public 导出目录也不是指向项目的符号链接。这只核对了当前两个副本，不把它称为经过不可变封存的原运行抓取。

## APK 与资源索引

原 APK 为 `/Users/kevin/Downloads/com.gameloft.android.anmp.glofto2hm.apk`，SHA256 `4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe`。863 个 ZIP 成员中没有 `InitialFeed.dat` 同名/规范名成员，也没有解包大小为 1084 B 的成员。原 GBMP 的 40,979 条目录记录也没有同名/规范名或同大小记录。

本批只检查目录及原 DEX，不重扫全部 payload。没有同名或同大小条目，不能排除另有包装、编码或动态生成内容。没有发现新的不同字节候选，因此未重复对两个相同副本运行已经冻结的解码控制，也未另试算法或 key。

## 三个原 Java 路径生产者

原 `classes.dex` SHA256 为 `088acd2c5cd39bb7da0a193a4cada1d6a10bdf9deaba2c70b27280174a5fd2e3`。下列方法均属于 `PackageUtils/AndroidUtils`，准确 Dalvik 记录为 `java-path-producer-01..03.dalvik.txt`：

| 原方法 | 真实来源与分支 |
| --- | --- |
| `RetrieveDataPath()` | 用 `GLUtils/SUtils.getPreferenceString(context,"SDFolder",GameInstaller.mPreferencesName)` 取得字符串；`001c if-eq v0,v1` 将其与常量 `""` **按引用比较**。引用不相等即返回原字符串；相等才调用 `Context.getExternalFilesDir(null).getAbsolutePath()`。这里不是 `isEmpty()` 或 `String.equals()`。 |
| `RetrieveSavePath()` | `Context.getFilesDir().getAbsolutePath()`。不能把它当 DataPath 的默认分支。 |
| `RetrieveTempPath()` | `Context.getCacheDir().getAbsolutePath()`。 |

原 `GameInstaller.<clinit>` 的 `0018/001c` 将 `mPreferencesName` 设为常量 `MainActivityPrefs`；只保存了该原片段（`java-path-producer-04`），不把其他静态初始化称为已经执行。`GLUtils/SUtils` 的 Context 版 getter（`java-path-producer-00`）真实调用 `getSharedPreferences(prefsName,0)`，再调用 `getString(key,"")`。

以上只是原方法的生产规则。本批没有读取真实 Android `MainActivityPrefs`，没有执行 Context，也没有提供或假定当前会话返回了哪条目录。JNI 到原全局/路径 setter 的链由主代理另核，本批不重复替换或执行该链。

## 安装与复制的明确范围

已从原 DEX 固定 8 个有实际 asset/read/write 调用的候选，其中原 `GameInstaller`、`SilentInstaller` 各有一个相同签名的 `a(String,String,String,String,boolean)` ZIP 复制消费者：先取得 `ZipEntry.getName()`，`016e` 取得成员输入流；`01b4` 将读取结果写入缓冲 `v2`，`01cc` 将**同一缓冲的同一读取长度**写出，中间没有内容变换。`.so` 成员另选 `LIBS_PATH` 并设置可执行权限。

原 `ResLoader.getInputStream`、`SUtils.getAssetAsString` 等 asset 方法接受参数，再调用 `AssetManager.open`；它们不是已经查明的 InitialFeed 复制调用。原 DEX 的 34,015 条字符串中没有规范化的 `InitialFeed` 名称，但动态拼接、原生生成或其他编码仍未排除。

准确结论是：**已核的通用复制方法没有提供导致这两个本地副本不同的证据；尚未把其中任一调用与 InitialFeed 的实际安装/生成输入绑定。** 当前没有新的正文、脚本加载器或原任务批准消息。下一项应由主代理沿已经找到的原路径规则和实际流选择继续，不能从名称检索未命中宣称文件或脚本不存在。
