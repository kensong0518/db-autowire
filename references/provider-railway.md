# db-autowire 技能參考

## 概述

db-autowire 是一個通用、可重複使用的 Claude Code 技能。部署到任何專案後，它能自動：
1. 掃描程式碼中的資料模型（JPA entities、Hibernate 映射等）
2. 產生相應的資料庫 schema（DDL 語句）
3. 偵測堆疊類型（Java/Spring、Node.js、Python 等）
4. 對接真實或本機資料庫
5. 執行初始化與遷移

本文檔涵蓋：
- 支援的免費雲端資料庫與當前限制（2026 年6月）
- 準確的連線字串格式（標準 URL 與 JDBC 兩種）
- 對接步驟與常見雷區
- 本機測試路徑

---

## 免費雲端資料庫選項

### 1. Neon（PostgreSQL 推薦）

**現狀**（2026 年6月）：Neon 仍提供**慷慨的永久免費方案**，最適合開發與原型設計。

#### 免費方案額度
- **儲存空間**：每個專案 0.5 GB，最多 5 GB（跨最多 10 個專案）
- **計算**：每月 100 CU-hours（足以運行 0.25 CU 資料庫 400 小時，或滿速 1 CU 資料庫 100 小時）
- **連線**：無限連線數（透過 pgBouncer 連線池，最多 10,000 個池化連線）
- **流量**：每月 5 GB 輸出流量（egress）
- **專案數**：最多 20 個免費專案

#### 註冊與建立

1. 造訪 [neon.com](https://neon.com)，點選「Start Free」
2. 用 GitHub / Google / 電子郵件註冊（無需信用卡）
3. 建立新專案，選擇 region（預設 us-east-2）
4. 自動建立預設資料庫 `neondb` 與使用者 `neondb_owner`

#### 取得連線字串

**方式一：網頁主控台**
- 進入 Neon 儀表板 → 專案 → Connection → Database
- 複製「Connection string」（預設 psql 格式）或選擇 JDBC

**方式二：Neon CLI**
```powershell
# 安裝（npm）
npm install -g neon

# 登入
neon auth

# 取得連線字串
neon connection-string [project-id] [branch-name] --database [dbname]
```

#### 連線字串格式

**標準 URL 格式**（用於 psql、應用層連線池等）
```
postgresql://[user]:[password]@[host]/[database]?sslmode=require
```

**JDBC 格式**（Java 應用）
```
jdbc:postgresql://[host]/[database]?user=[user]&password=[password]&sslmode=require&channelBinding=require
```

**實例**
```
postgresql://neondb_owner:AbCdEf123456@ep-cool-darkness-123456.us-east-2.aws.neon.tech/neondb?sslmode=require

jdbc:postgresql://ep-cool-darkness-123456.us-east-2.aws.neon.tech/neondb?user=neondb_owner&password=AbCdEf123456&sslmode=require&channelBinding=require
```

**URL 元件**
- `host`：`ep-[project-id].region.aws.neon.tech`（例：ep-cool-darkness-123456.us-east-2.aws.neon.tech）
- `port`：預設 5432（URL 中通常省略）
- `database`：預設 `neondb`
- SSL：**強制** `sslmode=require` 與 `channelBinding=require`

#### 載入 Schema

**方式一：網頁 SQL 編輯器**
- Neon 主控台 → SQL Editor → 貼上 DDL 語句 → Execute

**方式二：psql 客戶端**
```bash
# 連線到資料庫
psql "postgresql://[user]:[password]@[host]/[database]?sslmode=require"

# 或透過 Neon CLI
neon connect

# 執行 SQL 檔案
\i schema.sql
```

**方式三：應用初始化**
- Spring Boot：將 DDL 寫入 `schema.sql`，設置 `spring.sql.init.mode=always`
- Hibernate：設置 `hibernate.hbm2ddl.auto=create-drop`（開發用）或自訂初始化碼

#### 雷區與最佳實踐

| 雷區 | 狀況 | 對應方案 |
|------|------|--------|
| **SSL 強制** | Neon 強制 SSL，`sslmode=require` 不可少 | 所有連線字串務必包含 `?sslmode=require` |
| **無使用者名稱前綴** | Neon 不強制前綴（與某些提供商不同） | 使用真實使用者名稱（例：neondb_owner） |
| **FK 支援** | PostgreSQL 完全支援外鍵 | JPA `@ManyToOne` / Hibernate 無額外設定需求 |
| **Region 選擇** | 免費方案可選 region（建議選最近） | 建立專案時明確指定，避免預設遠端 region |
| **連線池限制** | 免費方案限 10,000 池化連線（足夠大多數應用） | 若應用使用 HikariCP，設置 `maximumPoolSize=10` 左右 |
| **閒置暫停** | 免費版不自動暫停（已取消此政策） | 無需擔憂——連線可持續保持 |

---

### 2. Supabase（PostgreSQL，含後端功能）

**現狀**（2026 年6月）：免費方案存在，但額度有限且包含暫停政策。

#### 免費方案額度
- **專案數**：2 個活躍專案
- **資料庫儲存**：500 MB
- **檔案儲存**：1 GB（Supabase Storage）
- **連線**：600 個直接連線，200 個連線池連線
- **流量**：5 GB 資料庫 egress + 5 GB 快取 egress
- **API 呼叫**：無限制
- **其他**：Edge Functions、Realtime、Auth

#### 暫停政策
- 免費專案在 **1 週無活動後自動暫停**（重啟即可恢復）
- 無備份、無 SLA、無 SSO

#### 連線字串

**標準格式**
```
postgresql://[user]:[password]@db.[project-id].supabase.co:5432/[database]?sslmode=require
```

**JDBC 格式**
```
jdbc:postgresql://db.[project-id].supabase.co:5432/[database]?user=[user]&password=[password]&sslmode=require
```

#### 雷區
- **暫停政策**：若無法接受 1 週閒置即暫停，不推薦（改用 Neon）
- **額度有限**：500 MB 儲存不適合資料量大的專案
- **2 專案限制**：無法同時執行多個開發分支

---

### 3. Railway（PostgreSQL 與 MySQL）

**現狀**（2026 年6月）：**不再有永久免費方案**。新用戶獲 $5 試用額度（30 天內過期）。

#### 付費方案
- **$5/月 Hobby 方案**：額度內 $5 使用費（超額按量計費）
- **$20/月 Pro 方案**：額度內 $20 使用費

#### 何時選用
- 若已有預算或已消費過試用額度
- 需要 MySQL（相對 PostgreSQL 較少選項）

#### 連線字串

**Railway 私網（同專案內部連線）**
```
postgresql://postgres:[password]@[service-name].railway.internal:5432/[database]
```

**公開訪問（需啟用 TCP Proxy）**
```
postgresql://[user]:[password]@[host]:[port]/[database]?sslmode=require
```

#### 載入 Schema

使用 Railway CLI：
```powershell
# 安裝 Railway CLI
npm install -g @railway/cli

# 登入
railway login

# 連線到資料庫
railway connect [SERVICE_NAME]

# 執行 SQL
\i schema.sql
```

---

### 4. Aiven（PostgreSQL 與 MySQL，企業級）

**現狀**：有限免費試用，適合需要高可用性的專案。

**特點**
- Terraform / Kubernetes 支援
- 受管服務（自動備份、監控）
- 無永久免費層（試用期後付費）

**使用場景**：非原型設計，不推薦此技能使用。

---

### 推薦決策樹

```
開發原型或側專案？
├─ 是 → 無預算，需長期免費？
│  └─ 是 → Neon（慷慨免費、無暫停）
│  └─ 否 → Supabase（功能豐富，但 1 週暫停 + 2 專案限制）
└─ 否 → 已預算或已消費試用額度？
   └─ 是 → Railway（$5/月，支援 MySQL）
   └─ 否 → Neon（再用免費方案）
```

---

## 本機開發與測試

### Docker Compose 快速啟動

**PostgreSQL**
```yaml
version: '3.8'
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: localuser
      POSTGRES_PASSWORD: localpass
      POSTGRES_DB: localdb
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
volumes:
  postgres_data:
```

**MySQL**
```yaml
version: '3.8'
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: localdb
      MYSQL_USER: localuser
      MYSQL_PASSWORD: localpass
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
volumes:
  mysql_data:
```

**連線字串**
```
# PostgreSQL
postgresql://localuser:localpass@localhost:5432/localdb

# MySQL
mysql://localuser:localpass@localhost:3306/localdb
```

### 本機 psql 與 mysql 用戶端

**PostgreSQL（psql）**
```bash
# 安裝（Windows via chocolatey）
choco install postgresql

# 連線
psql -h localhost -U localuser -d localdb

# 執行 SQL 檔案
psql -h localhost -U localuser -d localdb -f schema.sql
```

**MySQL（mysql）**
```bash
# 安裝（Windows via chocolatey）
choco install mysql

# 連線
mysql -h localhost -u localuser -p localdb
# 提示輸入密碼

# 執行 SQL 檔案
mysql -h localhost -u localuser -p localdb < schema.sql
```

---

## 程式碼對接路徑

### Spring Boot + Hibernate

**application.properties**
```properties
# Neon 雲端
spring.datasource.url=jdbc:postgresql://[host]/[db]?sslmode=require&channelBinding=require
spring.datasource.username=[user]
spring.datasource.password=[password]
spring.jpa.hibernate.ddl-auto=validate

# 本機 Docker
spring.datasource.url=jdbc:postgresql://localhost:5432/localdb
spring.datasource.username=localuser
spring.datasource.password=localpass
spring.jpa.hibernate.ddl-auto=create-drop
```

**pom.xml（PostgreSQL）**
```xml
<dependency>
    <groupId>org.postgresql</groupId>
    <artifactId>postgresql</artifactId>
    <version>42.7.3</version>
</dependency>
```

### Node.js + Sequelize / TypeORM

**PostgreSQL（Sequelize）**
```javascript
const sequelize = new Sequelize(
  process.env.DB_NAME,
  process.env.DB_USER,
  process.env.DB_PASSWORD,
  {
    host: process.env.DB_HOST,
    dialect: 'postgres',
    ssl: true,
    dialectOptions: {
      ssl: { rejectUnauthorized: false }
    }
  }
);
```

**.env 格式**
```
DB_HOST=ep-cool-darkness-123456.us-east-2.aws.neon.tech
DB_PORT=5432
DB_USER=neondb_owner
DB_PASSWORD=AbCdEf123456
DB_NAME=neondb
```

### Python + SQLAlchemy

```python
from sqlalchemy import create_engine

# Neon
engine = create_engine(
    f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}",
    echo=True
)

# 本機
engine = create_engine(
    "postgresql+psycopg2://localuser:localpass@localhost:5432/localdb"
)
```

---

## 常見連線錯誤排查

| 錯誤訊息 | 原因 | 解決方案 |
|--------|------|--------|
| `FATAL: no pg_hba.conf entry for host` | IP 未授權或 SSL 未啟用 | 確認 `sslmode=require`，檢查雲端資料庫防火牆規則 |
| `SSL connection error` | SSL 参數錯誤 | 檢查 `channelBinding=require`（Neon 強制）或移除 `sslmode=disable` |
| `password authentication failed` | 憑證錯誤 | 複製 URL 時留意特殊字符（@ $ % 等），使用 URL encoding |
| `connection timeout` | 無法連線到主機 | 檢查 host 名稱正確性、網路訪問權限、防火牆規則 |
| `too many connections` | 超過連線池限制 | 降低連線池大小（HikariCP：`maximumPoolSize=5` ）或升級方案 |

---

## 設定環境變數與加密

### Windows PowerShell

```powershell
# 設置環境變數（暫時）
$env:DATABASE_URL = "jdbc:postgresql://..."

# 設置環境變數（持久）
[Environment]::SetEnvironmentVariable("DATABASE_URL", "jdbc:postgresql://...", "User")
```

### Linux / macOS

```bash
# 暫時
export DATABASE_URL="postgresql://..."

# 持久（.bashrc 或 .zshrc）
echo 'export DATABASE_URL="postgresql://..."' >> ~/.bashrc
source ~/.bashrc
```

### .env 檔案（應用層）

```
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
DB_USER=localuser
DB_PASSWORD=localpass
```

### 敏感資訊最佳實踐

- **不提交密碼到版控**：使用 `.env.example` 搭配 `.gitignore`
- **本機 vs. 雲端分離**：應用啟動時根據環境載入不同設定（environment profiles）
- **密鑰管理**：生產環境用專業密鑰管理服務（AWS Secrets Manager、HashiCorp Vault）

---

## 驗證與初始化流程

### 步驟 1：驗證連線

**Java**
```java
String url = "jdbc:postgresql://[host]/[db]?sslmode=require";
String user = "[user]";
String password = "[password]";

try (Connection conn = DriverManager.getConnection(url, user, password)) {
    System.out.println("連線成功！");
} catch (SQLException e) {
    System.err.println("連線失敗: " + e.getMessage());
}
```

**psql**
```bash
psql "postgresql://[user]:[password]@[host]/[db]?sslmode=require"
\d  # 列出所有表
\q  # 離開
```

### 步驟 2：載入 Schema

```bash
# 本機檔案
psql "postgresql://[user]:[password]@[host]/[db]?sslmode=require" -f schema.sql

# 或貼入 SQL 編輯器（Neon 主控台或 pgAdmin）
```

### 步驟 3：驗證資料

```sql
-- 確認表已建立
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public';

-- 確認索引
SELECT indexname FROM pg_indexes 
WHERE schemaname = 'public';
```

---

## FAQ

### Q: 如何從一個資料庫切換到另一個（Neon → Railway 或反向）？

A: 
1. 從舊資料庫匯出 schema：`pg_dump -s [舊 URL] > schema.sql`
2. 驗證 schema 相容性（檢查 MySQL vs. PostgreSQL 差異）
3. 在新資料庫執行 schema：`psql [新 URL] -f schema.sql`
4. 更新應用連線字串與環境變數
5. 若需遷移資料：使用 ETL 工具（例：DBeaver、Airbyte）

### Q: 可以在多個環境（開發、測試、生產）共用同一個免費資料庫嗎？

A: 不推薦。建議每個環境獨立資料庫：
- **開發**：Neon 免費方案（或本機 Docker）
- **測試**：Neon 免費方案（另一專案）或本機
- **生產**：Railway / Supabase / Neon Pro（付費）

### Q: 如何在 CI/CD 中安全地注入連線字串？

A: 
1. 將敏感資訊存放在 CI 供應商的加密祕密（GitHub Actions Secrets、GitLab CI Variables）
2. 在 pipeline YAML 中引用：`DATABASE_URL: ${{ secrets.DATABASE_URL }}`
3. 確保 log 不輸出密碼（設置 `--mask-secrets`）

### Q: Neon 的 `sslmode=require` 與 `channelBinding=require` 差別？

A:
- `sslmode=require`：強制 SSL/TLS 加密連線，阻止中間人攻擊
- `channelBinding=require`：進一步綁定 TLS channel，防止憑證被竊用後的重放攻擊（Neon 強制）

兩者搭配為最高安全級別。

---

## 參考連結

### Neon
- 官網：https://neon.com
- 定價（含免費方案詳情）：https://neon.com/pricing
- 文檔：https://neon.com/docs/introduction/plans
- Java/JDBC 連線指南：https://neon.com/docs/guides/java
- 連線字串工具：https://neon.com/docs/reference/cli-connection-string

### Supabase
- 官網：https://supabase.com
- 定價：https://supabase.com/pricing
- PostgreSQL 連線：https://supabase.com/docs/guides/database/connecting-to-postgres

### Railway
- 官網：https://railway.com
- 定價：https://railway.com/pricing
- 資料庫文檔：https://docs.railway.com/databases/build-a-database-service
- CLI 文檔：https://docs.railway.com/cli/connect

### PostgreSQL JDBC
- pgJDBC 官方：https://jdbc.postgresql.org
- SSL 設定指南：https://jdbc.postgresql.org/documentation/ssl/

### MySQL JDBC
- MySQL Connector/J：https://dev.mysql.com/doc/connector-j/
- SSL 設定：https://razorsql.com/articles/mysql_ssl_jdbc.html

### 通用 JDBC
- JDBC URL 格式對照：https://www.baeldung.com/java-jdbc-url-format

---

## 本文檔版本與更新

- **版本**：1.0（2026 年6月）
- **來源驗證日期**：2026 年6月10日
- **涵蓋範圍**：Neon、Supabase、Railway、本機 Docker 開發
- **更新頻率**：每季度審視免費方案變動；若發現資訊過期，請提交更新請求
