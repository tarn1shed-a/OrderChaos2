本批补齐默认FS剩余+0x40／+0x58供应者的具体写者和原App挂载调用。**原客户端确实尝试将两个具名OBB作为文件系统归档挂载，证据范围已超过此前仅确认的音频入口。**尚未观察实际挂载成功、包内容或InitialFeed流，也不能认定OBB内含任务脚本。

原库SHA256：`77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。不重做缓存／patch／texture／lightmap／FS+80已冻分支；原代码、Ghidra只读响应及源合约留 `analysis/raw/tutorial-script-remaining-providers-20261115/`。

| 默认FS字段 | 原写者／真实虚表槽 | 供应者及原打开行为 |
|---|---|---|
| +40 | 12709dc；24160f0+48 | 构造0x48对象，vptr246e948。先调FS v18打开输入名字；返回非空流才构造、读127699c索引并入+40。目录记录布局为56字节名字＋4字节offset＋4字节length，12字节头，为PAK样式。原头门只检查byte0=P或byte1=A，不加强为完整PACK魔数校验。解析函数返回值未被用来阻止入向量。provider v20=1276f34按索引取得offset/length，构造子流。 |
| +58 | 12705a4；24160f0+40 | 构造0x68对象，vptr246ebb8；127b86c复制目录前缀并确保末尾斜线，然后入+58。它是物理目录前缀供应者，不是名字别名表或脚本解码器。provider v20=127b9f4拼前缀＋请求名，走15441d0存在性检查与1274120物理文件reader，仍可返回空。注册本身没有目录存在性门。 |

这两个写者的Ghidra静态引用包含真实`.data.rel.ro`虚表项和`.eh_frame`／`.eh_frame_hdr`展开元数据；没有把后两类算调用者。对于+40的FS v48，本批限定的App frame与8f7a14路径没有闭合实际客户端调用点；这不排除其它虚调用。对于+58，已找到以下具体原客户端调用。

原3ba314 frame在App+3c0==3分支依次执行：

1. 3ba610调用当前FS的v40，参数是2f8728返回字符串、W2/W3=1/1。若当前FS为已核默认类，进入12705a4，临时挂目录前缀。
2. 3ba638与3ba660调用当前FS的v38，W2/W3/W4都为1，分别传下面两个原常量。
3. 3ba680调用当前FS的v78；默认类目标12717f0，按同一个2f8728路径移除+58中的目录供应者。
4. 随后仅当global2528209==0时，先8f4e3c，再由3ba70c调用8f7a14；返回值用于日志，随后guard置1并将App状态写4。不能把guard置1当归档成功。

2f8728返回全局对象2526fb0+8的C++字符串地址；现场前缀值未观测。本批没有把它替换为网页路径、用户存档目录或一个猜出的Android目录。

| 实际调用PC | 原常量地址 | 精确文件名 |
|---|---|---|
| 3ba638 | 1dfa6b9 | `main.31320.com.gameloft.android.ANMP.GloftO2HM.obb` |
| 3ba660 | 1dfd556 | `patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb` |

默认FS v38真实目标是1270734。127078c通过同一个FS的v18打开同名文件，1270798检查结果为空则跳过构造和入向量；非空才构造provider（vptr246eb58）、读127a484索引，并经12708e0／127091c加入FS+28。该路径没有额外的FS vD8 exists检查，且**没有在append前检查127a484返回值**。所以原源码证实的是挂载尝试和非空流条件，不能由此认定文件存在、索引有效或本次会话实际挂载成功。

外部只读采集可具体询问这两个精确文件。`Android/obb/com.gameloft.android.ANMP.GloftO2HM/` 是Android侧采集候选位置；本批没有取得原运行前缀，不能把这个候选位置称为已观测到的实际路径，也不能推断包内任务内容。

InitialFeed端只补一个有限队列前沿：原8e335c从owner+8取controller，按controller+50选择子任务；不等于2时构造vptr24211e8，等于2时选2421288，再将子任务入controller+8队列。24211e8+28的真实方法是8e3864；其v20=8ec1b4要求task+14==-1，8e3864内部再次检查该资格后才进入文件路径／打开。

上述虚表和队列生产者不是现场执行记录。本批没有闭合该队列实际调度者相对于App state3／8f7a14的完整先后，因此 **InitialFeed在资源挂载之前还是之后仍为unknown**。已证的局部顺序“临时目录→OBB→删除目录→资源挂载”不应被扩大成“InitialFeed必定读到了这些OBB”。未展开其它启动功能、未执行应用或制造打开成功。

复跑：`PYTHONPATH=tools .venv/bin/python tools/tutorial_script_remaining_providers_probe.py --output analysis/raw/tutorial-script-remaining-providers-20261115/source-contract-next.json`。公共边界核查用`--public-only`，不读取原ELF／Ghidra内容。验证覆盖14段原函数SHA、10条直接BL、9个重定位虚表槽、16个具体原操作及2个原OBB常量。旧冻结校验与任何父级勘误单独留receipt；本批只新增本工具和本文档，没有修改旧工具、游戏、共享文件、存档、服务、Docker或部署。

父级勘误单列：root确认提交`d30e1d3`有意修改上一批quest_refs工具（把NativeImage导入移入run，支持无capstone的公共CI）及文档（区分完全无私有资料时1通过／8跳过，与本地PUBLIC_ONLY的2／7）。本批保留原215清单，精确核对这两项父级已提交新SHA并留`parent-corrections-v1.json`；其余213旧文件和用户草稿／bitmap checkpoint未变，不回退父级修正。
