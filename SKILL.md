---
name: db-autowire
description: >-
  把任何專案接上真實資料庫。自動偵測後端技術棧（Spring Boot/JPA、Prisma、Django、TypeORM、
  Sequelize、SQLAlchemy/Alembic、Rails）、依程式碼的資料模型產生 schema（或用該框架原生的
  migration 工具）、選一家免費雲端資料庫（TiDB Cloud / Neon / Supabase…）或本機 DB 對接，
  再把整個資料庫串起來並驗證。Use this skill WHENEVER the user wants to「把資料庫接起來 / 串起來 /
  接上」、「自動產生 schema / 建表 / migration」、「連真實資料庫 / 上線資料庫 / 持久化」、
  「connect / wire up / provision a database」、「資料庫沒串 / 資料存不進去 / 重整就不見」、
  或要把一個專案從假資料切成真資料庫——even if they don't name a specific DB or framework。
  這是「套到任何專案、自動生成與對接資料庫」的通用 skill。
---

# db-autowire — 通用資料庫自動生成 + 對接

把**任何**專案接上真實資料庫。核心四步：**偵測 → 產生 schema → 對接 DB → 驗證**。

這份 SKILL.md 是權威操作流程與正確指令來源。`references/` 內的細節文件由研究彙整而成、內容詳盡，
但若其中的指令參數與本頁不一致，**以本頁與 `scripts/*.py --help` 為準**。

---

## 步驟 1：偵測技術棧（一定先做）

跑偵測腳本，搞清楚這個專案用什麼 ORM/框架、什麼資料庫引擎、有沒有 migration 工具、模型在哪：

```bash
python <skill>/scripts/detect_stack.py --path <專案根>          # 人類可讀
python <skill>/scripts/detect_stack.py --path <專案根> --json   # 機器可讀
```

它會輸出偵測到的棧、建議的「產 schema 指令」、以及該讀哪份 `references/stack-*.md`。
（`<skill>` = 這個 skill 的資料夾路徑。）

支援偵測：`spring-jpa` / `prisma` / `django` / `typeorm` / `sequelize` / `sqlalchemy` / `rails`。

## 步驟 2：依模型產生 / 套用 schema

**大原則：能用框架原生工具就用原生工具**，那才是「從模型自動生成 schema」最可靠的方式。
只有在 Java 專案沒有 migration 工具時，才用本 skill 附的 `gen_schema_jpa.py` 當起手。

| 偵測到的棧 | 產生 / 套用 schema 的正規做法 | 細節 |
|---|---|---|
| spring-jpa | 有 Flyway/Liquibase → 放版本化 SQL；否則 `ddl-auto=update` 自動建表；都沒有 → 用下方 `gen_schema_jpa.py` | `references/stack-springboot-jpa.md` |
| prisma | `npx prisma migrate deploy`（正式）／`npx prisma db push`（雛形） | `references/stack-prisma.md` |
| django | `python manage.py makemigrations && python manage.py migrate` | `references/stack-django.md` |
| typeorm / sequelize | `typeorm migration:run`／`sequelize-cli db:migrate`（開發可 synchronize/sync） | `references/stack-node-typeorm-sequelize.md` |
| sqlalchemy | `alembic upgrade head`（正式）／`Base.metadata.create_all()`（雛形） | `references/stack-python-sqlalchemy-alembic.md` |
| rails | `rails db:migrate` | `references/stack-rails-activerecord.md` |

### JPA 後備產生器（無 migration 工具時）

```bash
python <skill>/scripts/gen_schema_jpa.py --entities <entity或src目錄> \
       --dialect mysql --out schema.sql [--drop] [--database <名稱>]
```

- 遞迴掃 `@Entity`，從 `@Column`/`@Id`/`@ManyToOne`/`@JoinColumn`/`@Table(indexes=…)` 推導
  欄位、型別、unique、外鍵、索引。
- `--dialect mysql|postgres` 切換型別與自增策略（`AUTO_INCREMENT` vs `BIGSERIAL` 等）。
- `--drop` 產生 FK-safe 的乾淨重建腳本。
- 限制：`@OneToMany`/`@ManyToMany` 的 join table 不自動產生；非 `@ManyToOne` 的隱含外鍵欄位
  （純 `Long xxxId`）推不出 FK，需手動補。

## 步驟 3：選一家資料庫並建立連線

### 雲端免費方案現況（2026-06，已查證——免費方案常變，務必照 reference 再確認一次）

| 供應商 | 引擎 | 免費現況 | 適合 | 細節 |
|---|---|---|---|---|
| **TiDB Cloud (Starter)** | MySQL 相容 | ✅ 永久免費，5 GiB，無到期 | MySQL 專案首選 | `references/provider-tidb.md` |
| **Neon** | PostgreSQL | ✅ 永久免費，0.5 GB，閒置 5 分鐘休眠 | Postgres 專案首選 | `references/provider-neon.md` |
| **Supabase** | PostgreSQL | ⚠️ 免費但 500 MB、閒置 1 週自動暫停 | Postgres + 想要附帶 Auth/Storage | `references/provider-supabase.md` |
| **Render PostgreSQL** | PostgreSQL | ⚠️ 免費資料庫**30 天到期** | 短期 demo | `references/provider-render-postgres.md` |
| **Railway** | PG/MySQL | ❌ 已無永久免費（$5 試用 30 天） | — | `references/provider-railway.md` |
| **PlanetScale** | MySQL | ❌ 免費方案已下線 | — | `references/provider-planetscale.md` |

> 經驗法則：**MySQL 用 TiDB、PostgreSQL 用 Neon**，兩者免費、無到期、最穩。
> 本機開發則直接用本機 MySQL/Postgres 或 Docker Compose，不需雲端。

### 連線（各框架都靠環境變數，不改 code）

- Java/Spring：`SPRING_DATASOURCE_URL` / `SPRING_DATASOURCE_USERNAME` / `SPRING_DATASOURCE_PASSWORD`
- Node（Prisma/TypeORM/Sequelize）：`DATABASE_URL`
- Python（Django/SQLAlchemy）：`DATABASE_URL`（Django 配 `dj-database-url`）
- Rails：`DATABASE_URL`

連線字串要點（雲端幾乎都強制 SSL）：
- TiDB：`jdbc:mysql://<host>:4000/<db>?sslMode=VERIFY_IDENTITY`，使用者名稱有 cluster 前綴。
- Neon / Supabase / Render：`postgresql://...?sslmode=require`（Neon 還要 `channelBinding=require`）。

## 步驟 4：載入 schema + 驗證串起來了

1. 把步驟 2 的 schema 載入該 DB（網頁 SQL editor，或 `mysql`/`psql` client）。
2. 啟動後端，確認連得上：健康檢查端點（Spring 是 `/actuator/health` → `UP`）。
3. 從前端或 API 寫一筆資料 → 直接到 DB `SELECT` 查那張表，看得到 = 真的寫進去。
4. 重整 / 換裝置，資料還在 = 持久化成功（不像假資料重整就還原）。

各供應商的「載入 schema」「連線字串確切格式」「雷區」見對應 `references/provider-*.md`。

---

## 重要原則

- **先偵測再動手**：不同棧的做法差很多，別套錯流程。
- **優先用原生 migration 工具**：Prisma migrate / Django migrate / Alembic / Rails migrate / Flyway
  才是「從模型生成並版本化 schema」的正解；純解析註解產 DDL 只是沒有工具時的後備。
- **密碼只進環境變數**：連線字串含密碼，絕不寫進程式碼或 commit 進版控。
- **免費方案會變**：表格是 2026-06 查證的；正式採用前照 reference 的官方連結再確認一次。
- **這是通用 skill**：可丟進任何專案的 `~/.claude/skills/` 重複使用；本專案範例見
  voyago 的 `voyago-db-connect` skill（同樣機制的具體實作）。
