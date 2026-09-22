# runs_archive — LTspice 运行归档区

**这个文件夹的唯一目的：让任何一次 LTspice 运行都不会因为"下一次运行覆盖同名文件"而丢失。**

工程根目录（`self_LPspice/`）里所有仿真都从同一批 `.asc` 跑，所以每次运行都会覆盖上一轮的
`<名字>.log / .raw / .net / .op.raw / .db`。**扫描 B 就是这样丢的**：它的原始日志和
398 MB `.raw` 被扫描 C 覆盖，只留下解析后的 2430 组数据（`bone_sweep_analysis/work/sweeps/`）。
`ingest.py` 只快照**日志**，而且只对成功入库的扫描快照——波形和网表从来没被保存过。

## 怎么用

跑完 LTspice 后（换扫描参数**之前**）执行一条命令：

```bash
cd ../bone_sweep_analysis/scripts
python archive_run.py
```

它会把工程根目录里**所有尚未归档**的运行整个搬进来。幂等：已经归档过的运行（按
`basename + 日志 sha256` 判定）会被跳过，所以重复执行没有副作用，忘了几天再跑也来得及。

```bash
python archive_run.py --newest        # 只归档最新的一次
python archive_run.py Draft2_sweep    # 只归档指定名字
python archive_run.py --raw copy      # 波形留在工程根目录，只复制一份进归档
python archive_run.py --raw skip      # 不要波形
python archive_run.py --list          # 看归档清单
python archive_run.py --dry-run       # 只看会做什么，不动文件
```

## 每个运行文件夹里有什么

| 文件 | 角色 | 处理方式 |
|---|---|---|
| `<名字>.log` | 运行日志（`.step` 展开 + `.meas` 结果） | 复制 |
| `<名字>.net` | **权威网表** —— 真正被仿真的那份 deck | 复制 |
| `<名字>.raw` | 全部波形数据（几百 MB） | **默认移动**（见下） |
| `<名字>.op.raw` | 工作点解 | 复制 |
| `<名字>.db` | LTspice 26 的索引文件 | 复制 |
| `<名字>.asc` | 原理图 | 复制，但**不一定匹配**（见下） |
| `meta.json` | 元数据 + 每个文件的 sha256 | 写入 |

### `.raw` 默认是「移动」不是「复制」

波形是体积最大、且**重跑一次就能再生**的文件。默认移入归档后，工程根目录不再保留它，
省下几百 MB 到 1 GB；LTspice 下次运行会重新生成。想保留原地一份就加 `--raw copy`。
`meta.json` 和 `INDEX.md` 里都记了每个文件是 `move` 还是 `copy`。

### ⚠ 归档里的 `.asc` 可能不是产生这份日志的那一版

这是本工程反复踩到的坑：**LTspice 改仿真指令时若没存盘，`.asc` 留在旧版本，而 `.net` 已经是新的**。
所以归档时 `archive_run.py` 会把 `.asc` 里的指令（`.step/.param/.tran/.meas`）和 `.net` 的逐条比对，
结果写进 `meta.json` 的 `schematic` 段：

- `same_name_directives_match_deck`：同名 `.asc` 是否与网表指令一致（`true/false/null`）
- `matching_schematic`：若同名的不一致，就在工程根目录里找出**真正匹配**的那张原理图一并归档
- 注意这是**指令级比对，不是电路等价性证明**

已归档的两个运行都是 `false`，即旁边的 `.asc` 都不是那一版：

| 运行 | 权威 deck | 同名 `.asc` | 实际匹配的原理图 |
|---|---|---|---|
| 扫描 A（5730 行） | `Draft2.net`（`RB 10k 200k 1k`） | `Draft2.asc` —— 旧修订版，不匹配 | `Draft2_sweep.asc`（重建版，已验证网表等价） |
| 扫描 C（2730 行） | `Draft2_sweep.net`（`RB 1Meg 10Meg 100k`） | `Draft2_sweep.asc`（写的是 `RB 10k 200k 1k`），不匹配 | **无** —— 那一版 `.asc` 从未存盘 |

**结论：要复现某次运行，请以归档里的 `.net` 为准，不要以 `.asc` 为准。**

### `meta.json` 还记了什么

- `log_sha256` 与 `sweep.signature`：与 `bone_sweep_analysis/work/manifest.json` 的入库记录对应
  （`manifest_sweep` 给出扫描编号，`log_matches_manifest_sha256` 确认归档的日志就是当初入库的那一份）
- `sweep`：行数、RB 范围与步长、VBP/IREF 取值、该判据下的 PASS 计数
- `files`：每个文件的字节数与 sha256，可随时重算校验
- `criterion_pct`：判定 PASS 用的 IERR 阈值（当前 1.5）

`index.json` 和 `INDEX.md` 由脚本自动重建，不要手改。

## 覆盖范围与不覆盖的部分

**覆盖**：工程根目录里任何一次运行的完整输出（含波形），无论是否入库过——没入库的运行同样会被归档。

**不覆盖**：

- `bone_sweep_analysis/refine/` 下精细化扫描的 deck —— 它们本来就在**每轮一个独立文件夹**
  （`decks_<时间戳>/`）里，`refine.py` 会主动删掉那些 deck 的 `.raw`（每轮只有 11 点，
  波形没有保留价值），日志和网表都留在原地。
- `.ltspice-mcp/` 里 MCP 工具自己的运行记录。
- 工程根目录的 `.raw` 一旦被新运行覆盖，**归档区之外无法找回** —— 所以请在换参数前跑一次
  `archive_run.py`。已经归档过的运行不会因为根目录被覆盖而受影响。

## 完整性校验

`meta.json` 里每个文件都有 sha256。想确认归档没坏：

```bash
cd ../bone_sweep_analysis/scripts
python - <<'EOF'
import hashlib, json, pathlib
for d in sorted(pathlib.Path('../../runs_archive').glob('2026*')):
    m = json.loads((d / 'meta.json').read_text(encoding='utf-8'))
    for f in m['files']:
        h = hashlib.sha256()
        with open(d / f['name'], 'rb') as fh:
            for b in iter(lambda: fh.read(4 << 20), b''):
                h.update(b)
        print(d.name, f['name'], 'OK' if h.hexdigest() == f['sha256'] else 'MISMATCH')
EOF
```
