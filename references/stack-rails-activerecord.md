## db-autowire 技能參考文件：Rails/ActiveRecord 自動化資料庫配置

### 目標

將此技能應用到任何 Rails 專案，自動化完成：
1. **偵測專案堆疊** — 確認 Rails 和 ActiveRecord 環境
2. **掃描資料模型** — 讀取 app/models 中的 Model 定義
3. **產生 Schema** — 透過 migration 建置資料庫結構
4. **連接真實資料庫** — 配置 config/database.yml，應用連線字串
5. **驗證關聯** — 檢查 belongs_to/has_many、索引完整性
6. **套用 Schema** — 執行 migrate/schema:load，同步資料庫狀態

---

## 第一步：專案堆疊偵測

### 檢查檔案與相依套件

執行以下檢查，確認是 Rails 專案：

```bash
# 1. 確認 Gemfile 存在且包含 rails
test -f Gemfile && grep -q "^\s*gem\s['\"]rails['\"]" Gemfile
echo $?  # 0 = 是 Rails 專案

# 2. 確認必要目錄結構
test -d app/models && test -f db/schema.rb
echo $?  # 0 = Rails 標準結構

# 3. 查看 Rails 版本
grep "^Rails" Gemfile.lock | head -1

# 4. 檢查是否有待執行的 migration（重要）
rails db:migrate:status
```

### 自動偵測條件（全部符合 = Rails 專案）

| 條件 | 檔案/命令 | 說明 |
|------|---------|------|
| Gemfile 存在 | `./Gemfile` | Rails 專案標配 |
| Rails gem 記錄 | `grep "gem.*rails" Gemfile` | 相依套件宣告 |
| 模型目錄存在 | `./app/models/` | ActiveRecord 模型位置 |
| Schema 記錄存在 | `./db/schema.rb` 或 `./db/structure.sql` | 資料庫結構快照 |
| config/database.yml 存在 | `./config/database.yml` | 資料庫連線配置 |

---

## 第二步：掃描資料模型

### 讀取 Model 定義

```bash
# 列出所有 model 檔案
ls -la app/models/*.rb

# 查看特定 model 內容（例：User）
cat app/models/user.rb
```

### 典型 Model 結構範例

```ruby
# app/models/user.rb
class User < ApplicationRecord
  has_many :posts, dependent: :destroy
  has_many :comments, through: :posts
  validates :email, presence: true, uniqueness: true
end

# app/models/post.rb
class Post < ApplicationRecord
  belongs_to :user
  has_many :comments, dependent: :destroy
  validates :title, presence: true
end

# app/models/comment.rb
class Comment < ApplicationRecord
  belongs_to :post
  belongs_to :user
end
```

### 關鍵關聯型態

| 關聯型態 | 定義位置 | 需要的欄位 |
|---------|--------|----------|
| `belongs_to :user` | 從屬 Model | 外鍵：user_id |
| `has_many :posts` | 主導 Model | （關聯方自動推導） |
| `has_many :through` | 多對多 | 兩個 belongs_to + join table |
| `has_one` | 一對一 | 外鍵在被指向的 table |

---

## 第三步：產生 Schema（Migration）

### 基本流程

```bash
# 1. 檢查待執行的 migration
rails db:migrate:status
# 輸出示例：
#  Status   Migration ID    Migration Name
# --------------------------------------------------
#    up     20240101000000  Create users
#    up     20240102000000  Create posts
#  down     20240103000000  Add index to posts

# 2. 如果有待執行，執行 migrate
rails db:migrate

# 3. 驗證 schema.rb 已更新
cat db/schema.rb | tail -20
```

### 新建 Model 及 Migration

```bash
# 全自動：生成 model + migration
rails generate model Post user:references title:string content:text published:boolean

# 此命令會生成：
# - app/models/post.rb
# - db/migrate/[timestamp]_create_posts.rb

# 檢查生成的 migration
cat db/migrate/*_create_posts.rb
```

### Migration 檔案範例

```ruby
# db/migrate/20240101000001_create_posts.rb
class CreatePosts < ActiveRecord::Migration[7.0]
  def change
    create_table :posts do |t|
      t.references :user, foreign_key: true
      t.string :title, null: false
      t.text :content
      t.boolean :published, default: false

      t.timestamps
    end
    
    # 添加索引以提升查詢效能
    add_index :posts, :user_id
    add_index :posts, :published
  end
end
```

### 執行 Migration

```bash
# 執行所有待執行的 migration
rails db:migrate

# 指定環境（預設為 development）
RAILS_ENV=production rails db:migrate

# 回滾最後一個 migration
rails db:rollback

# 回滾到指定時間點
rails db:migrate VERSION=20240101000000
```

### 從 Schema 快速重建資料庫

```bash
# 方法 1：使用 schema.rb（推薦）
rails db:schema:load

# 方法 2：完整重建（清空 + schema:load）
rails db:drop db:create db:schema:load

# 方法 3：使用 structure.sql（如有）
rails db:structure:load
```

---

## 第四步：連接真實資料庫

### 檢查與配置 database.yml

```bash
# 查看當前配置
cat config/database.yml
```

### database.yml 標準結構

```yaml
# config/database.yml
default: &default
  adapter: postgresql
  encoding: unicode
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 5 } %>
  
development:
  <<: *default
  database: myapp_development
  host: localhost
  username: postgres
  password: <%= ENV["DB_PASSWORD"] %>

test:
  <<: *default
  database: myapp_test

production:
  <<: *default
  url: <%= ENV["DATABASE_URL"] %>
  pool: <%= ENV.fetch("RAILS_MAX_THREADS") { 20 } %>
```

### 環境變數配置（.env 檔）

```bash
# .env（開發環境）
DATABASE_URL=postgresql://postgres:password@localhost:5432/myapp_development
RAILS_ENV=development

# .env.production
DATABASE_URL=postgresql://user:pass@prod-db-host:5432/myapp_prod
RAILS_ENV=production
```

### 常見連線字串格式

| 資料庫 | 連線字串格式 | 預設埠 |
|------|-----------|-------|
| PostgreSQL | `postgresql://user:pass@host:5432/dbname` | 5432 |
| MySQL | `mysql2://user:pass@host:3306/dbname` | 3306 |
| SQLite | `sqlite3:db/development.sqlite3` | N/A |
| SQLServer | `sqlserver://user:pass@host:1433;database=dbname` | 1433 |

### 環境變數讀取方式

```ruby
# config/database.yml 中讀取環境變數
url: <%= ENV["DATABASE_URL"] %>

# 在 .env 或 .env.local 定義（需要 dotenv gem）
# gem 'dotenv-rails'

# 或直接執行前設定
DATABASE_URL=postgresql://... rails db:migrate
```

---

## 第五步：驗證與套用 Schema

### 完整驗證清單

```bash
# 1. 檢查 migration 狀態
rails db:migrate:status

# 2. 驗證 schema.rb 的完整性
cat db/schema.rb | grep -E "create_table|add_index"

# 3. 驗證資料庫連線
rails dbconsole  # 進入資料庫命令列（輸入 exit 或 quit 離開）

# 4. 列出資料庫中的所有 table
# PostgreSQL
rails dbconsole << 'EOF'
\dt
EOF

# MySQL
rails dbconsole << 'EOF'
SHOW TABLES;
EOF

# SQLite
rails dbconsole << 'EOF'
.tables
EOF
```

### 檢查關聯與索引

```bash
# 檢查 schema.rb 中是否定義了所有必要的外鍵
grep "foreign_key: true" db/schema.rb

# 檢查索引
grep "add_index" db/schema.rb

# 在資料庫中驗證索引（PostgreSQL）
rails dbconsole << 'EOF'
SELECT * FROM pg_indexes WHERE tablename = 'posts';
EOF
```

### 套用 Schema 到資料庫

```bash
# 前提：確認環境變數已設定正確的 DATABASE_URL

# 方法 A：執行待執行的 migration
rails db:migrate

# 方法 B：若 migration 有問題，直接從 schema 重建（開發環境）
rails db:drop db:create db:schema:load

# 方法 C：檢查無誤後在生產環境執行
RAILS_ENV=production rails db:migrate --verbose

# 驗證執行結果
rails db:migrate:status  # 應全為 up
```

---

## 常見問題與解決方案

### 問題 1：schema.rb vs structure.sql

**現象**：不知道該用哪個

**原因**：Rails 支援兩種方式記錄資料庫結構

| 方案 | 格式 | 何時使用 | 缺點 |
|------|------|--------|------|
| schema.rb | Ruby | 純 Ruby 應用，跨資料庫相容 | 無法記錄觸發器、預存程序 |
| structure.sql | SQL | 複雜的 SQL 特性 | 資料庫特定，遷移困難 |

**解決**：
```bash
# 檢查當前配置
grep "config.active_record.schema_format" config/application.rb
# 或
cat db/schema_format.txt (某些版本)

# 設定為 schema.rb（推薦）
# config/application.rb
config.active_record.schema_format = :ruby

# 設定為 structure.sql（需要進階 SQL）
config.active_record.schema_format = :sql
```

### 問題 2：Migration 待執行狀態

**現象**：`rails db:migrate:status` 顯示某些 migration 為 down

**原因**：
1. 新 migration 檔案未執行
2. 資料庫已刪除但 migration 記錄未清
3. 資料庫連線失敗

**解決**：
```bash
# 1. 確認連線
rails db:migrate:status

# 2. 執行所有待執行的 migration
rails db:migrate

# 3. 若連線有問題，檢查環境變數
echo $DATABASE_URL
rails db:drop  # 小心！會刪除資料

# 4. 重新建立
rails db:create db:schema:load
```

### 問題 3：外鍵約束錯誤

**現象**：Migration 失敗，提示 foreign key constraint 違反

**原因**：
1. 關聯的父 table 尚未建立
2. 已存在的資料參照不存在的記錄

**解決**：
```bash
# 在 migration 中顯式指定 foreign_key
# db/migrate/[timestamp]_create_posts.rb
class CreatePosts < ActiveRecord::Migration[7.0]
  def change
    create_table :posts do |t|
      t.references :user, foreign_key: true  # 自動建立外鍵
    end
  end
end

# 或手動加入外鍵（用於現有 table）
add_foreign_key :posts, :users

# 移除外鍵
remove_foreign_key :posts, :users
```

### 問題 4：Schema 與程式碼不同步

**現象**：Model 定義了關聯，但 schema.rb 中沒有對應欄位

**原因**：Migration 未執行或遺漏必要的欄位

**解決**：
```bash
# 1. 建立新 migration 添加遺漏的欄位
rails generate migration AddUserIdToPosts user:references

# 2. 檢查生成的 migration 檔案
cat db/migrate/*_add_user_id_to_posts.rb

# 3. 執行 migration
rails db:migrate

# 4. 驗證 schema.rb 已更新
grep "user_id" db/schema.rb
```

---

## 自動化技能實作步驟

### 步驟 1：自動偵測

```bash
#!/bin/bash
# 檢查是否為 Rails 專案
if [[ ! -f Gemfile ]] || ! grep -q "gem.*rails" Gemfile; then
  echo "Not a Rails project"
  exit 1
fi

if [[ ! -d app/models ]] || [[ ! -f config/database.yml ]]; then
  echo "Missing Rails structure"
  exit 1
fi

echo "✓ Rails project detected"
```

### 步驟 2：掃描模型

```bash
#!/bin/bash
# 列出所有 model 及其關聯
for model in app/models/*.rb; do
  echo "=== $(basename $model) ==="
  grep -E "belongs_to|has_many|has_one" "$model"
done
```

### 步驟 3：檢查待執行 Migration

```bash
#!/bin/bash
rails db:migrate:status
# 若有 down 狀態，通知使用者待執行
```

### 步驟 4：套用 Schema

```bash
#!/bin/bash
# 確認環境變數已設定
if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL not set"
  exit 1
fi

# 執行 migration
RAILS_ENV=${RAILS_ENV:-development} rails db:migrate

# 驗證成功
rails db:migrate:status
```

---

## 快速參考：常用指令

```bash
# 生成新 model（含 migration）
rails generate model ModelName field:type field:type

# 執行所有 migration
rails db:migrate

# 檢查 migration 狀態
rails db:migrate:status

# 回滾最後一個 migration
rails db:rollback

# 從 schema 重建資料庫
rails db:schema:load

# 完整重建（危險！）
rails db:drop db:create db:schema:load

# 進入資料庫命令列
rails dbconsole

# 查看 schema.rb
cat db/schema.rb

# 生成 migration（現有 table 添加欄位）
rails generate migration AddFieldNameToTableName field_name:type
```

---

## 注意事項與陷阱

### 須知事項

1. **Migration 順序很重要**：Migration 應按時間順序執行，否則會失敗
2. **schema.rb 是唯讀**：不要手動編輯 schema.rb，而是透過 migration 修改
3. **外鍵依賴順序**：有外鍵的 table 必須在被參照的 table 之後建立
4. **敏感資訊**：不要在 migration 中硬編碼密碼，使用環境變數
5. **測試環境隔離**：test database 應獨立於 development

### 常見陷阱

| 陷阱 | 症狀 | 原因 | 解決 |
|------|------|------|------|
| Schema 與程式碼不同步 | Model 有欄位但 migration 沒有 | 手動編輯 model 後忘記 migrate | 執行 `rails db:migrate` |
| 外鍵衝突 | Migration 失敗 | 資料參照不存在的記錄 | 檢查資料完整性或移除外鍵約束 |
| 連線字串錯誤 | 無法連接資料庫 | DATABASE_URL 格式或認證錯誤 | 驗證環境變數與 database.yml |
| Migration 重複名稱 | 衝突或意外覆蓋 | 多人開發時 migration 名稱相同 | 重新命名或重建 |
| pending migrations | rails 伺服器無法啟動 | Migration 未執行 | 執行 `rails db:migrate` |

---

## 相關資源

- [Rails Guides - ActiveRecord Migrations](https://guides.rubyonrails.org/active_record_migrations.html)
- [Rails Guides - ActiveRecord Associations](https://guides.rubyonrails.org/association_basics.html)
- [Rails API - db:migrate](https://guides.rubyonrails.org/command_line.html#bin-rails-db)
- [PostgreSQL Adapter Documentation](https://guides.rubyonrails.org/configuring.html#connection-preference)
