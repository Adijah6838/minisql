import time, shutil, os
from engine import MiniSQL

def fresh(name):
    d = f"test_{name}"
    shutil.rmtree(d, ignore_errors=True)
    return MiniSQL(data_dir=d)

def test_crud_and_where():
    db = fresh("crud")
    db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, active BOOLEAN)")
    db.execute("INSERT INTO users VALUES (1, 'Ada', true)")
    db.execute("INSERT INTO users VALUES (2, 'Bob', false)")
    _, res = db.execute("SELECT * FROM users WHERE active = true")
    assert res["count"] == 1 and res["rows"][0]["name"] == "Ada"
    db.execute("UPDATE users SET name = 'Ada L' WHERE id = 1")
    _, res = db.execute("SELECT * FROM users WHERE id = 1")
    assert res["rows"][0]["name"] == "Ada L"
    db.execute("DELETE FROM users WHERE id = 2")
    _, res = db.execute("SELECT * FROM users")
    assert res["count"] == 1

def test_duplicate_pk():
    db = fresh("dup")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO t VALUES (1, 'x')")
    try:
        db.execute("INSERT INTO t VALUES (1, 'y')")
        assert False, "should fail"
    except ValueError as e:
        assert "Duplicate" in str(e)

def test_invalid_queries():
    db = fresh("invalid")
    for bad in ["SELEC * FROM t", "INSERT INTO t VALUES (1)", "CREATE TABLE", "DROP TABLE t"]:
        try:
            db.execute(bad)
            assert False, f"should fail: {bad}"
        except ValueError:
            pass

def test_persistence():
    db = fresh("persist")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO t VALUES (1, 'hello')")
    # Simulate restart: new engine, reload from disk via Table load
    from storage import Table
    t = Table("t", [("id","INTEGER"),("name","TEXT")], pk="id", data_dir="test_persist")
    assert len(t.rows) == 1 and t.rows[0]["name"] == "hello"

def test_transaction_rollback():
    db = fresh("tx")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    db.execute("INSERT INTO t VALUES (1, 'a')")
    db.execute("BEGIN")
    db.execute("INSERT INTO t VALUES (2, 'b')")
    db.execute("ROLLBACK")
    _, res = db.execute("SELECT * FROM t")
    assert res["count"] == 1
    db.execute("BEGIN")
    db.execute("INSERT INTO t VALUES (2, 'b')")
    db.execute("COMMIT")
    _, res = db.execute("SELECT * FROM t")
    assert res["count"] == 2

def test_10000_and_index_vs_scan():
    db = fresh("big")
    db.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    for i in range(10000):
        db.execute(f"INSERT INTO t VALUES ({i}, 'user{i}')")
    # Indexed
    t0 = time.time()
    db.execute("SELECT * FROM t WHERE id = 9999")
    indexed = time.time() - t0
    # Full scan (non-PK)
    t0 = time.time()
    db.execute("SELECT * FROM t WHERE name = 'user9999'")
    scan = time.time() - t0
    print(f"\nIndexed: {indexed:.5f}s, Scan: {scan:.5f}s")
    _, res = db.execute("SELECT * FROM t WHERE id = 9999")
    assert res["plan"] == "INDEX SCAN (PK)"
    _, res2 = db.execute("SELECT * FROM t WHERE name = 'user9999'")
    assert res2["plan"] == "FULL SCAN"
    assert res["count"] == 1