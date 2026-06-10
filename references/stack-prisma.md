# Prisma db-autowire Skill Reference Guide

## 技能目標

db-autowire 是一個通用、可重複使用的 Claude Code skill，能在任何 Prisma + TypeScript/Node 專案上自動：

1. **偵測**專案是否使用 Prisma 棧
2. **產生或更新** schema.prisma（從程式碼模型或既有資料庫）
3. **套用遷移**到開發、測試或正式環境
4. **反向工程**既有資料庫為 Prisma models
5. **配置連線字串**與連線池設定

---

## 技術棧

- **ORM**: Prisma (`@prisma/client`, `prisma` dev dependency)
- **執行環境**: Node.js 16+
- **語言**: TypeScript（推薦）或 JavaScript
- **資料庫**: PostgreSQL、MySQL、SQLite、SQL Server、MongoDB、CockroachDB（支援所有 Prisma 驅動）

---

## 自動偵測機制

### 1. 檢查套件依賴

在專案根目錄的 `package.json` 中尋找：

```json
{
  "dependencies": {
    "@prisma/client": "^5.0.0"
  },
  "devDependencies": {
    "prisma": "^5.0.0"
  }
}
```

**檢查指令**:
```bash
npm list @prisma/client prisma
```

### 2. 檢查 Prisma 配置檔案

必須存在以下任一：

- **`prisma/schema.prisma`** (標準位置)
- **`schema.prisma`** (根目錄替代位置)
- **`prisma.schema`** 或其他自訂路徑（在 `prisma/prisma.config.ts` 中定義）

檢查檔案內容必須包含：
```prisma
datasource db {
  provider = "postgresql" // 或其他支援的提供商
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}
```

**檢查指令**:
```bash
test -f prisma/schema.prisma && echo "Found" || echo "Not found"
```

### 3. 檢查環境配置

查看 `.env` 或 `.env.local`：

```env
DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

如果找不到 `.env`，skill 應提示使用者提供連線字串。

---

## 核心命令參考

### 開發工作流（Development）

#### 1. **初始化 Prisma**（新專案）

```bash
npx prisma init
```

這會建立：
- `prisma/schema.prisma`（空的 schema 範本）
- `.env`（空的環境變數檔）
- `.gitignore`（已配置忽略 `.env`）

#### 2. **產生新的遷移**（開發環境）

```bash
npx prisma migrate dev --name <migration_name>
```

例如：
```bash
npx prisma migrate dev --name add_user_table
```

**這個指令會**：
- 建立或重設 shadow database（用於偵測 schema drift）
- 執行所有待機的遷移
- 產生新的遷移檔案（存放在 `prisma/migrations/<timestamp>_<migration_name>/migration.sql`）
- 更新 `_prisma_migrations` 表格
- 重新產生 Prisma Client

**互動行為**：
- 如果 schema 有改變但尚未建立遷移，會提示確認
- 如果偵測到 schema drift（手動修改了資料庫），會警告

#### 3. **快速同步（無遷移文件）**

```bash
npx prisma db push
```

**這個指令會**：
- 直接同步 `schema.prisma` 到資料庫
- **不產生遷移檔案**
- **不保留修改歷史**

**適用場景**：
- 專案早期原型階段
- 本地開發環境
- 與團隊協作初期（還未確定 schema）

**警告**：不應用於正式環境！

#### 4. **查看遷移狀態**

```bash
npx prisma migrate status
```

輸出例：
```
Following migrations have not yet been applied:
  20240110_add_user_posts
  20240112_create_comment_table
```

---

### 正式環境部署（Production）

#### 1. **套用所有待機遷移**

```bash
npx prisma migrate deploy
```

**這個指令會**：
- 執行所有待機的遷移到正式資料庫
- 如果資料庫不存在，會自動建立
- 更新 `_prisma_migrations` 表格

**部署最佳實踐**：
- 在 CI/CD pipeline 中執行此命令
- 不應直接在本地機器上執行
- 建議在部署前測試遷移

範例 GitHub Actions workflow：
```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npx prisma migrate deploy
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL_PROD }}
```

#### 2. **驗證遷移（不實際執行）**

```bash
npx prisma migrate resolve --rolled-back <migration_name>
```

用於標記遷移為已回滾（在需要修復失敗的遷移時）。

---

### 反向工程（Introspection）

#### 1. **從既有資料庫產生 Prisma Schema**

```bash
npx prisma db pull
```

**這個指令會**：
- 連線到 `DATABASE_URL` 指定的資料庫
- 讀取所有表格、欄位、索引、外鍵
- 自動產生對應的 Prisma models
- 覆寫 `prisma/schema.prisma`（備份舊檔！）

**例子**：
```bash
# 假設 .env 包含：
# DATABASE_URL="postgresql://user:pass@localhost:5432/legacy_db"

npx prisma db pull
```

輸出會產生 `schema.prisma`，例如：
```prisma
model User {
  id    Int     @id @default(autoincrement())
  email String  @unique
  name  String?
  posts Post[]
}

model Post {
  id     Int     @id @default(autoincrement())
  title  String
  userId Int
  user   User    @relation(fields: [userId], references: [id])

  @@index([userId])
}
```

**重要事項**：
- 此命令會**覆寫** `schema.prisma`，務必先備份或提交到版本控制
- 如果有手動新增的 comments 或 `@attributes`，會被保留
- 某些資料庫特性可能無法完全表達（如複雜的觸發器、check constraints）

---

## 連線字串（DATABASE_URL）

### 格式

每種資料庫的格式不同：

#### PostgreSQL
```env
DATABASE_URL="postgresql://username:password@hostname:5432/database_name"
```

或簡寫：
```env
DATABASE_URL="postgres://username:password@hostname:5432/database_name"
```

#### MySQL
```env
DATABASE_URL="mysql://username:password@hostname:3306/database_name"
```

#### SQLite
```env
DATABASE_URL="file:./dev.db"
```

#### SQL Server
```env
DATABASE_URL="sqlserver://hostname:1433;database=database_name;user=sa;password=password;"
```

#### MongoDB
```env
DATABASE_URL="mongodb://username:password@hostname:27017/database_name"
```

### 特殊字元處理

如果密碼包含特殊字元（如 `@`, `:`, `/`），必須使用 URL encoding：

| 字元 | 編碼 |
|------|------|
| `@` | `%40` |
| `:` | `%3A` |
| `/` | `%2F` |
| `#` | `%23` |

例：密碼是 `pass@word`
```env
DATABASE_URL="postgresql://user:pass%40word@localhost:5432/dbname"
```

### 環境變數載入

Prisma 自動載入 `.env` 和 `.env.local` 的變數。優先順序：

1. 系統環境變數（最高優先）
2. `.env.local`
3. `.env`

檢查 skill 應在執行任何命令前驗證 `DATABASE_URL` 存在：
```bash
grep -q DATABASE_URL .env .env.local 2>/dev/null && echo "Found" || echo "Missing"
```

---

## Prisma Schema 核心概念

### Model 定義

```prisma
model User {
  // 欄位與類型
  id        Int     @id @default(autoincrement())
  email     String  @unique
  name      String?
  createdAt DateTime @default(now())

  // 關聯
  posts     Post[]
  profile   Profile?

  // 索引
  @@unique([email, name])
  @@index([createdAt])
}

model Post {
  id     Int     @id @default(autoincrement())
  title  String
  userId Int
  
  // 關聯定義
  user   User    @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
}

model Profile {
  id     Int     @id @default(autoincrement())
  bio    String?
  userId Int     @unique
  user   User    @relation(fields: [userId], references: [id], onDelete: Cascade)
}
```

### 常用屬性

| 屬性 | 用途 | 例 |
|------|------|-----|
| `@id` | 主鍵 | `id Int @id` |
| `@unique` | 唯一約束 | `email String @unique` |
| `@default()` | 預設值 | `status String @default("active")` |
| `@db.*` | 資料庫原生類型 | `@db.VarChar(255)` |
| `@relation()` | 外鍵關聯 | `@relation(fields: [userId], references: [id])` |
| `@@unique()` | 複合唯一索引 | `@@unique([email, provider])` |
| `@@index()` | 查詢索引 | `@@index([email])` |
| `@@fulltext()` | 全文搜尋索引（MySQL） | `@@fulltext([title, content])` |

---

## Shadow Database

### 說明

Shadow database 是 `prisma migrate dev` 自動建立的**暫時資料庫**，用於：

1. **偵測 schema drift**：檢查是否有人直接修改了資料庫（不透過遷移）
2. **驗證新遷移**：測試新遷移不會導致資料遺失或衝突
3. **產生遷移差異**：比對目前 schema 與預期狀態

### 工作流程

```
執行 prisma migrate dev
    ↓
建立 shadow database（通常名稱是原資料庫名 + "_shadow"）
    ↓
重放所有既有遷移到 shadow database
    ↓
套用新的 schema 變更到 shadow database
    ↓
檢查是否有 schema drift 警告
    ↓
刪除 shadow database
    ↓
套用遷移到主資料庫
    ↓
輸出新的遷移檔案
```

### 常見問題

**Q: Shadow database 建立失敗**

常見原因：
- 資料庫使用者無建立新資料庫的權限
- PostgreSQL 中 `CREATEDB` 權限不足

解決方案：
```sql
-- PostgreSQL
ALTER ROLE username CREATEDB;
```

**Q: 如何自訂 shadow database 名稱**

在 `schema.prisma` 中設定：
```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
  shadowDatabaseUrl = env("SHADOW_DATABASE_URL")
}
```

然後在 `.env` 中：
```env
DATABASE_URL="postgresql://user:pass@localhost:5432/main_db"
SHADOW_DATABASE_URL="postgresql://user:pass@localhost:5432/shadow_db"
```

---

## 連線池與 Connection Pooling

### 問題背景

應用程式每次建立新的 Prisma Client 實例時，都會建立新的資料庫連線。在高併發場景下，這會耗盡資料庫的連線限制。

### 解決方案

#### 1. **使用 Prisma Accelerate（官方託管方案）**

```bash
npm install @prisma/extension-accelerate
```

在應用程式中：
```typescript
import { PrismaClient } from '@prisma/client'
import { withAccelerate } from '@prisma/extension-accelerate'

const prisma = new PrismaClient()
  .$extends(withAccelerate())

export default prisma
```

環境變數：
```env
DATABASE_URL="postgresql://..."
ACCELERATE_URL="caches://..." // 自動產生
```

#### 2. **使用外部連線池（PgBouncer）**

適用於 PostgreSQL。在 Prisma schema 中設定 PgBouncer 位置：

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}
```

`.env`：
```env
# 指向 PgBouncer，而不是直接指向 PostgreSQL
DATABASE_URL="postgresql://user:pass@localhost:6432/database_name"
```

PgBouncer 配置範例（`pgbouncer.ini`）：
```ini
[databases]
database_name = host=actual-postgres-host port=5432 dbname=database_name

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

啟動 PgBouncer：
```bash
pgbouncer -d /etc/pgbouncer/pgbouncer.ini
```

#### 3. **連線池參數（驅動層）**

在 Prisma v5.0+，連線池行為由驅動程式管理，無法透過連線字串參數調整。如需要自訂池大小，應使用 Prisma Accelerate 或外部連線池。

### 最佳實踐

- **開發環境**：無需額外配置（連線數量少）
- **測試環境**：可使用 SQLite（記憶體）或單一連線
- **正式環境**：使用 Prisma Accelerate 或 PgBouncer

---

## migrate vs db push：常見混淆

| 功能 | `prisma migrate dev` | `prisma db push` |
|------|----------------------|------------------|
| **遷移檔案** | ✅ 產生 `.sql` 遷移檔 | ❌ 不產生 |
| **版本控制** | ✅ 可追蹤變更歷史 | ❌ 無歷史記錄 |
| **Shadow DB** | ✅ 檢查 schema drift | ❌ 無 |
| **資料遺失檢測** | ✅ 有警告 | ⚠️ 直接執行，無警告 |
| **使用場景** | 常規開發 + 正式環境 | 原型快速迭代 |
| **備份建議** | 選擇性 | **必須** |
| **適用環境** | 開發、測試、正式 | **僅開發** |

**建議決策樹**：
```
專案初期（還在探索 schema）？
  ├─ 是 → 使用 db push（快速迭代）
  └─ 否 → 使用 migrate dev（有版本控制）

已上線到測試/正式環境？
  └─ 一律使用 migrate deploy（安全、可追蹤）
```

---

## 常見錯誤與解決方案

### 1. "Error: P1001 - Can't reach database server"

**原因**：`DATABASE_URL` 連線字串錯誤或資料庫無法訪問

**解決**：
```bash
# 驗證連線字串語法
echo $DATABASE_URL

# 測試連線（PostgreSQL）
psql $DATABASE_URL -c "SELECT 1"

# 測試連線（MySQL）
mysql -u user -p -h host -D database -e "SELECT 1"
```

### 2. "Error: P3009 - Prisma Migrate could not create the shadow database"

**原因**：資料庫使用者無建立資料庫的權限

**解決**（PostgreSQL）：
```sql
ALTER ROLE your_user CREATEDB;
```

### 3. "Schema is out of sync with the database"

**原因**：有人直接修改了資料庫（不透過遷移）

**解決**：
```bash
# 重新同步（會覆寫 schema.prisma）
npx prisma db pull

# 或手動檢查資料庫
npx prisma migrate diff --from-schema-datamodel --to-schema-datamodel
```

### 4. "Error: P2002 - Unique constraint failed on the fields: (email)"

**原因**：嘗試在現有資料中違反唯一約束

**解決**：
```bash
# 檢查現有資料
SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

# 清理重複或新增遷移來安全地處理
```

### 5. "Cannot find Prisma schema file"

**原因**：`schema.prisma` 不在預期位置

**解決**：
```bash
# 尋找 schema 檔案
find . -name "schema.prisma" -type f

# 如果在非標準位置，設定 PRISMA_SCHEMA_PATH
export PRISMA_SCHEMA_PATH="./custom/path/schema.prisma"
```

---

## Skill 執行流程

### 一. 偵測階段

```
1. 檢查 package.json 中是否有 @prisma/client 與 prisma
2. 查找 prisma/schema.prisma（或其他位置）
3. 驗證 .env / .env.local 包含 DATABASE_URL
4. 列出所有待機遷移
```

### 二. 使用者選擇

```
根據偵測結果，提示使用者：
- 「初始化新 Prisma 專案」（如果無 schema.prisma）
- 「產生新遷移」（開發）
- 「直接同步（db push）」（原型）
- 「反向工程（db pull）」（既有資料庫）
- 「部署遷移」（正式環境）
```

### 三. 執行

```
根據選擇執行相應命令，監控輸出並提示：
- 遷移產生的檔案位置
- 資料庫變更摘要
- 任何警告或錯誤
```

### 四. 驗證

```
執行後：
1. npx prisma migrate status（確認狀態）
2. npx prisma generate（更新 Prisma Client）
3. 提示用戶檢查 /prisma/migrations 中的新檔案
```

---

## Skill 命令範例

以下為 skill 應支援的使用者命令：

```
/db-autowire init                    # 初始化新專案
/db-autowire migrate                 # 產生新遷移（開發）
/db-autowire migrate-name "add posts table"  # 產生具名遷移
/db-autowire push                    # 直接同步（無遷移文件）
/db-autowire deploy                  # 部署到正式（執行待機遷移）
/db-autowire introspect              # 反向工程既有資料庫
/db-autowire status                  # 查看遷移狀態
/db-autowire reset                   # 重設本地資料庫（開發用）
/db-autowire generate                # 重新產生 Prisma Client
/db-autowire studio                  # 啟動 Prisma Studio（視覺化資料管理）
```

---

## 參考資源

- [Prisma Migrate 官方文件](https://www.prisma.io/docs/orm/prisma-migrate)
- [Prisma db push 說明](https://www.prisma.io/docs/orm/reference/prisma-cli-reference#db-push)
- [Prisma Introspection](https://www.prisma.io/docs/orm/prisma-schema/introspection)
- [Prisma Schema Reference](https://www.prisma.io/docs/orm/reference/prisma-schema-reference)
- [Connection Pooling in Prisma](https://www.prisma.io/docs/orm/prisma-client/setup-and-configuration/databases-connections/connection-pool)
- [Shadow Database](https://www.prisma.io/docs/orm/prisma-migrate/understanding-prisma-migrate/shadow-database)
- [PgBouncer 設定](https://www.prisma.io/docs/orm/prisma-client/setup-and-configuration/databases-connections/pgbouncer)
