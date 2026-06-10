# db-autowire 技能參考文件：Supabase PostgreSQL 快速上手

db-autowire 是通用、可重複使用的 Claude Code skill，旨在將任何專案的資料模型自動產生 schema、對接真實雲端資料庫、並串起整個資料庫連線。本文件提供最新的免費 PostgreSQL 雲端服務設置步驟及常見雷區。

## 概述

Supabase 提供免費層 PostgreSQL 資料庫服務，適合開發與測試。支援 JDBC、JavaScript SDK、REST API 等多種連線方式。

### 免費方案限制（2026）

Supabase 免費方案仍然存在，但有以下限制：

| 限制項目 | 免費方案 |
|--------|--------|
| 儲存容量 | 500 MB |
| 資料庫連線數 | 10 個並行連線 |
| 自動暫停 | 無活動 1 週後暫停（需手動重啟） |
| 強制 SSL | 是（支援 `sslmode=require`） |
| Egress 流量 | 無限制 |
| 外鍵支援 | 完全支援 |

**關鍵變動**：免費方案於 2023 年末調整為 500MB，原來的 3 GB 已停用。如需更大空間建議升級至付費方案或改用自架 PostgreSQL。

## 註冊與建立免費資料庫

### 步驟 1：建立帳戶

前往 https://supabase.com 點擊「Start Your Project」。

支援登入方式：
- GitHub（推薦，減少密碼管理）
- Google
- Email + 密碼

### 步驟 2：建立組織與專案

1. 登入後進入 Dashboard
2. 新建組織（Organization）（若為首次）
3. 新建專案（Project），選項如下：
   - **專案名稱**：自訂（例如 `my-app-db`）
   - **密碼**：設定 PostgreSQL `postgres` 使用者密碼（重要：務必記住）
   - **地區**：選擇最接近你的區域（例如 `ap-northeast-1` 東京、`eu-west-1` 愛爾蘭）
   - **定價方案**：選「Free」

### 步驟 3：等待初始化

專案建立通常需要 1-2 分鐘。完成後進入 Project Dashboard。

## 取得連線字串

### 位置

在 Supabase Dashboard 左側菜單選 **Settings** → **Database** → **Connection String**。

### 連線字串格式

Supabase 提供三種 URI 格式：

#### 標準 URI（URI 格式）

```
postgresql://postgres:YOUR_PASSWORD@db.XXXX.supabase.co:5432/postgres
```

#### JDBC URL（Java 應用）

```
jdbc:postgresql://db.XXXX.supabase.co:5432/postgres?user=postgres&password=YOUR_PASSWORD&sslmode=require
```

#### 連線池 URI（使用 PgBouncer，推薦用於短連線）

```
postgresql://postgres:YOUR_PASSWORD@db.XXXX.supabase.co:6543/postgres
```

### 連線字串各部分解釋

| 部分 | 說明 | 例值 |
|-----|------|------|
| `postgres` | 預設使用者 | `postgres` |
| `YOUR_PASSWORD` | 你設定的密碼 | 自訂 |
| `db.XXXX.supabase.co` | 主機名稱 | `db.abcdefgh.supabase.co` |
| `5432` | 標準 PostgreSQL port（直連） | 5432 |
| `6543` | 連線池 port（PgBouncer） | 6543 |
| `postgres` | 預設資料庫名稱 | `postgres` |
| `sslmode=require` | 強制 SSL 連線 | 必須 |

### 連線池 vs 直連

| 連線方式 | Port | 用途 | 特性 |
|--------|------|------|------|
| 直連（Direct） | 5432 | 長連線應用 | 無限並行，但連線較重 |
| 連線池（PgBouncer） | 6543 | 短連線、web 應用 | 並行 10-20，輕量，推薦 |

對於 web 應用（Node.js、Java Spring 等），**建議用 port 6543**。

## 設置資料庫 Schema

### 方法 1：使用 Supabase SQL Editor（網頁）

1. 在 Dashboard 左側菜單選 **SQL Editor**
2. 新建查詢（New Query）
3. 貼入你的 DDL 指令，例如：

```sql
CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  name VARCHAR(255),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE posts (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(500) NOT NULL,
  content TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

4. 點擊「Run」執行

### 方法 2：使用命令行工具（psql）

首先安裝 `psql`（PostgreSQL client）：

**Windows:**
```powershell
# 使用 winget
winget install PostgreSQL.PostgreSQL -v 16

# 驗證安裝
psql --version
```

**macOS:**
```bash
brew install postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install postgresql-client
```

連線到你的資料庫：

```bash
psql postgresql://postgres:YOUR_PASSWORD@db.XXXX.supabase.co:5432/postgres
```

或直接執行 SQL 檔案：

```bash
psql postgresql://postgres:YOUR_PASSWORD@db.XXXX.supabase.co:5432/postgres < schema.sql
```

### 方法 3：使用 DBeaver 或 pgAdmin（GUI）

1. 新建資料庫連線，輸入連線字串中的各部分
2. Host: `db.XXXX.supabase.co`
3. Port: `5432` 或 `6543`
4. Database: `postgres`
5. User: `postgres`
6. Password: `YOUR_PASSWORD`
7. **SSL Mode**: 務必勾選 `Require`

## 常見雷區與注意事項

### 1. SSL 連線必須啟用

Supabase 強制 SSL。所有連線都**必須**包含 SSL 參數，否則會被拒絕。

**正確做法：**
```
jdbc:postgresql://db.XXXX.supabase.co:5432/postgres?sslmode=require&user=postgres&password=PASSWORD
```

**錯誤做法：**
```
jdbc:postgresql://db.XXXX.supabase.co:5432/postgres  # 會連線失敗
```

### 2. 自動暫停（Pausing）

無活動超過 7 天的免費專案會自動暫停，重啟需要 1-2 分鐘。若應用需要高可用性，建議升級至付費方案（可禁用自動暫停）。

**檢查暫停狀態**：在 Dashboard 左側的 **Status** 頁面查看。

### 3. 使用者名稱前綴

Supabase 對使用者名稱**沒有**強制前綴要求（不同於某些 tier 1 服務），直接使用 `postgres` 即可。

### 4. 外鍵完全支援

Supabase PostgreSQL 完全支援 FOREIGN KEY 約束：

```sql
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  ...
);
```

### 5. 並行連線限制

免費方案限制 **10 個並行連線**。若使用 ORM（如 Hibernate），務必設定連線池上限 ≤ 10：

**Java/Spring Boot 範例（application.properties）：**
```properties
spring.datasource.hikari.maximum-pool-size=8
spring.datasource.hikari.minimum-idle=2
spring.datasource.url=jdbc:postgresql://db.XXXX.supabase.co:6543/postgres?sslmode=require
spring.datasource.username=postgres
spring.datasource.password=YOUR_PASSWORD
spring.datasource.driver-class-name=org.postgresql.Driver
```

### 6. 區域選擇

一旦建立專案，區域**無法改變**。選擇時考慮延遲，改變區域需要另建專案並遷移資料。

### 7. 時區與 TIMESTAMP 預設

PostgreSQL 預設時區為 UTC。建議在 schema 中明確指定：

```sql
SET timezone = 'UTC';
-- 或在特定列上
CREATE TABLE events (
  id SERIAL PRIMARY KEY,
  happened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## 從程式碼連線

### JavaScript/Node.js（使用 pg 或 supabase-js）

**使用 pg 套件：**
```javascript
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: 'postgresql://postgres:PASSWORD@db.XXXX.supabase.co:6543/postgres',
  ssl: { rejectUnauthorized: false }  // Supabase 需要此設定
});

const result = await pool.query('SELECT * FROM users');
console.log(result.rows);
```

**使用 Supabase 官方 SDK：**
```javascript
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  'https://XXXX.supabase.co',
  'YOUR_ANON_KEY'  // 從 Settings → API 取得
);

const { data, error } = await supabase.from('users').select('*');
```

### Java/Spring Boot

**Maven 依賴：**
```xml
<dependency>
  <groupId>org.postgresql</groupId>
  <artifactId>postgresql</artifactId>
  <version>42.7.0</version>
</dependency>

<dependency>
  <groupId>com.zaxxer</groupId>
  <artifactId>HikariCP</artifactId>
  <version>5.1.0</version>
</dependency>
```

**application.properties：**
```properties
spring.datasource.url=jdbc:postgresql://db.XXXX.supabase.co:6543/postgres?sslmode=require
spring.datasource.username=postgres
spring.datasource.password=YOUR_PASSWORD
spring.datasource.driver-class-name=org.postgresql.Driver
spring.jpa.hibernate.ddl-auto=validate
spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.PostgreSQLDialect
spring.datasource.hikari.maximum-pool-size=8
spring.datasource.hikari.connection-timeout=20000
```

### Python（使用 psycopg2 或 SQLAlchemy）

**psycopg2 範例：**
```python
import psycopg2

conn = psycopg2.connect(
    dbname='postgres',
    user='postgres',
    password='YOUR_PASSWORD',
    host='db.XXXX.supabase.co',
    port=6543,
    sslmode='require'
)

cursor = conn.cursor()
cursor.execute('SELECT * FROM users')
print(cursor.fetchall())
cursor.close()
conn.close()
```

**SQLAlchemy 範例：**
```python
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://postgres:PASSWORD@db.XXXX.supabase.co:6543/postgres',
    connect_args={'sslmode': 'require'}
)

result = engine.execute('SELECT * FROM users')
```

## 資料庫備份與恢復

### 自動備份

Supabase 免費方案提供 7 天的自動備份。在 Dashboard **Settings** → **Backups** 查看。

### 手動匯出

```bash
pg_dump -h db.XXXX.supabase.co -U postgres -d postgres -F c > backup.dump
```

### 匯入備份

```bash
pg_restore -h db.XXXX.supabase.co -U postgres -d postgres -F c backup.dump
```

## 故障排除

### 連線超時 / 拒絕連線

**原因 1：缺少 SSL**
```
解決方案：加上 sslmode=require
jdbc:postgresql://db.XXXX.supabase.co:5432/postgres?sslmode=require
```

**原因 2：密碼或主機名稱錯誤**
```
檢查 Dashboard Settings → Database，確認密碼和主機名稱
```

**原因 3：專案被暫停**
```
檢查 Dashboard Status，點擊「Resume」重啟
```

### 連線池耗盡

```
症狀：「too many connections」
原因：ORM 或應用建立超過 10 個並行連線
解決：
1. 減少連線池大小 (HikariCP: maximum-pool-size=6-8)
2. 改用 port 6543（PgBouncer）
```

### 無法寫入資料

```
症狀：INSERT/UPDATE 時權限不足
原因：某些自訂角色權限不足
解決：確保使用 postgres 使用者，或另建使用者時授予足夠權限
```

## 替代方案（若 Supabase 免費方案不適用）

### 1. PostgreSQL on Railway.app（推薦，2025 年仍有免費層）

- **儲存**：5 GB
- **SSL**：強制
- **連線**：無限制
- **自動暫停**：無
- 支援 JDBC、psycopg2 等

註冊 → New Project → Add Database (PostgreSQL) → 取得連線字串

### 2. PostgreSQL on Render.com（推薦）

- **儲存**：100 GB
- **連線**：無限制
- **自動暫停**：無
- 提供免費層用於開發測試

### 3. PostgreSQL on Heroku（已停用免費方案，2022 年取消）

Heroku 已於 2022 年停用免費 Dyno 和免費資料庫。不建議新專案使用。

### 4. 本地 Docker PostgreSQL

如果想避免雲端限制，可在本地運行：

```bash
docker run --name my-postgres \
  -e POSTGRES_PASSWORD=secret \
  -e POSTGRES_DB=mydb \
  -p 5432:5432 \
  -d postgres:16
```

連線字串：`postgresql://postgres:secret@localhost:5432/mydb`

## 快速清單

為了快速部署，按順序執行：

- [ ] 訪問 https://supabase.com，使用 GitHub 登入
- [ ] 建立新專案，記住密碼和區域
- [ ] 等待 1-2 分鐘讓專案初始化
- [ ] 從 **Settings** → **Database** 複製連線字串
- [ ] 在 **SQL Editor** 執行你的 schema DDL（或使用 psql）
- [ ] 驗證表格已建立：**Table Editor** 看得到新表
- [ ] 在你的應用程式碼中設定連線字串，注意 `sslmode=require`
- [ ] 測試讀寫操作

## 官方文件與參考

- Supabase 定價與免費方案：https://supabase.com/pricing
- PostgreSQL 連線字串：https://supabase.com/docs/guides/database/overview
- 常見問題：https://supabase.com/docs/faq
- Supabase 社群論壇：https://github.com/supabase/supabase/discussions
