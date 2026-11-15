# 原任务簿页点与滚动条

`tools/preview/quest_journal_widgets.mjs` 提供纯控件投影，有限解释原 PageIndicator、ScrollBarNew、base ScrollBar、ScrollPane 和任务簿 fold/stretch 的指定方法。宽度、getBounds、textHeight、类型和事件是具名宿主端口；不执行完整 Flash 初始化、定时/拖拽/事件分派，不创建任务状态或新美术。

先调用 `await createOriginalJournalWidgets(sourceJSON)`，输入私有 `analysis/raw/ordinary-quest-journal-widgets-20261116/source-v1/source-program.json`，SHA 为 `4b4c88e6cc7edcc7aaee351dbb01533c4e7f9e2f83fbc17821c7990407492171`。原 mainUI/library 中13个指定控件方法 SHA一致；完整字段与19方法原指令只留忽略目录。

## 页点

`pager({widthBak,indicators}, {pages,currentPage,horizontal})` 的 measurement 必须显式给10项 `{name:'mc_IndiN',width,x,selectionChild:'SelState'}`。源码 MAX_NUM_PAGE=10，InitPageNum第二参原默认true。helper只准入0..10的有界显示，超过10拒绝是宿主边界，不称原方法有 clamp。

原构造通过 mc_Indi0..9查找 MovieClip，并保存初始化前 this.width 到 WidthBak。InitPageNum 的横向起点为 `(WidthBak - pageNum*第一点.width)/2`，后续按每一点自己的宽累加；它并没有按所有点宽度和重新计算起点。隐藏点 x=0、visible=false。可见点先清 SelState，再由 SetCurrPageNum选中当前页；RealWidth是可见点宽度和。单页不是隐藏控件。

本任务簿源首帧几何输入给 WidthBak≈159.9999847412，首点宽≈15.9999847412，单页输出 mc_Indi0.x=72、visible=true、SelState=true，其他9点隐藏。这个72是控件局部像素；原 SVG 节点坐标仍为 twip，应用时乘20并保留原父变换。不是自填屏幕坐标或 live Flash width。

## 条尺寸与位置

原 base 构造在属性未绑定时使用别名 btn_handle→mc_btn_handle、slot→mc_slot、btn_dec/inc→mc_btn_dec/inc；后二者可缺。getBoundsAndMoveItAllAround 可优先用名为 bounds 的 MovieClip，否则用本体。helper的 barValue 输入是已选择节点在 bar 内的显式矩形；当前来源几何走本体，没有编额外 bounds 子节点。

`handleByRange({slotWidth,slotHeight,vertical}, overflow)` 执行完整 InitBtnHandleByRange。垂直原 thumb height 为 `slot.height-min(overflow,0.9*slot.height)`；它不是可视区域/全文的比例公式。原横向分支上限仍取 slot.height，helper保留这个原指令行为。原 ValueStep=`0.1*slotAxis/500`。

Init临时写enabled=true，向handle分派PRESS/RELEASE，再写false；本次只观察该分派端口，不自动递送事件。原 QuestListHero.subInit 也明确将 m_Scroll1/2/3.enabled=false。所以这里只恢复随正文比例更新的原条显示，不据此添加新的可拖拽原输入。

`barValue({slotWidth,slotHeight,slotBounds,handleBounds,handleX,handleY}, ratio, {isBeingAltered})` 消费**resize后**的显式 getBounds 结果。垂直 min=`slot.top+handleY-handle.top`，max=`slot.bottom-(handle.bottom-handleY)`；原setter先 Math.round((max-min)*ratio+min)，再cap到[min,max]。返回的 actualRatio由原getter按实际thumb位置计算。原isBeingAltered必须显式给；退化 min>=max 拒绝，不伪造ratio0。

本源 m_Scroll2 authored root初始parent高度360，slot局部高度≈357.9515380859，handle初始高69。range100时原handle高≈257.9515380859。stretchText先按slot局部尺寸Init，再将**整个bar**高度设为 MaskHeight2=261；不能直接用261替slot高度算thumb。若采用这些静态、无旋转来源矩形，可在原handle原点周围按 targetHeight/69更新其SVG局部scale与所选bounds，再调用barValue；这是明确宿主几何适配，不能冒称原 Flash getBounds现场。

## 正文范围与内容位移

`bodyLayout({expanded,summary,detail,textHeight,maskHeight1,maskHeight2,previousStepBarVisible,previousBodyBarVisible})` 有限运行原 foldText/stretchText。textHeight必须是调用方对**最终那段HTML文字**的测量；不能用静态文本框矩形或原文长度推算。

fold恢复summary、content.y=0、mask=MaskHeight1、文本框高MaskHeight1-1，隐藏m_Scroll2并请求value0。stretch使用原summary+分隔线+detail，height=textHeight+40；若小于MaskHeight2，改为MaskHeight2-1。只有严格大于MaskHeight2才请求overflow=height-MaskHeight2、设置bar整体height=MaskHeight2并show。小于等于时原方法没有另写bar.visible，所以helper要求保留 previousBodyBarVisible，不能擅自清掉旧状态。真实先fold再stretch时该前值为false。previousStepBarVisible在stretch代表当前m_Scroll3.visible，在fold代表原缓存_IsScroll3Visible。

`contentY({contentY,contentTop,contentHeight,boundsTop,boundsHeight}, ratio)` 执行原 ScrollPane.positionRatioY setter：

`newY = -ratio*(contentHeight-boundsHeight) + boundsTop + (oldContentY-contentBounds.top)`。

它保留内容padding/初始偏移，源setter自身不clamp ratio。原 onPanelScroll 是 **pane.positionRatioY→m_Scroll2.value**；不要把显示条的取整actualRatio自动回写到正文，改变原pane比例。定时惯性、手势和父级交互事件不由本helper实现。

## 检查与范围

Node：15组、145断言通过；公开仅2个错误输入断言。Python：2项通过，含全程序原读取重放逐字节一致；公开1通过1跳过。原节点别名、0/1/2页、非等宽/越界页、thumb上限、getBounds偏移、取整/cap、isBeingAltered、退化拒绝、正文padding及fold/stretch边界均有控制。

全部原资源、完整方法和收据留忽略目录，没有修改父级profile/renderer、共享代码、存档或生产。完整原 MovieClip 测量与真实事件时序仍未恢复；helper可以在明示测量输入下复用，不能称Flash/GPU现场通过。

## 最小调用与 SVG 应用

以下使用明确选择的 source-authored-first-frame 测量，不冒称完整 live movie。所有 helper 几何单位是控件父坐标的像素，不能直接给屏幕 CSS 像素或 raw SVG twip。

```js
const widgets = await createOriginalJournalWidgets(sourceJSON);
const a = widgets.authoredMeasurements;
const pages = widgets.pager({
  widthBak: a.pager.width,
  indicators: a.indicators.map((v, i) => ({
    name: 'mc_Indi' + i, width: v.width, x: v.x,
    selectionChild: 'SelState'
  }))
}, {pages: 1, currentPage: 0});

const b = a.bars.m_Scroll2;
const thumb = widgets.handleByRange({
  slotWidth: b.slot.width, slotHeight: b.slot.height, vertical: true
}, overflow);
const scaleY = thumb.handleHeight / b.handle.height;
const old = b.handle.authoredParentBounds;
const moved = widgets.barValue({
  slotWidth: b.slot.width, slotHeight: b.slot.height,
  slotBounds: b.slot.authoredParentBounds,
  handleBounds: {...old,
    top: b.handle.y + (old.top - b.handle.y) * scaleY,
    bottom: b.handle.y + (old.bottom - b.handle.y) * scaleY},
  handleX: b.handle.x, handleY: b.handle.y
}, paneRatio, {isBeingAltered: false});
```

调整原 `.m_PageIndiForReward.mc_IndiN` 的 x 平移为 `pages.indicators[N].x*20`，保留原其他矩阵项；outer visible按输出，SelState只在输出不是null时写其visible。不要重新画点或改变父 `.m_PageIndiForReward` 的原摆放。

原 `.m_Scroll2.mc_btn_handle` 是单位、无旋转本地矩阵；将其原Y scale乘上述 scaleY，平移Y设 `moved.handleY*20`，保留原X项。`.m_Scroll2.mc_slot` 和其他原底图不重画。若原 stretch请求整体displayHeight=261，当前静态来源中整个 `.m_Scroll2` 的原Y scale再乘 `261/b.root.height`（此源b.root.height=360），保留其原摆放；这一步在thumb local resize之后。

若宿主手势使用原 pane 比例，`.panel_content.mc_content` 的Y平移为 `widgets.contentY(measuredPane, paneRatio).y*20`；m_Scroll3同理使用自己的原父scale。实际文字/bounds若从SVG或CSS测量，先显式换回对应pane局部像素。显示条取整后的 actualRatio不自动回灌正文。此示例不为bar安装点击/drag事件，不处理原未恢复的定时惯性。
