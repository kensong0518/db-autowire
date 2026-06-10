#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 JPA → SQL DDL 產生器（db-autowire skill）。

適用情境：Java 專案用 JPA/Hibernate 註解（@Entity）但**沒有** Flyway/Liquibase 之類的
migration 工具時，從 entity 直接產出建表 SQL 當作起手 schema。
（有 migration 工具時，優先用原生工具——見 references/stack-springboot-jpa.md。）

能力：
- 遞迴掃描目錄找所有 @Entity
- 欄位/型別/長度/nullable/unique/default 從 @Column 與欄位初始值推導
- 外鍵從 @ManyToOne / @OneToOne + @JoinColumn 推導（參照表自動對應）
- @Table(indexes=@Index(...), uniqueConstraints=@UniqueConstraint(...)) 一併產出
- 支援 --dialect mysql | postgres
- FK 依賴拓樸排序；--drop 產生乾淨重建

限制：@OneToMany/@ManyToMany 的 join table 不自動產生；非關聯的隱含外鍵欄位（純 Long id）無法推斷 FK。

用法：
  python gen_schema_jpa.py --entities <entity目錄> [--dialect mysql] [--out schema.sql] [--drop] [--database name]
"""
import argparse
import os
import re
import sys

FIELD_RE = re.compile(
    r"((?:@\w+(?:\([^)]*\))?\s*)*)"
    r"(?:private|protected)\s+([A-Za-z0-9_<>\[\]]+)\s+([A-Za-z0-9_]+)\s*"
    r"(?:=\s*(.+?))?\s*;",
    re.DOTALL,
)

TYPE_MAP = {
    "mysql": {
        "Long": "BIGINT", "long": "BIGINT", "Integer": "INT", "int": "INT",
        "Short": "SMALLINT", "Byte": "TINYINT", "Double": "DOUBLE", "double": "DOUBLE",
        "Float": "FLOAT", "float": "FLOAT", "Boolean": "TINYINT(1)", "boolean": "TINYINT(1)",
        "BigDecimal": "DECIMAL(19,2)", "BigInteger": "BIGINT",
        "LocalDate": "DATE", "LocalDateTime": "DATETIME", "LocalTime": "TIME",
        "Instant": "DATETIME", "OffsetDateTime": "DATETIME", "ZonedDateTime": "DATETIME",
        "Date": "DATETIME", "UUID": "CHAR(36)", "byte[]": "LONGBLOB",
        "_id_suffix": "AUTO_INCREMENT", "_id_type": "BIGINT", "_bool_true": "1", "_bool_false": "0",
        "_now": "CURRENT_TIMESTAMP", "_today": "CURRENT_DATE",
    },
    "postgres": {
        "Long": "BIGINT", "long": "BIGINT", "Integer": "INTEGER", "int": "INTEGER",
        "Short": "SMALLINT", "Byte": "SMALLINT", "Double": "DOUBLE PRECISION", "double": "DOUBLE PRECISION",
        "Float": "REAL", "float": "REAL", "Boolean": "BOOLEAN", "boolean": "BOOLEAN",
        "BigDecimal": "NUMERIC(19,2)", "BigInteger": "BIGINT",
        "LocalDate": "DATE", "LocalDateTime": "TIMESTAMP", "LocalTime": "TIME",
        "Instant": "TIMESTAMP", "OffsetDateTime": "TIMESTAMPTZ", "ZonedDateTime": "TIMESTAMPTZ",
        "Date": "TIMESTAMP", "UUID": "UUID", "byte[]": "BYTEA",
        "_id_suffix": "", "_id_type": "BIGSERIAL", "_bool_true": "TRUE", "_bool_false": "FALSE",
        "_now": "CURRENT_TIMESTAMP", "_today": "CURRENT_DATE",
    },
}


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", t)


def camel_to_snake(n):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", n).lower()


def anno_arg(blob, anno, key):
    m = re.search(anno + r"\(([^)]*)\)", blob)
    if not m:
        return None
    mk = re.search(key + r"\s*=\s*\"?([^,\")]+)\"?", m.group(1))
    return mk.group(1).strip() if mk else None


def anno_has(blob, anno):
    return re.search(r"(?<![A-Za-z])" + anno + r"\b", blob) is not None


def parse_class_table(text):
    """回傳 (class_name, table_name)。"""
    cm = re.search(r"(?:class|record)\s+([A-Za-z0-9_]+)", text)
    cls = cm.group(1) if cm else None
    tm = re.search(r'@Table\s*\([^)]*name\s*=\s*"([^"]+)"', text)
    if tm:
        return cls, tm.group(1)
    en = re.search(r'@Entity\s*\(\s*name\s*=\s*"([^"]+)"', text)
    if en:
        return cls, en.group(1)
    return cls, camel_to_snake(cls) if cls else None


def parse_table_indexes(text, table):
    """從 @Table 的 indexes / uniqueConstraints 產出索引定義字串。"""
    out = []
    tm = re.search(r"@Table\s*\((.*?)\)\s*(?:public|private|class|@|abstract)", text, re.DOTALL)
    block = tm.group(1) if tm else ""
    for m in re.finditer(r"@Index\s*\(([^)]*)\)", block):
        args = m.group(1)
        cols = re.search(r'columnList\s*=\s*"([^"]+)"', args)
        uniq = re.search(r"unique\s*=\s*true", args)
        nm = re.search(r'name\s*=\s*"([^"]+)"', args)
        if cols:
            collist = ", ".join(c.strip() for c in cols.group(1).split(","))
            name = nm.group(1) if nm else "idx_%s_%s" % (table, re.sub(r"\W+", "_", cols.group(1)))
            kind = "UNIQUE KEY" if uniq else "KEY"
            out.append("%s %s (%s)" % (kind, name, collist))
    for m in re.finditer(r"@UniqueConstraint\s*\(([^)]*)\)", block):
        cols = re.search(r'columnNames\s*=\s*\{?([^}\)]*)\}?', m.group(1))
        if cols:
            names = re.findall(r'"([^"]+)"', cols.group(1))
            if names:
                out.append("UNIQUE KEY uq_%s_%s (%s)" % (table, "_".join(names), ", ".join(names)))
    return out


def sql_default(expr, dm):
    e = expr.strip()
    if e in ("true", "Boolean.TRUE"):
        return dm["_bool_true"]
    if e in ("false", "Boolean.FALSE"):
        return dm["_bool_false"]
    if re.search(r"\.now\(\)$", e) or "Instant.now" in e or "LocalDateTime.now" in e:
        return dm["_now"]
    if "LocalDate.now" in e:
        return dm["_today"]
    if e.startswith('"') and e.endswith('"'):
        return "'" + e[1:-1].replace("'", "''") + "'"
    if re.fullmatch(r"-?\d+(\.\d+)?[fFdDlL]?", e):
        return re.sub(r"[fFdDlL]$", "", e)
    return None


def parse_entity(path, dialect):
    text = strip_comments(open(path, encoding="utf-8", errors="ignore").read())
    if "@Entity" not in text:
        return None
    dm = TYPE_MAP[dialect]
    cls, table = parse_class_table(text)
    if not table:
        return None
    cols, pk, uniques, fks = [], None, [], []

    for blob, jtype, fname, default in FIELD_RE.findall(text):
        if anno_has(blob, "@Transient") or anno_has(blob, "@OneToMany") or anno_has(blob, "@ManyToMany"):
            continue  # 不對應到本表的欄位
        is_id = anno_has(blob, "@Id")
        is_rel = anno_has(blob, "@ManyToOne") or anno_has(blob, "@OneToOne")

        if is_rel:
            col = anno_arg(blob, "@JoinColumn", "name") or (camel_to_snake(fname) + "_id")
            sqltype = dm["_id_type"] if False else "BIGINT"  # FK 欄位用 BIGINT（指向常見的 BIGINT 主鍵）
            ref_type = re.sub(r"<.*>", "", jtype)
            opt = anno_arg(blob, "@ManyToOne", "optional") or anno_arg(blob, "@OneToOne", "optional")
            jc_null = anno_arg(blob, "@JoinColumn", "nullable")
            not_null = (opt == "false") or (jc_null == "false")
            definition = "BIGINT" + (" NOT NULL" if not_null else "")
            cols.append((col, definition))
            fks.append((col, ref_type))
            continue

        col = anno_arg(blob, "@Column", "name") or camel_to_snake(fname)
        coldef = anno_arg(blob, "@Column", "columnDefinition")
        if coldef:
            sqltype = coldef
        elif jtype == "String":
            length = anno_arg(blob, "@Column", "length") or "255"
            sqltype = "VARCHAR(%s)" % length
        elif jtype in ("BigDecimal",):
            p = anno_arg(blob, "@Column", "precision")
            s = anno_arg(blob, "@Column", "scale")
            sqltype = ("DECIMAL(%s,%s)" % (p, s or "0")) if p else dm["BigDecimal"]
        else:
            sqltype = dm.get(jtype) or ("VARCHAR(255)" if anno_has(blob, "@Enumerated") else "VARCHAR(255)")

        nn = anno_arg(blob, "@Column", "nullable") == "false"
        not_null = is_id or nn

        if is_id:
            definition = "%s NOT NULL %s" % (dm["_id_type"], dm["_id_suffix"]) if dm["_id_suffix"] else dm["_id_type"]
            definition = definition.strip()
            pk = col
        else:
            definition = sqltype + (" NOT NULL" if not_null else "")
            if default and not coldef:
                d = sql_default(default, dm)
                if d is not None:
                    definition += " DEFAULT " + d

        cols.append((col, definition))
        if anno_arg(blob, "@Column", "unique") == "true":
            uniques.append(col)

    return {"class": cls, "table": table, "cols": cols, "pk": pk,
            "uniques": uniques, "fks": fks, "indexes": parse_table_indexes(text, table)}


def order_tables(entities):
    name_by_table = {e["table"] for e in entities}
    deps = {e["table"]: set() for e in entities}
    cls_to_table = {e["class"]: e["table"] for e in entities}
    for e in entities:
        for col, ref_type in e["fks"]:
            rt = cls_to_table.get(ref_type, camel_to_snake(ref_type))
            if rt in name_by_table and rt != e["table"]:
                deps[e["table"]].add(rt)
    order, remaining = [], list(deps.keys())
    while remaining:
        progressed = False
        for t in list(remaining):
            if deps[t] <= set(order):
                order.append(t)
                remaining.remove(t)
                progressed = True
        if not progressed:
            order.extend(remaining)
            break
    return order, cls_to_table


def render(e, cls_to_table, dialect):
    t = e["table"]
    lines = ["  %s %s," % (c, d) for c, d in e["cols"]]
    tail = ["  PRIMARY KEY (%s)" % e["pk"]] if e["pk"] else []
    for c in e["uniques"]:
        tail.append("  UNIQUE KEY uq_%s_%s (%s)" % (t, c, c))
    for ix in e["indexes"]:
        tail.append("  " + ix)
    lead = {re.search(r"\(([A-Za-z0-9_]+)", x).group(1) for x in e["indexes"] if re.search(r"\(", x)}
    for col, ref_type in e["fks"]:
        rt = cls_to_table.get(ref_type, camel_to_snake(ref_type))
        if col not in lead:
            tail.append("  KEY idx_%s_%s (%s)" % (t, rt, col))
        tail.append("  CONSTRAINT fk_%s_%s FOREIGN KEY (%s) REFERENCES %s(id)" % (t, rt, col, rt))
    body = ",\n".join(lines[:-1] + [lines[-1].rstrip(",")]) if lines else ""
    if tail:
        body = ",\n".join([l.rstrip(",") for l in lines] + tail)
    suffix = " ENGINE=InnoDB DEFAULT CHARSET=utf8mb4" if dialect == "mysql" else ""
    return "CREATE TABLE IF NOT EXISTS %s (\n%s\n)%s;" % (t, body, suffix)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entities", required=True)
    ap.add_argument("--dialect", default="mysql", choices=["mysql", "postgres"])
    ap.add_argument("--out")
    ap.add_argument("--drop", action="store_true")
    ap.add_argument("--database")
    args = ap.parse_args()

    entities = []
    for dp, _, fns in os.walk(args.entities):
        for fn in sorted(fns):
            if fn.endswith(".java"):
                e = parse_entity(os.path.join(dp, fn), args.dialect)
                if e:
                    entities.append(e)
    if not entities:
        print("找不到任何 @Entity。", file=sys.stderr)
        return 1

    order, cls_to_table = order_tables(entities)
    by_table = {e["table"]: e for e in entities}

    out = ["-- 由 db-autowire/scripts/gen_schema_jpa.py 依 JPA entity 產生（dialect=%s）" % args.dialect,
           "-- 來源：%s。請改 entity 後重跑，勿手改本檔。" % args.entities, ""]
    if args.database and args.dialect == "mysql":
        out += ["CREATE DATABASE IF NOT EXISTS %s DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" % args.database,
                "USE %s;" % args.database, ""]
    if args.drop:
        if args.dialect == "mysql":
            out.append("SET FOREIGN_KEY_CHECKS = 0;")
        for t in reversed(order):
            out.append("DROP TABLE IF EXISTS %s%s;" % (t, " CASCADE" if args.dialect == "postgres" else ""))
        if args.dialect == "mysql":
            out.append("SET FOREIGN_KEY_CHECKS = 1;")
        out.append("")
    for t in order:
        out.append(render(by_table[t], cls_to_table, args.dialect))
        out.append("")

    sql = "\n".join(out).rstrip() + "\n"
    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as f:
            f.write(sql)
        print("已寫入 %s（%d 張表）" % (args.out, len(order)))
    else:
        sys.stdout.write(sql)
    return 0


if __name__ == "__main__":
    sys.exit(main())
