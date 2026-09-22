# 模型恢复记录 (2026-09-21)

## 背景

分析所依据的扫描网表（`Draft2.net`）在 20:53:30 被删除，同时工程目录 `self/Draft2.asc` 里
保存的是**较早的一个修订版**，与产生 `Draft2.log` 的那份 deck 不一致。本文件记录恢复内容与依据。

时间线（文件系统时间戳，未做任何修改）：

| 时刻 | 事件 |
|---|---|
| 09-21 17:22:27 | `Draft2.asc` 存盘（旧修订版：`.param IREF 100u`、`.step RB list …150k`、`.meas OP`、OPAx333） |
| 09-21 19:15 | `.net` / `.op.raw` 由 LTspice 生成（扫描版，未存盘为 .asc） |
| 09-21 20:07 | `.log` / `.raw` 生成（本次分析的数据源） |
| 09-21 20:48:43 | 本会话最后一次写入（全部在 `bone_sweep_analysis/` 内） |
| 09-21 20:53:30 | `self/` 目录被改动 → `Draft2.net` 消失（非本会话命令所为） |

## 恢复内容

### 1. `Draft2.net` —— **逐字节原文恢复**

- 路径：`../Draft2.net`（1362 字节）
- 依据：会话开始时完整读取过该文件，重建后按字节数校验
- 字节数校验：**1362 == 1362**。文件中含 4 个 `§`（U+00A7），UTF-8 下每个 2 字节；只有 UTF-8 编码能得到
  1362 字节（cp1252 无法解码），因此编码也确认为 UTF-8
- sha256：`4ddd6cf838ce401bcc5cdc58f0469f95abfd8a493272132cee913567938265d9`
- 备份：`Draft2.net.original`（同目录，内容相同）

### 2. `Draft2_sweep.asc` —— **重建**（非原文，但已证明网表等价）

- 路径：`../Draft2_sweep.asc`（3993 字节）
- sha256：`220c086ac4889d371ff4653088103acf7f82dbe5180df29c4f0b9269d6889e77`
- 生成脚本：`build_sweep_asc.py`
- 依据：用 LTspice 对现存旧版 `.asc` 导出网表，发现 **19 个器件里 18 个已经与目标逐字符一致**，
  仅三处不同，于是只改这三处：

  | # | 改动 | 从 | 到 |
  |---|---|---|---|
  | 1 | R5 数值表达式 | `{10k*(3.3/(IREF*3k)-1)}` | `{R5SET}` + `.param R5SET=…` |
  | 2 | U1 模型 | `opamp2` + `Value OPAx333` | `UniversalOpAmp2` + `Value2`/`SpiceLine`/`SpiceLine2`（OPA333 规格参数） |
  | 3 | 指令 TEXT 块 | `.lib OPAx333.LIB` / `.param IREF 100u` / `.step RB list …` / `.meas OP …` | `.meas tran … FROM 12m TO 15m` ×4、`.tran`、`.param R5SET`、`.step IREF`、`.step RB 10k 200k 1k`、`.step VBP` |

  其余（全部 WIRE / FLAG / IOPIN / 18 个器件及其坐标）逐字节取自现存 `.asc`。

- **U1 符号位置已补偿**：`opamp2` 的 In+ 在符号内偏移 (−32,+80)，`UniversalOpAmp2` 是 (−32,+16)，
  两套引脚几何不同，直接换名会让 5 根线全部脱开。按引脚坐标联立求解得新锚点
  `(656,160) → (656,224)`，使 5 个引脚落在原导线的同一坐标上。
- **指令顺序经过还原**：LTspice 按 `.asc` 中 TEXT 行的先后顺序输出网表指令，而 `.step` 的先后
  决定哪个参数变化最快（本次是 IREF 最快）。目标网表的顺序是 `.meas`×4 → `.tran` → `.param` →
  `.step IREF` → `.step RB` → `.step VBP`，重建的 TEXT 行按此顺序排列。

## 验证（三重，全部通过）

1. **图等价检查**（LTspice MCP `verify_circuit`，对照恢复后的 `Draft2.net`，mode=equivalence）：
   `equivalent: true`、`structurally_equivalent: true`；
   added / removed / retyped / value_mismatches / param_mismatches / node_partition_mismatches /
   anchor_violations / arity_errors **全部为空**。
2. **逐行 diff**：重建导出网表 vs 原始 `Draft2.net`，**36 行全部相同，仅第 1 行路径注释不同**
   （差异 31 字节完全由该注释的路径长度解释）。
3. **几何/质量对照**：重建版与基线版给出**完全相同**的 2 条 observation（同一坐标），
   即这两项是原理图原有特征，非本次改动引入：
   - `dangling_wire_end` @ (432,−128)：一处悬空线端（纯外观残留，不影响网表 —— 19 器件 12 网络齐全）
   - `label_island`：`BONE_N` 由 2 个标签桩连接、无绘制导线（这是该设计的正常接法）

## 文件清单

| 文件 | 说明 |
|---|---|
| `../Draft2.net` | **已恢复**，原始扫描 deck，可直接在 LTspice 中运行（5730 点扫描） |
| `../Draft2_sweep.asc` | **重建**的扫描版原理图，可图形化打开/编辑 |
| `../Draft2.asc` | **未改动**（旧修订版，sha256 `c7ad0171…`，仍为 3677 字节 / 17:22） |
| `Draft2.asc.old-revision-backup` | 旧修订版的备份（与上者同一 sha256） |
| `Draft2_baseline.asc` / `.net` | 旧修订版及其 LTspice 导出网表（对照基准） |
| `Draft2_sweep.net` | 重建版的 LTspice 导出网表（即验证用的产物） |
| `Draft2.net.original` | `Draft2.net` 原文备份 |

## 注意

- 重建版命名为 `Draft2_sweep.asc` 而非覆盖 `Draft2.asc`，有两个好处：保留旧修订版；
  且重跑时生成的是 `Draft2_sweep.log/.raw`，**不会覆盖被分析的那份 `Draft2.log`/`Draft2.raw`**。
  若希望它成为主文件名 `Draft2.asc`，改名即可（建议先留好备份）。
- 重建版的图形布局取自旧修订版，因此**符号位置与当初 LTspice 内存里那一版可能有细微差别**；
  电气上是等价的（已验证），但若你要对照当初的截图，可能不完全一致。
- 建议拿到后在 LTspice 里按 `Ctrl+R` 跑一次确认；本次未运行完整仿真（5730 点 × 15 ms 耗时过长）。
