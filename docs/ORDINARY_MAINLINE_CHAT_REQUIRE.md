# 原聊天条件表的身份与消费边界

本批只核原 `tables/chat_menu_require.tbl`。具名 `.rodata` 字串在 `1f01234`，其4个直接代码引用对应表加载路径、写出路径、记录读取和记录写出；没有据此宣称执行了原条件。固定原库SHA为 `77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。

## 已闭合的原对象链

`chat_menu_require → loader d28e84 → vptr2430278 → DataManager+290 → getter c99488`

真实虚表在 `.data.rel.ro`，`+40=d28e84`、`+18=d28b2c`、`+58=d29548`。原构造器 `c8b4a0` 的 `c8d6cc` 写该vptr，`c8d6e0` 把表对象写入管理器 `+290`。按ID查询的 `+18` 复制记录并返回是否找到；未使用内存表的分支转 `+58` 从原后备存储取记录。它们是取数据接口，不是任务条件判断。

记录原格式为 `uiiiuiuius`，依次是 `id,quest,buff,item_1,num_1,item_2,num_2,item_3,num_3,step`。原读器 `d29f70` 前9字段各占4字节，`step` 用 `e881dc` 写8字节COW字符串，运行时偏移 `+24`、总跨度44字节；物理表中字符串是4字节偏移和2字节长度，总42字节。原加载/清理指令以 `+2c` 跨行并读取 `+24` 字符串，与该布局相符。没有将原字符串 `"1"` 当整数阶段或任务状态。

## 确有消费，但不是原评估器

`c99488` 有一个具名直接代码调用者 `3e7638`（调用点 `3e76a8`）。这已属于旧 `quests` getter `c99370` 的14个直接调用审计；本批只是补全它的require表身份，未把旧函数包装成新的脚本执行入口。

该函数查询前一行的 `+24` 作为require编号，再通过本表 `virtual+18` 复制行。成功后将 `require.quest(+4)` 写输出 `+4`；再读原quests记录的 `+10` 写输出 `+8`。末端 `3e77cc..3e78a0` 对 `require.step(+24)` 做COW减引用/释放。完整620字节函数中，这个字符串没有被解析或拿来与当前任务阶段比较。

因此可证的是菜单与任务元数据关联。不能把它称为require116评估，更不能据“查询到行”让208通过。原116仍为 `quest=208, step="1"`，其它buff/item/num字段为0；菜单64的info条件是116，首选项的条件另为117。原资料与六行索引见 `analysis/raw/ordinary-mainline-require116-20261115/`。

## 覆盖范围

本批仅从具名加载器、真实虚表、构造器和getter直接引用出发。`.eh_frame`、`.eh_frame_hdr`引用均具名排除；没有重扫旧23全局路径，没有排除全程序中的内联/间接消费者，也没有证明条件只能在原服执行。没有找到新的实际条件评估调用，所以本分支到此收口。

可复跑静态检查：

```sh
PYTHONPATH=tools .venv/bin/python tools/ordinary_mainline_require_native_probe.py --output analysis/raw/ordinary-mainline-require-native-20261115/recheck-new.json
```

工具核7段完整原函数SHA、14条身份/字段流指令、原格式与真实重定位虚表。它不运行ARM64、不打开游戏/UI、不发请求。原反编译、汇编、Ghidra只读响应与交接均保留忽略目录；无共享入口、存档或部署变更。
