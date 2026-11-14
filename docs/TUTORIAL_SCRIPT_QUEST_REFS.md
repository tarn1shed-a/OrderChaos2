本批只审原quests getter c99370的14个直接代码调用者。没有发现这些调用者把原script+0x70值传给脚本调用或文件加载。结论仅覆盖这14个具名caller，不排除其他getter、间接调用、别名或不同表入口；没有扩成全程序无脚本的结论。

原库SHA256：`77f449f2100a4717578e282bb04f1f8fff25d25c7bfa461d7d39ee49d1cb8ca4`。输入清单来自root的 `tutorial-script-entry-20261115/manager-xrefs-response-v1.json`；14个原BL c99370均逐条核指令，另外2条`.eh_frame`／`.eh_frame_hdr`元数据引用排除。复用旧49e558、a43d40、a4572c、a46b8c完整反编译及SHA，另外10处只读导出原Ghidra反编译，没有重跑父任务的读表／任务CPU链。

| 具名caller | 已审的非script字段用途 |
|---|---|
| 3e7638 | 关联记录中的quest Type摘要 |
| 8b8df8 | 返回TrackingId |
| 418388 | Title本地化 |
| 49e558 | 任务选择、TrackingId、表现／analytics标量 |
| 4a24bc | 当前任务记录的TrackingId |
| 9ebec4 | NPC交互关联中的quest Type摘要 |
| a4572c | 原接收处理、TrackingId、表现／analytics标量 |
| a43d40 | 原查询接收处理、TrackingId、表现／analytics标量 |
| a48200 | 原任务接收处理与analytics标量 |
| a46b8c | 原任务完成接收处理与表现／analytics标量 |
| a4a3c4 | 原任务事件UI与analytics标量 |
| 8b13a4 | Type、Title、Objectives显示 |
| 8b2e08 | Title本地化 |
| 83fe44 | Title本地化 |

每处先对原lookup的输出栈record定位，再以该record+0x70确定script对应的Ghidra局部值。14处该值都只出现于声明及空串初始化，lookup后没有单独读取或作为参数转交。lookup之后至该record最后一次3e78a4清理之间，整个row指针也只转交给3e78a4，未转给其他函数。3e78a4中实际读取+0x70并减字符串引用的结论复用root本批原执行，不冒称本工具重新执行。

原ARM64再做了独立栈槽交叉核对：依据各函数实际保存区、SP减量与FP定位，将script槽换算为入口SP相对地址；14个函数中该槽的直接SP／FP内存访问均只有lookup之前的空串store，没有读取。工具同时保留原BL、表v+18 lookup、清理调用PC、栈槽、完整指令SHA。这里核的是具名函数的直接栈访问和已审反编译字段流，不能代替任意别名／跨函数的全程序证明。

a43d40、a4572c、a46b8c、a48200、a4a3c4会在不同时段复用同一块栈空间创建UI事件。本批按“表lookup→record清理”的生命期区分：此前或清理之后相同栈地址交给UI dispatcher，不算把quests.script交给脚本引擎。4a24bc两个条件分支的清理都已纳入，没有只检查其中一条。

因此，这14处没有提供新的脚本路径构造、扩展名、decoder或VM入口；也没有产生任务首次发放、活动对象或服务器批准。原script列读入仍不等于脚本正文载入。所有原反编译、指令、来源复用receipt和审查矩阵留ignored `analysis/raw/tutorial-script-quest-refs-20261115/`。

复跑：`PYTHONPATH=tools .venv/bin/python tools/tutorial_script_quest_refs_tests.py`；公共模式加 `OC2_SCRIPT_QUEST_REFS_PUBLIC_ONLY=1`。9项本地来源核查通过。完全没有原资料和私有冻结清单的独立导出中，1项公共检查通过、8项明确跳过；仅在本地设置公共模式时，旧冻结清单仍在，会另执行它的校验，不能将两种环境的计数混用。212份旧冻结文件、bitmap checkpoint及两份草稿保持；未运行新CPU父链、UI、服务、Docker、存档或部署。
