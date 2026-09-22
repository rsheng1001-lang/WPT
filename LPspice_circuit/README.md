# 输出端（接收端）恒流刺激电路 — 仿真与原理图

源图：`SCH_接收端原理图_2026-09-20.pdf`（嘉立创EDA，v1.0）
结论报告：**`仿真结论_2026-09-21.md`** ← 所有结论、可信度分级、未覆盖边界都在这里

## 先看这个

用 LTspice 双击打开（图里已带仿真指令，可直接运行）：

| 文件 | 内容 |
|---|---|
| **`ltspice/full_bus.asc`** | 全链路 6 个模块：输入 / 8V稳压 / 3.3V / 恒流调节 / 恒流控制 / BONE负载 |
| **`ltspice/sink_vendor.asc`** | 只含恒流沉三块（恒流调节 / 恒流控制 / BONE负载），配理想电源 |

不方便开 LTspice 时可先用浏览器看 `ltspice/preview/*.svg`。

## 目录结构

```
ltspice/
  *.asc               ★ 原理图（打开这两个）
  *.asy               子电路符号（必须与 .asc 同目录，LTspice 才找得到）
  *.net               图导出的网表（LTspice 生成，供比对工具使用）
  decks/*.cir         网表形式的仿真 deck
  inc/*.inc           被 include 的电路片段（sink / core / power / solver）
  models/*.lib        器件模型（原厂 2 个 + 自制近似 1 个 + Vth 变体 2 个）
  tools/*.py          脚本
  runs/               仿真输出（.raw / .log / .db），由 run_all.py 自动归集
  preview/*.svg       原理图预览
  summary.txt         最近一次完整验证的输出留档

  Data/               归档的结果数据与图（一次运行一个文件夹），规范见 ltspice/Data/README.md
  README_FILES.md     ltspice/ 文件地图（每个文件是干什么的）

vendor/               第三方资料：Vishay SPICE 库、ST715/MCP1703A 数据手册、OPA333 原厂模型
archive/              早期 PDF 渲染 + 顶层 GUI 副产物归档（manual_gui_byproducts_*）
                      （../self_LPspice/ 是你之前的简化版草稿，未纳入本工程，见下表）
```

## 一键复现全部结论

```
cd ltspice
python tools/run_all.py
```

跑 8 节：模型资格验证 → 直流工作点 → 合规曲线 → 冷启动 → 负载阶跃 →
全母线扫描 → **图与网表等价性** → 最坏情况栅极驱动与 TVS 模型对比。
输出同时写入 `summary.txt`。

其中第 7 节是两重验证：数值等价（跑图的结果与 `.cir` 逐数字比对）和
逐元件逐节点的网表比对（`tools/compare_netlists.py`）。任何一次改动后都该跑一遍——
它在本轮抓出过"漏掉三个器件"和"两条线共线交叠把 V_BUS 短到 PGND"两个真错误。

## 两条使用须知

1. **原厂 OPAx333 宏模型的直流求解有陷阱。** 同一份未改动的 deck，正常几秒跑完，
   偶尔会落到伪解（输出跑到供电轨之外）或步长崩塌而卡住。`run_all.py` 会重试并
   明确标注。因此**任何结果都要过物理校验**：输出在供电轨内、
   V(I_SENSE) = V(I_SET)、KCL 闭合。详见报告第二节。
2. **模型可信度分级。** OPA333 与 2N7002 是原厂模型；ST715 / MCP1703AT / TVS 是
   自制近似模型，只能用于连接性与直流可行性，不能用于判定 LDO 稳定性与保护行为。
   TVS 的钳位拐点已实测与官方库不同（报告第十节）。详见报告第六节。
