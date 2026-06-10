# db-autowire Skill Reference

## 概述

`db-autowire` 是一個通用的 Claude Code skill，用於自動化 SQLAlchemy 與 Alembic 的資料庫串接流程。丟到任何專案，即可自動：

1. **偵測棧**：檢查專案是否使用 SQLAlchemy + Alembic
2. **產生 Schema**：依程式碼的資料模型自動產生資料庫 schema
3. **對接資料庫**：設定連線字串並初始化資料庫
4. **遷移管理**：透過 Alembic 版本管理所有 schema 變更

---

## 部分 1：棧偵測 (Stack Detection)

### 如何判定一個專案使用 SQLAlchemy + Alembic

需要檢查以下**所有或部分**檔案/相依套件：

#### 相依套件檢查

```bash
# 檢查 requirements.txt、setup.py、pyproject.toml 或 pipfile
grep -E "sqlalchemy|alembic" requirements.txt
grep -E "sqlalchemy|alembic" setup.py
grep -E "sqlalchemy|alembic" pyproject.toml
grep -E "sqlalchemy|alembic" Pipfile
```

預期結果範例：
```
sqlalchemy>=2.0.0
alembic>=1.12.0
```

#### 檔案結構檢查

| 檔案/目錄 | 用途 | 優先度 |
|---------|------|------|
| `alembic/` | Alembic 遷移檔案目錄（若存在=確認使用 Alembic） | 高 |
| `alembic.ini` | Alembic 組態檔 | 高 |
| `models.py` 或 `models/` | SQLAlchemy 模型定義 | 中 |
| `app.py`, `main.py` 中的 `from sqlalchemy import ...` | 直接導入 | 中 |

#### Python 程式碼特徵

在 `models.py` 或類似檔案中尋找：

```python
# 檢查 declarative_base 的使用
from sqlalchemy.orm import declarative_base
Base = declarative_base()

# 或舊風格
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()

# 檢查模型定義
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
```

### 自動偵測實作

**檔案：`detect_stack.py`**

```python
import os
import re

def detect_sqlalchemy_alembic(project_root):
    """
    檢查專案是否使用 SQLAlchemy + Alembic。
    回傳 tuple: (is_detected: bool, details: dict)
    """
    details = {
        'has_alembic_dir': False,
        'has_alembic_ini': False,
        'has_sqlalchemy_deps': False,
        'has_models': False,
        'model_files': [],
        'python_version': None,
    }
    
    # 檢查 Alembic 目錄
    alembic_path = os.path.join(project_root, 'alembic')
    if os.path.isdir(alembic_path):
        details['has_alembic_dir'] = True
    
    # 檢查 alembic.ini
    if os.path.isfile(os.path.join(project_root, 'alembic.ini')):
        details['has_alembic_ini'] = True
    
    # 檢查相依套件
    for req_file in ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile']:
        req_path = os.path.join(project_root, req_file)
        if os.path.isfile(req_path):
            with open(req_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if re.search(r'sqlalchemy|alembic', content, re.IGNORECASE):
                    details['has_sqlalchemy_deps'] = True
                    break
    
    # 尋找模型檔案
    for root, dirs, files in os.walk(project_root):
        # 跳過常見的非程式碼目錄
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.env'}]
        
        for file in files:
            if file in {'models.py'} or file.startswith('model_'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    if 'declarative_base' in content or 'Base' in content and 'Column' in content:
                        details['has_models'] = True
                        details['model_files'].append(file_path)
    
    # 判定：至少需要兩個指標
    is_detected = sum([
        details['has_alembic_dir'],
        details['has_alembic_ini'],
        details['has_sqlalchemy_deps'],
        details['has_models'],
    ]) >= 2
    
    return is_detected, details
```

---

## 部分 2：Schema 產生 (Schema Generation)

### 原始方式：`metadata.create_all()`

最簡單的方式，直接從 ORM 模型產生表格。適用於**初始化或開發環境**。

**指令：**

```python
# 檔案：scripts/init_db.py
from sqlalchemy import create_engine
from app.models import Base  # 導入 declarative_base 實例

# 建立引擎（見下面連線字串部分）
DATABASE_URL = "sqlite:///./test.db"  # 開發用
engine = create_engine(DATABASE_URL)

# 產生所有表格
Base.metadata.create_all(bind=engine)
print("Database tables created successfully!")
```

**執行：**

```bash
python scripts/init_db.py
```

**缺點：**
- 無法版本管理遷移歷史
- 難以追蹤 schema 變更
- 團隊協作時容易產生衝突

### 正式方式：使用 Alembic

**強烈推薦**用於生產環境或協作開發。Alembic 提供：
- 自動偵測模型變更並產生遷移檔
- 版本控制每一次 schema 變更
- 支援向上/向下遷移

#### Alembic 初始化

若專案尚未有 Alembic，初始化它：

```bash
cd /path/to/project
alembic init alembic
```

這會產生：
```
alembic/
├── versions/          # 遷移檔案（由命令產生）
├── env.py             # Alembic 環境設定（需要修改）
├── script.py.mako     # 遷移腳本範本
└── README
alembic.ini           # 主組態檔
```

#### 設定 Alembic：`alembic/env.py`

Alembic 需要知道 Base 與 DATABASE_URL 在哪：

```python
# alembic/env.py
import os
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from app.models import Base  # 導入 declarative_base

# 讀環境變數或使用預設值
config = context.config
database_url = os.getenv('DATABASE_URL', 'sqlite:///./test.db')
config.set_main_option('sqlalchemy.url', database_url)

# 設定目標 metadata
target_metadata = Base.metadata

def run_migrations_online() -> None:
    """執行線上遷移"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        
        with context.begin_transaction():
            context.run_migrations()

# 檢查是否線上或離線模式
if context.is_offline_mode():
    # 離線遷移（生成 SQL 但不執行）
    pass
else:
    run_migrations_online()
```

#### 產生遷移檔

修改 `app/models.py` 後，自動偵測變更並產生遷移檔：

```bash
# 自動產生遷移檔（Alembic 會比對 metadata vs 資料庫 schema）
alembic revision --autogenerate -m "Add user table with email"
```

這會在 `alembic/versions/` 產生檔案，如：
```
2024_01_15_123456_add_user_table_with_email.py
```

檔案內容範例：
```python
def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

def downgrade() -> None:
    op.drop_table('users')
```

#### 執行遷移

```bash
# 升級到最新版本
alembic upgrade head

# 升級到特定版本
alembic upgrade <revision_hash>

# 降級一個版本
alembic downgrade -1

# 降級到特定版本
alembic downgrade <revision_hash>

# 檢查當前版本
alembic current

# 顯示遷移歷史
alembic history
```

### 常見陷阱與解決

| 陷阱 | 症狀 | 解決 |
|-----|------|------|
| **Autogenerate 未偵測某些變更** | 新增的 `Index` 或 `CHECK` 條件未出現在遷移檔 | 手動編輯遷移檔，加入 `op.create_index()` 或 `op.execute()` |
| **遺漏外鍵約束** | Autogenerate 產生的檔案沒有 `ForeignKeyConstraint` | 檢查模型是否正確定義 `ForeignKey` 與 `relationship` |
| **資料庫中斷連接** | `alembic upgrade head` 失敗 | 檢查 `DATABASE_URL` 環境變數與資料庫服務是否運行 |
| **衝突的遷移檔** | 多人協作時產生重複 revision | 合併衝突的 `.py` 檔案，或重新產生 revision |

---

## 部分 3：連線字串 (Connection Strings)

### SQLAlchemy 引擎 URL 格式

```
dialect+driver://username:password@host:port/database
```

#### SQLite（開發/測試）

```python
DATABASE_URL = "sqlite:///./test.db"           # 相對路徑
DATABASE_URL = "sqlite:////tmp/test.db"        # 絕對路徑（Unix）
DATABASE_URL = "sqlite:///C:\\data\\test.db"   # 絕對路徑（Windows）
```

#### MySQL/MariaDB

```python
# 基礎格式
DATABASE_URL = "mysql+pymysql://root:password@localhost:3306/mydb"

# 使用環境變數
import os
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'mysql+pymysql://root:password@localhost:3306/mydb'
)
```

**注意：** MySQL 需要 `pymysql` 驅動程式，安裝：
```bash
pip install pymysql
```

#### PostgreSQL

```python
DATABASE_URL = "postgresql://user:password@localhost:5432/mydb"

# 使用 psycopg2（推薦）
DATABASE_URL = "postgresql+psycopg2://user:password@localhost:5432/mydb"
```

**安裝驅動：**
```bash
pip install psycopg2-binary
```

#### 環境變數讀取（推薦）

**檔案：`.env`**

```
DATABASE_URL=mysql+pymysql://root:mypass@localhost:3306/myapp
SQLALCHEMY_ECHO=true
```

**在程式中讀取：**

```python
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./test.db')
SQLALCHEMY_ECHO = os.getenv('SQLALCHEMY_ECHO', 'false').lower() == 'true'

from sqlalchemy import create_engine
engine = create_engine(DATABASE_URL, echo=SQLALCHEMY_ECHO)
```

**安裝 dotenv：**
```bash
pip install python-dotenv
```

---

## 部分 4：模型定義與關聯 (Model Definition & Relationships)

### 基本模型結構

```python
# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 關聯到 Post
    posts = relationship('Post', back_populates='author')
    
    __table_args__ = (
        UniqueConstraint('email', name='uq_user_email'),
        Index('idx_username', 'username'),
    )
    
    def __repr__(self):
        return f'<User id={self.id} email={self.email}>'

class Post(Base):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 反向關聯
    author = relationship('User', back_populates='posts')
    
    __table_args__ = (
        Index('idx_author_id', 'author_id'),
    )
```

### 關鍵概念

#### ForeignKey（外鍵）

```python
author_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
```

- `ForeignKey('users.id')`：參照 `users` 表的 `id` 欄位
- `ondelete='CASCADE'`：刪除 User 時自動刪除相關 Post
- 選項：`CASCADE`, `SET NULL`, `RESTRICT`, `NO ACTION`

#### relationship（關聯）

```python
# 在 User 模型
posts = relationship('Post', back_populates='author')

# 在 Post 模型
author = relationship('User', back_populates='posts')
```

- `back_populates`：建立雙向參照
- 允許在程式碼中存取：`user.posts`, `post.author`

#### Unique 與 Index

```python
# 單一欄位唯一約束
email = Column(String(255), unique=True, nullable=False)

# 複合唯一約束
__table_args__ = (
    UniqueConstraint('user_id', 'role_id', name='uq_user_role'),
)

# 複合索引
__table_args__ = (
    Index('idx_user_role', 'user_id', 'role_id'),
)
```

---

## 部分 5：端對端工作流 (End-to-End Workflow)

### 案例：啟動新專案

#### 第 1 步：初始化環境

```bash
# 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Unix
# 或 venv\Scripts\activate  # Windows

# 安裝相依套件
pip install sqlalchemy alembic pymysql python-dotenv

# 建立專案結構
mkdir -p app/models
touch app/__init__.py
touch app/models/__init__.py
touch app/models.py
touch .env
```

#### 第 2 步：定義模型

**檔案：`app/models.py`**

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    posts = relationship('Post', back_populates='author')

class Post(Base):
    __tablename__ = 'posts'
    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    author_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'))
    author = relationship('User', back_populates='posts')
```

#### 第 3 步：初始化 Alembic

```bash
alembic init alembic
```

#### 第 4 步：設定連線

**檔案：`.env`**

```
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/myapp
```

**編輯 `alembic/env.py`**

```python
import os
from sqlalchemy import engine_from_config
from alembic import context
from app.models import Base

config = context.config
database_url = os.getenv('DATABASE_URL')
config.set_main_option('sqlalchemy.url', database_url)
target_metadata = Base.metadata

def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=None,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    pass
else:
    run_migrations_online()
```

#### 第 5 步：產生並執行遷移

```bash
# 產生初始遷移檔
alembic revision --autogenerate -m "Initial schema"

# 執行遷移
alembic upgrade head

# 驗證
alembic current
```

#### 第 6 步：驗證資料庫

```python
# 檔案：scripts/verify_db.py
from sqlalchemy import create_engine, inspect
import os
from dotenv import load_dotenv

load_dotenv()
database_url = os.getenv('DATABASE_URL')
engine = create_engine(database_url)

inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables: {tables}")

for table in tables:
    columns = inspector.get_columns(table)
    print(f"\n{table}:")
    for col in columns:
        print(f"  {col['name']}: {col['type']}")
```

執行：
```bash
python scripts/verify_db.py
```

---

## 部分 6：Skill 實作框架

### 主要流程

```python
# db_autowire_skill.py

def run(project_root: str, action: str = 'auto') -> dict:
    """
    Main entry point for db-autowire skill.
    
    Args:
        project_root: 專案根目錄
        action: 'detect', 'init', 'migrate', 'verify' 或 'auto'（全部）
    
    Returns:
        結果字典
    """
    results = {}
    
    # 第 1 步：偵測
    is_detected, details = detect_sqlalchemy_alembic(project_root)
    results['detected'] = is_detected
    results['details'] = details
    
    if not is_detected:
        return {'error': 'SQLAlchemy + Alembic not detected'}
    
    # 第 2 步：初始化（若需要）
    if action in ['init', 'auto']:
        results['init'] = init_alembic_if_needed(project_root)
    
    # 第 3 步：產生遷移
    if action in ['migrate', 'auto']:
        results['migration'] = generate_migration(project_root)
    
    # 第 4 步：驗證
    if action in ['verify', 'auto']:
        results['verification'] = verify_database(project_root)
    
    return results
```

### 各子功能

#### 初始化 Alembic

```python
def init_alembic_if_needed(project_root: str) -> dict:
    """若 Alembic 不存在，初始化它"""
    alembic_path = os.path.join(project_root, 'alembic')
    alembic_ini = os.path.join(project_root, 'alembic.ini')
    
    if os.path.exists(alembic_ini):
        return {'status': 'already_initialized'}
    
    # 執行 alembic init
    result = subprocess.run(
        ['alembic', 'init', 'alembic'],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        return {'status': 'failed', 'error': result.stderr}
    
    return {'status': 'initialized', 'alembic_dir': alembic_path}
```

#### 產生遷移

```python
def generate_migration(project_root: str, message: str = 'Auto-generated') -> dict:
    """執行 alembic revision --autogenerate"""
    result = subprocess.run(
        ['alembic', 'revision', '--autogenerate', '-m', message],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        return {'status': 'failed', 'error': result.stderr}
    
    # 解析輸出找到產生的檔案
    import re
    match = re.search(r'Generating (.+?alembic/versions/.+?\.py)', result.stderr)
    migration_file = match.group(1) if match else None
    
    return {
        'status': 'generated',
        'migration_file': migration_file,
        'output': result.stderr,
    }
```

#### 驗證資料庫

```python
def verify_database(project_root: str) -> dict:
    """檢查資料庫連線與表格"""
    try:
        # 讀取環境變數
        load_dotenv(os.path.join(project_root, '.env'))
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            return {'status': 'failed', 'error': 'DATABASE_URL not set'}
        
        engine = create_engine(database_url)
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        return {
            'status': 'success',
            'tables': tables,
            'table_count': len(tables),
        }
    except Exception as e:
        return {'status': 'failed', 'error': str(e)}
```

---

## 常見問題 (FAQ)

### Q1：Alembic autogenerate 沒有偵測到新增的 Index

**A：** Alembic 的 autogenerate 有限制，某些變更需手動編輯。

**解決步驟：**

1. 產生遷移檔（即使不完整）
   ```bash
   alembic revision --autogenerate -m "Add index"
   ```

2. 編輯 `alembic/versions/xxxx.py`，手動加入：
   ```python
   from alembic import op
   
   def upgrade() -> None:
       op.create_index('idx_email', 'users', ['email'])
   
   def downgrade() -> None:
       op.drop_index('idx_email', 'users')
   ```

3. 執行遷移
   ```bash
   alembic upgrade head
   ```

### Q2：foreign key constraint 失敗

**A：** 常見原因：

1. **表格存在順序錯誤** — 被參照的表必須先建立
   - 解決：Alembic 通常會自動排序，若失敗需手動編輯

2. **約束名稱衝突** — 多個外鍵有相同名稱
   - 解決：明確命名：
   ```python
   ForeignKey('users.id', name='fk_post_author')
   ```

3. **資料庫存在舊的不相容資料**
   - 解決：備份後清空表或手動修正資料

### Q3：如何在團隊協作時避免遷移檔衝突？

**A：**

1. **定期同步 `alembic/versions/`**
   ```bash
   git pull
   alembic upgrade head
   ```

2. **若遇到衝突的 revision**（兩人同時產生）
   - 確認兩個遷移檔都有效
   - 手動編輯其中一個的時間戳，確保順序正確
   - 測試：`alembic upgrade head`

3. **使用 branch 隔離開發**
   - 每個功能在分支上產生遷移
   - merge 前測試完整遷移鍊

### Q4：DATABASE_URL 該如何安全地傳遞？

**A：**

**開發環境：** 使用 `.env` + `python-dotenv`
```bash
# .env （添加到 .gitignore）
DATABASE_URL=mysql+pymysql://root:password@localhost/myapp
```

**生產環境：**
1. **使用環境變數** — CI/CD 設定密密不上傳代碼
   ```bash
   export DATABASE_URL="mysql+pymysql://user:secret@prod-host/db"
   ```

2. **使用密鑰管理系統** — AWS Secrets Manager、Azure Key Vault 等

3. **Alembic env.py 中讀取**
   ```python
   database_url = os.getenv('DATABASE_URL')
   if not database_url:
       raise ValueError('DATABASE_URL environment variable not set')
   ```

---

## 檢查清單 (Checklist)

在使用 db-autowire 前，確保：

- [ ] 專案具有 `requirements.txt` 或 `pyproject.toml` 含 `sqlalchemy` 和 `alembic`
- [ ] 存在 `models.py` 或 `models/` 目錄含 `declarative_base` 定義
- [ ] `.env` 檔案存在並含有效的 `DATABASE_URL`
- [ ] 資料庫服務正在運行（MySQL/PostgreSQL/SQLite 可訪問）
- [ ] Python 虛擬環境已激活
- [ ] Alembic 已初始化（存在 `alembic.ini`）
- [ ] `alembic/env.py` 已正確配置 `DATABASE_URL` 和 `Base.metadata`

---

## 指令快速參考

| 指令 | 用途 |
|-----|------|
| `python scripts/init_db.py` | 直接建立表（不使用 Alembic） |
| `alembic init alembic` | 初始化 Alembic 目錄結構 |
| `alembic revision --autogenerate -m "msg"` | 產生遷移檔 |
| `alembic upgrade head` | 應用所有待遷移 |
| `alembic downgrade -1` | 降級一個版本 |
| `alembic current` | 顯示當前版本 |
| `alembic history` | 顯示遷移歷史 |
| `alembic revision` | 手動建立空遷移檔 |
