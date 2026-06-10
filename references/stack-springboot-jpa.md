# db-autowire Skill 參考文件

## 概述

**db-autowire** 是一套通用、可重複使用的 Claude Code skill，用於 Spring Boot + JPA/Hibernate 專案。一鍵即可：

1. **自動偵測** 專案是否使用 Spring Data JPA
2. **產生 SQL Schema** 從 @Entity 註解（支援多層級策略，從版本化遷移到動態建表）
3. **對接真實資料庫** 透過環境變數注入連線參數
4. **驗證映射** 確認 @Entity 與資料庫 schema 同步

本文件涵蓋技術棧、自動偵測、Schema 產生、連線設定、常見陷阱及解方。

---

## 一、技術棧偵測

### 1.1 必要依賴偵測

#### 檔案位置

- **Maven**: `pom.xml`
- **Gradle**: `build.gradle` 或 `build.gradle.kts`
- **原始碼 @Entity**: `src/main/java/**/*Entity.java` 或 `src/main/java/**/*.java`（搜尋 `@Entity` 註解）

#### 核心簽名

Maven `pom.xml` 中須包含：
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
```

Gradle `build.gradle` 中須包含：
```gradle
implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
```

#### 自動偵測邏輯

```bash
# Maven 專案
if [ -f "pom.xml" ]; then
    grep -q "spring-boot-starter-data-jpa" pom.xml && echo "JPA detected"
fi

# Gradle 專案
if [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
    grep -q "spring-boot-starter-data-jpa" build.gradle* && echo "JPA detected"
fi

# 搜尋 @Entity 註解
find src -name "*.java" -exec grep -l "@Entity" {} \;
```

### 1.2 可選但常見的相依

- **Flyway**: `org.flywaydb:flyway-core` → 版本化 migration
- **Liquibase**: `org.liquibase:liquibase-core` → 另一種 migration 工具
- **MySQL 驅動**: `mysql:mysql-connector-java` 或 `com.mysql:mysql-connector-j`
- **PostgreSQL 驅動**: `org.postgresql:postgresql`
- **H2 (開發/測試)**: `com.h2database:h2`

---

## 二、Schema 產生策略（按優先級排序）

Skill 應依下列優先順序選擇策略：

### 策略 1：Flyway 版本化遷移（推薦於生產環境）

**偵測方式**：
```bash
grep -q "flyway-core" pom.xml || grep -q "flyway-core" build.gradle*
```

**流程**：
1. 掃描 `src/main/resources/db/migration/` 下現有的 migration 檔案
2. 使用 Flyway 的 `validate` 或 `info` 指令檢查狀態
3. 若無現有 migration，用 `gen_schema_jpa.py` 產生初始 V001__Initial_schema.sql
4. 複製到 `src/main/resources/db/migration/` 目錄
5. Spring Boot 啟動時會自動執行

**application.yml 設定**：
```yaml
spring:
  flyway:
    enabled: true
    baselineOnMigrate: true
    locations: classpath:db/migration
```

**示例 migration 檔案名**：
```
V001__Initial_schema.sql
V002__Add_user_index.sql
V003__Create_audit_table.sql
```

命名規則：`V<版本>__<描述>.sql`（雙底線分隔符）

### 策略 2：Liquibase 版本化遺移

**偵測方式**：
```bash
grep -q "liquibase-core" pom.xml || grep -q "liquibase-core" build.gradle*
```

**流程**：
1. 掃描 `src/main/resources/db/changelog/` 下現有 changelog
2. 使用 `gen_schema_jpa.py --format=liquibase` 產生 XML/YAML changelog
3. 複製到指定目錄，Spring Boot 自動執行

**application.yml 設定**：
```yaml
spring:
  liquibase:
    enabled: true
    changeLog: classpath:db/changelog/db.changelog-master.xml
```

### 策略 3：Hibernate ddl-auto（開發/測試場景）

**偵測方式**：
- 檢查 `application.yml` 或 `application.properties` 中 `hibernate.ddl-auto` 設定
- 或檢查 pom.xml 中是否 **缺少** Flyway/Liquibase

**流程**：
1. 設定環境變數或 `application.yml`：
   ```yaml
   spring:
     jpa:
       hibernate:
         ddl-auto: update  # 或 create, create-drop, validate
   ```
2. Spring Boot 啟動時 Hibernate 自動執行

**模式說明**：
- `validate`: 只驗證，不修改（生產推薦）
- `update`: 新增欄位/表，但不刪除（開發可用）
- `create`: 每次啟動前刪除再建立（測試用）
- `create-drop`: 應用關閉時刪除（測試用）

**注意**：此模式不建立索引、外鍵約束等，僅基於 @Entity。

### 策略 4：Hibernate SchemaExport 匯出 DDL

**流程**（用於已有 migration 但需驗證或匯出的場景）：
```bash
# 使用 Hibernate 的 SchemaExport 工具
mvn exec:java -Dexec.mainClass="org.hibernate.tool.hbm2ddl.SchemaExport" \
  -Dexec.args="--out schema.sql --properties=src/main/resources/hibernate.properties"
```

或在 Spring Boot 啟動類中呼叫：
```java
SchemaExport schemaExport = new SchemaExport();
schemaExport.createOnly(EnumSet.of(TargetType.SCRIPT), metadata);
```

### 策略 5：通用 JPA 註解解析（無 Migration 工具時）

**偵測方式**：
- 確認無 Flyway/Liquibase
- 有 `@Entity` 類定義

**Skill 附帶工具**：`gen_schema_jpa.py`

**使用方式**：
```bash
python3 gen_schema_jpa.py \
  --entities src/main/java \
  --dialect=mysql \
  --out schema.sql
```

**支援的 Dialect**：mysql, postgres, h2, oracle, sqlserver

**功能**：
- 遞迴掃描 `src/main/java` 下所有 `.java` 檔案
- 解析 `@Entity`, `@Table`, `@Column`, `@Id`, `@GeneratedValue`, `@ManyToOne`, `@OneToMany`, `@JoinColumn`, `@Index`, `@UniqueConstraint`
- 產生對應資料庫的標準 DDL

---

## 三、連線設定

### 3.1 環境變數（推薦用於自動化）

Spring Boot 使用 **relaxed binding**，支援多種環境變數格式。優先級順序：

1. `application.yml`/`application.properties`（highest）
2. 環境變數（`SPRING_DATASOURCE_*` 或 `spring.datasource.*` 的環境變數形式）
3. 預設值

#### 標準環境變數

```bash
# MySQL
export SPRING_DATASOURCE_URL="jdbc:mysql://localhost:3306/mydb?useSSL=false&serverTimezone=UTC"
export SPRING_DATASOURCE_USERNAME="root"
export SPRING_DATASOURCE_PASSWORD="password"
export SPRING_DATASOURCE_DRIVER_CLASS_NAME="com.mysql.cj.jdbc.Driver"

# PostgreSQL
export SPRING_DATASOURCE_URL="jdbc:postgresql://localhost:5432/mydb"
export SPRING_DATASOURCE_USERNAME="postgres"
export SPRING_DATASOURCE_PASSWORD="password"
export SPRING_DATASOURCE_DRIVER_CLASS_NAME="org.postgresql.Driver"

# H2 (in-memory, 開發用)
export SPRING_DATASOURCE_URL="jdbc:h2:mem:testdb"
export SPRING_DATASOURCE_USERNAME="sa"
export SPRING_DATASOURCE_PASSWORD=""
export SPRING_DATASOURCE_DRIVER_CLASS_NAME="org.h2.Driver"
```

#### application.yml 範例

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb?useSSL=false&serverTimezone=UTC
    username: root
    password: password
    driver-class-name: com.mysql.cj.jdbc.Driver
  jpa:
    hibernate:
      ddl-auto: update
    properties:
      hibernate:
        dialect: org.hibernate.dialect.MySQL8Dialect
        format_sql: true
        use_sql_comments: true
```

### 3.2 方言 (Dialect) 對應

| 資料庫 | Dialect 類別 | JDBC URL 前綴 |
|--------|------------|------------|
| MySQL 5.7 | `org.hibernate.dialect.MySQL5Dialect` | `jdbc:mysql://` |
| MySQL 8.0+ | `org.hibernate.dialect.MySQL8Dialect` | `jdbc:mysql://` |
| PostgreSQL | `org.hibernate.dialect.PostgreSQLDialect` | `jdbc:postgresql://` |
| PostgreSQL 10+ | `org.hibernate.dialect.PostgreSQL10Dialect` | `jdbc:postgresql://` |
| Oracle | `org.hibernate.dialect.Oracle12cDialect` | `jdbc:oracle:thin:` |
| SQL Server | `org.hibernate.dialect.SQLServer2012Dialect` | `jdbc:sqlserver://` |
| H2 | `org.hibernate.dialect.H2Dialect` | `jdbc:h2:` |

**自動偵測邏輯**：
```bash
# 從 pom.xml 偵測驅動
if grep -q "mysql-connector-j" pom.xml; then
    DIALECT="org.hibernate.dialect.MySQL8Dialect"
elif grep -q "postgresql" pom.xml; then
    DIALECT="org.hibernate.dialect.PostgreSQLDialect"
fi
```

### 3.3 URL 參數常見設定

#### MySQL
```
jdbc:mysql://host:3306/dbname?useSSL=false&serverTimezone=UTC&allowPublicKeyRetrieval=true
```

#### PostgreSQL
```
jdbc:postgresql://host:5432/dbname
```

#### 連線池設定
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 10
      minimum-idle: 5
      connection-timeout: 30000
      idle-timeout: 600000
      max-lifetime: 1800000
```

---

## 四、@Entity 註解與 Schema 對應

### 4.1 基礎欄位對應

```java
@Entity
@Table(name = "users")
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "username", nullable = false, unique = true, length = 50)
    private String username;

    @Column(name = "email", nullable = false, length = 100)
    private String email;

    @Column(name = "created_at", nullable = false, columnDefinition = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    @CreationTimestamp
    private LocalDateTime createdAt;

    @Column(name = "is_active", nullable = false, columnDefinition = "BOOLEAN DEFAULT true")
    private Boolean isActive;

    @Column(name = "bio", columnDefinition = "TEXT")
    private String bio;
}
```

**產生的 DDL (MySQL 8)**：
```sql
CREATE TABLE users (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    bio LONGTEXT
);
```

### 4.2 關係對應

#### @ManyToOne 與 @JoinColumn

```java
@Entity
@Table(name = "posts")
public class Post {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false, foreignKey = @ForeignKey(name = "fk_posts_user"))
    private User author;

    @Column(name = "title", nullable = false)
    private String title;
}
```

**產生的 DDL**：
```sql
CREATE TABLE posts (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

#### @OneToMany

```java
@Entity
@Table(name = "users")
public class User {
    // ... 其他欄位 ...

    @OneToMany(mappedBy = "author", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Post> posts = new ArrayList<>();
}
```

**產生的 DDL**：不產生額外 FK，FK 由 @JoinColumn (在 Post 端) 定義。

#### @ManyToMany

```java
@Entity
@Table(name = "users")
public class User {
    // ...

    @ManyToMany
    @JoinTable(
        name = "user_roles",
        joinColumns = @JoinColumn(name = "user_id"),
        inverseJoinColumns = @JoinColumn(name = "role_id"),
        foreignKey = @ForeignKey(name = "fk_user_roles_user"),
        inverseForeignKey = @ForeignKey(name = "fk_user_roles_role")
    )
    private Set<Role> roles = new HashSet<>();
}
```

**產生的 DDL**：
```sql
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL,
    role_id BIGINT NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);
```

### 4.3 索引與唯一約束

```java
@Entity
@Table(
    name = "products",
    indexes = {
        @Index(name = "idx_sku", columnList = "sku"),
        @Index(name = "idx_category_price", columnList = "category,price"),
        @Index(name = "idx_created_at", columnList = "created_at")
    },
    uniqueConstraints = {
        @UniqueConstraint(name = "uk_sku", columnNames = "sku")
    }
)
public class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "sku", nullable = false, unique = true)
    private String sku;

    @Column(name = "category", nullable = false)
    private String category;

    @Column(name = "price", nullable = false)
    private BigDecimal price;

    @Column(name = "created_at", nullable = false, updatable = false)
    @CreationTimestamp
    private LocalDateTime createdAt;
}
```

**產生的 DDL**：
```sql
CREATE TABLE products (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(255) NOT NULL,
    price DECIMAL(19,2) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE UNIQUE INDEX uk_sku ON products(sku);
CREATE INDEX idx_sku ON products(sku);
CREATE INDEX idx_category_price ON products(category, price);
CREATE INDEX idx_created_at ON products(created_at);
```

---

## 五、gen_schema_jpa.py 工具

### 5.1 用途與安裝

**gen_schema_jpa.py** 是 Skill 內建的 Python 工具，用於解析 Spring Data JPA 的 @Entity 註解並產生 SQL DDL，適合在無 Flyway/Liquibase 的場景使用。

**依賴**：
```bash
pip3 install javalang pyyaml
```

### 5.2 使用方法

```bash
# 基礎用法（預設 MySQL）
python3 gen_schema_jpa.py --entities src/main/java --out schema.sql

# 指定資料庫方言
python3 gen_schema_jpa.py \
  --entities src/main/java \
  --dialect=postgres \
  --out schema.sql

# 產生 Liquibase changelog (XML)
python3 gen_schema_jpa.py \
  --entities src/main/java \
  --format=liquibase \
  --dialect=mysql \
  --out db/changelog/db.changelog-001.xml

# 強制重新掃描（忽略快取）
python3 gen_schema_jpa.py \
  --entities src/main/java \
  --dialect=h2 \
  --no-cache

# 詳細日誌
python3 gen_schema_jpa.py \
  --entities src/main/java \
  --verbose
```

### 5.3 輸出格式

**SQL (預設)**：
```sql
-- Generated from JPA entities
-- dialect: mysql
-- timestamp: 2025-06-10T10:30:00

CREATE TABLE users (
    id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- ... 其他表格定義 ...
```

**Liquibase XML**：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<databaseChangeLog
    xmlns="http://www.liquibase.org/xml/ns/dbchangelog"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://www.liquibase.org/xml/ns/dbchangelog
    http://www.liquibase.org/xml/ns/dbchangelog/dbchangelog-4.1.xsd">

    <changeSet id="001-initial-schema" author="db-autowire">
        <createTable tableName="users">
            <column name="id" type="BIGINT" autoIncrement="true">
                <constraints primaryKey="true" primaryKeyName="pk_users"/>
            </column>
            <column name="username" type="VARCHAR(50)">
                <constraints nullable="false" unique="true"/>
            </column>
            <!-- ... -->
        </createTable>
    </changeSet>
</databaseChangeLog>
```

### 5.4 支援的 JPA 註解

| 註解 | 功能 |
|------|------|
| `@Entity` | 標記為實體類 |
| `@Table(name, schema, indexes, uniqueConstraints)` | 表名、索引、唯一約束 |
| `@Column(name, nullable, unique, length, columnDefinition, updatable, insertable)` | 欄位對應 |
| `@Id` | 主鍵 |
| `@GeneratedValue(strategy, generator)` | 自增策略 (IDENTITY/SEQUENCE/TABLE/UUID) |
| `@ManyToOne` | 多對一關係 |
| `@OneToMany(mappedBy)` | 一對多關係 |
| `@ManyToMany` | 多對多關係 |
| `@JoinColumn(name, nullable, foreignKey)` | 外鍵欄位 |
| `@JoinTable(name, joinColumns, inverseJoinColumns, foreignKey)` | 關聯表 (多對多) |
| `@Index(name, columnList, unique)` | 索引 |
| `@UniqueConstraint(name, columnNames)` | 唯一約束 |
| `@Temporal(TemporalType.TIMESTAMP)` | 日期時間型別提示 |
| `@CreationTimestamp` / `@UpdateTimestamp` | 自動時間戳（JPA 擴展） |

---

## 六、常見陷阱與解方

### 6.1 ddl-auto 不建立索引和外鍵約束

**問題**：
- `hibernate.ddl-auto=update` 只產生基礎表和欄位
- 不會自動建立 `@Index` 定義的索引
- 可能不完整地建立外鍵（取決於方言）

**解方**：
1. 使用 Flyway/Liquibase（推薦）
2. 使用 `gen_schema_jpa.py` 產生完整 DDL，手動執行
3. 在 `application.yml` 中設定 `spring.jpa.properties.hibernate.hbm2ddl.create_namespaces` 和額外 SQL

### 6.2 MySQL vs PostgreSQL Dialect 差異

**常見陷阱**：
- MySQL 預設不支援外鍵約束（MyISAM 引擎），需要使用 InnoDB
- PostgreSQL 的序列與 MySQL 的 AUTO_INCREMENT 行為不同
- `columnDefinition="TIMESTAMP DEFAULT CURRENT_TIMESTAMP"` 在 PostgreSQL 應為 `CURRENT_TIMESTAMP` (無引號)

**解方**：
```yaml
spring:
  jpa:
    properties:
      hibernate:
        dialect: org.hibernate.dialect.MySQL8Dialect
        # 若使用 MySQL 5.7，改為 MySQL5Dialect
        # 若使用 PostgreSQL，改為 PostgreSQLDialect
```

**MySQL InnoDB 設定**：
```java
@Entity
@Table(name = "users")
public class User {
    // 確保 application.yml 包含
}
```

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/mydb?useSSL=false&serverTimezone=UTC
  jpa:
    properties:
      hibernate:
        dialect: org.hibernate.dialect.MySQL8Dialect
        # 明確指定存儲引擎（某些版本 Hibernate 需要）
        storage_engine: innodb
```

### 6.3 時間戳欄位的型別選擇

**問題**：
- `java.util.Date` vs `java.time.LocalDateTime`
- MySQL TIMESTAMP vs DATETIME
- PostgreSQL TIMESTAMP vs TIMESTAMPTZ (含時區)

**最佳實踐**：
```java
// 推薦用法（Java 8+）
@Column(name = "created_at", nullable = false, updatable = false)
@CreationTimestamp
private LocalDateTime createdAt;

@Column(name = "updated_at", nullable = false)
@UpdateTimestamp
private LocalDateTime updatedAt;
```

**產生的 DDL**：
```sql
-- MySQL
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP NOT NULL

-- PostgreSQL
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
```

### 6.4 連線字串編碼與字符集

**問題**：
- MySQL 預設字符集為 `latin1`，不支援 emoji
- 需要明確指定 `utf8mb4` 與排序規則

**解方**：
```
jdbc:mysql://localhost:3306/mydb?useSSL=false&serverTimezone=UTC&characterEncoding=utf8mb4&allowMultiQueries=true
```

並確保資料庫與表已用 utf8mb4 建立：
```sql
CREATE DATABASE mydb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 6.5 延遲加載 (Lazy Loading) 與 N+1 查詢

**問題**：
```java
@ManyToOne(fetch = FetchType.LAZY) // 預設已是 LAZY
@JoinColumn(name = "user_id")
private User author;
```

在序列化或交易外存取會拋 `LazyInitializationException`

**解方**：
1. 使用 `@Transactional` 確保會話開啟
2. 使用 `@EntityGraph` 明確載入
3. 使用 DTO 投影 (推薦)

```java
@Transactional(readOnly = true)
public Post getPost(Long id) {
    return postRepository.findById(id).orElse(null);
}

// 或使用 @EntityGraph
@Repository
public interface PostRepository extends JpaRepository<Post, Long> {
    @EntityGraph(attributePaths = {"author"})
    Optional<Post> findById(Long id);
}

// 或 DTO 投影
public interface PostDTO {
    Long getId();
    String getTitle();
    String getAuthorUsername();
}
```

### 6.6 Cascade 刪除風險

**問題**：
```java
@OneToMany(mappedBy = "author", cascade = CascadeType.ALL, orphanRemoval = true)
private List<Post> posts = new ArrayList<>();
```

刪除 User 時會自動刪除所有 Post（可能非預期）

**解方**：
- 明確指定需要的 cascade 類型
- 應用層面控制刪除邏輯
- 使用軟刪除 (soft delete) 而非物理刪除

```java
@OneToMany(mappedBy = "author", cascade = CascadeType.PERSIST) // 只 persist，不 delete
private List<Post> posts = new ArrayList<>();
```

---

## 七、Skill 工作流程

### 7.1 初始化流程

1. **偵測專案類型**
   - 檢查 `pom.xml` 或 `build.gradle` 中是否有 `spring-boot-starter-data-jpa`
   - 搜尋 `src/main/java` 中的 `@Entity` 類

2. **確定 Schema 產生策略**
   ```bash
   if [ -f "pom.xml" ] && grep -q "flyway-core" pom.xml; then
       STRATEGY="flyway"
   elif [ -f "build.gradle" ] && grep -q "liquibase-core" build.gradle; then
       STRATEGY="liquibase"
   else
       STRATEGY="gen_schema_jpa"
   fi
   ```

3. **收集 @Entity 類資訊**
   - 檔案路徑
   - 欄位與註解
   - 關係定義

4. **偵測資料庫方言**
   - 從 pom.xml/build.gradle 的驅動依賴推斷
   - 檢查 application.yml 中的 `hibernate.dialect`

5. **產生 Schema**
   - 呼叫對應工具（Flyway 遷移、gen_schema_jpa.py、或 ddl-auto 配置）
   - 驗證 DDL 語法

### 7.2 連線與驗證流程

1. **環境變數注入**
   ```bash
   export SPRING_DATASOURCE_URL="..."
   export SPRING_DATASOURCE_USERNAME="..."
   export SPRING_DATASOURCE_PASSWORD="..."
   ```

2. **啟動 Spring Boot 應用**
   ```bash
   mvn spring-boot:run
   # 或
   gradle bootRun
   ```

3. **驗證 Schema 同步**
   - Hibernate 自動驗證 @Entity 與資料庫一致性
   - 若 `ddl-auto=validate` 會在啟動時檢查，不符合則拋錯

4. **測試連線**
   ```bash
   # 執行簡單查詢驗證
   curl http://localhost:8080/api/users  # (假設有此端點)
   ```

---

## 八、應用範例

### 8.1 完整的使用情景

```bash
#!/bin/bash
set -e

# 1. 偵測專案
PROJECT_ROOT=$(pwd)
if [ ! -f "pom.xml" ] && [ ! -f "build.gradle" ]; then
    echo "Error: Not a Maven or Gradle project"
    exit 1
fi

# 2. 確認有 Spring Data JPA
if ! grep -q "spring-boot-starter-data-jpa" pom.xml build.gradle* 2>/dev/null; then
    echo "Error: Spring Data JPA not found"
    exit 1
fi

# 3. 偵測策略
if grep -q "flyway-core" pom.xml 2>/dev/null; then
    echo "Using Flyway strategy"
    MIGRATION_DIR="src/main/resources/db/migration"
    mkdir -p "$MIGRATION_DIR"
    
    # 生成遷移
    python3 gen_schema_jpa.py \
      --entities src/main/java \
      --dialect=$(detect_dialect) \
      --format=flyway \
      --out "${MIGRATION_DIR}/V001__Initial_schema.sql"
    
    echo "Migration created at ${MIGRATION_DIR}/V001__Initial_schema.sql"
else
    echo "Using gen_schema_jpa strategy"
    python3 gen_schema_jpa.py \
      --entities src/main/java \
      --dialect=$(detect_dialect) \
      --out schema.sql
    
    # 手動執行 DDL (需要資料庫連線)
    mysql -h "$DB_HOST" -u "$DB_USER" -p"$DB_PASS" "$DB_NAME" < schema.sql
fi

# 4. 設定環境變數
export SPRING_DATASOURCE_URL="jdbc:mysql://localhost:3306/mydb?useSSL=false&serverTimezone=UTC"
export SPRING_DATASOURCE_USERNAME="root"
export SPRING_DATASOURCE_PASSWORD="password"

# 5. 啟動應用
mvn spring-boot:run

# 應用會自動驗證 schema
```

### 8.2 Docker Compose 本地開發

```yaml
version: '3.8'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: password
      MYSQL_DATABASE: mydb
      MYSQL_CHARACTER_SET_SERVER: utf8mb4
      MYSQL_COLLATION_SERVER: utf8mb4_unicode_ci
    ports:
      - "3306:3306"
    volumes:
      - mysql-data:/var/lib/mysql

  app:
    build: .
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/mydb?useSSL=false&allowPublicKeyRetrieval=true
      SPRING_DATASOURCE_USERNAME: root
      SPRING_DATASOURCE_PASSWORD: password
      SPRING_JPA_HIBERNATE_DDL_AUTO: update
    ports:
      - "8080:8080"
    depends_on:
      - mysql

volumes:
  mysql-data:
```

---

## 九、Skill 檢查清單

使用 db-autowire 時應驗證的項目：

- [ ] 專案包含 `spring-boot-starter-data-jpa`
- [ ] 至少有一個 `@Entity` 類定義
- [ ] `pom.xml` 或 `build.gradle` 有資料庫驅動依賴
- [ ] `application.yml` 或環境變數設定了資料庫連線
- [ ] 若使用 Flyway，`src/main/resources/db/migration/` 目錄存在
- [ ] 若使用 Hibernate ddl-auto，已設定 `spring.jpa.hibernate.ddl-auto` 值
- [ ] Hibernate dialect 與實際資料庫相符
- [ ] 驗證所有 @Entity 的 @JoinColumn 都有 foreignKey 名稱（避免自動命名問題）
- [ ] 驗證時間戳欄位使用 `java.time.*` 而非過時的 `java.util.Date`
- [ ] MySQL 字符集設定為 utf8mb4 (如需 emoji 支援)
- [ ] 執行應用後無 Hibernate 驗證錯誤或欄位不匹配警告

---

## 十、參考資料

- **Spring Boot Data JPA 官方文件**: https://spring.io/projects/spring-data-jpa
- **Hibernate 官方文件**: https://hibernate.org/orm/
- **Flyway 文件**: https://flywaydb.org/documentation/
- **Liquibase 文件**: https://docs.liquibase.com/
- **Spring Boot 配置屬性**: https://docs.spring.io/spring-boot/docs/current/reference/html/application-properties.html
- **JPA 規範**: https://jakarta.ee/specifications/persistence/

---

## 附錄：gen_schema_jpa.py 簽名

```python
#!/usr/bin/env python3
"""
JPA Entity to SQL DDL Generator

Usage:
    gen_schema_jpa.py --entities <path> [--dialect=<dialect>] [--out <file>] [--format=<format>]

Options:
    --entities       Source directory containing @Entity classes (required)
    --dialect       Database dialect: mysql, postgres, h2, oracle, sqlserver (default: mysql)
    --out        Output file path (default: schema.sql)
    --format        Output format: sql, liquibase, flyway (default: sql)
    --no-cache      Ignore cached results
    --verbose       Enable verbose logging
"""
```

---

**文件版本**: 1.0  
**最後更新**: 2025-06-10  
**相容 Spring Boot 版本**: 3.0+  
**相容 Java 版本**: 11+
