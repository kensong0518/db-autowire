# db-autowire Skill Reference

## 概述

此文件供 **db-autowire** Claude Code skill 使用，用於自動化以下流程：

1. **掃描程式碼** 偵測資料模型（Java JPA entity / Python SQLAlchemy model）
2. **產生 SQL Schema**（DDL）
3. **連接到真實資料庫**（雲端或本地）
4. **初始化 Schema** 並驗證連線

本 skill 設計為通用、可重複使用，適用於任何專案。

---

## 推薦選項：Neon PostgreSQL（免費雲端）

### 為何選擇 Neon

- **完全免費**，無需信用卡
- **無自動升級**，不會突然收費
- **支援 PostgreSQL** 生態（最成熟的開源 SQL）
- **快速部署** 新資料庫（< 1 分鐘）

### 2026 年 Neon 免費方案規格

| 限制項目 | 免費方案額度 |
|--------|-----------|
| **儲存空間** | 0.5 GB/專案 |
| **計算額度** | 100 CU-hours/月 |
| **外發流量（Egress）** | 5 GB/月 |
| **專案數** | 最多 100 個 |
| **分支數/專案** | 最多 10 個 |
| **連接數**（pgBouncer） | 最多 10,000 個（需透過 pooler 連接） |
| **自動暫停** | 5 分鐘無活動後自動暫停（無法關閉） |
| **SQL Editor** | 網頁版內置 |
| **快照/復原** | 6 小時內復原，1 GB 變動上限 |

**雷區**：
- 免費方案自動暫停 5 分鐘無活動，會有冷啟動延遲（通常 200-500ms）
- 儲存空間上限 0.5 GB **per branch**，但 **project aggregate 最多 5 GB**（跨所有分支）
- 所有連線 **必須使用 SSL**（sslmode=require），無法關閉

### 註冊與建立免費資料庫

#### 步驟 1：登入 Neon

1. 前往 https://neon.com
2. 點擊 **Sign Up**
3. 選擇登入方式：
   - Email
   - GitHub
   - Google
   - Microsoft

#### 步驟 2：建立專案

登入後，系統會引導建立第一個 **Project**。

- 輸入專案名稱（例：`my-app-dev`）
- 選擇地區（通常選離你最近的，例 US East, EU West）
- 點擊 **Create Project**

系統自動產生：
- 一個 **production** branch（預設）
- 一個預設 **postgres** database
- 一個 **postgres** 角色（使用者）

#### 步驟 3：取得連線字串

專案建立完成後，進入控制台。

1. 左側菜單找到 **Connect** 或 **Connection Details**
2. 選擇：
   - **Branch**：production（預設）
   - **Database**：postgres
   - **Role**：postgres
   - **Database client**：Generic（或具體的工具，如 psql/JDBC/Node）

3. 複製顯示的連線字串

---

## 連線字串格式

### 通用 PostgreSQL URI 格式

```
postgresql://[username]:[password]@[hostname]/[database_name]?sslmode=require
```

### Neon 連線字串範例

```
postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?sslmode=require
```

**分解：**

| 部分 | 例值 | 說明 |
|------|------|------|
| `postgres://` | 常數 | PostgreSQL 協定 |
| `postgres` | 使用者名 | Neon 預設角色 |
| `abc123xyz` | 密碼 | 隨機產生，妥善保管 |
| `ep-calm-tree-12345.us-east-1.aws.neon.tech` | hostname | Neon endpoint，含地區 |
| `neondb` | database | 預設 database 名稱 |
| `sslmode=require` | 參數 | 強制 SSL 加密（必須） |

### JDBC 格式（Java/Spring Boot）

```
jdbc:postgresql://[hostname]/[database]?user=[username]&password=[password]&sslmode=require&channelBinding=require
```

**Neon JDBC 範例：**

```
jdbc:postgresql://ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?user=postgres&password=abc123xyz&sslmode=require&channelBinding=require
```

**參數說明：**

| 參數 | 值 | 說明 |
|------|----|----|
| `sslmode=require` | 必須 | 啟用 SSL 加密 |
| `channelBinding=require` | 推薦 | Neon 特有，增強安全 |
| `connectTimeout=15` | 選用 | 連接逾時（秒） |
| `pool_timeout=15` | 選用 | 連接池逾時（秒） |

### Python psycopg2 格式

```python
import psycopg2

conn = psycopg2.connect(
    host='ep-calm-tree-12345.us-east-1.aws.neon.tech',
    port=5432,
    database='neondb',
    user='postgres',
    password='abc123xyz',
    sslmode='require'
)
```

或使用 DSN：

```python
dsn = "postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?sslmode=require"
conn = psycopg2.connect(dsn)
```

### Spring Boot 配置

在 `application.properties` 或 `application.yml` 中：

```properties
spring.datasource.url=jdbc:postgresql://ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?sslmode=require&channelBinding=require
spring.datasource.username=postgres
spring.datasource.password=abc123xyz
spring.datasource.driver-class-name=org.postgresql.Driver

# Hibernate 自動建表
spring.jpa.hibernate.ddl-auto=update
spring.jpa.database-platform=org.hibernate.dialect.PostgreSQL95Dialect
```

或 YAML：

```yaml
spring:
  datasource:
    url: jdbc:postgresql://ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?sslmode=require&channelBinding=require
    username: postgres
    password: abc123xyz
    driver-class-name: org.postgresql.Driver
  jpa:
    hibernate:
      ddl-auto: update
    database-platform: org.hibernate.dialect.PostgreSQL95Dialect
```

---

## 載入 Schema 的方法

### 方法 1：Neon 網頁 SQL Editor（最簡單）

1. 進入 Neon 控制台
2. 左側菜單 → **SQL Editor**
3. 選擇 Branch 和 Database
4. 粘貼 DDL 語句（CREATE TABLE 等）
5. 點擊 **Run**

**優點：**無需本地工具，立即執行  
**缺點：**大型 schema 可能需多次執行

### 方法 2：psql 命令列（推薦用於自動化）

#### 安裝 psql

**Windows:**
```powershell
# 使用 PostgreSQL 官方安裝器或 scoop
scoop install postgresql

# 或下載 PostgreSQL：
# https://www.postgresql.org/download/windows/
```

**macOS:**
```bash
brew install postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install postgresql-client
```

#### 執行 psql 連線

```bash
psql postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb
```

連線成功後會進入 psql 提示符 `neondb=>`。

#### 執行 DDL 檔案

```bash
# 方法 1：直接執行文件
psql postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb -f schema.sql

# 方法 2：從標準輸入管道
cat schema.sql | psql postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb
```

#### psql 常用指令

進入 psql 提示符後：

```sql
-- 查看所有表
\dt

-- 查看特定表結構
\d table_name

-- 執行 SQL
CREATE TABLE users (id SERIAL PRIMARY KEY, name TEXT);

-- 查看執行結果
SELECT * FROM users;

-- 離開
\q
```

### 方法 3：Java/Spring Boot Hibernate 自動建表

如果使用 Spring Boot + Hibernate，設定 `ddl-auto=update` 或 `create-drop`：

```properties
spring.jpa.hibernate.ddl-auto=update
```

啟動應用時，Hibernate 自動掃描 `@Entity` 類並建立對應表。

**警告：** 生產環境不建議使用 `update` 或 `create-drop`，改用 Flyway/Liquibase 進行版本控制的遷移。

### 方法 4：Python SQLAlchemy

```python
from sqlalchemy import create_engine

# 建立引擎
engine = create_engine(
    "postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb"
)

# 自動建表（從 ORM 定義）
Base.metadata.create_all(engine)
```

---

## 連線池與限制詳解

### Neon pgBouncer 連線池

Neon 內置 **PgBouncer**（連接池管理器），支援最多 **10,000 個客户端連接**。

**運作模式：**
- **transaction mode**：每次事務後連接歸還池（推薦用於無伺服器函式）
- **session mode**（不可用於免費方案）：連接綁定到整個會話

**限制：**
- 免費方案無法關閉自動暫停，5 分鐘無活動自動進入休眠
- 連接池 per user/database 上限約 **377 個併發**（1 CU compute）
- 不支援 `SET` 語句、`LISTEN`/`NOTIFY`、會話級 prepared statement

**建議：**
- 使用 **pooled connection** 進行 web 應用與無伺服器函式
- 使用 **direct connection** 進行 schema 遷移、pg_dump、邏輯複製

### 連線字串中的 Pooler 參數

如需使用 Neon pooler（推薦）：

```
postgresql://postgres:password@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?sslmode=require
```

**vs. 直連（跳過 pooler）：**

某些工具可在 hostname 中插入 `-direct` 後綴：

```
postgresql://postgres:password@ep-calm-tree-12345-direct.us-east-1.aws.neon.tech/neondb?sslmode=require
```

---

## 關鍵雷區與最佳實踐

### 1. SSL 強制要求

**雷區：** Neon 所有連接都必須使用 SSL，無法關閉。

**檢查：** 連線字串務必包含 `?sslmode=require`

**驗證：**
```bash
psql postgresql://postgres:password@...?sslmode=require -c "SELECT version();"
```

### 2. 自動暫停與冷啟動

**雷區：** 免費方案 5 分鐘無活動自動暫停，重啟時延遲 200-500ms。

**解決方案：**
- 無伺服器 app 需容忍冷啟動
- 本地開發可接受延遲
- 付費方案可配置暫停延遲或禁用

### 3. 儲存空間計數

**雷區：** 0.5 GB per branch，但 **aggregate 限制 5 GB per project**。

**範例：** 若有 10 個分支，平均每分支只能用 0.5 GB；若某個分支佔 1 GB，其他分支受限。

**管理：**
- 定期刪除不用的分支
- 檢查 Neon 控制台 → Usage
- 定期清理大型資料（logs、臨時表）

### 4. 使用者名稱與密碼

**Neon 預設角色：** `postgres`（不含前綴）

**密碼安全性：** 妥善保管，考慮存放在 `.env` 檔案並加入 `.gitignore`

```bash
# .env
DATABASE_URL=postgresql://postgres:password@...?sslmode=require

# .gitignore
.env
```

### 5. 外發流量限制

免費方案 **5 GB egress/月**（資料下載）。

**常見用途：**
- 應用伺服器查詢
- 資料匯出
- 日誌流

**監控：** Neon 控制台 → Usage → Network

---

## 環境變數與連線字串管理

### 推薦做法

使用環境變數避免硬碼密碼。

#### Java/Spring Boot

1. 建立 `.env` 檔案：

```
DATABASE_URL=postgresql://postgres:abc123xyz@ep-calm-tree-12345.us-east-1.aws.neon.tech/neondb?sslmode=require
```

2. 使用 dotenv-java 載入：

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.github.cdimascio</groupId>
    <artifactId>dotenv-java</artifactId>
    <version>3.0.0</version>
</dependency>
```

```java
import io.github.cdimascio.dotenv.Dotenv;

Dotenv dotenv = Dotenv.load();
String dbUrl = dotenv.get("DATABASE_URL");
```

或設定 JVM 環境變數：

```bash
# Windows PowerShell
$env:DATABASE_URL = "postgresql://..."

# Linux/macOS bash
export DATABASE_URL="postgresql://..."
```

3. `application.properties` 讀取環境變數：

```properties
spring.datasource.url=${DATABASE_URL}
```

#### Python

使用 `python-dotenv`：

```python
from dotenv import load_dotenv
import os

load_dotenv()
db_url = os.getenv('DATABASE_URL')
```

---

## Neon 控制台快速導覽

### 主要選單

| 選項 | 用途 |
|------|------|
| **Projects** | 列出所有專案 |
| **SQL Editor** | 網頁 SQL 編輯器（執行 DDL/DML） |
| **Branches** | 建立/刪除分支（開發分支） |
| **Databases** | 列出各 branch 的 database |
| **Roles** | 管理資料庫使用者 |
| **Connection Details** | 取得連線字串 |
| **Usage** | 檢查儲存、計算、流量使用量 |

### 快速操作

- **檢查連線：** Projects → [Project] → Connection Details
- **查看表結構：** SQL Editor → \dt（列表），\d table_name（詳情）
- **刪除分支：** Branches → [Branch] → Delete
- **監控使用：** Usage → Storage/Compute/Network tabs

---

## 備選免費雲端資料庫

如果 Neon 不適用，考慮以下選項：

### Supabase（PostgreSQL + 後端服務）

- **免費方案：** 2 個專案，500 MB 儲存，50,000 MAU
- **暫停政策：** 7 天無活動後暫停
- **優點：** 內含 Auth、Realtime、Vector Search (pgvector)
- **缺點：** 儲存空間更少（500 MB vs 0.5 GB），暫停時間更長
- **連線字串：** 與 Neon 相同（PostgreSQL URI）

**官方：** https://supabase.com

### Railway（通用容器部署）

- **免費方案：** 已取消（2024 年）
- **現況：** $5 試用額度，過期後 $5/月 Hobby 方案
- **特點：** 支援 Postgres、Redis、MySQL 等
- **適用：** 若願意花 $5/月，部署更靈活
- **連線字串：** PostgreSQL 標準格式

**官方：** https://railway.app

### Firebase Realtime Database（NoSQL，非關聯式）

- **免費方案：** Spark Plan，1 GB 儲存，100 併發連接
- **優點：** 實時同步，支援 Google Cloud 生態
- **缺點：** NoSQL（JSON），不適合複雜 SQL 查詢
- **連線：** RESTful API 或 SDK（非 SQL）

**官方：** https://firebase.google.com

---

## 故障排除

### 連線超時

**症狀：** `psql: error: could not translate host name`

**原因：** 
- hostname 錯誤
- 網路連線問題
- Neon endpoint 未啟用

**解決：**
```bash
# 驗證 hostname 格式
echo "ep-calm-tree-12345.us-east-1.aws.neon.tech"

# 測試 DNS 解析
nslookup ep-calm-tree-12345.us-east-1.aws.neon.tech

# 確保 Neon 專案啟用（控制台應可見）
```

### SSL 錯誤

**症狀：** `FATAL: no pg_hba.conf entry for host ... SSL off`

**原因：** 缺少 `sslmode=require` 或 SSL 參數錯誤

**解決：**
```bash
# 確認連線字串包含完整參數
psql postgresql://postgres:pwd@host/db?sslmode=require&channelBinding=require
```

### 儲存空間超限

**症狀：** `ERROR: disk full` 或建表失敗

**原因：** 達到 0.5 GB（per branch）或 5 GB（per project）上限

**解決：**
1. Neon 控制台 → Usage 檢查磁碟使用
2. 刪除大型表或過舊資料
3. 建立新分支轉移資料
4. 升級付費方案

### 自動暫停導致應用掛起

**症狀：** 應用啟動慢或首次查詢逾時

**原因：** 資料庫暫停，冷啟動延遲

**解決：**
- 應用端設置更長的連接逾時
- 使用連接池保持最少連線活躍
- 考慮升級付費方案禁用暫停

---

## 相關指令速查

### 獲取連線字串

```bash
# Neon CLI（若已安裝）
neon connection-string

# 或手動組合（replace placeholders）
postgresql://postgres:PASSWORD@HOSTNAME/neondb?sslmode=require
```

### 驗證連線

```bash
# psql 連線測試
psql "postgresql://postgres:PASSWORD@HOSTNAME/neondb?sslmode=require" -c "SELECT NOW();"

# 若成功，顯示當前時間
```

### 匯出 Schema

```bash
# 僅 schema（無資料）
pg_dump --schema-only postgresql://postgres:PASSWORD@HOSTNAME/neondb > schema.sql

# 含資料
pg_dump postgresql://postgres:PASSWORD@HOSTNAME/neondb > backup.sql
```

### 匯入 Schema

```bash
# 執行 SQL 檔案
psql postgresql://postgres:PASSWORD@HOSTNAME/neondb -f schema.sql
```

---

## 安全性檢查清單

- [ ] 連線字串中密碼未硬碼到原始檔案
- [ ] `.env` 檔案加入 `.gitignore`
- [ ] 使用 `sslmode=require` 強制 SSL
- [ ] 定期檢查 Neon 使用量，避免超過限制
- [ ] 生產環境使用獨立角色（非 postgres），設置最小權限
- [ ] 啟用 Neon 計畫警告（Usage → Alerts）

---

## 參考資源

- **Neon 官方文件**：https://neon.com/docs
- **連線指南**：https://neon.com/docs/connect/connection-latency
- **SQL Editor**：https://neon.com/docs/get-started/query-with-neon-sql-editor
- **psql 連線**：https://neon.com/docs/connect/query-with-psql-editor
- **Java 指南**：https://neon.com/docs/guides/java
- **PostgreSQL JDBC**：https://jdbc.postgresql.org
- **Prisma with Neon**：https://www.prisma.io/docs/orm/overview/databases/neon
