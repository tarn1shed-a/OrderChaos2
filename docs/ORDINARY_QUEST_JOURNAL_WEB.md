# 原任务簿分支的浏览器校验接口

`tools/preview/quest_journal_program.mjs` 是已冻结 `tools/ordinary_quest_journal_program.mjs` 的浏览器复用件。唯一宿主接口变化是异步 WebCrypto SHA-256，调用方需 `await createOriginalJournalControls(sourceJSON, explicitInputs)`。校验的原程序 SHA 为 `fb5f7211e4a9353ed025a30e6beb4863276437fd6adfb395ed93d340fba71c7a`。没有修改旧文件、原分支、参数、确认码或选中行读取。

原 onAbandon、MessageBoxYesNo 和 MessageBox 按钮仍通过同一有限指令解释器运行。YES=0、NO=1；ShowMsg 的5是回调用户数据，不叫窗口层级。正常模态背后能否换选中行仍未知；显式 currSel 变化仅为控制输入，不能称原游戏正常操作会误删另一任务。不会连接服务器、创建界面、批准任务或运输研究 ActionID16。

`tools/quest_journal_program_tests.mjs` 对整个模块做逐字校验，只允许上述 hash/async 替换；再对 Node 旧接口与 WebCrypto 新接口运行相同原问题文本、双平台、YES/NO、全屏取消、缺选中、缺回调、损坏程序和显式改选控制。私有原程序存在时120断言通过，5组返回与旧接口完全一致；`--public-only` 为3断言，通过错误输入拒绝与逐字接口差异核对。这里使用 Node WebCrypto 验证宿主逻辑，不称浏览器/GPU/Flash已执行。

私有输入与收据位于忽略目录 `analysis/raw/ordinary-quest-journal-web-20261116/`。原 native ShowMsg→GetMessageBoxInfo 真窗口交接仍不由这个控制器实施，宿主 ledger、session/revision 与 UI 生命周期由父级独立接线。
