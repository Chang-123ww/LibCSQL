# -*- coding: utf-8 -*-
"""
db_setup.py — 构建模拟高校图书馆测试数据库（SQLite）
所有数据为确定性随机生成（固定种子），不含任何真实读者信息。
运行: python -m src.db_setup
"""
import argparse
import os
import random
import sqlite3
from datetime import date, timedelta

SCHEMA = """
DROP TABLE IF EXISTS borrow_records;
DROP TABLE IF EXISTS books;
DROP TABLE IF EXISTS readers;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS publishers;
DROP TABLE IF EXISTS locations;

CREATE TABLE locations (
  location_id   INTEGER PRIMARY KEY,
  location_name TEXT NOT NULL,
  floor         INTEGER NOT NULL,
  shelf_range   TEXT
);
CREATE TABLE publishers (
  publisher_id   INTEGER PRIMARY KEY,
  publisher_name TEXT NOT NULL,
  address        TEXT
);
CREATE TABLE categories (
  category_id     INTEGER PRIMARY KEY,
  category_name   TEXT NOT NULL,
  parent_category INTEGER,
  location_id     INTEGER REFERENCES locations(location_id)
);
CREATE TABLE books (
  book_id          INTEGER PRIMARY KEY,
  isbn             TEXT,
  title            TEXT NOT NULL,
  author           TEXT,
  publisher_id     INTEGER REFERENCES publishers(publisher_id),
  category_id      INTEGER REFERENCES categories(category_id),
  publish_year     INTEGER,
  total_copies     INTEGER,
  available_copies INTEGER
);
CREATE TABLE readers (
  reader_id     INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  student_id    TEXT,
  department    TEXT,
  reader_type   TEXT,          -- 本科生 / 研究生 / 教师
  register_date TEXT           -- 'YYYY-MM-DD'
);
CREATE TABLE borrow_records (
  record_id   INTEGER PRIMARY KEY,
  reader_id   INTEGER REFERENCES readers(reader_id),
  book_id     INTEGER REFERENCES books(book_id),
  borrow_date TEXT,            -- 'YYYY-MM-DD'
  due_date    TEXT,
  return_date TEXT,            -- 未归还为 NULL
  renew_count INTEGER DEFAULT 0
);
"""

LOCATIONS = [
    (1, "三楼理科借阅区", 3, "A001-C120"),
    (2, "二楼文学借阅区", 2, "D001-F080"),
    (3, "四楼社科借阅区", 4, "G001-H060"),
    (4, "五楼外文借阅区", 5, "J001-K040"),
]
PUBLISHERS = [
    (1, "机械工业出版社", "北京"),
    (2, "清华大学出版社", "北京"),
    (3, "人民文学出版社", "北京"),
    (4, "高等教育出版社", "北京"),
    (5, "电子工业出版社", "北京"),
    (6, "外语教学与研究出版社", "北京"),
]
CATEGORIES = [
    (1, "计算机科学", None, 1),
    (2, "数据库技术", 1, 1),
    (3, "人工智能", 1, 1),
    (4, "中国文学", None, 2),
    (5, "外国文学", None, 2),
    (6, "经济学", None, 3),
    (7, "管理学", None, 3),
    (8, "英语语言", None, 4),
    (9, "数学", None, 1),
]

# 核心图书（测试用例中按书名引用的必须在此固定存在）
CORE_BOOKS = [
    ("数据库系统概念", "Silberschatz", 1, 2, 2021),
    ("深入理解计算机系统", "Bryant", 1, 1, 2020),
    ("人工智能：现代方法", "Russell", 2, 3, 2025),
    ("机器学习", "周志华", 2, 3, 2016),
    ("SQL必知必会", "Forta", 1, 2, 2025),
    ("深度学习入门", "斋藤康毅", 1, 3, 2025),
    ("红楼梦", "曹雪芹", 3, 4, 2019),
    ("活着", "余华", 3, 4, 2017),
    ("经济学原理", "Mankiw", 4, 6, 2022),
    ("Python编程实践", "Matthes", 2, 1, 2025),
    ("算法导论", "Cormen", 1, 1, 2018),
    ("边城", "沈从文", 3, 4, 2020),
    ("百年孤独", "马尔克斯", 3, 5, 2017),
    ("管理学原理", "Robbins", 4, 7, 2023),
    ("高等数学", "同济大学数学系", 4, 9, 2021),
]
TITLE_POOL = [
    "计算机网络", "操作系统概念", "数据结构与算法分析", "软件工程导论", "编译原理",
    "自然语言处理综论", "统计学习方法", "分布式系统原理", "数字图像处理", "信息检索导论",
    "西方经济学", "计量经济学", "组织行为学", "市场营销学", "财务管理",
    "呐喊", "围城", "平凡的世界", "白鹿原", "许三观卖血记",
    "老人与海", "了不起的盖茨比", "傲慢与偏见", "月亮与六便士", "动物农场",
    "新视野大学英语", "英语语法大全", "线性代数", "概率论与数理统计", "离散数学",
]
SURNAMES = "王李张刘陈杨赵黄周吴徐孙马朱胡郭何高林罗郑"
GIVEN = ["晓明", "思雨", "伟", "静", "洋", "敏", "浩然", "雨欣", "磊", "雪",
         "子涵", "梓萱", "俊杰", "欣怡", "宇轩", "诗涵", "博文", "嘉怡", "天佑", "若曦"]
DEPARTMENTS = ["计算机学院", "文学院", "经济学院", "外国语学院", "数学学院", "管理学院"]

CORE_READERS = [
    ("王晓明", "2023011201", "计算机学院", "本科生", "2023-09-01"),
    ("李思雨", "2022030405", "计算机学院", "本科生", "2022-09-01"),
    ("张伟",   "2021150607", "文学院",     "本科生", "2021-09-01"),
    ("陈静",   "2024220101", "经济学院",   "研究生", "2024-09-01"),
    ("赵敏",   "T2019005",   "文学院",     "教师",   "2019-03-01"),
]


def rand_date(rng, start: date, end: date) -> date:
    return start + timedelta(days=rng.randint(0, (end - start).days))


def build(db_path: str, n_books: int = 120, n_readers: int = 100, n_records: int = 800):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    rng = random.Random(42)  # 固定种子，保证可复现
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    cur.executemany("INSERT INTO locations VALUES (?,?,?,?)", LOCATIONS)
    cur.executemany("INSERT INTO publishers VALUES (?,?,?)", PUBLISHERS)
    cur.executemany("INSERT INTO categories VALUES (?,?,?,?)", CATEGORIES)

    # ---- books ----
    books = []
    bid = 101
    for title, author, pub, cat, year in CORE_BOOKS:
        total = rng.randint(5, 20)
        books.append((bid, f"9787{rng.randint(10**8, 10**9-1)}", title, author,
                      pub, cat, year, total, rng.randint(0, total)))
        bid += 1
    pool = list(TITLE_POOL)
    while len(books) < n_books:
        title = pool[(bid - 101) % len(pool)]
        suffix = f"（第{rng.randint(2,5)}版）" if rng.random() < 0.3 else ""
        total = rng.randint(2, 25)
        books.append((bid, f"9787{rng.randint(10**8, 10**9-1)}",
                      title + suffix,
                      rng.choice(SURNAMES) + rng.choice(GIVEN),
                      rng.randint(1, len(PUBLISHERS)),
                      rng.randint(1, len(CATEGORIES)),
                      rng.randint(2015, 2025), total, rng.randint(0, total)))
        bid += 1
    cur.executemany("INSERT INTO books VALUES (?,?,?,?,?,?,?,?,?)", books)

    # ---- readers ----
    readers = []
    rid = 1
    for name, sid, dept, rtype, reg in CORE_READERS:
        readers.append((rid, name, sid, dept, rtype, reg))
        rid += 1
    used_names = {r[1] for r in readers}
    while len(readers) < n_readers:
        name = rng.choice(SURNAMES) + rng.choice(GIVEN)
        if name in used_names:
            name += rng.choice("轩然睿泽")
        used_names.add(name)
        rtype = rng.choices(["本科生", "研究生", "教师"], weights=[70, 22, 8])[0]
        year = rng.randint(2019, 2024)
        sid = f"T{year}{rng.randint(100,999)}" if rtype == "教师" else f"{year}{rng.randint(10**7, 10**8-1)}"
        readers.append((rid, name, sid, rng.choice(DEPARTMENTS), rtype, f"{year}-09-01"))
        rid += 1
    cur.executemany("INSERT INTO readers VALUES (?,?,?,?,?,?)", readers)

    # ---- borrow_records ----
    records = []
    rec_id = 1
    start, end = date(2024, 1, 1), date(2025, 6, 30)
    for _ in range(n_records):
        borrow = rand_date(rng, start, end)
        due = borrow + timedelta(days=30 if rng.random() < 0.8 else 60)
        # 越近期的借阅越可能未归还
        unreturned = rng.random() < (0.6 if borrow > date(2025, 5, 1) else 0.12)
        ret = None if unreturned else (borrow + timedelta(days=rng.randint(3, 45))).isoformat()
        # 末尾8本图书保留为"零借阅"，保证"从未被借阅"类查询有非空结果
        records.append((rec_id, rng.randint(1, n_readers), rng.randint(101, 100 + n_books - 8),
                        borrow.isoformat(), due.isoformat(), ret, rng.choices([0, 1, 2], [75, 20, 5])[0]))
        rec_id += 1
    # 固定保障记录：确保按姓名引用的测试用例结果非空
    fixed = [
        (rec_id,     1, 101, "2025-03-02", "2025-04-02", "2025-03-28", 0),  # 王晓明借过《数据库系统概念》
        (rec_id + 1, 1, 103, "2025-05-11", "2025-06-11", None,          1),  # 王晓明未归还《人工智能：现代方法》
        (rec_id + 2, 2, 101, "2025-02-14", "2025-03-14", "2025-03-10", 0),
        (rec_id + 3, 3, 107, "2025-03-05", "2025-04-05", "2025-04-01", 0),
        (rec_id + 4, 4, 109, "2025-04-15", "2025-05-15", None,          0),
    ]
    records.extend(fixed)
    cur.executemany("INSERT INTO borrow_records VALUES (?,?,?,?,?,?,?)", records)

    conn.commit()
    for t in ["locations", "publishers", "categories", "books", "readers", "borrow_records"]:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<16} {n} rows")
    conn.close()
    print(f"数据库已生成: {db_path}")


def get_ddl_text() -> str:
    """返回注入 Prompt 用的建表语句文本。"""
    return (
        "-- 高校图书馆核心业务数据库（SQLite）。日期字段为 'YYYY-MM-DD' 文本；未归还时 return_date 为 NULL。\n"
        "CREATE TABLE books (book_id INTEGER PRIMARY KEY, isbn TEXT, title TEXT, author TEXT, "
        "publisher_id INTEGER, category_id INTEGER, publish_year INTEGER, total_copies INTEGER, available_copies INTEGER);\n"
        "CREATE TABLE readers (reader_id INTEGER PRIMARY KEY, name TEXT, student_id TEXT, department TEXT, "
        "reader_type TEXT /*本科生/研究生/教师*/, register_date TEXT);\n"
        "CREATE TABLE borrow_records (record_id INTEGER PRIMARY KEY, reader_id INTEGER, book_id INTEGER, "
        "borrow_date TEXT, due_date TEXT, return_date TEXT, renew_count INTEGER);\n"
        "CREATE TABLE categories (category_id INTEGER PRIMARY KEY, category_name TEXT, parent_category INTEGER, location_id INTEGER);\n"
        "CREATE TABLE publishers (publisher_id INTEGER PRIMARY KEY, publisher_name TEXT, address TEXT);\n"
        "CREATE TABLE locations (location_id INTEGER PRIMARY KEY, location_name TEXT, floor INTEGER, shelf_range TEXT);"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/library.db")
    args = ap.parse_args()
    build(args.db)
