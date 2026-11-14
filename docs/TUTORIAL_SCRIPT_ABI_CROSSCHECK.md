# 原 APK 三架构的 InitialFeed 初值交叉核对

三种架构的原库都包含与已核 ARM64 初值完全相同的 16 字节序列，每库各出现两处。**相同字节不是解码调用证据**：本批没有把另外两个架构的这些位置认定为实际 key 消费者，也没有确认新的解码算法或尝试解文件。

原 APK SHA256 固定为 `4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe`。全部库只从这份 APK 只读取得，未复制成新的 Ghidra 程序或写回原文件。

| APK 内原库 | ELF 架构 | 库 SHA256 | 相同 16 B 所在 `.data` 虚拟地址 |
| --- | --- | --- | --- |
| `lib/arm64-v8a/libOrderChaos2.so` | `EM_AARCH64`，64 位 | `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4` | `250bef0`、`250bf4c` |
| `lib/armeabi-v7a/libOrderChaos2.so` | `EM_ARM`，32 位 | `ee016b1c1b8ffe8fd8a8bfc99467ebb261c896da74181473630410f019b739ba` | `223d690`、`223d6ec` |
| `lib/x86/libOrderChaos2.so` | `EM_386`，32 位 | `6f26dbe9e17f7a0f4971baa2874506dd1b14a10609cc79fb8c20db342f2d8577` | `2662e1c`、`2662e78` |

取作比较的原 ARM64 初值来自已证的 VA `250bef0`，按 ELF 段映射读取，未把虚拟地址误当文件偏移。16 B 的 SHA256 为 `7757fe462cc33e43218e57f833f67e7daddb73aa281d1e3ac3a6af854beb0096`，不输出原值。只有 ARM64 第一处已有此前 `ecbd54 → 18d5140` 将地址放入 `X4` 的原消费者证据；不能把每库第二处相同序列自动归为同一用途。

对这些位置检查了覆盖符号、相关相对重定位及原绝对地址字节，未得到新的具体消费链。ARMv7 保留的三个 `CrmManager` 名字均是静态对象符号，不是具名解码函数。三库各有 `InitialFeed.dat` 字面量，也只记录其位置，不把文件名当作函数调用。上述检查未穷尽 PIC、容器相对或间接地址生产，不能据未命中声称其他架构没有消费者。

## libgenerator 的已知关联

另只核了三份原 `libgenerator.so` 的 ELF 身份、特定 JNI 导出、声明依赖和初始化数组项数。三库均有两个明确 JNI 导出：

- `Java_com_gameloft_android_hdidfv_HDIDFV_getNHDIDFV`
- `Java_com_gameloft_android_hdidfv_HDIDFV_getNHDIDFVVersion`

原 `GLUtils/Device.getHDIDFV()` 的精确片段 `00ca..00da` 为加载 `"generator"`，随后调用 `hdidfv/HDIDFV.getHDIDFV()`。这里只确认该原调用点与对应 JNI 导出，没有执行分支、读取真实设备标识或追遍初始化器；未找到它与 InitialFeed 解码的具体关联，不能把名字或导入清单当作其所有行为的证明。

本批结果在忽略目录 `analysis/raw/tutorial-script-abi-crosscheck-20261115/abi-crosscheck-v1.json`；新工具为 `tools/tutorial_script_abi_crosscheck_probe.py`。没有原文件解码、不同 key 试验、Android/外服运行、Ghidra 切换、存档或服务变化。当前模拟器实际选择哪个 ABI 未观测，不能默认它正在运行 x86。此有界交叉核查完成后停止，不扩建通用 ABI 逆向平台。
