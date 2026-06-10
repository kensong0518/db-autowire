# db-autowire 技能參考：Render 免費 PostgreSQL

**更新時間**：2026 年 6 月 10 日

本文檔指導如何在 Render 上建立免費 PostgreSQL 資料庫、取得連線字串、載入 schema，並將其整合到 db-autowire skill。

---

## 1. Render 免費 PostgreSQL 方案概覽

### 方案可用性
Render **持續提供免費 PostgreSQL 方案**（截至 2026 年 6 月）。

### 免費方案限制

| 項目 | 限制 |
|------|------|
| 儲存容量 | 1 GB |
| 有效期限 | 30 天後自動過期 |
| 過期寬限期 | 額外 14 天可升級，之後資料被刪除 |
| 連線數 | 無官方限制，但需注意連線池限制 |
| 同時實例數 | 每個 workspace 只能有**一個**免費資料庫 |
| 頻寬 | 自 2026 年 4 月起：5 GB/月（之前為 100 GB/月） |

### 收費方案
如需保持資料永久存儲，最低收費方案起價 **$7/月**。

---

## 2. 註冊與建立免費資料庫

### 2.1 註冊 Render 帳戶

1. 前往 https://render.com
2. 點擊 **Sign Up** （無需信用卡）
3. 使用 GitHub、Google 或電子郵件帳戶註冊
4. 驗證電子郵件

### 2.2 建立免費 PostgreSQL 資料庫

**方式一：使用儀表板**

1. 登入 https://dashboard.render.com
2. 點擊 **+ New**，選擇 **Postgres**
3. 填寫以下資訊：
   - **Name**：輸入資料庫名稱（例：`my-app-db`）
   - **Database**：留空（Render 將自動產生 `render_<hash>`）
   - **User**：留空（Render 將自動產生）
4. **Region**：選擇與應用程式相同的區域（可用區域：Oregon、Ohio、Frankfurt、Singapore——2026 年 4 月起無 Mumbai/India）
5. **Plan**：確保選擇 **Free**
6. 點擊 **Create Database**
7. 等待 2-5 分鐘，資料庫初始化完成

**方式二：直接連結**

前往 https://dashboard.render.com/new/database，預先選定 Free 方案。

### 2.3 查看資料庫狀態

建立後，Render 會顯示：
- 資料庫狀態（Available / Creating / Failed）
- 過期倒計時（30 天）
- 連線資訊（見 2.4）

---

## 3. 取得連線字串與設置

### 3.1 連線資訊位置

在 Render 儀表板中，進入資料庫詳情頁面，向下捲動至 **Connections** 分頁，可看到：

```
External Database URL:
postgres://user_xxxx:password_yyyy@dpg-xxxxx-a.region-postgres.render.com/render_dbname

PostgreSQL Command Line:
psql "postgres://user_xxxx:password_yyyy@dpg-xxxxx-a.region-postgres.render.com/render_dbname"

Host:        dpg-xxxxx-a.region-postgres.render.com
Database:    render_dbname
User:        user_xxxx
Password:    password_yyyy
Port:        5432
```

### 3.2 連線字串格式

**標準 PostgreSQL URL（用於大多數工具）**

```
postgres://username:password@host:port/database?sslmode=require
```

範例：

```
postgres://user_abc:mypassword123@dpg-xyz-a.oregon-postgres.render.com:5432/myappdb?sslmode=require
```

**JDBC 連線字串（Java 應用程式）**

```
jdbc:postgresql://host:port/database?ssl=true&sslmode=require&user=username&password=password
```

範例：

```
jdbc:postgresql://dpg-xyz-a.oregon-postgres.render.com:5432/myappdb?ssl=true&sslmode=require&user=user_abc&password=mypassword123
```

**psql 命令列**

```bash
psql "host=dpg-xyz-a.oregon-postgres.render.com port=5432 dbname=myappdb user=user_abc password=mypassword123 sslmode=require"
```

### 3.3 SSL 要求

**Render 強制使用 SSL**——所有連線**必須**指定 `sslmode=require`（或更高層級如 `verify-full`）。

**Node.js / JavaScript**

```javascript
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: "postgres://user:pass@dpg-xxx.region-postgres.render.com/dbname",
  ssl: { rejectUnauthorized: false }  // Render 不要求 CA 認證
});
```

**Python**

```python
import psycopg2

conn = psycopg2.connect(
    host="dpg-xxx.region-postgres.render.com",
    port=5432,
    database="dbname",
    user="user",
    password="pass",
    sslmode="require"
)
```

**Spring Boot (Java)**

在 `application.properties` 或 `application.yml`：

```properties
spring.datasource.url=jdbc:postgresql://dpg-xxx.region-postgres.render.com:5432/dbname?sslmode=require
spring.datasource.username=user_abc
spring.datasource.password=password_xyz
spring.datasource.driver-class-name=org.postgresql.Driver
```

---

## 4. 載入 Schema

### 4.1 使用 Render 網頁 SQL 編輯器

1. 在 Render 儀表板中，點擊資料庫詳情
2. 選擇 **Browser** 分頁（如果可用）
3. 貼上 SQL DDL 語句，執行

### 4.2 使用 psql 指令列

**安裝 psql**（如未安裝）

- **Windows**：下載 PostgreSQL（https://www.postgresql.org/download/windows/），或使用 chocolatey：`choco install postgresql`
- **macOS**：`brew install postgresql@15`
- **Linux**：`sudo apt-get install postgresql-client`

**連線並執行 SQL**

```bash
psql "postgres://user_abc:password@dpg-xxx-a.region-postgres.render.com:5432/mydbname?sslmode=require" < schema.sql
```

或交互式：

```bash
psql -h dpg-xxx-a.region-postgres.render.com \
     -p 5432 \
     -U user_abc \
     -d mydbname \
     -c "your_sql_statement_here;"
```

### 4.3 使用 DBeaver / TablePlus

**DBeaver（免費、跨平台）**

1. 開啟 DBeaver
2. **File > New > Database Connection > PostgreSQL**
3. 填寫：
   - Host: `dpg-xxx-a.region-postgres.render.com`
   - Port: `5432`
   - Database: `render_dbname`
   - Username: `user_abc`
   - Password: `password_xyz`
4. 勾選 **SSL**
5. 連線，然後於 SQL Editor 貼上 schema

**TablePlus（付費但可免費試用）**

1. 點擊 **+** 新增連線
2. 選擇 **PostgreSQL**
3. 填入上述同樣連線資訊
4. **SSL Mode** 選擇 **Require**
5. 連線並執行 SQL

### 4.4 自動化：載入 SQL 檔案

**Node.js 範例**

```javascript
const fs = require('fs');
const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

async function loadSchema() {
  const sql = fs.readFileSync('./schema.sql', 'utf-8');
  try {
    await pool.query(sql);
    console.log('Schema loaded successfully');
  } catch (err) {
    console.error('Schema load failed:', err);
  }
}

loadSchema();
```

**Python 範例**

```python
import psycopg2
import os

conn = psycopg2.connect(os.environ['DATABASE_URL'] + '?sslmode=require')
cur = conn.cursor()

with open('schema.sql', 'r') as f:
    cur.execute(f.read())

conn.commit()
cur.close()
conn.close()
print('Schema loaded successfully')
```

---

## 5. db-autowire Skill 整合方式

### 5.1 自動偵測與產生 Schema

當 `db-autowire` skill 執行時，應：

1. **掃描專案代碼**
   - 偵測 JPA entities（`@Entity`）
   - 或偵測 Sequelize/TypeORM models
   - 或偵測 Prisma schema

2. **產生 DDL**
   - 根據 entities 產生 `CREATE TABLE` 語句
   - 包含約束、索引、外鍵

3. **提示使用者選擇資料庫**

   ```
   選擇資料庫類型：
   1. 免費 Render PostgreSQL（建議開發/測試）
   2. 本地 PostgreSQL / MySQL（Docker）
   3. 付費 TiDB Cloud / AWS RDS
   
   > 選擇 [1]: 1
   ```

4. **引導建立 Render 免費資料庫**
   - 提供逐步指示（開啟 dashboard.render.com、點擊 + New）
   - 等待使用者確認資料庫已建立
   - 提示輸入或自動偵測連線字串（從環境變數）

5. **載入 Schema**
   - 使用 psql、Pool 或 DBeaver 自動化連線
   - 執行產生的 DDL
   - 驗證 schema 成功建立

6. **產生環境變數**

   自動產生或更新 `.env` / `docker-compose.yml`：

   ```env
   DATABASE_URL=postgres://user_abc:password@dpg-xxx-a.region-postgres.render.com:5432/dbname?sslmode=require
   DB_HOST=dpg-xxx-a.region-postgres.render.com
   DB_PORT=5432
   DB_NAME=dbname
   DB_USER=user_abc
   DB_PASSWORD=password
   ```

### 5.2 外鍵與約束支援

Render PostgreSQL **完全支援**：
- PRIMARY KEY
- FOREIGN KEY
- UNIQUE constraints
- CHECK constraints
- DEFAULT values
- NOT NULL 約束

無特殊限制。

### 5.3 連線池設置

**推薦設置（開發環境）**

```properties
# Spring Boot
spring.datasource.hikari.maximum-pool-size=5
spring.datasource.hikari.minimum-idle=2
spring.datasource.hikari.connection-timeout=20000
spring.datasource.hikari.idle-timeout=300000
spring.datasource.hikari.max-lifetime=1200000
```

由於 Render 免費方案無官方連線限制，但建議保守設置以防止資源耗盡。

### 5.4 注意事項

1. **免費資料庫會自動過期**——若超過 30 天未升級，資料將遺失
2. **一個 workspace 只能一個免費 DB**——若需多個資料庫，使用付費方案或多個 Render 帳戶
3. **region 選擇很重要**——與應用同 region 可降低延遲；Render 支援 Oregon、Ohio、Frankfurt、Singapore
4. **使用者名稱前綴**——Render 自動產生，格式 `user_<hash>`，無法自訂
5. **SSL 強制**——務必在連線字串加 `sslmode=require`；Render 不要求 CA 認證（`rejectUnauthorized: false` in Node.js）

---

## 6. 疑難排解

### 連線失敗：「sslmode required」

**解決**：確保連線字串包含 `?sslmode=require`

```
正確: postgres://user:pass@dpg-xxx.region-postgres.render.com/db?sslmode=require
錯誤: postgres://user:pass@dpg-xxx.region-postgres.render.com/db
```

### 連線失敗：「too many connections」

**原因**：連線池未正確配置或洩漏

**解決**：
- 檢查連線池大小
- 確保所有連線都被 close()
- 設置 `idle-timeout` 和 `max-lifetime`

### 資料庫已過期

**警告**：免費資料庫 30 天後自動過期，進入 14 天寬限期。過期後無法復原。

**升級步驟**：
1. 在 Render 儀表板中，進入該資料庫
2. 點擊 **Upgrade Plan**
3. 選擇付費方案（最低 $7/月）
4. 完成升級——資料保留，過期計時重置

### 無法建立第二個免費資料庫

**限制**：每個 workspace 只能一個免費 PostgreSQL 實例

**解決**：
- 升級現有資料庫為付費方案，或
- 使用不同的 Render 帳戶 / workspace，或
- 使用本地 Docker MySQL/PostgreSQL

---

## 7. 環境變數範本

將此複製到 `.env.example`（提交到版控，敏感值用佔位符）：

```env
# Render PostgreSQL Free Tier
DATABASE_URL=postgres://user_xxxx:password_yyyy@dpg-xxxxx-a.region-postgres.render.com:5432/render_dbname?sslmode=require

# 或分解為個別變數
DB_TYPE=postgresql
DB_HOST=dpg-xxxxx-a.region-postgres.render.com
DB_PORT=5432
DB_NAME=render_dbname
DB_USER=user_xxxx
DB_PASSWORD=password_yyyy
DB_SSL=true
```

在本機 `.env` 中填入實際憑證（絕不提交）：

```bash
cp .env.example .env
# 編輯 .env 並填入真實值
```

---

## 附錄：常見實作堆疊

### Spring Boot + JPA + Render PostgreSQL

```xml
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
<dependency>
  <groupId>org.postgresql</groupId>
  <artifactId>postgresql</artifactId>
  <version>42.7.3</version>
</dependency>
```

`application.properties`：

```properties
spring.jpa.database-platform=org.hibernate.dialect.PostgreSQL15Dialect
spring.datasource.url=${DATABASE_URL}
spring.jpa.hibernate.ddl-auto=validate
spring.datasource.hikari.maximum-pool-size=5
```

### Node.js + TypeORM + Render PostgreSQL

```bash
npm install typeorm pg
```

`data-source.ts`：

```typescript
import { DataSource } from 'typeorm';

export const AppDataSource = new DataSource({
  type: 'postgres',
  url: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  synchronize: false,
  logging: false,
  entities: ['src/**/*.entity.ts']
});
```

### Python + SQLAlchemy + Render PostgreSQL

```bash
pip install sqlalchemy psycopg2-binary
```

```python
from sqlalchemy import create_engine

engine = create_engine(
    os.environ['DATABASE_URL'],
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)
```

---

## 參考資源

- [Render 官方文檔：建立與連線 PostgreSQL](https://render.com/docs/postgresql-creating-connecting)
- [Render 定價頁面](https://render.com/pricing)
- [Render 部署文檔首頁](https://render.com/docs/free)
- [PostgreSQL SSL/TLS 連線](https://www.postgresql.org/docs/current/ssl-tcp.html)
