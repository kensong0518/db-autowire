# db-autowire 參考文件：TiDB Cloud Starter（免費層）

## 重要聲明

**PlanetScale 免費層已於 2024 年 4 月 8 日永久下線。** 本文檔改為推薦 **TiDB Cloud Starter** 作為替代方案，提供慷慨的免費額度且完全相容 MySQL。

---

## TiDB Cloud Starter 免費方案概覽

### 可用資源（免費層）

| 項目 | 額度 | 說明 |
|-----|-----|------|
| 行資料儲存空間 | 5 GiB | 超出則限制新連線 |
| 欄型儲存空間 | 5 GiB | 分析型 OLAP 儲存 |
| 月度請求單位（RUs） | 5,000 萬 | 資料庫操作計費單位 |
| 免費實例數 | 每組織 5 個 | 無需信用卡 |
| 並行連線數 | 400 | 設定花費限制後提升至 5,000 |
| TLS 版本 | 1.2, 1.3 | 強制 SSL/TLS |

### 成本模式

- 免費額度內：完全免費（無月費）
- 超出額度後：按量計費（儲存 $0.33/GiB/月，RU $0.00002 每單位）
- 可設定花費限制防止意外超費

---

## 快速開始

### 1. 註冊與建立免費資料庫

#### 步驟

1. 瀏覽 https://tidbcloud.com
2. 點擊「Sign Up」，使用 Google、GitHub 或電子郵件註冊
3. 通過電子郵件驗證
4. 在控制面板點擊「Create Cluster」
5. 選擇「Serverless（TiDB Cloud Starter）」方案
6. 設定叢集名稱（例如：`demo-cluster`）
7. 選擇地區（建議選擇靠近你的地區，例如 `ap-northeast-1` for Tokyo）
8. 點擊「Create」，等待 1-3 分鐘完成啟用

#### 取得初始登入憑證

- 系統自動產生 root 使用者
- 在叢集概覽頁面點擊「Connect」按鈕可取得密碼
- 保存密碼到安全位置（無法再次檢視）

---

### 2. 連線字串格式

#### 通用格式

```
mysql://<USERNAME>:<PASSWORD>@<HOST>:4000/<DATABASE>?ssl=true
```

#### 參數說明

| 參數 | 範例 | 說明 |
|-----|------|------|
| `<USERNAME>` | `xxx1234567.root` | 組織 ID 前綴 + `root`，用引號包裹 |
| `<PASSWORD>` | `abc123XyZ9!@#` | 叢集建立時產生的密碼 |
| `<HOST>` | `gateway01.ap-northeast-1.prod.aws.tidbcloud.com` | 叢集特定主機名 |
| `<DATABASE>` | `test` | 預設資料庫名稱 |

#### 取得特定連線資訊

1. 登入 TiDB Cloud 控制面板
2. 選擇你的叢集
3. 點擊「Connect」按鈕
4. 選擇「MySQL CLI」或你的程式語言
5. 系統自動生成已填入正確參數的連線字串

---

### 3. 連線字串示例

#### MySQL 命令列

```bash
mysql --ssl-mode=VERIFY_IDENTITY \
  -h gateway01.ap-northeast-1.prod.aws.tidbcloud.com \
  -P 4000 \
  -u "xxx1234567.root" \
  -p \
  test
```

#### JDBC（Java）

```
jdbc:mysql://gateway01.ap-northeast-1.prod.aws.tidbcloud.com:4000/test?useSSL=true&serverTimezone=UTC
```

連線程式碼：
```java
String url = "jdbc:mysql://gateway01.ap-northeast-1.prod.aws.tidbcloud.com:4000/test?useSSL=true";
String user = "xxx1234567.root";
String password = "your_password";

Connection conn = DriverManager.getConnection(url, user, password);
```

#### Python（mysqlclient）

```python
import MySQLdb

conn = MySQLdb.connect(
    host="gateway01.ap-northeast-1.prod.aws.tidbcloud.com",
    user="xxx1234567.root",
    passwd="your_password",
    db="test",
    port=4000,
    ssl_mode="VERIFY_IDENTITY",
    ssl={"ca": "ca.pem"}  # 可選，使用系統 CA 憑證
)
```

#### Node.js（mysql2）

```javascript
const mysql = require('mysql2/promise');

const connection = await mysql.createConnection({
  host: 'gateway01.ap-northeast-1.prod.aws.tidbcloud.com',
  port: 4000,
  user: 'xxx1234567.root',
  password: 'your_password',
  database: 'test',
  ssl: 'amazon'  // 或 true 使用系統 CA
});
```

#### Spring Boot（application.yml）

```yaml
spring:
  datasource:
    url: jdbc:mysql://gateway01.ap-northeast-1.prod.aws.tidbcloud.com:4000/test?useSSL=true&serverTimezone=UTC
    username: xxx1234567.root
    password: your_password
    driver-class-name: com.mysql.cj.jdbc.Driver
```

---

## 透過 Web 主控台載入 Schema

### 方法 1：使用 TiDB Cloud Web 主控台

1. 登入 https://tidbcloud.com
2. 選擇叢集，點擊「Console」標籤
3. 選擇目標分支（預設為 `main`）
4. 在左側邊欄點擊「Connect」
5. 主控台自動連線，輸入 SQL 語句：
   ```sql
   CREATE TABLE users (
     id INT PRIMARY KEY AUTO_INCREMENT,
     name VARCHAR(100) NOT NULL,
     email VARCHAR(100) UNIQUE,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```
6. 按 Ctrl+Enter 或點擊「Execute」執行
7. 執行結果顯示於下方

### 方法 2：使用 MySQL CLI 工具

#### 安裝 MySQL 客戶端

**Windows（PowerShell）：**
```powershell
# 使用 Scoop
scoop install mysql
```

**macOS：**
```bash
brew install mysql-client
```

**Linux（Debian/Ubuntu）：**
```bash
sudo apt-get install mysql-client
```

#### 執行 SQL 檔案

```bash
mysql --ssl-mode=VERIFY_IDENTITY \
  -h gateway01.ap-northeast-1.prod.aws.tidbcloud.com \
  -P 4000 \
  -u "xxx1234567.root" \
  -p < schema.sql
```

#### 互動式 Shell

```bash
mysql --ssl-mode=VERIFY_IDENTITY \
  -h gateway01.ap-northeast-1.prod.aws.tidbcloud.com \
  -P 4000 \
  -u "xxx1234567.root" \
  -p test
```

進入 MySQL 提示符後輸入 SQL，以 `;` 結尾，再按 Enter 執行。

---

## 重要事項與陷阱

### 1. 使用者名稱前綴（必須）

- TiDB Cloud Starter 要求使用者名稱格式：`<ORGANIZATION_ID>.root`
- 許多連線工具要求用**雙引號或反引號包裹**：`"xxx1234567.root"`
- 部分 JDBC 驅動需要轉義：`xxx1234567\.root`

### 2. 強制 SSL/TLS

- **所有連線必須使用 SSL/TLS**，不允許明文連線
- 支援 TLS 1.2 及 1.3
- 大多數驅動自動使用作業系統根憑證，無需手動提供 CA 檔案
- 若連線失敗：設定 `ssl_mode=VERIFY_IDENTITY` 或 `?useSSL=true`

### 3. 儲存空間限制

- 免費層限制行儲存為 5 GiB
- 超出限制時，資料庫會**拒絕新連線**直到儲存回到限制以下
- 定期檢查儲存使用量：TiDB Cloud 主控台 → 叢集 → Metrics

### 4. 月度 RU 額度

- 免費層提供 5,000 萬 RU/月
- RU 消耗取決於查詢複雜度與資料量
- 每月自動重置
- 可在主控台設定花費限制防止超費

### 5. 地區選擇

可用地區（依可用性而定）：
- `ap-northeast-1`（東京）
- `ap-southeast-1`（新加坡）
- `us-east-1`（美國東部）
- `eu-west-1`（歐洲西部）

選擇靠近你的應用的地區以降低延遲。

### 6. 並行連線

- 預設 400 個並行連線
- 若設定花費限制，提升至 5,000
- 應用應實現連線池（如 HikariCP、Druid）以最大化效率

### 7. 外鍵支援

TiDB 完全支援外鍵（自版本 6.6+ 起），語法與 MySQL 相同：
```sql
ALTER TABLE orders ADD CONSTRAINT fk_user_id 
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
```

### 8. 休眠政策

- TiDB Cloud Starter **無自動休眠政策**
- 只要在免費額度內，叢集保持活躍
- 若 30 天未使用可手動刪除以釋放空間

---

## 從程式碼模型自動產生 Schema

`db-autowire` skill 應包含工具來檢測 JPA/Hibernate 實體並生成對應的 CREATE TABLE 語句。

### JPA 實體範例

```java
@Entity
@Table(name = "users")
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private String name;
    
    @Column(unique = true)
    private String email;
    
    @CreationTimestamp
    private LocalDateTime createdAt;
}
```

### 自動生成的 DDL

```sql
CREATE TABLE users (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  email VARCHAR(255) UNIQUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 執行流程

1. 執行 `detect_stack.py` 或 `gen_schema.py` 掃描實體
2. 產生 `schema.sql`
3. 在 TiDB Cloud Web 主控台或 CLI 執行 SQL
4. 驗證表結構：`DESCRIBE users;`

---

## 連線故障排查

### 錯誤：「server does not allow insecure connections」

**原因：** 未啟用 SSL/TLS  
**解決方案：**
- 確保連線字串包含 `?useSSL=true` 或 `ssl=true`
- 檢查驅動版本是否支援 TLS 1.2/1.3

### 錯誤：「Access denied for user」

**原因：** 使用者名稱或密碼錯誤  
**解決方案：**
- 確認使用者名稱格式為 `"xxx1234567.root"`（含前綴）
- 在 TiDB Cloud 主控台重新取得或重設密碼
- 檢查複製貼上時是否遺漏特殊字元

### 錯誤：「Connection refused」

**原因：** 網路連線或主機名稱錯誤  
**解決方案：**
- 驗證主機名稱來自 TiDB Cloud 主控台（不要手動輸入）
- 確認本機網路能存取 AWS/雲端（檢查防火牆規則）
- 在 TiDB Cloud 主控台設定 IP 白名單（如需要）

### 錯誤：「Connection pool exhausted」

**原因：** 超過並行連線限制（400 預設值）  
**解決方案：**
- 在應用中實現連線池並設定適當的最大池大小（建議 10-50）
- 在 TiDB Cloud 設定花費限制以提升限制至 5,000
- 檢查應用是否正確關閉連線

### 測試連線

```bash
# 使用 MySQL CLI 測試
mysql --ssl-mode=VERIFY_IDENTITY \
  -h gateway01.ap-northeast-1.prod.aws.tidbcloud.com \
  -P 4000 \
  -u "xxx1234567.root" \
  -e "SELECT 1;" test

# 若成功會輸出：
# +---+
# | 1 |
# +---+
# | 1 |
# +---+
```

---

## 環境變數設定（適用於 db-autowire）

建議在 `.env` 檔案中設定連線參數：

```bash
DB_HOST=gateway01.ap-northeast-1.prod.aws.tidbcloud.com
DB_PORT=4000
DB_USER=xxx1234567.root
DB_PASSWORD=your_secure_password
DB_NAME=test
DB_SSL=true
DB_SSL_MODE=VERIFY_IDENTITY
```

應用程式讀取這些變數以初始化資料庫連線池。

---

## 下一步：整合至 db-autowire Skill

1. 檢測專案堆疊（JPA/Hibernate、Spring Boot）
2. 掃描實體類別產生 DDL
3. 提示使用者建立 TiDB Cloud Starter 帳戶
4. 協助使用者取得連線字串
5. 自動在 Web 主控台或 CLI 執行 Schema
6. 驗證連線並列出建立的表

---

## 參考資源

- [TiDB Cloud 官方文件](https://docs.pingcap.com/tidbcloud/)
- [TiDB Cloud Starter 定價與限制](https://docs.pingcap.com/tidbcloud/select-cluster-tier/)
- [TiDB Cloud 安全連線](https://docs.pingcap.com/tidbcloud/secure-connections-to-serverless-clusters/)
- [TiDB Cloud 快速開始](https://tidbcloud.com/)
