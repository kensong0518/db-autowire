# db-autowire: Django 資料庫自動對接技能參考

## 概述

`db-autowire` 是一個通用、可重複使用的 Claude Code skill，用於自動化 Django 專案的資料庫設定與連線。只需將其丟進任何 Django 專案，就能自動偵測現有資料模型、產生 schema、對接真實資料庫，並確保整個資料庫系統完整串聯。

## 自動偵測 Django 專案

### 偵測條件

執行 skill 時，先檢查以下條件判定是否為 Django 專案：

#### 1. 檔案結構標記
```
manage.py                    # Django 專案必備的管理脚本
<app_name>/models.py         # 各 app 的資料模型定義
<app_name>/migrations/       # 遷移記錄目錄（通常自動產生）
settings.py 或 settings/     # Django 設定檔
```

#### 2. 相依套件確認
```bash
# 檢查是否安裝了 Django
pip list | grep -i django

# 或在 Python 環境中檢查
python -c "import django; print(django.VERSION)"
```

#### 3. 標誌性配置檢查
- `settings.py` 中存在 `INSTALLED_APPS` 列表
- `settings.py` 中存在 `DATABASES` 配置（或 `DATABASE_URL` 環境變數）
- 至少存在一個 `apps.py` 檔案（每個 Django app 的配置）

### 快速偵測指令

```bash
# 檢查是否為 Django 專案
test -f manage.py && grep -q "INSTALLED_APPS" settings.py && echo "Django Project Detected" || echo "Not a Django Project"

# 列出所有已註冊的 app
python manage.py shell -c "from django.conf import settings; print('\n'.join(settings.INSTALLED_APPS))"
```

---

## 核心工作流程

### 第一步：環境檢查與初始化

```bash
# 1. 確認 Django 版本（建議 3.2+）
python manage.py --version

# 2. 檢查現有的資料模型（無需 migrate）
python manage.py makemigrations --dry-run

# 3. 列出當前 INSTALLED_APPS
python manage.py shell -c "from django.conf import settings; [print(app) for app in settings.INSTALLED_APPS]"
```

### 第二步：產生並套用 Schema

#### 2a. 從模型自動產生遷移
```bash
# 為所有已變更的模型產生遷移檔
python manage.py makemigrations

# 指定特定 app（如果只想遷移某個 app）
python manage.py makemigrations <app_name>

# 乾跑模式（不實際產生檔案）
python manage.py makemigrations --dry-run --verbosity 3
```

#### 2b. 套用遷移至資料庫
```bash
# 套用所有待處理的遷移
python manage.py migrate

# 套用特定 app 的遷移
python manage.py migrate <app_name>

# 套用至特定遷移版本（回滾用）
python manage.py migrate <app_name> <migration_name>

# 查看遷移狀態
python manage.py showmigrations
python manage.py showmigrations <app_name>
```

#### 2c. 反推現有資料庫 Schema（inspectdb）
如果已有現成的資料庫，可用 `inspectdb` 反推模型：

```bash
# 自動產生 models.py（基於現有資料庫）
python manage.py inspectdb > models.py

# 指定特定資料表
python manage.py inspectdb <table_name> > models.py

# 指定資料庫別名（非預設 database）
python manage.py inspectdb --database <db_alias> > models.py
```

產生的模型檔需手動調整（移除 `managed = False`，修正欄位類型等）。

---

## 資料庫連線配置

### settings.py 中的 DATABASES 設定

#### 基本結構
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',  # 或 mysql, sqlite3, oracle
        'NAME': 'your_database_name',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',  # PostgreSQL 預設 5432, MySQL 預設 3306
        'ATOMIC_REQUESTS': True,  # 建議啟用事務支持
        'CONN_MAX_AGE': 600,      # 連線重用時間（秒）
    }
}
```

#### 使用環境變數（推薦）

使用 `dj-database-url` 套件，從單一環境變數讀取所有連線資訊：

```bash
# 安裝套件
pip install dj-database-url
```

在 `settings.py` 中：
```python
import dj_database_url
import os

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600,
        atomic_requests=True,
    )
}
```

#### 連線字串格式（DATABASE_URL 環境變數）

```
# PostgreSQL
postgresql://user:password@localhost:5432/dbname
postgres://user:password@localhost:5432/dbname

# MySQL
mysql://user:password@localhost:3306/dbname
mysql+pymysql://user:password@localhost:3306/dbname

# SQLite
sqlite:///path/to/db.sqlite3
sqlite:////absolute/path/to/db.sqlite3

# Oracle
oracle://user:password@localhost:1521/dbname
```

### 常見資料庫後端引擎

| 資料庫 | ENGINE | 預設 PORT | 套件需求 |
|--------|--------|-----------|---------|
| PostgreSQL | `django.db.backends.postgresql` | 5432 | `psycopg2` 或 `psycopg2-binary` |
| MySQL | `django.db.backends.mysql` | 3306 | `mysqlclient` |
| SQLite | `django.db.backends.sqlite3` | N/A | 無需額外套件 |
| Oracle | `django.db.backends.oracle` | 1521 | `cx_Oracle` |

---

## 資料模型關聯與索引

### 常見欄位類型與關聯

#### ForeignKey（一對多）
```python
from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=100)

class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)
    # on_delete 選項: CASCADE, SET_NULL, SET_DEFAULT, PROTECT, SET(), DO_NOTHING
```

#### ManyToManyField（多對多）
```python
class Student(models.Model):
    name = models.CharField(max_length=100)

class Course(models.Model):
    title = models.CharField(max_length=200)
    students = models.ManyToManyField(Student, related_name='courses')
    # 自動產生中間表 (throughModel)
```

#### OneToOneField（一對一）
```python
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField()
```

### 模型 Meta 選項

#### 索引與約束
```python
class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 單欄位索引
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['sku']),
        ]
        # 複合索引（多欄位）
        indexes = [
            models.Index(fields=['name', 'sku']),
        ]
        # 具名索引
        indexes = [
            models.Index(fields=['created_at'], name='product_created_idx'),
        ]
        # 唯一約束
        unique_together = [['sku', 'name']]  # Django 3.2+ 改用 constraints
        
        # 較新的約束語法（Django 3.2+）
        constraints = [
            models.UniqueConstraint(fields=['sku', 'name'], name='unique_sku_name'),
            models.CheckConstraint(check=models.Q(price__gte=0), name='positive_price'),
        ]
```

---

## 常見問題與排除步驟

### 問題 1: App 未在 INSTALLED_APPS 中註冊

**症狀**：`python manage.py migrate` 時忽略某個 app 的模型

**排除**：
```python
# 在 settings.py 檢查
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    # ... 其他內建 app ...
    'your_app_name',  # 確保已加入
    # 或使用完整路徑
    'your_app_name.apps.YourAppConfig',
]
```

驗證方法：
```bash
python manage.py shell -c "from django.apps import apps; print([app.label for app in apps.get_app_configs()])"
```

### 問題 2: 遷移衝突

**症狀**：`merge` 訊息或遷移依賴錯誤

**排除**：
```bash
# 檢查遷移狀態
python manage.py showmigrations

# 自動合併衝突遷移（Django 自動解決）
python manage.py makemigrations --merge

# 如須刪除未套用的遷移（謹慎操作）
# 手動移除 migrations/ 目錄下的衝突檔案，再重新 makemigrations
```

### 問題 3: 資料庫連線失敗

**排除步驟**：
```bash
# 1. 檢查環境變數是否正確設定
echo $DATABASE_URL  # Linux/macOS
$env:DATABASE_URL  # Windows PowerShell

# 2. 測試連線（在 Django shell 中）
python manage.py shell
>>> from django.db import connections
>>> connections.databases
>>> connections['default'].connect()  # 若無例外，連線正常

# 3. 查看詳細錯誤
python manage.py migrate --verbosity 3
```

### 問題 4: 遺失 migration 檔案

**症狀**：`No migrations to apply` 但模型已變更

**排除**：
```bash
# 檢查遷移是否真的遺失
python manage.py showmigrations

# 若遺失，需重新產生
python manage.py makemigrations

# 如需保留資料庫狀態，手動建立空遷移
python manage.py makemigrations <app_name> --empty --name <migration_name>
```

### 問題 5: 欄位類型不符

**症狀**：遷移後資料庫欄位類型與模型不一致

**排除**：
```bash
# 使用 inspectdb 檢查現有資料庫狀態
python manage.py inspectdb > current_models.py

# 與現有 models.py 對比，識別差異
diff models.py current_models.py

# 修正模型後重新遷移
python manage.py makemigrations
python manage.py migrate
```

---

## 自動化整合流程

### 完整執行清單（適合 CI/CD）

```bash
#!/bin/bash
# db-autowire.sh - 完整自動化流程

set -e  # 任何命令失敗都停止

echo "[1/5] 檢查 Django 環境..."
python manage.py --version

echo "[2/5] 檢查資料庫連線..."
python manage.py shell -c "from django.db import connections; connections['default'].ensure_connection()" || exit 1

echo "[3/5] 產生遷移..."
python manage.py makemigrations --check || python manage.py makemigrations

echo "[4/5] 套用遷移..."
python manage.py migrate --plan  # 先預演
python manage.py migrate

echo "[5/5] 驗證 schema..."
python manage.py showmigrations
python manage.py shell -c "
from django.apps import apps
for model in apps.get_models():
    print(f'{model.__name__}: {[f.name for f in model._meta.get_fields()]}')
"

echo "✓ 資料庫自動化設定完成！"
```

### Skill 執行邏輯

```
1. 偵測專案類型
   └─ 檢查 manage.py、settings.py、INSTALLED_APPS
   └─ 確認 Django 版本 >= 3.2

2. 讀取現有配置
   └─ 解析 DATABASES 或 DATABASE_URL
   └─ 列出 INSTALLED_APPS 中的所有 app

3. 產生與驗證 schema
   └─ 執行 makemigrations（乾跑）
   └─ 檢查遷移衝突
   └─ 套用 migrate

4. 驗證關聯與索引
   └─ 檢查 ForeignKey / ManyToManyField
   └─ 驗證 Meta.indexes 是否正確建立
   └─ 檢查唯一約束與檢查條件

5. 回報結果
   └─ 列出已套用的遷移
   └─ 顯示模型與欄位清單
   └─ 提示任何警告或錯誤
```

---

## 環境變數與敏感資訊

### 推薦實踐

```bash
# .env 檔案（不版控）
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
```

使用 `python-dotenv` 載入：
```python
# settings.py
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', 'sqlite:///db.sqlite3'),
        conn_max_age=600,
        atomic_requests=True,
    )
}
```

### 在 CI/CD 中設定環境變數

```yaml
# GitHub Actions 範例
env:
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  SECRET_KEY: ${{ secrets.SECRET_KEY }}

# GitLab CI 範例
variables:
  DATABASE_URL: $DATABASE_URL_SECRET
  SECRET_KEY: $SECRET_KEY_SECRET
```

---

## 相關資源與參考

### 官方文件
- Django 遷移系統: https://docs.djangoproject.com/en/stable/topics/migrations/
- django-admin 指令: https://docs.djangoproject.com/en/stable/ref/django-admin/
- Model 欄位參考: https://docs.djangoproject.com/en/stable/ref/models/fields/
- Meta 選項: https://docs.djangoproject.com/en/stable/ref/models/options/

### 相關套件
- `dj-database-url`: 環境變數式資料庫連線配置
- `python-dotenv`: .env 檔案管理
- `django-extensions`: 提供 `shell_plus` 等增強工具

### 常見 Django 版本支援

| 版本 | 發佈日期 | 長期支持 | 推薦用於 |
|------|---------|---------|---------|
| 5.0 | 2023年11月 | 無 | 最新功能 |
| 4.2 | 2023年4月 | 至 2026年4月 | 生產環境（推薦） |
| 3.2 | 2021年4月 | 至 2024年4月 | 舊系統維護 |

---

## 驗證清單

執行完整的 db-autowire 後，確認以下項目：

- [ ] Django 版本 >= 3.2
- [ ] manage.py 存在且可執行
- [ ] settings.py 包含 INSTALLED_APPS 與 DATABASES
- [ ] 所有 app 均在 INSTALLED_APPS 中註冊
- [ ] DATABASE_URL 環境變數設定無誤（或 DATABASES 正確配置）
- [ ] 所有遷移檔案產生成功（無衝突）
- [ ] migrate 套用成功，無例外
- [ ] ForeignKey/ManyToManyField 欄位正確建立
- [ ] 索引與約束已在資料庫中建立
- [ ] 可透過 Django ORM 查詢資料（測試連線）

---

## 快速開始

若要在新 Django 專案中立即使用 db-autowire：

```bash
# 1. 確保已安裝相依套件
pip install django dj-database-url python-dotenv

# 2. 建立 .env 檔案
echo "DATABASE_URL=postgresql://user:password@localhost:5432/mydb" > .env

# 3. 執行自動化設定
python manage.py makemigrations
python manage.py migrate

# 4. 驗證結果
python manage.py showmigrations
python manage.py shell -c "from django.db import connection; print('✓ DB Connected')"
```
