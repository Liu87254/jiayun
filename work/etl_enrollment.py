# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas", "python-calamine", "xlrd"]
# ///
"""
把 114-1 在學人數 .xls（第一個工作表）轉成 work/enrollment_114-1.csv。

每列 = 系所 × 學制 × 性別，欄位：college, dept_raw, program_raw, gender, count
"""
import re
from pathlib import Path
import pandas as pd
import xlrd

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "東華大學統計資料" / "在學人數統計表"
OUT = ROOT / "work" / "enrollment_114-1.csv"

# 報表的學制標籤（第 0 欄）→ 標準學制名稱；「碩專班」底下是碩士在職專班
PROGRAM_LABELS = [("博士班", "博士班"), ("碩士班", "碩士班"),
                  ("碩專班", "碩士在職專班"), ("學士班", "學士班")]

# 欄位位置：學制(0)、學院(1)、系所(2)、分組(3)；第 4 欄是「合計」，第 5、6 欄才是女、男
COL_LABEL, COL_COLLEGE, COL_DEPT = 0, 1, 2
COL_FEMALE, COL_MALE = 5, 6

strip_note = lambda s: re.sub(r"[（(].*?[)）]", "", str(s)).strip()


def cell(v):
    return "" if pd.isna(v) else str(v).strip()


def num(v):
    x = pd.to_numeric(v, errors="coerce")
    return 0 if pd.isna(x) else int(x)


def find_source() -> Path:
    files = sorted(SRC_DIR.glob("114-1*.xls"))
    if len(files) != 1:
        raise SystemExit(f"預期找到 1 個 114-1 的 .xls，實際：{files}")
    return files[0]


def merged_rows(path: Path, col: int) -> set[int]:
    """回傳位於某個合併儲存格範圍內的列號（0-based）。calamine 讀不到合併資訊，所以用 xlrd。"""
    sh = xlrd.open_workbook(path, formatting_info=True).sheet_by_index(0)
    return {r for rlo, rhi, clo, chi in sh.merged_cells if clo <= col < chi
            for r in range(rlo, rhi)}


def main():
    path = find_source()
    raw = pd.read_excel(path, sheet_name=0, header=None, engine="calamine", dtype=object)
    in_dept_merge = merged_rows(path, COL_DEPT)

    rows, program, college, dept = [], None, "", None
    for r in range(4, len(raw)):  # 0–3 列是標題與「總計」，跳過
        label = cell(raw.iat[r, COL_LABEL])
        if label.startswith("備註"):
            break  # 最下方的備註不是資料
        for key, name in PROGRAM_LABELS:
            if label.startswith(key):
                program = name
        if "合計" in label or "總計" in label:
            continue  # 小計列不是資料列

        # 學院只寫在合併範圍的第一格，往下沿用
        if cell(raw.iat[r, COL_COLLEGE]):
            college = strip_note(raw.iat[r, COL_COLLEGE])

        # 系所寫在合併範圍的第一格：範圍內沿用上一個系所，範圍外（沒有合併）留待往下找
        labeled = bool(cell(raw.iat[r, COL_DEPT]))
        if labeled:
            dept = cell(raw.iat[r, COL_DEPT])
        elif r not in in_dept_merge:
            dept = None
        if program is None:
            continue

        rows.append(dict(r=r, college=college, dept_raw=dept, labeled=labeled, program_raw=program,
                         female=num(raw.iat[r, COL_FEMALE]), male=num(raw.iat[r, COL_MALE])))

    # 沒有合併、也沒有系所名稱的列：歸到同學制裡下一個有名稱的系所
    for i, rec in enumerate(rows):
        if rec["dept_raw"] is None:
            nxt = next(x for x in rows[i + 1:]
                       if x["labeled"] and x["program_raw"] == rec["program_raw"])
            rec["dept_raw"] = nxt["dept_raw"]
            print(f"第 {rec['r'] + 1} 列未在合併範圍內，歸入下一個系所：{nxt['dept_raw']}")

    df = pd.DataFrame(rows)
    # 同一系所、同一學制下的分組（如一般組、國際組）加總
    agg = (df.groupby(["college", "dept_raw", "program_raw"], sort=False)[["female", "male"]]
             .sum().reset_index())
    long = agg.melt(id_vars=["college", "dept_raw", "program_raw"],
                    value_vars=["female", "male"], var_name="gender", value_name="count")
    long["gender"] = long["gender"].map({"female": "女", "male": "男"})
    long = long[["college", "dept_raw", "program_raw", "gender", "count"]]

    OUT.parent.mkdir(exist_ok=True)
    long.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"寫入 {OUT}：{len(long)} 列；女 {long.loc[long.gender=='女','count'].sum()}、"
          f"男 {long.loc[long.gender=='男','count'].sum()}")


if __name__ == "__main__":
    main()
