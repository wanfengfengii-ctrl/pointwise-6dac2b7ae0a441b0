# 固定校准网络与计量账

相邻刻度的标定边可以组成换算路线。网络先通过全量程一致性核验，质控才用它出账。报告供研究员逐笔核对实际校准出处。旧单边流程、接口和示例见 `README.md`。

## 登记网络

`Archive.register_network(network_id, edges)` 返回 `network_id`。`edges` 是有限可迭代的四项记录序列，每条为 `(edge_id, source, target, knots)`，记录用元组或列表。边 ID 在该网络内唯一。网络与直接校准各自具名，登记网络不改已有直接校准。标识、刻度和结点沿用直接校准的规则。两端异名，原结点从 `(0, 0)` 到 `(1, 1)` 且两轴严格递增。原结点序列计入内容，包含共线原结点。反向使用同一边的反函数并保留原段号。

允许平行边、环和互不相连的分量。对同一分量中的任意源、目标刻度，所有可行路线在闭区间 `[0, 1]` 上须给出完全相同的有理数换算，包含往返环路与恒等路线的比较。非法输入、重复边 ID、矛盾网络与同网络号异内容均抛 `ValueError`，整次拒绝。边记录的提交顺序不影响身份，有理数按精确值比较。已登记网络可重开使用，提交容器修改不影响登记。拒绝新网络后原请求号可用于合法登记。

## 建账与重放

`Archive.build_network_report(report_id, batch_revision, network_id, target, window)` 使用明确的 `RevisionRef` 及 V1 的整数半开窗口。读取固定修订的源刻度后，选择边数最少的路线。并列按从源到目标的 `(edge_id, direction)` 序列取字典序最小，边 ID 按字符串序，方向为 `forward` 在 `reverse` 前。同刻度直接使用空路线，换算为恒等，仍须引用存在的网络和修订。异刻度不可达抛 `ValueError`。缺网络或修订抛 `KeyError`。零宽或无交集窗口在引用、路线及窗口合法时交付空账和零量，仍保存路线上下文。

用原相邻采样对插值并裁到窗口。每对采样的有效时段按所选路线任一原边的切换拆账，边界重合只切一次。即使相邻时段的复合换算公式一样，只要原段路径变化也须分账。段号沿用登记方向的零基序号。恒值在各边输入内结点属于右段，在 1 属于末段。下降按时间升序出账，切换端点不产生零时长账项，不跨原采样对合并。积分为最终刻度的换算值乘以秒长后在片内精确累计，覆盖与总量分别为各片时长和积分之和。用 `Fraction` 保持时间、读数和积分精确。

网络报告与原直接报告共享报告号。绑定包含报告种类、批次修订、网络或直接校准 ID、目标和窗口。同号同绑定返回已存快照，异绑定抛 `ValueError`，包括两种报告之间的同号请求。绑定、路线、贡献和总量共同发布，引用、计算或写入失败均无本次成果，SQLite 写入异常沿原约定传播。上游更正、调用方容器修改与重开不改变已经发布的快照。读取、重放及导出直接使用已存成果。旧库数据、旧直接报告及 V1 导出形状保持兼容。

## 读取和交付形状

`build_network_report` 与 `read_report` 返回相等口径的快照记录。字段为 `report_id`、`binding`、`source`、`coverage`、`total`、`route`、`contributions`。`binding` 包含 `revision`（`RevisionRef`）、`network_id`、`target`、`window`。`route` 是有序的 `(edge_id, direction)` 元组序列，空路线为 `()`。`contributions` 是时间升序元组，逐笔有 `start`、`end`、`samples`、`path`、`integral`。`samples` 是原 `Sample` 对。`path` 是按路线排序的记录元组，每步有 `edge_id`、`direction`、`segment_index`（原段号）、`knots`（该段在登记方向的两个原结点）。空路线的 `path` 为空。记录的具体 Python 类型由实现选择。`assess_report` 沿用原覆盖、积分及账项复核规则。

`export_report` 对网络报告返回确定性 JSON。顶层沿用 V1 的 `report_id`、`binding`、`coverage`、`total`、`contributions`，将 `format_version` 设为 2，另加 `route`，形状为 `[[edge_id, direction], ...]`。`binding` 将 `curve_id` 换为 `network_id`，其余字段同 V1。每笔保留 V1 的 `start_s`、`end_s`、`samples`、`integral`，用 `path` 数组取代原单边四字段。`path` 的每步对象使用上述四个字段名。分数和原采样时刻沿用 V1 编码。离库仅用该 JSON 就能从原采样对和每笔原段路径复核逐笔积分、覆盖和总量。

例如，在新库把 `day` 的 A 读数 `[(0, 0), (1, 1)]` 发布为目标也是 A 的 `same`，所引用网络号为 `net`，窗口为 `(0, 1)`。导出内容如下。

```json
{
  "format_version": 2,
  "report_id": "same",
  "binding": {
    "batch_id": "day", "revision": 1, "network_id": "net",
    "source": "A", "target": "A", "window": [0, 1]
  },
  "route": [],
  "coverage": [1, 1],
  "total": [1, 2],
  "contributions": [{
    "start_s": [0, 1], "end_s": [1, 1],
    "samples": [{"time_s": 0, "reading": [0, 1]}, {"time_s": 1, "reading": [1, 1]}],
    "path": [], "integral": [1, 2]
  }]
}
```

## 样例与运行

`network_examples.py` 提供输入及手算期望。以抵消例核对回归时可调用：

```python
from archive import Archive
from network_examples import CASES

case = next(case for case in CASES if case['name'] == 'cancellation')
with Archive() as archive:
    archive.register_network('net', case['edges'])
    revision = archive.put_batch('day', case['source'], case['samples'])
    report = archive.build_network_report('sheet', revision, 'net', case['target'], case['window'])
    actual = tuple((item.start, item.end, tuple(step.segment_index for step in item.path),
                    item.integral) for item in report.contributions)
    assert (report.route, actual, report.coverage, report.total) == (
        case['route'], case['items'], case['coverage'], case['total'],
    )
    assert archive.read_report('sheet') == report
```

级联网在 `1/2`、`2/3` 切开，三笔积分为 `3/32`、`3/32`、`7/24`。给该网络再加直接恒等边得到 `CONFLICT_EDGES`，两条路线在 `1/2` 分别给出 `3/8` 和 `1/2`，登记拒绝。同一网络号可再用于级联网。抵消例的第一笔路径为 `e01` 正向原段 0、`e02` 反向原段 0，各步 `knots` 均对应各自登记的原段。

沿用根目录 `.pointwise-runtime.json` 的版本 1 和 CLI 类型。`setup` 是准备命令的参数数组列表，`verify` 和 `demo` 各为一条命令的参数数组。交付时使 `verify` 核验全部原回归和新增业务链，核验失败返回非零。`demo` 展示抵消例的两笔原段来源、实际积分和更正后重开的真实导出。交付中附简短的交接不变量说明和独立核账。
