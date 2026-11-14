离线原代码已能确定OBB的索引及成员读取方式，不需要先连接服务器。原provider `246eb58`使用**ZIP32样式的尾目录／本地头布局**，支持成员method0原样子流和method8 raw DEFLATE；这个判断来自完整函数的字段偏移及解码调用，不是`.obb`扩展名。实际两个OBB尚未取得，所以没有恢复它们的目录、成员或任务脚本，也不能判断包内一定有脚本。

固定原ARM64库SHA256：`77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。本批只做静态原指令核对，完整相关函数、原虚表重定位与报告留忽略目录`analysis/raw/tutorial-script-obb-reader-20261115/`。不执行应用，不提供伪造归档／字节流／打开成功，不扩大到其它启动状态或任务规则。

上一批已证App依次尝试挂载下面两个原常量，且默认FS v38只有在FS v18返回非空流时才构造该provider。此处只复用该来源，不把挂载尝试当成功：

- `main.31320.com.gameloft.android.ANMP.GloftO2HM.obb`
- `patch.31320.com.gameloft.android.ANMP.GloftO2HM.obb`

原`127a484`从provider+10取底层流，按以下方式建立64字节运行时记录。所有整数按原AArch64小端加载；下表的“ZIP字段名”是根据布局所作识别，函数没有验证这些记录的PK魔数。

| 原位置／函数 | 实际读取与使用 |
|---|---|
| 尾部；127a4b4..127a4f4 | seek至`length-22`，读22字节；+10按signed16作条目计数，+16按signed32作目录起点。计数小于1直接退出。没有向前搜索带comment的尾记录。 |
| 目录；127a500..127a580 | 每次读46字节；+42按signed32作本地头offset，seek过去调用127aa90，再回到这条目录固定段之后，加+28/+30/+32三个signed16长度跳过name／extra／comment。 |
| 本地头；127aa90 | 读30字节，布局为signature4、version2、flags2、method2、time2、date2、CRC4、compressed4、uncompressed4、nameLen2、extraLen2。CRC、两size、nameLen、extraLen偏移分别14／18／22／26／28。 |
| 名字和payload；127ab00..127aba8 | nameLen按signed16，读原名字字节，追加NUL后用strlen复制；extraLen按signed16相对seek。最后取流position，截为32位写运行时record+18，作为payload offset。 |
| 运行时记录 | stride64；+0／+8／+10为三个C++字节字符串，+18为payload offset，+1c保存30字节本地头。因此method在+24，compressed在+2e，uncompressed在+32。偏移均十六进制。 |

flags bit3有一处必须原样保留：`127ab74..127ab94`在name／extra之后、保存payload起点之前**立刻再读12字节**，覆盖CRC和两size。本批没有将其改写成通常的“payload之后descriptor”，因此不宣称该provider完整支持所有标准ZIP descriptor形式。上述读取的返回字节数及seek结果没有在这两个完整函数中作为失败门；没有可见的ZIP64分支、目录或本地头魔数验证。

名字链也已闭合到实际查找：`127a8f4`构造名字键，`12723ec`构造请求键，`127b3ec`在64字节记录向量中以memcmp＋字节长度二分查找。provider flags bit1调用`11e122c`，完整函数只把ASCII `A..Z`加0x20；bit2使用basename键，构造端扫描`/`，查询端扫描`/`或`\\`。未见UTF-8／UTF-16转换、Unicode大小写或资源名哈希；不能把“字节保持”写成“已确定名字编码是UTF-8”。嵌入NUL会在strlen阶段截断。原name读入函数使用栈内缓冲，本函数没有显式nameLen上限门；这里记录代码行为，不据此构造坏包。

真实provider v20为`12884d4`，它将X2置0并跳v48=`127ae44`。后者先调用名字查找，-1时输出空，否则进入`127aeb8(provider,index)`。v48的可选X2输出写的是**record+18的payload offset**，不是成员大小；这点不能按接口猜测成size。直接index入口本身没有显式索引范围门，名字入口由前面的查找结果限定。

| 127aeb8原分支 | 成员打开／解码与返回 |
|---|---|
| method0 | seek到record+18，按record+32的signed32长度，经1274f00构造子流。provider flags bit4选择缓存／克隆句柄所有权分支；具体底层clone仍是外部流接口，不宣布已成功。普通vptr246e778与缓存子类24790a0的read／seek槽一致。 |
| method8 | compressed／uncompressed按uint32分配两个缓冲；seek并读取compressed字节。原18cc60c以windowBits=-15、版本常量`1.2.3`、结构大小0x70初始化，原体与参数识别为zlib inflateInit2_等价入口；负windowBits选择raw DEFLATE。成功后18cc76c(stream,4)，即inflate／Z_FINISH等价调用，再两次18cdf48清理。通过122987c把输出缓冲及声明的uncompressed长度包装成内存流。这里的库函数名是研究识别，地址及参数是原值。 |
| 其它method | 输出原日志`file has unsupported compression method.`并返回空；没有method14或其它decoder分支。 |

初始化18cc60c返回非0时会记录`Error decompressing`、释放输出缓冲并返回空。初始化之后，`127b1a0`的inflate返回值、实际total_out／avail_out没有被调用者校验；packed read结果也未检查，CRC字段没有在这条完整成员打开链中参与校验。两次end中第二次的返回值同样未使用。因此“返回了内存流”不等于“实际解压字节已经证实有效”。本批没有执行该分支或制造成功内容。

范围门限定在实际返回流：`1274f00`用底层当前位置为start，加声明长度得到end；没有在该构造及成员打开函数内将`offset+size`与物理流总长比较。`1275520`在逻辑end之前将读取请求裁到剩余长度，再按底层实际返回量推进；到end返回0。解压内存流vptr246e860的`12762ec`同样裁到size-cursor，到EOF返回0；其copy入口是原memcpy。`12756ac`／`1276430`有上界比较，但完整函数内没有显式负位置／下界拒绝。这不是对所有底层流或全文件系统验证能力的全局结论。

与已有格式的对照范围如下：

| 格式 | 本批可证关系 |
|---|---|
| ZIP | 尾22／目录46／本地30的布局及method8 raw DEFLATE均由原代码给出，可识别为ZIP32目录样式；魔数不校验、comment不回扫及bit3行为使其不能直接等同一个完整标准ZIP验证器。 |
| GBMP | 复用已有完整54da70原导出：该入口会核本地头`PK0304`或`GBMP`，并有0／8／14分支；30字节本地字段布局有共同点。其目录／索引、名字规范化与哈希入口不同，不能把当前provider当作原GBMP组或直接套GBMP挂载顺序。 |
| BDAE | 是归档成员内可能出现的资源格式；这条provider负责返回字节流，没有按BDAE头分派的分支。本批没有实际成员，不能宣布OBB内有模型／脚本或选用BDAE解码。 |

可离线解决的索引、名字和解码调用现已闭合。若继续验证**这个归档分支**，需要实际归档字节，不限定必须联网取得：本机、旧设备或备份中的原文件均可用于只读核查。但后续 [本版本Java路径](TUTORIAL_SCRIPT_OBB_PATH.md) 已确认 `RetrieveObbPath()` 直接返回 `NA`；不能把标准Android/obb当当前APK已证运行目录，也不能将两个文件认定为恢复主线的唯一或已证必要输入。未取得实际文件前，目录、编码、嵌套形式及是否含`教程脚本`均未知。本批不将其推成“只在服务器”，也不沿本读器无限递归zlib内部或其它frame。

复跑：`PYTHONPATH=tools .venv/bin/python tools/tutorial_script_obb_reader_probe.py --output analysis/raw/tutorial-script-obb-reader-20261115/source-contract-next.json`。输出必须是该私有目录中的新文件。检查20段完整读器／相关函数SHA、1段已冻GBMP对照SHA、14条直接调用、14个真实重定位虚表槽、52条原操作、3个原codec／错误常量。只做静态核对，没有原CPU／Android流执行的成功声明。

`--public-only`仅用stdlib、跳过私有ELF检查；本地仍核已有冻结清单，完全无私有资料的公共checkout会明确标记该清单不可用。已实际用只含必要公开源码的临时目录、`python -S`关闭site-packages核查通过，没有复制原ELF或私有清单。旧215清单保持，保留root已提交`d30e1d3`的两项勘误；其余213与上批2文件均不改，用户两草稿及bitmap checkpoint继续保持。仅新增本工具、本文档及专属忽略证据目录，没有改共享文件、游戏／存档／服务／部署，也未启动Docker或新增界面。
