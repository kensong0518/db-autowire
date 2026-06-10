#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
偵測一個專案用的後端技術棧、資料庫引擎、migration 工具與資料模型位置，
並建議「產生 + 套用 schema」的指令。這是 db-autowire skill 的入口：先偵測，再照對應 reference 做。

用法：
  python detect_stack.py [--path <專案根>] [--json]
不給 --path 預設掃目前目錄。
"""
import argparse
import json
import os
import re
import sys

PRUNE = {
    "node_modules", ".git", "target", "build", "dist", ".venv", "venv", "env",
    "__pycache__", ".gradle", ".idea", ".next", "out", "bin", "obj", "vendor",
    ".mvn", "coverage", ".pytest_cache", ".terraform",
}


def walk(root):
    """回傳 (相對路徑小寫, 絕對路徑) 清單，略過大型/雜訊目錄。"""
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in PRUNE and not d.startswith(".") or d in (".github",)]
        for fn in filenames:
            ap = os.path.join(dirpath, fn)
            rel = os.path.relpath(ap, root).replace("\\", "/")
            files.append((rel.lower(), ap))
    return files


def read(path, limit=200000):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return f.read(limit)
    except OSError:
        return ""


def any_file_contains(files, exts, needles, cap=400):
    """在副檔名符合的檔案裡找關鍵字，回傳第一個命中的相對路徑（或 None）。"""
    n = 0
    for rel, ap in files:
        if not rel.endswith(exts):
            continue
        n += 1
        if n > cap:
            break
        txt = read(ap, 60000)
        if any(s in txt for s in needles):
            return rel
    return None


def detect(root):
    files = walk(root)
    relset = {rel for rel, _ in files}
    abs = {rel: ap for rel, ap in files}

    def has(name):  # 任一檔名（basename）存在
        return any(rel == name or rel.endswith("/" + name) for rel in relset)

    def find(name):
        for rel, ap in files:
            if rel == name or rel.endswith("/" + name):
                return ap
        return None

    # 彙整相依檔內容供判斷
    pkg = read(find("package.json") or "", 60000) if has("package.json") else ""
    poms = " ".join(read(ap, 60000) for rel, ap in files if rel.endswith("pom.xml"))
    gradles = " ".join(read(ap, 60000) for rel, ap in files if rel.endswith("build.gradle") or rel.endswith("build.gradle.kts"))
    reqs = " ".join(read(ap, 60000) for rel, ap in files if rel.endswith("requirements.txt") or rel.endswith("pyproject.toml") or rel.endswith("pipfile"))
    gemfile = read(find("Gemfile") or "", 60000) if has("gemfile") else ""

    stacks = []

    # ---- Spring Boot / JPA ----
    jpa_dep = bool(re.search(r"spring-boot-starter-data-jpa|jakarta\.persistence|javax\.persistence|hibernate-core", poms + gradles, re.I))
    entity_file = any_file_contains(files, (".java", ".kt"), ["@Entity"])
    if jpa_dep or entity_file:
        ev = []
        if jpa_dep:
            ev.append("相依含 spring-data-jpa / JPA / Hibernate")
        if entity_file:
            ev.append("原始碼有 @Entity（如 %s）" % entity_file)
        mig = None
        if re.search(r"flyway", poms + gradles, re.I) or any("db/migration" in r for r in relset):
            mig = "Flyway"
        elif re.search(r"liquibase", poms + gradles, re.I):
            mig = "Liquibase"
        ddl = any_file_contains(files, (".yml", ".yaml", ".properties"), ["ddl-auto", "hbm2ddl"])
        stacks.append({
            "stack": "spring-jpa", "name": "Spring Boot + JPA / Hibernate (Java)",
            "evidence": ev, "migration_tool": mig,
            "ddl_auto": bool(ddl), "reference": "references/stack-springboot-jpa.md",
        })

    # ---- Prisma ----
    if has("schema.prisma") or re.search(r'"@?prisma', pkg):
        mig = "prisma migrate" if any("prisma/migrations" in r for r in relset) else None
        stacks.append({
            "stack": "prisma", "name": "Prisma (Node/TS)",
            "evidence": ["有 schema.prisma" if has("schema.prisma") else "package.json 依賴 prisma"],
            "migration_tool": mig, "reference": "references/stack-prisma.md",
        })

    # ---- Django ----
    if has("manage.py") or any_file_contains(files, (".py",), ["INSTALLED_APPS"]):
        mig = "django migrations" if any(re.search(r"/migrations/\d{4}_", r) or r.endswith("/migrations/0001_initial.py") for r in relset) else "django (尚無 migration)"
        stacks.append({
            "stack": "django", "name": "Django (Python)",
            "evidence": ["有 manage.py" if has("manage.py") else "settings 有 INSTALLED_APPS"],
            "migration_tool": mig, "reference": "references/stack-django.md",
        })

    # ---- TypeORM / Sequelize ----
    if re.search(r'"typeorm"', pkg):
        stacks.append({"stack": "typeorm", "name": "TypeORM (Node)", "evidence": ["package.json 依賴 typeorm"],
                       "migration_tool": "typeorm migrations", "reference": "references/stack-node-typeorm-sequelize.md"})
    if re.search(r'"sequelize"', pkg):
        stacks.append({"stack": "sequelize", "name": "Sequelize (Node)", "evidence": ["package.json 依賴 sequelize"],
                       "migration_tool": "sequelize-cli", "reference": "references/stack-node-typeorm-sequelize.md"})

    # ---- SQLAlchemy / Alembic ----
    if re.search(r"sqlalchemy", reqs, re.I) or has("alembic.ini") or any_file_contains(files, (".py",), ["declarative_base", "DeclarativeBase"]):
        mig = "Alembic" if has("alembic.ini") else None
        stacks.append({"stack": "sqlalchemy", "name": "SQLAlchemy + Alembic (Python)",
                       "evidence": ["有 alembic.ini" if has("alembic.ini") else "程式用 SQLAlchemy"],
                       "migration_tool": mig, "reference": "references/stack-python-sqlalchemy-alembic.md"})

    # ---- Rails ----
    if re.search(r"\brails\b", gemfile, re.I) or has("schema.rb"):
        stacks.append({"stack": "rails", "name": "Rails / ActiveRecord (Ruby)",
                       "evidence": ["Gemfile 含 rails" if gemfile else "有 db/schema.rb"],
                       "migration_tool": "rails db:migrate", "reference": "references/stack-rails-activerecord.md"})

    # ---- 資料庫引擎推測 ----
    blob = pkg + poms + gradles + reqs + gemfile
    for rel, ap in files:
        if rel.endswith((".yml", ".yaml", ".properties", ".env", ".prisma", "database.yml")) or rel.endswith(".env.example"):
            blob += read(ap, 20000)
    engine = "unknown"
    if re.search(r"postgres|psql|pg8000|psycopg|postgresql://|jdbc:postgresql", blob, re.I):
        engine = "postgresql"
    elif re.search(r"\bmysql\b|jdbc:mysql|mysql://|mysql2|mysql-connector|pymysql", blob, re.I):
        engine = "mysql"
    elif re.search(r"sqlite", blob, re.I):
        engine = "sqlite"

    return {"root": root, "stacks": stacks, "db_engine": engine}


GEN_HINT = {
    "spring-jpa": "Flyway/Liquibase 有的話放版本化 SQL；否則 ddl-auto=update 自動建表；都沒有就用本 skill 的 scripts/gen_schema_jpa.py 產 DDL",
    "prisma": "npx prisma migrate deploy（正式）或 npx prisma db push（雛形）",
    "django": "python manage.py makemigrations && python manage.py migrate",
    "typeorm": "typeorm migration:run（正式）或 DataSource synchronize:true（僅開發）",
    "sequelize": "npx sequelize-cli db:migrate 或 sequelize.sync({ alter:true })（僅開發）",
    "sqlalchemy": "alembic upgrade head（正式）或 Base.metadata.create_all()（雛形）",
    "rails": "rails db:migrate",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    root = os.path.abspath(args.path)

    result = detect(root)
    for s in result["stacks"]:
        s["generate_schema_hint"] = GEN_HINT.get(s["stack"], "")

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print("專案：%s" % root)
    print("推測資料庫引擎：%s" % result["db_engine"])
    if not result["stacks"]:
        print("\n沒偵測到已知的後端 ORM/框架。可能是純前端、或用了未涵蓋的技術棧。")
        return 0
    print("\n偵測到 %d 個技術棧：" % len(result["stacks"]))
    for s in result["stacks"]:
        print("\n● %s  [%s]" % (s["name"], s["stack"]))
        for e in s["evidence"]:
            print("   - 證據：%s" % e)
        print("   - migration 工具：%s" % (s.get("migration_tool") or "（未設定）"))
        print("   - 產 schema 建議：%s" % s["generate_schema_hint"])
        print("   - 詳細步驟讀：%s" % s["reference"])
    print("\n下一步：依上面的 reference 把 schema 套到真實 DB，再用 references/provider-*.md 選一家免費雲端 DB 對接。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
