# /// script
# requires-python = ">=3.10"
# dependencies = ["pandas"]
# ///
"""
把 data/ 的三個 CSV 整理成網頁用的 docs/data.js。

docs/index.html 用 <script src="data.js"> 載入，所以直接雙擊就能開，不需要伺服器。
輸出格式：window.DATA = { enrollment, leave, depts }
- enrollment / leave：{ cols: [...], rows: [[...], ...] }，用陣列而非物件，檔案比較小
- depts：系所對照表，aliases 拆成陣列
"""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "docs" / "data.js"
CHECK_SEM, CHECK_TOTAL = "114-1", 10035

ENROLL_KEYS = ["semester", "college", "dept", "degree", "gender"]
LEAVE_KEYS = ["semester", "college", "dept", "degree", "gender", "reason"]


def load(name):
    return pd.read_csv(DATA / name, encoding="utf-8-sig")


def table(df, keys, values):
    """依 keys 加總 values，回傳 {cols, rows}。"""
    g = df.groupby(keys, sort=False)[values].sum().reset_index()
    return {"cols": keys + values, "rows": g.values.tolist()}


def main():
    enroll = load("enrollment.csv")
    leave = load("leave.csv")
    mapping = load("dept_mapping.csv").fillna("")

    # 核對：在學人數合計
    total = int(enroll.loc[enroll.semester == CHECK_SEM, "count"].sum())
    if total != CHECK_TOTAL:
        raise SystemExit(f"❌ {CHECK_SEM} 在學人數合計 {total}，應為 {CHECK_TOTAL}")
    print(f"✅ {CHECK_SEM} 在學人數合計 {total}")

    enrollment = table(enroll, ENROLL_KEYS, ["count"])
    leave_tbl = table(leave, LEAVE_KEYS, ["new_leave", "on_leave_end"])
    depts = [{"dept": r.dept, "college": r.college,
              "aliases": [a for a in r.aliases.split(";") if a]}
             for r in mapping.itertuples()]

    payload = {"enrollment": enrollment, "leave": leave_tbl, "depts": depts}
    OUT.parent.mkdir(exist_ok=True)
    text = "window.DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(text, encoding="utf-8")
    print(f"寫入 {OUT}：{len(text.encode('utf-8')) / 1024:.1f} KB；"
          f"在學 {len(enrollment['rows'])} 列、休學 {len(leave_tbl['rows'])} 列、系所 {len(depts)} 個")


if __name__ == "__main__":
    main()
