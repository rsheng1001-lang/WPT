# 2026-09-22 · BONE 8 V / 100 µA · VBUS 等效负载分析

本次运行的内容：在 **VBUS = 8 V、恒流沉设定 100 µA** 的工作点上，把骨阻抗从 0.5 kΩ 扫到
1 MΩ，测量 **VBUS 端口等效负载 Req = V_BUS/I_BUS** 与骨端（电流、电压、耗散）的对应关系。

数据来源：`ltspice/full_bus.asc` 的同一网表（8V LDO ST715_APPROX + 3.3V LDO MCP1703A33_APPROX
+ OPAx333 + 2N7002 + 骨负载），LTspice 26 批处理，`.tran 30m startup`，取 27–30 ms 稳态平均。
OPAx333 与 2N7002 为原厂模型；两颗 LDO 与 TVS 为自制近似模型（直流电流收支可信，dropout
精确位置与稳定性不可信）。骨负载是**纯电阻测试件**，非实测电极阻抗。

## 关键结论

1. **恒流档（R_BONE ≤ 77 kΩ）：两端都"死平"。** I_bone = 99.782 µA，I_bus = 164.801 µA，
   **Req = 48.544 kΩ，与骨阻完全无关**（一位数字都不变）。这就是"骨负载变化不影响 VBUS
   等效负载"的直接证据。
2. **拐点在 77–78 kΩ 之间**（77 kΩ 仍守 99.782 µA，78 kΩ 掉到 98.738 µA）。理论值
   (7.9991 − 0.345)/99.782 µA = 76.7 kΩ。
3. **越限后 VBUS 等效负载变轻而非变重**：I_bus 降到 73.101 µA（1 MΩ），Req 升到
   **109.437 kΩ**，渐近上限约 123 kΩ（受 65.1 µA 固定偏置限制）。同时环路失效
   （V(OUTA) 2.48 V → 3.271 V，V(I_SENSE) 不再等于 V(I_SET)），电流改由
   `I = V_BONE_P/(R_BONE + 3 kΩ)` 决定，与骨阻成反比。
4. **耗散位置反转**：骨上功耗在临界点 77 kΩ 达到全区间最大值 **766.6 µW**，越限后随骨阻
   增大而下降；MOSFET 耗散从近短路时的 763 µW 一路降到 0。
5. **剂量标定值**：恒流档实际是 **99.782 µA**，不是 100.000 µA（−0.22%，来自 R9 = 10 MΩ
   从栅极节点灌入采样节点的 218 nA）。要正好 100.00 µA 可把 R10 改为 2.994 kΩ（随 Vth/
   温度漂，非全温度补偿）。

## 文件清单

| 文件 | 内容 |
|---|---|
| `BONE_8V100uA_Req_analysis.xlsx` | 数据表：`说明` / `BONE扫描_8V_100uA`（23 点主表）/ `多母线两端电流`（16 点）/ `VBUS负载曲线_10k`（801 点） |
| `charts/Fig1_BONE_8V100uA_Req.png` | ★ 四面板图（600 dpi，183 mm 双栏宽） |
| `charts/Fig1_BONE_8V100uA_Req.pdf` `.svg` `.tiff` | 同一张图的矢量/可编辑/投稿栅格版本 |
| `charts/qa/Fig1.alignment.json` | 面板对齐门测量记录（PASS） |
| `charts/qa/Fig1.alignment.svg` | 对齐门测量矩形（仅 QA 用，不是图） |
| `charts/qa/Fig1.collision-audit.json` | 渲染碰撞审计报告（PASS） |
| `plot_Fig1_BONE_8V100uA_Req.py` | 绘图脚本（含图契约 docstring，可一键复现） |
| `data/BONE_8V100uA_curve.csv` | 主表原始数据（SI 单位，含模型值与状态位） |
| `data/BONE_multibus_sweep.csv` | 8 / 3.3 / 12 V 母线 × 各骨阻的两端电流 |
| `data/VBUS_load_curve_R10k.csv` | VBUS 4→16 V 连续扫描（R_BONE = 10 kΩ），801 点 |

复现：`python plot_Fig1_BONE_8V100uA_Req.py`（需 `matplotlib`，并把 nature-figure 技能的
`scripts/` 加入 `PYTHONPATH`，脚本会调用其面板对齐门）。

## 图契约（五段式）

1. **核心结论**：8 V / 100 µA 工作点下，VBUS 端口等效负载在骨阻抗不超过 ~77 kΩ 时是与骨阻
   无关的 48.5 kΩ 恒流型负载；越过该顺从上限后刺激电流按欧姆定律坍塌、母线侧负载变轻
   （1 MΩ 时 109.4 kΩ），耗散从器件全部转移到骨负载。
2. **证据链**：a 剂量控制（I_bone 平台与拐点）→ b 端口等效负载（不变性与抬升）→
   c 环路失调（在同一 77 kΩ 边界上由 0 变为负，证明这是环路失控而非绘图假象）→
   d 耗散分配（同一边界把功耗从器件搬到组织）。四面板共用一条对数 x 轴与一处阴影区。
3. **原型**：`quantitative grid`（2×2 等宽），主面板 a。
4. **后端**：Python / matplotlib（独占）。
5. **导出契约**：183 mm × 118 mm，正文 7 pt / 刻度 6.5 pt / 面板标签 8 pt 粗体小写，
   最小渲染字号 6 pt（≥5 pt 下限）；`svg.fonttype='none'`、`pdf.fonttype=42`（文字可编辑）；
   源数据为 `data/BONE_8V100uA_curve.csv`，23 点全部绘出、无排除；确定性仿真，无统计检验。
## QA 记录（本次交付）

| 检查 | 工具 | 结果 |
|---|---|---|
| 源码预检 | `validate_figure.py` | **21 pass / 0 warn / 0 fail** → READY FOR VISUAL QA |
| 面板对齐门 | `audit_panel_alignment.py`（渲染时调用） | **PASS**（4 组比较，0 fail / 0 warn，容差 1.5 pt） |
| PDF 字号下限 | `audit_pdf_text.py --min-pt 5` | **PASS**（120 段文本，最小 6 pt） |
| 渲染碰撞审计 | `audit_figure_collisions.py` | **PASS**（0 fail / 0 warn；23 处"文字位于填充区内"为有意标注，信息级） |
| 标注越界自检 | 脚本内 `check_notes_inside_axes()` | 通过（11 条标注全部位于所属坐标区内） |

逐面板目检（最终物理尺寸 183 mm 宽）：

| 面板 | 唯一主张 | 中心值 | 离散 | 重复单元 | 标注 | 对齐 | 碰撞 | 通过 |
|---|---|---|---|---|---|---|---|---|
| a | 剂量在 77 kΩ 内恒定，之后坍塌 | 99.782 µA（恒流档 14 点均值） | 无（确定性仿真） | 23 个稳态工作点 | 恒流 99.78 µA / 恒流区 / 越限区：环路饱和 | row1-col1 PASS | 0 FAIL | 是 |
| b | VBUS 等效负载与骨阻无关，越限后升 | 48.544 kΩ（恒流档均值） | 无 | 同上 | 48.54 kΩ 与骨阻无关 / 109.4 kΩ @1 MΩ / 偏置 65 µA、渐近上限 123 kΩ | row1-col2 PASS | 0 FAIL | 是 |
| c | 环路在控与失控的分界恰在 77 kΩ | 0 mV（恒流档）/ −275.1 mV（1 MΩ） | 无 | 同上 | 误差为 0：环路在控 / −275 mV @1 MΩ | row2-col1 PASS | 0 FAIL | 是 |
| d | 同一分界把耗散从器件搬到组织 | 峰值 766.6 µW @77 kΩ | 无 | 同上 | 骨负载 P_bone / MOSFET P_FET / 峰值 767 µW @77 kΩ | row2-col2 PASS | 0 FAIL | 是 |

修正记录（审计驱动，均已复验）：

- 首轮碰撞审计 8 处 `text-stroke` FAIL：标注文字被数据连线/参考线穿过 → 全部重新定位到实测
  空旷区，并把两条恒流参考线改为只画到拐点（语义也更准确）。
- 自检发现 3 处标注越出坐标区（panel a 的欧姆极限标注、panel b 的端点与偏置说明、panel d 的
  峰值标注）→ 欧姆极限标注移入脚注，其余改为双行并调整 y 轴上限。
- panel a/b 早期两处 `text-fill-edge` WARN（标签压住阴影区边缘）→ 重新定位后消失。

字体说明（对技能强制规则的一处有意偏离）：技能要求中文字形在 Arial 下缺失，且 matplotlib
的逐字形回退只在 **`font.family` 为字体列表**时生效（放在 `font.sans-serif` 里不生效）。
脚本保留技能规定的三行强制配置，随后追加 `font.family = ['Arial', 'Microsoft YaHei',
'DejaVu Sans']`：拉丁/希腊字形仍用 Arial，中文回退到 Microsoft YaHei，渲染零缺字。

## 复核（2026-09-22 同日，5 V 工况出图时统一改版）

新建 5 V 工况（`../2026-09-22_BONE_5V100uA_Req_analysis/`）出图时发现
`bbox_inches="tight"` 会把页面裁到 168.9 mm，与图契约声明的 183 mm 不符。两张图随之统一改为
**固定页边距、不裁边**，实测页面尺寸严格 **183.0 mm × 118.0 mm**；改版后本图的全部 QA 已重跑：

| 检查 | 改版后结果 |
|---|---|
| 面板对齐门 | PASS（4 组比较，0 fail / 0 warn） |
| PDF 字号下限 | PASS（120 段文本，最小 6 pt） |
| 渲染碰撞审计 | PASS（0 fail / 0 warn） |
| 标注越界自检 | 通过 |

改版过程中还暴露出并修掉了面板标签 a/b 顶出页面上边界的问题（原 top 边距不足以容纳 8 pt
标签 + 3 pt 偏移）。图的内容与数据未变，逐面板目检结论与上表一致。
