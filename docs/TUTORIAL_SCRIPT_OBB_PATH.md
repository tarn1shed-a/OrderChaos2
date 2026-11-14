# 原 RetrieveObbPath 的返回来源

这版原 APK 的 `PackageUtils/AndroidUtils.RetrieveObbPath()` **直接返回字符串 `"NA"`**，没有调用 `getObbDir()`，也没有读取偏好设置或 Context 目录。

完整原 Dalvik 只有两条指令（6 B）：

```text
0000 const-string v0, "NA"
0004 return-object v0
```

原 APK SHA256 为 `4a11628bfc0aa54f0f34a6de828e003ff760a7a2b4c132ddc156518618c73ebe`；`classes.dex` SHA256 为 `088acd2c5cd39bb7da0a193a4cada1d6a10bdf9deaba2c70b27280174a5fd2e3`。唯一方法的精确类名、完整字节码 SHA 和源指令见忽略目录 `analysis/raw/tutorial-script-obb-path-20261115/obb-path-v1.json`、`RetrieveObbPath.dalvik.txt`。

本批只打开已知 APK 的 `classes.dex`，定位这个目标类和方法；没有重复全 DEX 候选搜索、其他 13 份源体核查或任何解码试验。新工具为 `tools/tutorial_script_obb_path_probe.py`，其断言核对唯一方法、两条完整指令及 6 B 字节码。

主代理另核的 `309a8c → 2526fb8 → 2f8728` 原生关联仍由主线保留，本批没有运行 Android、JNI 或路径 setter。因此当前已确认的是**这个方法被调用时的固定返回规则**，没有观察实际会话调用，也未排除其他原全局 setter 后续覆盖，更没有证明某个真实 OBB 目录或文件存在/不存在。不能擅自把 `"NA"` 替换为推定的系统目录，或由它推断任务脚本已经丢失；也不能据此宣称原版永远不会加载 OBB。

既有 InitialFeed、key、origin 冻结证据不变，未改游戏存档、服务、原文件或部署；此小项完成后停止扩展。
