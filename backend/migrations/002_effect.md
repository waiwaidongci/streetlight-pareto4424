# 002 整治效果测算

在 001 之上支持「整治效果测算」：新增完工登记册，运行记录携带测算类型与登记快照。应用启动以 `create_all` 补建缺失的 `completions` 表，并对已有 `runs` 表执行幂等加列（PostgreSQL `ADD COLUMN IF NOT EXISTS`），无需手工迁移。

- `completions` 完工登记册：`completion_id` 完工单号全册唯一，`site_id` 灯组编号，`completion_date` 完工日期，另记登记人与登记时间。登记只可追加，重复单号导入时跳过。
- `runs.kind` 测算类型：`concentration`（集中度测算，默认）或 `effect`（整治效果测算）。既有运行默认 `concentration`。
- `runs.registry_snapshot` 完工登记快照（JSON，可空）：整治效果测算在发起时固化当时的完工登记；晚到的完工记录只供新测算，后台中断恢复沿用发起时的快照。
