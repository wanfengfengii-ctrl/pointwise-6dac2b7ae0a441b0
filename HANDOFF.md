# 网络账交接说明

本说明面向接手河口计量归档的同事，概括固定校准网络新增能力的不变量、代码位置与独立核账方式。
旧单边（直接校准）流程、接口、SQLite 表、`format_version: 1` 导出与全部原测试保持不变。

## 新增入口

- `Archive.register_network(network_id, edges)`：登记固定校准网络，返回网络号。
- `Archive.get_network(network_id)`：读取固定网络，缺号抛 `KeyError`。
- `Archive.build_network_report(report_id, revision, network_id, target, window)`：
  发布网络计量账，返回 `NetworkReportSnapshot`。
- `read_report`、`export_report`、`assess_report` 同时服务直接报告与网络报告，按报告号分发。

## 核心不变量

1. **整网一致才登记**：同一连通分量内，任意源、目标刻度的全部可行路线（含环路、往返、恒等路线）
   在闭区间 `[0,1]` 上必须逐点相等。核验用 `Fraction` 在所有路线断点的并集上精确比较，
   矛盾网络、非法输入、重复边 ID、同号异内容一律 `ValueError` 整次拒绝；被拒请求号可再用于合法登记。
2. **网络固定**：登记即冻结（元组化、排序按边 ID），提交容器之后被修改不影响登记内容；
   同号同内容重放返回同一网络，提交顺序不影响身份。
3. **路线确定**：先选边数最少的路线；并列按从源到目标的 `(edge_id, direction)` 序列取字典序最小，
   边 ID 按字符串序，`forward` 排在 `reverse` 前。同刻度用空路线 `()`（换算为恒等），
   仍要求网络与修订存在；异刻度不可达抛 `ValueError`，缺网络或修订抛 `KeyError`。
4. **按实际切换拆账**：每对原相邻采样在所选路线任一原边切换（内结点的原像）处切开，重合边界只切一次；
   即使相邻片的复合公式相同，只要某一步的原段路径变化也分账；不跨原采样对合并；切换端点不产生零时长账项；
   下降仍按时间升序；恒值输入在内结点归右段、在 1 归末段。
5. **精确有理**：时间、读数、段路径与积分全程 `Fraction`，每笔积分是终刻度两端换算值的均值乘秒长；
   覆盖与总量为各片之和。
6. **报告号共用且固定**：网络报告与直接报告共用报告号空间，绑定含报告种类、修订、网络/校准 ID、
   目标与窗口。同号同绑定返回已存快照，异绑定（含两种报告之间）抛 `ValueError`。
   绑定、路线、逐笔路径与总量在一个事务内共同发布，任一步失败不留新成果（SQLite 异常向上传播）。
7. **快照不可变**：上游更正、调用方容器修改、重开归档与重复 `initialize()` 都不改变旧账；
   读取、重放、导出只取已存成果，不重新计算。
8. **零宽/无交集**：引用、路线、窗口合法时交付空账与零量，同时保存路线上下文。

## 代码位置

- `networks/piecewise.py`：有理折线的求值、反函数、复合与全量程相等判定。
- `networks/frozen.py`：边与网络的冻结、输入校验（沿用直接校准的结点规则）。
- `networks/consistency.py`：生成树路线与每条边的全量程一致性核验。
- `networks/routing.py`：最少边 + 字典序路线选择。
- `networks/ledger.py`：有向边、路线复合折线、按切换拆账与逐笔原段路径。
- `networks/catalog.py`、`networks/storage.py`、`networks/snapshots.py`：登记、SQLite 持久化与快照。
- `networks/plans.py`：`build_network_report` 的绑定、重放、加工、原子发布。
- `reports/reader.py`、`reports/export.py`：按报告种类分发；网络导出为 `format_version: 2`。
- `review/network_audit.py`：只依赖 V2 JSON 的独立离库核账（不导入任何加工/校准模块）。
- `tests/test_network.py`：网络业务链回归；`network_examples.py` 提供手算输入与期望。

## 离库独立核账

`review/network_audit.py` 的 `audit_network_export`（或 `audit_network_json` 接受 JSON 字符串）
仅用导出文件中的原采样对与每笔原段路径：先按原采样对在账项两端插值得读数，再沿 `path` 各步
（反向步交换原结点坐标角色）逐段换算两个端值，梯形面积即逐笔积分；随后按时间核对相邻性、
覆盖与总量。核账不通过会抛错。`verify.py` 在全部单测之外，对 `network_examples.CASES`
逐例重算并跑一遍该独立核账。

## 运行清单

- 核验：`python3 -B verify.py`（发现并运行 `tests/` 全部 49 个测试，再做手算与独立核账对账，失败返回非零）。
- 演示：`python3 -B demo.py`（原单边场景后，展示抵消例两笔原段来源、精确积分、更正后重开的真实 V2 导出）。
