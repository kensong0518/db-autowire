# db-autowire Skill Reference Guide

一個通用、可重複使用的 Claude Code skill，用於自動化資料庫配置。將本 skill 放入任何專案，就能自動：

1. **掃描程式碼** — 偵測 JPA entity、Hibernate 配置、資料模型定義
2. **產生 Schema** — 從 entity 類別產生 CREATE TABLE DDL
3. **初始化資料庫** — 對接真實資料庫（本機 MySQL、Docker、雲端）
4. **驗證連線** — 執行健康檢查、測試 SQL 連接

---

## 第一部分：快速開始

### 前置條件

- **IDE / CLI：** VS Code（搭配 Claude Code extension）或任何 shell
- **Java 專案：** Spring Boot / Quarkus / 任何 JPA 專案（資料模型在 `src/main/java/**/entity/` 或類似位置）
- **資料庫選項：**
  - 本機 MySQL（已安裝）
  - Docker Compose + MySQL（推薦）
  - TiDB Cloud Serverless（免費雲端，見下節）

### 基本工作流

```
1. 觸發 skill：/db-autowire --detect
   ↓ 偵測堆棧、找出 entity、掃描 JPA 註解
   
2. 生成 schema：/db-autowire --generate-schema
   ↓ entity → CREATE TABLE + CREATE INDEX + ALTER TABLE (FK)
   
3. 建立連線：/db-autowire --init-db
   ↓ 載入連線字串 → 執行 DDL → 驗證表格
   
4. 驗證：/db-autowire --health-check
   ↓ 連線測試 → 執行示例查詢 → 顯示結果
```

---

## 第二部分：免費雲端選項 — TiDB Cloud Serverless

### 概況（2026 年最新）

**服務名稱更新：**
自 2025 年 8 月 12 日起，「TiDB Cloud Serverless」改名為「TiDB Cloud Starter」。本文同時使用兩個名稱。

**免費方案狀態：存在且活躍**

| 項目 | 額度 |
|------|------|
| **行儲存（Row Storage）** | 5 GiB /月 |
| **列儲存（Columnar Storage）** | 5 GiB /月 |
| **Request Units (RU)** | 50 million /月 |
| **組織免費額度上限** | 25 GiB row + 25 GiB columnar + 250M RU /月 |
| **免費例項上限** | 5 個 /組織 |
| **費用** | 完全免費（無需信用卡） |

**超額政策：**
達到月度配額後，系統**立即拒絕新連線**，但現存連線會經歷**節流**（throttling）。月份重新開始時額度重置。

**連線穩定性：**
閒置連線可能被中介網路設備斷開。建議應用層實現**連線池重試邏輯**。

**外鍵支援：**
支援。TiDB 自 v6.6.0 起支援外鍵，v8.5.0 起正式發布（GA）。外鍵檢查可能造成效能影響——建議效能敏感場景下測試。

---

### 註冊與建立免費叢集

#### 步驟 1：建立帳戶

瀏覽 [TiDB Cloud 登入頁面](https://tidbcloud.com/onboarding/serverless)

選項：
- 電郵 + 密碼
- Google / GitHub / Microsoft 登入
- AWS / Azure / Google Cloud / Alibaba Cloud Marketplace 訂閱

#### 步驟 2：在主控台建立 Starter 叢集

1. 登入 TiDB Cloud 主控台
2. 點擊 **My TiDB** 頁籤
3. 點擊 **Create Resource** → 選擇 **Starter** plan
4. 設定：
   - **Cluster Name：** 任意名稱（如 `my-app-db`）
   - **Cloud Provider & Region：** 選擇距你最近的地區（如 `us-west-2` for AWS US West）
   - **Project：** 可選，用於分組
   - **Spending Limit：** 設定為 **$0**（確保免費）
5. 點擊 **Create**（約 30 秒建立完畢）

#### 步驟 3：設定密碼

叢集建立後，**必須**設定 SQL 使用者密碼才能連線。

1. 點擊剛建立的叢集名稱
2. 進入 **Connect** 分頁
3. 點擊 **Create Password** 並設定密碼
4. 記錄以下資訊（連線字串用）：
   - **Host：** 形如 `gateway01.us-west-2.prod.aws.tidbcloud.com`
   - **Port：** `4000`
   - **Default Database：** `test`
   - **Username：** `<你的使用者名稱>`（通常是註冊帳戶的電郵前綴或自訂名稱）
   - **Password：** 剛設定的密碼

---

### 連線字串格式

#### JDBC 連線字串（Java / Spring Boot）

```
jdbc:mysql://gateway01.us-west-2.prod.aws.tidbcloud.com:4000/test?useSsl=true
```

**設定詳解：**

| 參數 | 值 | 說明 |
|------|-----|------|
| `useSsl` | `true` | **必須**。TiDB Cloud Serverless 強制 SSL 連線 |
| `autoReconnect` | `true` | 連線中斷後自動重連（推薦） |
| `allowMultiQueries` | `true` | 允許批次 SQL 語句（選項） |
| `serverTimezone` | `UTC` | 時區設定（避免時間戳混亂） |

**完整 JDBC URL 範例（Spring Boot）：**

```properties
spring.datasource.url=jdbc:mysql://gateway01.us-west-2.prod.aws.tidbcloud.com:4000/test?useSsl=true&autoReconnect=true&serverTimezone=UTC
spring.datasource.username=<your_username>
spring.datasource.password=<your_password>
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver
```

#### 一般 URL 格式

```
mysql://gateway01.us-west-2.prod.aws.tidbcloud.com:4000/test
```

#### MySQL CLI 連線

```bash
mysql --comments --connect-timeout 150 \
  -u '<your_username>' \
  -h gateway01.us-west-2.prod.aws.tidbcloud.com \
  -P 4000 \
  -D test \
  --ssl-mode=VERIFY_IDENTITY \
  --ssl-ca=/path/to/ca.pem \
  -p<your_password>
```

**SSL 憑證：**
TiDB Cloud Serverless 使用 **Let's Encrypt ISRG Root X1** 簽署。多數現代 OS 已內建此憑證鏈，故通常無需指定 `--ssl-ca`。若遇 SSL 驗證錯誤，從 [Let's Encrypt](https://letsencrypt.org/certificates/) 下載根憑證。

---

### 透過 MySQL CLI 載入 Schema

#### 準備 SQL 檔案

建立 `schema.sql`：

```sql
CREATE DATABASE IF NOT EXISTS test;
USE test;

CREATE TABLE users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NOT NULL UNIQUE,
  username VARCHAR(100) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE posts (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  title VARCHAR(255) NOT NULL,
  content LONGTEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
```

#### 執行匯入

```bash
mysql --comments --connect-timeout 150 \
  -u '<your_username>' \
  -h gateway01.us-west-2.prod.aws.tidbcloud.com \
  -P 4000 \
  -D test \
  --ssl-mode=VERIFY_IDENTITY \
  -p<your_password> \
  < schema.sql
```

**預期輸出：** 無錯誤即表示成功。

#### 驗證匯入

```bash
mysql --comments --connect-timeout 150 \
  -u '<your_username>' \
  -h gateway01.us-west-2.prod.aws.tidbcloud.com \
  -P 4000 \
  -D test \
  --ssl-mode=VERIFY_IDENTITY \
  -p<your_password> \
  -e "SHOW TABLES; DESCRIBE users;"
```

---

### 使用 TiDB Cloud 網頁 SQL Editor

1. 進入叢集 → **SQL Editor**（左側導覽列）
2. 貼上 SQL 指令，點 **Run**
3. 支援完整 DDL / DML 操作
4. **成本提示：** 每次查詢都消耗 RU（但免費額度內足夠開發測試）

---

## 第三部分：本機選項

### 選項 A：本機 MySQL（已安裝）

**連線字串：**

```properties
spring.datasource.url=jdbc:mysql://localhost:3306/dev_db?useSSL=false&serverTimezone=UTC
spring.datasource.username=root
spring.datasource.password=your_password
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver
```

**建立資料庫：**

```bash
mysql -u root -p
> CREATE DATABASE dev_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> EXIT;
```

**載入 schema：**

```bash
mysql -u root -p dev_db < schema.sql
```

---

### 選項 B：Docker Compose + MySQL（推薦開發）

**docker-compose.yml：**

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: dev_mysql
    environment:
      MYSQL_ROOT_PASSWORD: rootpassword
      MYSQL_DATABASE: dev_db
      MYSQL_CHARSET: utf8mb4
      MYSQL_COLLATION: utf8mb4_unicode_ci
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mysql_data:
```

**啟動：**

```bash
docker-compose up -d
```

**連線字串：**

```properties
spring.datasource.url=jdbc:mysql://localhost:3306/dev_db?useSSL=false&serverTimezone=UTC
spring.datasource.username=root
spring.datasource.password=rootpassword
```

**驗證：**

```bash
docker exec dev_mysql mysql -u root -prootpassword dev_db -e "SHOW TABLES;"
```

---

## 第四部分：Skill 實現細節

### 組件架構

```
db-autowire/
├── detect.py           # 堆棧偵測 + entity 掃描
├── schema_generator.py # entity → DDL
├── db_client.py        # 連線管理 + SQL 執行
├── config.py           # 連線字串解析
└── README.md           # 本檔案
```

### Skill Manifest (skill.json)

```json
{
  "name": "db-autowire",
  "version": "1.0.0",
  "description": "Auto-detect project stack, generate DB schema from entities, initialize and connect cloud/local database",
  "args": {
    "type": "string",
    "enum": ["--detect", "--generate-schema", "--init-db", "--health-check", "--config"],
    "help": "Choose operation: detect stack | generate schema from entities | init DB | verify connection | edit config"
  },
  "capabilities": ["file_search", "file_read", "bash", "web_search"],
  "compatible_stacks": ["spring-boot", "quarkus", "hibernate", "jpa-generic"],
  "databases": ["mysql", "tidb-serverless", "mariadb"]
}
```

### detect.py 邏輯

```python
import os
import re

def detect_stack(root_path):
    """
    Scan for:
    - pom.xml → Maven + Spring Boot / Quarkus version
    - build.gradle → Gradle
    - src/main/java/**/entity/*.java → JPA @Entity classes
    - application.properties / application.yml → existing DB config
    """
    findings = {
        "build_tool": None,
        "framework": None,
        "jpa_entities": [],
        "existing_config": None,
        "db_type": "unknown"
    }
    
    # Check pom.xml
    if os.path.exists(f"{root_path}/pom.xml"):
        findings["build_tool"] = "maven"
        with open(f"{root_path}/pom.xml") as f:
            pom_text = f.read()
            if "spring-boot" in pom_text:
                findings["framework"] = "spring-boot"
            elif "quarkus" in pom_text:
                findings["framework"] = "quarkus"
    
    # Find entities
    entity_pattern = re.compile(r'@Entity\s+public\s+class\s+(\w+)')
    for root, dirs, files in os.walk(f"{root_path}/src/main/java"):
        for file in files:
            if file.endswith(".java"):
                fpath = os.path.join(root, file)
                with open(fpath) as f:
                    content = f.read()
                    if "@Entity" in content or "@Table" in content:
                        matches = entity_pattern.findall(content)
                        findings["jpa_entities"].extend(matches)
    
    return findings
```

### schema_generator.py 邏輯

```python
import re

def extract_entity_metadata(java_file_content):
    """
    從 Java entity 類別提取：
    - @Table(name = "...")
    - @Id / @GeneratedValue
    - @Column(name = "...", nullable = false, length = 100)
    - @OneToMany / @ManyToOne → 外鍵推導
    """
    metadata = {
        "class_name": None,
        "table_name": None,
        "columns": [],
        "primary_key": None,
        "indexes": [],
        "foreign_keys": []
    }
    
    # Extract @Table name
    table_match = re.search(r'@Table\(name\s*=\s*"(\w+)"\)', java_file_content)
    metadata["table_name"] = table_match.group(1) if table_match else "default_table"
    
    # Extract class name
    class_match = re.search(r'public\s+class\s+(\w+)', java_file_content)
    metadata["class_name"] = class_match.group(1) if class_match else None
    
    # Extract @Column definitions
    column_pattern = re.compile(
        r'@Column\((?:[^)]*?)name\s*=\s*"(\w+)".*?\)\s+(?:private|public)\s+(\w+)\s+(\w+)',
        re.MULTILINE | re.DOTALL
    )
    for col_name, col_type, field_name in column_pattern.findall(java_file_content):
        metadata["columns"].append({
            "name": col_name,
            "java_type": col_type,
            "field_name": field_name
        })
    
    return metadata

def entity_to_ddl(entity_metadata_list):
    """
    Convert entity metadata → CREATE TABLE DDL
    """
    ddl_statements = []
    
    for entity in entity_metadata_list:
        table_name = entity["table_name"]
        columns_sql = []
        
        for col in entity["columns"]:
            sql_type = java_to_sql_type(col["java_type"])
            col_def = f"`{col['name']}` {sql_type}"
            
            if col.get("is_pk"):
                col_def += " PRIMARY KEY AUTO_INCREMENT"
            elif col.get("not_null"):
                col_def += " NOT NULL"
            
            columns_sql.append(col_def)
        
        # Add timestamps
        columns_sql.append("`created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        columns_sql.append("`updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
        
        create_table = f"""CREATE TABLE `{table_name}` (
  {',\\n  '.join(columns_sql)}
);"""
        ddl_statements.append(create_table)
    
    return "\\n\\n".join(ddl_statements)

def java_to_sql_type(java_type):
    """Map Java types to SQL types"""
    type_map = {
        "Long": "BIGINT",
        "Integer": "INT",
        "String": "VARCHAR(255)",
        "Boolean": "BOOLEAN",
        "LocalDateTime": "TIMESTAMP",
        "Date": "DATETIME",
        "BigDecimal": "DECIMAL(19,2)",
        "UUID": "CHAR(36)"
    }
    return type_map.get(java_type, "VARCHAR(255)")
```

### db_client.py 邏輯

```python
import mysql.connector
from urllib.parse import urlparse

class DBClient:
    def __init__(self, connection_string, ssl_mode="VERIFY_IDENTITY"):
        """
        Parse JDBC or standard URL → 建立連線
        """
        self.conn = None
        self.ssl_mode = ssl_mode
        self.parse_and_connect(connection_string)
    
    def parse_and_connect(self, conn_str):
        """
        Handle:
        - jdbc:mysql://host:port/db?params
        - mysql://host:port/db
        """
        # Remove jdbc: prefix if present
        if conn_str.startswith("jdbc:"):
            conn_str = conn_str[5:]
        
        parsed = urlparse(conn_str)
        
        config = {
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "database": parsed.path.lstrip("/"),
            "user": parsed.username,
            "password": parsed.password,
            "use_pure": True,
            "autocommit": True
        }
        
        # TiDB Cloud requires SSL
        if "tidbcloud.com" in config["host"] or self.ssl_mode == "VERIFY_IDENTITY":
            config["ssl_verify_cert"] = True
            config["ssl_verify_identity"] = True
        
        self.conn = mysql.connector.connect(**config)
        return self.conn
    
    def execute_ddl(self, ddl_statements):
        """
        Execute DDL statements (CREATE TABLE, CREATE INDEX, etc.)
        """
        cursor = self.conn.cursor()
        for statement in ddl_statements.split(";"):
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                    print(f"✓ {statement[:50]}...")
                except Exception as e:
                    print(f"✗ Failed: {e}")
        cursor.close()
    
    def health_check(self):
        """
        Test connection + list tables
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT VERSION();")
        version = cursor.fetchone()[0]
        print(f"✓ Connected to {version}")
        
        cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"✓ Tables: {', '.join(tables) if tables else 'none'}")
        
        cursor.close()
```

---

## 第五部分：使用手冊

### 命令 1：偵測堆棧

```bash
claude-code /db-autowire --detect
```

**輸出範例：**

```
Build Tool: Maven
Framework: Spring Boot 3.1.5
JPA Entities Found: 4
  - User
  - Post
  - Comment
  - Tag
Existing DB Config: None detected
```

### 命令 2：生成 Schema

```bash
claude-code /db-autowire --generate-schema
```

**輸出範例：** 產生 `schema.sql` 檔案

```sql
CREATE TABLE `users` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `email` VARCHAR(255) NOT NULL UNIQUE,
  `username` VARCHAR(100) NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE `posts` (
  `id` BIGINT PRIMARY KEY AUTO_INCREMENT,
  `user_id` BIGINT NOT NULL,
  `title` VARCHAR(255) NOT NULL,
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
);

CREATE INDEX idx_posts_user_id ON posts(user_id);
```

### 命令 3：初始化資料庫

```bash
claude-code /db-autowire --init-db
```

**互動式提示：**

```
Choose DB option:
1. TiDB Cloud Serverless (free)
2. Local MySQL
3. Docker Compose

Selection: 1

TiDB Cloud Setup:
  Host: gateway01.us-west-2.prod.aws.tidbcloud.com
  Port: 4000
  Username: your_username
  Password: ••••••••
  Database: test
  
Connecting...
✓ Connected to TiDB 7.1.0
Executing schema...
✓ CREATE TABLE users...
✓ CREATE TABLE posts...
✓ CREATE INDEX idx_posts_user_id...
✓ Database initialized successfully
```

### 命令 4：健康檢查

```bash
claude-code /db-autowire --health-check
```

**輸出範例：**

```
Connection Status: ✓ Active
Database: test
Host: gateway01.us-west-2.prod.aws.tidbcloud.com:4000
Tables: 2 (users, posts)
Sample Query:
  SELECT COUNT(*) FROM users;
  Result: 0 rows

✓ All checks passed
```

---

## 第六部分：常見陷阱與解決

### 陷阱 1：TiDB Cloud 強制 SSL

**症狀：** `SSLException: SSL connection error`

**解決：**
- 確保 JDBC URL 含 `useSsl=true`
- 檢查防火牆允許 4000 埠
- 更新 MySQL 驅動至最新版本（≥ 8.0.33）

### 陷阱 2：連線超時（TiDB Cloud）

**症狀：** `Connection refused` 或 `timeout after 30s`

**原因：** 
- 叢集尚未完全建立（等待 30 秒後重試）
- 區域選擇不當（AWS 連線到 Azure 端點）

**解決：**
- 確認叢集狀態為 "Available"（在 My TiDB 檢查）
- 選擇離應用最近的區域

### 陷阱 3：超過月度 RU 配額

**症狀：** 連線建立後立即被拒，現存連線節流

**解決：**
- 等待月初重置
- 升級至 Dedicated Tier
- 優化查詢，減少 RU 消耗（避免全表掃描、加索引）

### 陷阱 4：外鍵刪除行為差異

**症狀：** `ON DELETE CASCADE` 在刪除時未生效

**原因：** TiDB 外鍵檢查可能有延遲（尤其在高併發）

**解決：**
- 應用層手動實現級聯刪除邏輯
- 或改用 `ON DELETE SET NULL` + 定期清理 orphan 行

### 陷阱 5：使用者名稱格式

**症狀：** `Access denied for user 'yourname'@'...'`

**原因：** TiDB Cloud 可能對使用者名稱加前綴（如 `4::<cluster_name>:<username>`）

**解決：**
- 從 TiDB Cloud 主控台的 **Connect** 分頁複製確切的使用者名稱
- 不要自行拼接

---

## 第七部分：進階配置

### 連線池設定（HikariCP）

```properties
spring.datasource.hikari.maximum-pool-size=10
spring.datasource.hikari.minimum-idle=2
spring.datasource.hikari.connection-timeout=30000
spring.datasource.hikari.idle-timeout=600000
spring.datasource.hikari.max-lifetime=1800000
```

### 批量匯入（大 schema 檔案）

若 schema.sql 超過 50 MB：

```bash
# 分割成多個檔案
split -l 1000 schema.sql schema_part_

# 逐個執行
for f in schema_part_*; do
  mysql ... < $f
  echo "Completed $f"
done
```

### 備份與還原

```bash
# 備份 TiDB Cloud
mysqldump --ssl-mode=VERIFY_IDENTITY \
  -u '<username>' \
  -h gateway01.us-west-2.prod.aws.tidbcloud.com \
  -p<password> \
  --all-databases > backup.sql

# 還原到本機 MySQL
mysql -u root -p < backup.sql
```

---

## 第八部分：支援的資料庫與版本

| 資料庫 | 版本 | SSL 必須 | 外鍵支援 | 連線池上限 |
|--------|------|---------|---------|----------|
| **TiDB Serverless** | 7.0+ | ✓ 必須 | ✓ (v6.6+) | 100 /叢集 |
| **MySQL** | 5.7+ | ✓ 推薦 | ✓ (8.0+) | 無限制 |
| **MariaDB** | 10.3+ | ✓ 推薦 | ✓ | 無限制 |

---

## 附錄 A：範例 Entity 類別

```java
package com.example.entity;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "users")
public class User {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(name = "email", nullable = false, unique = true, length = 255)
    private String email;
    
    @Column(name = "username", nullable = false, length = 100)
    private String username;
    
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
    
    @Column(name = "updated_at")
    private LocalDateTime updatedAt = LocalDateTime.now();
    
    @OneToMany(mappedBy = "user", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<Post> posts;
    
    // Getters & Setters...
}

@Entity
@Table(name = "posts")
public class Post {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private User user;
    
    @Column(name = "title", nullable = false, length = 255)
    private String title;
    
    @Column(name = "content", columnDefinition = "LONGTEXT")
    private String content;
    
    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt = LocalDateTime.now();
    
    // Getters & Setters...
}
```

---

## 附錄 B：相關檔案清單

| 檔案 | 用途 |
|------|------|
| `schema.sql` | 生成的 DDL 檔案 |
| `.env` 或 `.env.local` | 敏感連線字串（.gitignore） |
| `application.properties` 或 `application-{profile}.yml` | Spring 配置 |
| `docker-compose.yml` | 本機開發資料庫 |
| `db-autowire-config.json` | Skill 記憶（可選） |

---

## 參考文獻

- [TiDB Cloud Pricing & Tiers](https://www.pingcap.com/tidb-cloud-starter-pricing-details/)
- [TiDB Cloud Starter FAQs](https://docs.pingcap.com/tidbcloud/serverless-faqs/)
- [Connect to TiDB Serverless](https://docs.pingcap.com/tidbcloud/connect-to-tidb-cluster-serverless/)
- [Import Data via MySQL CLI](https://docs.pingcap.com/tidbcloud/import-with-mysql-cli-serverless/)
- [TiDB Foreign Key Constraints](https://docs.pingcap.com/tidb/stable/foreign-key/)
- [Spring Boot JDBC Configuration](https://docs.spring.io/spring-boot/docs/current/reference/html/application-properties.html)
