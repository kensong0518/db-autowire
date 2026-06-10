# db-autowire

一個**通用、可重複使用**的 [Claude Code](https://claude.com/claude-code) skill：把**任何**專案接上真實資料庫。

## 它做什麼

四步走完，讓專案從「沒有 / 假資料庫」變成「連真實持久化資料庫」：

1. **偵測** — 自動辨識後端技術棧（Spring Boot/JPA、Prisma、Django、TypeORM、Sequelize、SQLAlchemy/Alembic、Rails）、資料庫引擎、有無 migration 工具、模型位置。
2. **產生 schema** — 優先用框架原生 migration 工具（Prisma migrate、Django migrate、Alembic、Flyway…）；Java 無工具時用內附的 `gen_schema_jpa.py` 從 `@Entity` 直接產 DDL（支援 MySQL / PostgreSQL）。
3. **對接** — 選一家免費雲端 DB（TiDB Cloud / Neon / Supabase…）或本機 DB，靠環境變數注入連線字串。
4. **驗證** — 健康檢查 + 實際寫一筆查一筆，確認真的串起來、資料持久化。

## 安裝

把整個資料夾放到使用者層級 skills 目錄，即可在所有專案使用：

```
~/.claude/skills/db-autowire/        # macOS / Linux
C:\Users\<you>\.claude\skills\db-autowire\   # Windows
```

之後在任何專案對 Claude Code 說「把資料庫串起來 / 連真實資料庫 / 自動產生 schema」即會觸發；
或直接呼叫腳本：

```bash
python ~/.claude/skills/db-autowire/scripts/detect_stack.py --path .
python ~/.claude/skills/db-autowire/scripts/gen_schema_jpa.py --entities src/main/java --dialect mysql --out schema.sql
```

## 結構

```
db-autowire/
├── SKILL.md                 權威流程：偵測 → 產生 → 對接 → 驗證
├── scripts/
│   ├── detect_stack.py      偵測技術棧 / DB 引擎 / migration 工具
│   └── gen_schema_jpa.py    JPA @Entity → DDL（mysql/postgres，後備用）
└── references/
    ├── stack-*.md           各技術棧的 schema 產生與連線做法
    └── provider-*.md        各免費雲端 DB 的註冊 / 連線字串 / 雷區（2026 查證）
```

## 免費雲端 DB 速查（2026-06 查證，會變動）

| 供應商 | 引擎 | 免費現況 |
|---|---|---|
| TiDB Cloud (Starter) | MySQL | ✅ 永久免費，5 GiB |
| Neon | PostgreSQL | ✅ 永久免費，0.5 GB |
| Supabase | PostgreSQL | ⚠️ 500 MB、閒置 1 週暫停 |
| Render PostgreSQL | PostgreSQL | ⚠️ 30 天到期 |
| Railway | PG/MySQL | ❌ 已無永久免費 |
| PlanetScale | MySQL | ❌ 免費已下線 |

> MySQL 選 TiDB、PostgreSQL 選 Neon，最穩。

---

由 Claude Code 產生。免費方案條件常變，正式採用前請照 `references/provider-*.md` 的官方連結再確認。
