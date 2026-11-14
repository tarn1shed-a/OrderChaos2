# 指定当前角色脱出运输适配（2026-11-14）

本批新增 `deploy/unstuck_return.mjs`、`tools/unstuck_return_tests.mjs` 与本文。它只接现有试玩POST `/__entry/return`，不增加原技能、战斗/移动资格、1800冷却或服务规则；未改服务器handler、原127、UI布局或角色文件。位置持久化边界见 `docs/CHARACTER_POSITION_RESTORE.md`。

## 固定接口

```js
import {createUnstuckReturn} from '/__delivery/unstuck_return.mjs';
const unstuck = createUnstuckReturn({
  captureSession, releaseSession, reconnect, canReturn, fetcher, wait,
});
// 原UI回调由主任务接入；重复触发由busy拒绝。
const result = await unstuck.returnEntry();
```

返回 `{returnEntry(), get busy()}`。fetcher缺省使用当前页fetch；wait缺省只用于有限运输重试。接口不接受任意UUID/坐标，returnEntry没有参数，唯一目标anchor固定cinematic7。

captureSession是同步函数，仅返回当前会话的 `{characterId,resumeToken,name,room,profession,epoch}` 或null。控制器校验并复制冻结这些字段；不会把token放进返回结果或错误消息。room为原网页房间号，profession为1..5；epoch是选角/页面意图标识，不能在这次有意断开时就失效。重新选角、另一次登录或退出页面应使旧epoch/允许状态失效。

回调契约：

- `canReturn(snapshot,{phase})`是可重复调用的同步纯判断，严格返回true才继续。preflight负责由父任务提供的已有资格；后续阶段必须守住当前选择身份/epoch与页面存活，并允许本次刻意断开的区间。不要在此消费冷却、发请求或改变状态。
- `releaseSession(snapshot)`只释放该snapshot所捕获的socket/会话，**等待真实close事件和清理完成后再resolve**。父任务负责清旧移动输入、物理/相机/呈现缓冲；不能在await后改用新的全局socket。失败应throw或返回false，不能把close()已发起当作关闭完成。
- `reconnect(snapshot)`先再次核身份/epoch，未切角才调用已有connect并清理恢复链。返回false表示已取消；其它正常完成表示已发起连接，未据此证明收到了welcome。父任务负责真实连接完成/浏览器验收。
- 页面退出、选角意图变化时，canReturn应返回false。若captureSession仍有当前连接，控制器还逐字段比较七个字段；同UUID但新epoch也拒绝。断开区间captureSession可为null，此时意图/epoch守卫必须由canReturn保持。

phase为preflight、after-release、before-request、before-retry、after-retry、before-reconnect、failure。若直接把“connected必须为true”用于所有phase，释放连接后会取消操作；这是集成契约，不应通过取消身份守卫来绕开。

## 顺序、重试与错误

顺序为：捕获当前会话→资格/身份检查→等待仅该会话关闭→检查意图仍相同→POST→核回复returned UUID与anchor→检查意图→同角色重连。

POST仅包含characterId、resumeToken、anchor=cinematic7，使用same-origin credentials和no-store。原handler继续负责所有权、离线检查、完整record备份、只替resources位置及flush失败回滚；适配器不写存储、数据库或localStorage。

**只有HTTP400且error精确为现有handler的 `角色仍在线，请关闭原游戏页后重试` 才重试。** 默认等待100/200/300毫秒，最多初次+3次，共等待600毫秒。近似文本、403/502、其它400、网络失败、无效JSON、错UUID/anchor都不重试。重试前后均核身份/epoch，切角后不继续请求。

默认关闭确认和单次请求/解析各最多5秒；重连也最多等待5秒。测试可注入更短时间与retryDelays，重试最多3次、每次不超过1秒，单项deadline不超过30秒。它们是网页运输期限，不是游戏冷却。

- 关闭未确认、关闭回调失败或超时：不发POST、不额外重连，避免旧连接仍在时制造重复连接。
- 请求失败或回复未确认：仍属同一身份/epoch时只尝试一次原身份重连，并返回说明。网络错误可能发生在服务器已应用之后，所以不声称原位置一定未改。
- 已确认位置恢复但reconnect失败：不再次POST或重连，返回resetConfirmed=true及重新进入该角色的说明。
- 切角/退出：取消后续请求与重连，reason=cancelled，可由父任务静默处理。已交付服务器的请求不能在浏览器侧撤回；不会因此改连新角色。
- finally恢复busy。处理中再次触发返回busy，不再关闭socket或发请求。

返回结果包含ok/reason/message、requests，完成或失败重连阶段还提供resetConfirmed/reconnectRequested。后者只表示已调用重连，不代表实际已入图；result不含恢复token。适配器没有toast、按钮、DOM、战斗/冷却实现。

## 检查与接线余项

```sh
node --check deploy/unstuck_return.mjs
node --test tools/unstuck_return_tests.mjs
```

16项纯测试通过：真实Promise异步关闭确认、busy并发、捕获字段冻结/无凭证、外部资格拒绝、精确在线错误与重试预算、HTTP/JSON/UUID/anchor失败、异步网络拒绝、关闭中切角/退出、请求中切角/重试时epoch变化、关闭拒绝/超时、请求abort、失败恢复与重连拒绝、断开期身份守卫及后续显式重试。所有运输/会话均为明确夹具，未读真实存档、发网络请求或伪称真实WebSocket/Linux浏览器验收。

父任务仍需接公开helper映射、原UI callback、当前会话捕获/定向release/reset/reconnect和原资格提供器，并在隔离Linux实际验收：同角色关闭→位置恢复→刷新、另角色不动、切角和页面退出不误连、输入/相机/缓冲不残留。生产备份、指定角色授权与发布归父任务；本批不改变此前冻结技能/位置审计或原EnterMap边界。
