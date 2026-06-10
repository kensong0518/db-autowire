# db-autowire: 資料庫自動化串接 Skill 參考文件

## 目標

此 skill 賦予 Claude Code 能力，讓使用者將 skill 套到任何專案，即可：
1. 自動偵測專案使用的資料庫 ORM 框架（TypeORM 或 Sequelize）
2. 根據程式碼中的資料模型產生資料庫 schema
3. 連線至真實資料庫
4. 完整串接整個資料庫工作流

---

## 專案偵測邏輯

### 1. TypeORM 偵測

**檢查項目：**
- `package.json` 中存在 `"typeorm"` 相依套件
- 專案根目錄或 `src/` 目錄下有標記 `@Entity()` 的檔案
- 存在 `ormconfig.json`、`ormconfig.js`、`typeorm.config.ts` 或類似配置檔

**快速驗證指令：**
```bash
grep -E '"typeorm"' package.json
find . -type f \( -name '*.ts' -o -name '*.js' \) | xargs grep -l '@Entity\|@Column\|@PrimaryGeneratedColumn'
ls -la | grep -i ormconfig
```

### 2. Sequelize 偵測

**檢查項目：**
- `package.json` 中存在 `"sequelize"` 相依套件
- 通常搭配 `"sequelize-cli"`
- 專案中存在 `sequelize-cli` 配置檔：`config/config.json` 或 `.sequelizerc`
- 存在 `models/` 目錄，內有繼承 `Model` 的類別

**快速驗證指令：**
```bash
grep -E '"sequelize"|"sequelize-cli"' package.json
ls -la .sequelizerc config/config.json 2>/dev/null
find models/ -type f \( -name '*.ts' -o -name '*.js' \) 2>/dev/null | head -3
```

---

## TypeORM 完整工作流

### 架構概覽

```
專案 → package.json (偵測 typeorm)
     → src/entities/ (資料模型定義)
     → src/data-source.ts (DataSource 配置)
     → ormconfig.json (連線配置)
     → database (執行中的真實資料庫)
```

### 步驟 1：偵測與驗證

```bash
npm list typeorm
grep -r "@Entity" src/
cat ormconfig.json 2>/dev/null || cat ormconfig.js
```

### 步驟 2：資料模型定義（Entity）

典型的 TypeORM Entity 結構：

```typescript
// src/entities/User.ts
import { Entity, PrimaryGeneratedColumn, Column, OneToMany } from 'typeorm';
import { Post } from './Post';

@Entity('users')
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 100, unique: true })
  email: string;

  @Column({ type: 'varchar', length: 255 })
  name: string;

  @Column({ type: 'datetime', default: () => 'CURRENT_TIMESTAMP' })
  createdAt: Date;

  @OneToMany(() => Post, (post) => post.author)
  posts: Post[];
}
```

```typescript
// src/entities/Post.ts
import { Entity, PrimaryGeneratedColumn, Column, ManyToOne, JoinColumn, Index } from 'typeorm';
import { User } from './User';

@Entity('posts')
@Index('idx_author_id', ['authorId'])
@Index('idx_created_at', ['createdAt'])
export class Post {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 500 })
  title: string;

  @Column({ type: 'text' })
  content: string;

  @Column({ type: 'uuid' })
  authorId: string;

  @Column({ type: 'datetime', default: () => 'CURRENT_TIMESTAMP' })
  createdAt: Date;

  @ManyToOne(() => User, (user) => user.posts)
  @JoinColumn({ name: 'authorId' })
  author: User;
}
```

### 步驟 3：DataSource 配置

**檔案：`src/data-source.ts`**

```typescript
import 'reflect-metadata';
import { DataSource } from 'typeorm';
import { User } from './entities/User';
import { Post } from './entities/Post';

export const AppDataSource = new DataSource({
  type: 'mysql', // 或 'postgres', 'sqlite', 'mariadb' 等
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '3306'),
  username: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'myapp_dev',
  
  // Entity 掃描
  entities: [User, Post],
  // 或使用 glob 模式：
  // entities: ['src/entities/**/*.ts'],
  
  // 開發環境自動建表（正式環境務必關閉）
  synchronize: process.env.NODE_ENV !== 'production',
  
  // 控制台日誌
  logging: process.env.NODE_ENV !== 'production',
  
  // Migration 配置
  migrations: ['src/migrations/**/*.ts'],
  migrationsTableName: 'typeorm_migrations',
  migrationsRun: true,
  
  // 支援 CommonJS
  subscribers: [],
  cli: {
    entitiesDir: 'src/entities',
    migrationsDir: 'src/migrations',
  },
});
```

**環境變數檔：`.env`**

```bash
# TypeORM 連線配置
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=myapp_dev

# 或使用統一的 DATABASE_URL（某些 ORM 支援）
# DATABASE_URL=mysql://root:password@localhost:3306/myapp_dev
```

### 步驟 4：初始化資料庫連線

**主應用檔案（例如 `src/index.ts`）：**

```typescript
import 'reflect-metadata';
import { AppDataSource } from './data-source';

async function initializeDatabase() {
  try {
    await AppDataSource.initialize();
    console.log('Database connection initialized');
    
    // 若 synchronize: true，資料庫會自動建表
    console.log('Database schema synchronized');
  } catch (error) {
    console.error('Database initialization failed:', error);
    process.exit(1);
  }
}

initializeDatabase();
```

### 步驟 5：自動建表與 Synchronize

**開發環境（自動建表）：**

```typescript
synchronize: true  // 啟用時，每次應用啟動都會自動對齊 schema
```

**危險警告：**
- 在正式環境（production）務必設定 `synchronize: false`
- `synchronize: true` 會根據 Entity 定義自動增刪表欄位，可能導致資料遺失
- 正式環境應使用 Migration

### 步驟 6：Migration（正式環境）

**生成 Migration：**
```bash
npx typeorm migration:generate -n CreateUserAndPostTables -d src/data-source.ts
```

生成的 Migration 檔案位置：`src/migrations/1234567890000-CreateUserAndPostTables.ts`

**Migration 檔案結構：**
```typescript
import { MigrationInterface, QueryRunner } from 'typeorm';

export class CreateUserAndPostTables1234567890000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      CREATE TABLE users (
        id VARCHAR(36) NOT NULL PRIMARY KEY,
        email VARCHAR(100) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        createdAt DATETIME DEFAULT CURRENT_TIMESTAMP
      )
    `);
    // ... 更多建表語句
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`DROP TABLE IF EXISTS posts`);
    await queryRunner.query(`DROP TABLE IF EXISTS users`);
  }
}
```

**執行 Migration：**
```bash
npx typeorm migration:run -d src/data-source.ts
```

**檢視已執行 Migration：**
```bash
npx typeorm migration:show -d src/data-source.ts
```

**回復最後一次 Migration：**
```bash
npx typeorm migration:revert -d src/data-source.ts
```

### 常見關聯表達方式

**一對多（One-to-Many）：**
```typescript
// User 端
@OneToMany(() => Post, (post) => post.author)
posts: Post[];

// Post 端
@ManyToOne(() => User, (user) => user.posts)
@JoinColumn({ name: 'authorId' })
author: User;
```

**多對多（Many-to-Many）：**
```typescript
// Tag.ts
@Entity('tags')
export class Tag {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  name: string;

  @ManyToMany(() => Post, (post) => post.tags)
  posts: Post[];
}

// Post.ts
@ManyToMany(() => Tag, (tag) => tag.posts)
@JoinTable({ name: 'post_tags' })
tags: Tag[];
```

**索引定義：**
```typescript
@Index('idx_email', ['email'])
@Index('idx_created_date', ['createdAt', 'status'])
@Entity('users')
export class User { ... }
```

---

## Sequelize 完整工作流

### 架構概覽

```
專案 → package.json (偵測 sequelize + sequelize-cli)
     → models/ (資料模型定義)
     → config/config.json (連線配置)
     → migrations/ (版本管理)
     → seeders/ (初始資料)
     → database (執行中的真實資料庫)
```

### 步驟 1：偵測與驗證

```bash
npm list sequelize sequelize-cli
cat .sequelizerc 2>/dev/null || cat config/config.json
ls -la models/ | head -5
```

### 步驟 2：資料模型定義（Model）

**典型 Sequelize Model（ES6 Class 風格）：**

```typescript
// models/User.ts
import { DataTypes, Model, Sequelize } from 'sequelize';

export class User extends Model {
  public id!: string;
  public email!: string;
  public name!: string;
  public createdAt!: Date;

  public readonly posts?: any[]; // 關聯
}

export function initUser(sequelize: Sequelize) {
  User.init(
    {
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      email: {
        type: DataTypes.STRING(100),
        allowNull: false,
        unique: true,
      },
      name: {
        type: DataTypes.STRING(255),
        allowNull: false,
      },
      createdAt: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
      },
    },
    {
      sequelize,
      tableName: 'users',
      timestamps: false, // 若不使用 createdAt/updatedAt 自動欄位
      indexes: [
        { fields: ['email'] },
      ],
    }
  );

  return User;
}
```

```typescript
// models/Post.ts
import { DataTypes, Model, Sequelize } from 'sequelize';
import { User } from './User';

export class Post extends Model {
  public id!: string;
  public title!: string;
  public content!: string;
  public authorId!: string;
  public createdAt!: Date;

  public readonly author?: User;
}

export function initPost(sequelize: Sequelize) {
  Post.init(
    {
      id: {
        type: DataTypes.UUID,
        defaultValue: DataTypes.UUIDV4,
        primaryKey: true,
      },
      title: {
        type: DataTypes.STRING(500),
        allowNull: false,
      },
      content: {
        type: DataTypes.TEXT,
        allowNull: false,
      },
      authorId: {
        type: DataTypes.UUID,
        allowNull: false,
        references: {
          model: 'users',
          key: 'id',
        },
      },
      createdAt: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
      },
    },
    {
      sequelize,
      tableName: 'posts',
      timestamps: false,
      indexes: [
        { fields: ['authorId'] },
        { fields: ['createdAt'] },
      ],
    }
  );

  return Post;
}
```

### 步驟 3：Sequelize 實例配置

**檔案：`src/database.ts`**

```typescript
import { Sequelize } from 'sequelize';
import { initUser, User } from './models/User';
import { initPost, Post } from './models/Post';

const sequelize = new Sequelize({
  dialect: process.env.DB_TYPE || 'mysql',
  host: process.env.DB_HOST || 'localhost',
  port: parseInt(process.env.DB_PORT || '3306'),
  username: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_NAME || 'myapp_dev',
  
  // 或使用單一連線字串
  // sequelize = new Sequelize(process.env.DATABASE_URL || 'mysql://root:password@localhost:3306/myapp_dev'),
  
  logging: process.env.NODE_ENV !== 'production' ? console.log : false,
  timezone: '+08:00',
});

// 初始化所有 Model
initUser(sequelize);
initPost(sequelize);

// 建立關聯
User.hasMany(Post, { foreignKey: 'authorId', as: 'posts' });
Post.belongsTo(User, { foreignKey: 'authorId', as: 'author' });

export { sequelize, User, Post };
```

### 步驟 4：初始化資料庫連線

**主應用檔案（例如 `src/index.ts`）：**

```typescript
import { sequelize } from './database';

async function initializeDatabase() {
  try {
    // 測試連線
    await sequelize.authenticate();
    console.log('Database connection authenticated');

    // 同步所有 Model 到資料庫
    // alter: true 會修改現有表（謹慎使用）
    // force: true 會刪除並重建表（開發環境可用）
    await sequelize.sync({ alter: process.env.NODE_ENV !== 'production' });
    console.log('Database schema synchronized');
  } catch (error) {
    console.error('Database initialization failed:', error);
    process.exit(1);
  }
}

initializeDatabase();
```

### 步驟 5：自動建表與 Sync

**開發環境（使用 sync）：**

```typescript
await sequelize.sync({ alter: true });  // 修改現有表以符合 Model
// 或
await sequelize.sync({ force: true });  // 刪除並重建所有表（謹慎使用）
```

**危險警告：**
- `force: true` 會刪除所有表，僅在開發環境使用
- `alter: true` 會修改表結構，可能導致資料遺失
- 在正式環境應使用 Migration

### 步驟 6：Sequelize Migration

**初始化 Sequelize CLI：**
```bash
npx sequelize-cli init
```

這會生成：
- `config/config.json` - 資料庫配置
- `models/` - Model 目錄
- `migrations/` - Migration 檔案目錄
- `seeders/` - Seeder 檔案目錄

**配置檔：`config/config.json`**

```json
{
  "development": {
    "username": "root",
    "password": "password",
    "database": "myapp_dev",
    "host": "localhost",
    "port": 3306,
    "dialect": "mysql"
  },
  "production": {
    "username": "root",
    "password": "password",
    "database": "myapp_prod",
    "host": "db.example.com",
    "port": 3306,
    "dialect": "mysql"
  }
}
```

**生成 Migration：**
```bash
npx sequelize-cli migration:generate --name create-user-table
npx sequelize-cli migration:generate --name create-post-table
npx sequelize-cli migration:generate --name add-foreign-key-post
```

**Migration 檔案結構：**

```typescript
// migrations/20240101000001-create-user-table.js
module.exports = {
  up: async (queryInterface, Sequelize) => {
    await queryInterface.createTable('users', {
      id: {
        type: Sequelize.UUID,
        defaultValue: Sequelize.UUIDV4,
        primaryKey: true,
      },
      email: {
        type: Sequelize.STRING(100),
        allowNull: false,
        unique: true,
      },
      name: {
        type: Sequelize.STRING(255),
        allowNull: false,
      },
      createdAt: {
        type: Sequelize.DATE,
        allowNull: false,
        defaultValue: Sequelize.NOW,
      },
      updatedAt: {
        type: Sequelize.DATE,
        allowNull: true,
      },
    });

    await queryInterface.addIndex('users', ['email']);
  },

  down: async (queryInterface) => {
    await queryInterface.dropTable('users');
  },
};
```

**執行 Migration：**
```bash
npx sequelize-cli db:migrate

# 指定環境
npx sequelize-cli db:migrate --env production

# 回復上一次 Migration
npx sequelize-cli db:migrate:undo

# 回復所有 Migration
npx sequelize-cli db:migrate:undo:all
```

**檢視 Migration 狀態：**
```bash
npx sequelize-cli db:migrate:status
```

### 常見關聯表達方式

**一對多（One-to-Many）：**
```typescript
// 在 database.ts 或初始化檔案中
User.hasMany(Post, { foreignKey: 'authorId', as: 'posts' });
Post.belongsTo(User, { foreignKey: 'authorId', as: 'author' });

// 查詢時
const user = await User.findByPk(userId, { include: 'posts' });
const post = await Post.findByPk(postId, { include: 'author' });
```

**多對多（Many-to-Many）：**
```typescript
// 在 database.ts 中
const PostTag = sequelize.define('post_tag', {});
Post.belongsToMany(Tag, { through: PostTag, as: 'tags' });
Tag.belongsToMany(Post, { through: PostTag, as: 'posts' });

// 或指定明確的 through model
Post.belongsToMany(Tag, {
  through: 'post_tags',
  as: 'tags',
  foreignKey: 'postId',
  otherKey: 'tagId',
});
Tag.belongsToMany(Post, {
  through: 'post_tags',
  as: 'posts',
  foreignKey: 'tagId',
  otherKey: 'postId',
});
```

**索引定義：**
```typescript
const User = sequelize.define('user', {
  email: DataTypes.STRING,
  createdAt: DataTypes.DATE,
}, {
  indexes: [
    { fields: ['email'] },
    { fields: ['createdAt'] },
    { fields: ['email', 'createdAt'] },
  ],
});
```

---

## 環境變數標準格式

### 推薦格式

```bash
# 通用連線字串格式（適用於大多數 ORM）
DATABASE_URL=mysql://username:password@hostname:port/database_name

# 分項環境變數（便於動態配置）
DB_TYPE=mysql                    # mysql, postgres, sqlite, mariadb, etc.
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_secure_password
DB_NAME=myapp_dev

# 應用環境
NODE_ENV=development             # development, production, test
```

### 連線字串格式說明

**MySQL/MariaDB：**
```
mysql://username:password@hostname:port/database
mysql://root:password@localhost:3306/myapp_dev
```

**PostgreSQL：**
```
postgres://username:password@hostname:port/database
postgres://user:pass@localhost:5432/myapp_dev
```

**SQLite：**
```
sqlite://:memory:
sqlite:./myapp.db
```

---

## Skill 自動執行流程

### 1. 專案偵測階段

```bash
# 偵測 ORM 框架
if grep -q '"typeorm"' package.json; then
  DETECTED_ORM="typeorm"
elif grep -q '"sequelize"' package.json; then
  DETECTED_ORM="sequelize"
else
  echo "No supported ORM detected"
  exit 1
fi

# 驗證配置檔存在
if [ "$DETECTED_ORM" = "typeorm" ]; then
  find . -name "ormconfig.*" -o -name "*data-source*"
elif [ "$DETECTED_ORM" = "sequelize" ]; then
  ls config/config.json .sequelizerc 2>/dev/null
fi
```

### 2. Entity/Model 掃描階段

```bash
# TypeORM：查找所有 @Entity 定義
find src/ -type f \( -name "*.ts" -o -name "*.js" \) | xargs grep -l '@Entity'

# Sequelize：查找 models/ 下所有 Model 定義
find models/ -type f \( -name "*.ts" -o -name "*.js" \) | xargs grep -l 'extends Model\|Model.init'
```

### 3. 連線驗證階段

```bash
# 檢查環境變數
env | grep -E '^DB_|^DATABASE_URL'

# 若不存在，提示使用者建立 .env
if [ ! -f .env ]; then
  echo "Creating .env template..."
  cat > .env << 'EOF'
DB_TYPE=mysql
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=myapp_dev
NODE_ENV=development
EOF
fi
```

### 4. 自動化建表階段

**TypeORM：**
```bash
# 確保 synchronize: true（開發環境）
npx ts-node src/index.ts

# 或手動執行 Migration
npx typeorm migration:run -d src/data-source.ts
```

**Sequelize：**
```bash
# 執行所有 Migration
npx sequelize-cli db:migrate

# 或程式碼中調用 sync()
node -e "require('./src/database').sequelize.sync()"
```

### 5. 驗證與報告階段

```bash
# 列出所有表
npx ts-node -e "
import { AppDataSource } from './src/data-source';
await AppDataSource.initialize();
const tables = await AppDataSource.query('SHOW TABLES');
console.log(tables);
"

# 或 Sequelize
npx sequelize-cli db:migrate:status
```

---

## 常見雷區與解決方案

### 雷區 1：Synchronize 在正式環境導致資料遺失

**問題：**
```typescript
synchronize: true  // 危險！
```

在正式環境若開啟此選項，TypeORM 會在每次應用啟動時自動刪除未定義的欄位。

**解決方案：**
```typescript
synchronize: process.env.NODE_ENV !== 'production'
```

或明確禁用：
```typescript
synchronize: false  // 正式環境務必使用 Migration
```

### 雷區 2：Migration 未執行導致表不存在

**問題：**
```typescript
migrationsRun: true  // 設定為 true 會自動執行
```

但若 Migration 檔案未正確生成，schema 將不存在。

**解決方案：**
```bash
# 確認 Migration 檔案存在
ls src/migrations/

# 檢視 Migration 狀態
npx typeorm migration:show -d src/data-source.ts

# 手動生成與運行
npx typeorm migration:generate -n InitialSetup -d src/data-source.ts
npx typeorm migration:run -d src/data-source.ts
```

### 雷區 3：Sequelize Model 未初始化導致關聯失效

**問題：**
```typescript
// 忘記呼叫 initUser() 和 initPost()
// 導致 Model 未定義，關聯操作失敗
```

**解決方案：**
```typescript
// database.ts 中確保所有 Model 都被初始化
initUser(sequelize);
initPost(sequelize);
Tag.init(...);

// 之後定義關聯
User.hasMany(Post, { ... });
```

### 雷區 4：環境變數未設定導致連線失敗

**問題：**
```
Error: connect ECONNREFUSED 127.0.0.1:3306
```

表示 ORM 嘗試連線時環境變數未讀取。

**解決方案：**
```bash
# 檢查 .env 檔案
cat .env

# 確保載入 .env（若使用 dotenv）
import dotenv from 'dotenv';
dotenv.config();

# 列印現有環境變數
node -e "console.log(process.env.DATABASE_URL || process.env.DB_HOST)"
```

### 雷區 5：TypeScript 編譯失敗（缺少 reflect-metadata）

**問題：**
```
Error: reflect-metadata not installed
```

TypeORM 的 Decorator 須依賴 `reflect-metadata`。

**解決方案：**
```bash
npm install reflect-metadata

# 在應用進入點最前面載入
import 'reflect-metadata';
import { AppDataSource } from './data-source';
```

### 雷區 6：外鍵約束導致刪除失敗

**問題：**
```
Error: Cannot delete or update a parent row: a foreign key constraint fails
```

試圖刪除有關聯資料的主記錄。

**解決方案：**

**TypeORM：**
```typescript
@ManyToOne(() => User, (user) => user.posts, {
  onDelete: 'CASCADE',  // 刪除使用者時自動刪除相關貼文
})
@JoinColumn({ name: 'authorId' })
author: User;
```

**Sequelize：**
```typescript
User.hasMany(Post, {
  foreignKey: 'authorId',
  onDelete: 'CASCADE',
  onUpdate: 'CASCADE',
});
```

---

## 檢查清單

在執行 skill 之前，確保：

- [ ] `package.json` 中已明確依賴 `typeorm` 或 `sequelize`
- [ ] Entity/Model 檔案存在且正確定義
- [ ] 配置檔（`ormconfig.*` 或 `config/config.json`）已存在或已生成
- [ ] `.env` 檔案包含完整的資料庫連線資訊
- [ ] `DB_HOST`、`DB_PORT`、`DB_USER`、`DB_PASSWORD`、`DB_NAME` 與實際資料庫相符
- [ ] 目標資料庫已建立（若未自動建立）
- [ ] 對於 TypeORM，`synchronize: true` 僅在開發環境啟用
- [ ] 對於 Sequelize，已執行 `sequelize-cli db:migrate`
- [ ] 所有 Entity/Model 關聯均已正確定義
- [ ] 應用可成功初始化資料庫連線（無連線錯誤）

---

## 快速參考命令

### TypeORM

```bash
# 初始化
npm install typeorm reflect-metadata

# 建表與同步
npx ts-node src/index.ts  # 若 synchronize: true

# Migration
npx typeorm migration:generate -n CreateTables -d src/data-source.ts
npx typeorm migration:run -d src/data-source.ts
npx typeorm migration:show -d src/data-source.ts
npx typeorm migration:revert -d src/data-source.ts
```

### Sequelize

```bash
# 初始化
npm install sequelize sequelize-cli

# 建表與同步
npx sequelize-cli init
npx sequelize-cli db:migrate

# Migration
npx sequelize-cli migration:generate --name create-table
npx sequelize-cli migration:status
npx sequelize-cli db:migrate:undo
```

---

## 延伸資源

- **TypeORM 官方文件：** https://typeorm.io
- **Sequelize 官方文件：** https://sequelize.org
- **TypeORM Migration 指南：** https://typeorm.io/migrations
- **Sequelize CLI 文件：** https://github.com/sequelize/cli
