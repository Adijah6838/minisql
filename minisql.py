# minisql.py - CLI REPL
from engine import MiniSQL

def main():
    db = MiniSQL()
    print("MiniSQL. Type SQL, EXIT to quit. Example: SELECT * FROM users")
    while True:
        try:
            sql = input("minisql> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not sql:
            continue
        if sql.upper() in ("EXIT", "QUIT"):
            break
        try:
            kind, res = db.execute(sql)
            if kind == "ROWS":
                print(f"[{res['plan']}] {res['count']} row(s)")
                for r in res["rows"][:20]:
                    print(r)
                if res["count"] > 20:
                    print("... truncated to 20")
            else:
                print(res)
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    main()