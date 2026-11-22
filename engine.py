# engine.py - SQL parser + execution + transactions
import re
from storage import Table

class MiniSQL:
    def __init__(self, data_dir="data"):
        self.data_dir = data_dir
        self.tables = {}  # name -> Table
        self.in_tx = False
        self.tx_backup = None  # {table: rows copy}

    def _get_table(self, name):
        if name not in self.tables:
            raise ValueError(f"Table {name} does not exist")
        return self.tables[name]

    def _parse_value(self, raw):
        raw = raw.strip()
        if raw.lower() in ("true", "false"):
            return raw.lower() == "true"
        if raw.startswith("'") and raw.endswith("'"):
            return raw[1:-1]
        try:
            return int(raw)
        except ValueError:
            return raw

    def _parse_where(self, where_str):
        # Supports: col = val, col > val, col < val, combined with AND
        if not where_str:
            return None
        parts = re.split(r"\s+AND\s+", where_str.strip(), flags=re.I)
        conds = []
        for p in parts:
            m = re.match(r"(\w+)\s*(=|>|<|>=|<=|!=)\s*(.+)", p.strip())
            if not m:
                raise ValueError(f"Invalid WHERE: {p}")
            col, op, val_raw = m.groups()
            val = self._parse_value(val_raw)
            conds.append((col, op, val))
        def fn(row):
            for col, op, val in conds:
                rv = row.get(col)
                if op == "=" and not (rv == val):
                    return False
                if op == "!=" and not (rv != val):
                    return False
                if op == ">" and not (rv is not None and rv > val):
                    return False
                if op == "<" and not (rv is not None and rv < val):
                    return False
                if op == ">=" and not (rv is not None and rv >= val):
                    return False
                if op == "<=" and not (rv is not None and rv <= val):
                    return False
            return True
        return fn

    def explain(self, table, where_str):
        # Basic query plan
        if where_str and table.pk and re.match(rf"\s*{table.pk}\s*=\s*.+", where_str.strip()):
            return "INDEX SCAN (PK)"
        return "FULL SCAN"

    def execute(self, sql):
        sql = sql.strip()
        if not sql:
            return ("OK", "empty")
        upper = sql.upper()

        # --- TRANSACTION ---
        if upper.startswith("BEGIN"):
            if self.in_tx:
                raise ValueError("Transaction already started")
            self.in_tx = True
            self.tx_backup = {n: [dict(r) for r in t.rows] for n, t in self.tables.items()}
            return ("OK", "Transaction started")
        if upper.startswith("COMMIT"):
            if not self.in_tx:
                raise ValueError("No transaction")
            for t in self.tables.values():
                t.save()
            self.in_tx = False
            self.tx_backup = None
            return ("OK", "Transaction committed")
        if upper.startswith("ROLLBACK"):
            if not self.in_tx:
                raise ValueError("No transaction")
            for name, rows in self.tx_backup.items():
                self.tables[name].rows = [dict(r) for r in rows]
                self.tables[name]._rebuild_index()
            self.in_tx = False
            self.tx_backup = None
            return ("OK", "Transaction rolled back")

        # --- CREATE TABLE ---
        m = re.match(r"CREATE\s+TABLE\s+(\w+)\s*\((.+)\)", sql, re.I | re.S)
        if m:
            name, cols_str = m.groups()
            if name in self.tables:
                raise ValueError(f"Table {name} already exists")
            cols = []
            pk = None
            for part in cols_str.split(","):
                part = part.strip()
                cm = re.match(r"(\w+)\s+(INTEGER|TEXT|BOOLEAN)(\s+PRIMARY\s+KEY)?", part, re.I)
                if not cm:
                    raise ValueError(f"Invalid column: {part}")
                cname, ctype, is_pk = cm.groups()
                cols.append((cname, ctype.upper()))
                if is_pk:
                    pk = cname
            self.tables[name] = Table(name, cols, pk, self.data_dir)
            self.tables[name].save()
            return ("OK", f"Table {name} created")

        # --- INSERT ---
        m = re.match(r"INSERT\s+INTO\s+(\w+)\s+VALUES\s*\((.+)\)", sql, re.I | re.S)
        if m:
            name, vals_str = m.groups()
            t = self._get_table(name)
            # Split by comma, respecting single quotes
            vals = re.findall(r"'[^']*'|[^,]+", vals_str)
            vals = [self._parse_value(v) for v in vals]
            if len(vals) != len(t.columns):
                raise ValueError(f"Expected {len(t.columns)} values, got {len(vals)}")
            row = {col[0]: v for col, v in zip(t.columns, vals)}
            t.insert(row)
            if not self.in_tx:
                t.save()
            return ("OK", "1 row inserted")

        # --- SELECT ---
        m = re.match(r"SELECT\s+(.+?)\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+))?", sql, re.I | re.S)
        if m:
            cols_str, name, where_str = m.groups()
            t = self._get_table(name)
            plan = self.explain(t, where_str)
            where_fn = self._parse_where(where_str) if where_str else None
            # Fast path: PK = value -> indexed lookup
            rows = []
            if where_str and t.pk:
                pm = re.match(rf"\s*{t.pk}\s*=\s*(.+)", where_str.strip(), re.I)
                if pm and "AND" not in where_str.upper():
                    pk_val = self._parse_value(pm.group(1))
                    r = t.lookup_pk(pk_val)
                    if r and (not where_fn or where_fn(r)):
                        rows = [r]
                else:
                    rows = t.scan(where_fn)
            else:
                rows = t.scan(where_fn)
            if cols_str.strip() != "*":
                wanted = [c.strip() for c in cols_str.split(",")]
                rows = [{c: r.get(c) for c in wanted} for r in rows]
            return ("ROWS", {"plan": plan, "count": len(rows), "rows": rows})

        # --- UPDATE ---
        m = re.match(r"UPDATE\s+(\w+)\s+SET\s+(.+?)(?:\s+WHERE\s+(.+))?$", sql, re.I | re.S)
        if m:
            name, set_str, where_str = m.groups()
            t = self._get_table(name)
            where_fn = self._parse_where(where_str) if where_str else None
            sets = {}
            for part in set_str.split(","):
                cm = re.match(r"(\w+)\s*=\s*(.+)", part.strip())
                if not cm:
                    raise ValueError(f"Invalid SET: {part}")
                sets[cm.group(1)] = self._parse_value(cm.group(2))
            count = 0
            for r in t.rows:
                if not where_fn or where_fn(r):
                    # PK change check
                    if t.pk and t.pk in sets and sets[t.pk] != r[t.pk]:
                        if sets[t.pk] in t.index:
                            raise ValueError(f"Duplicate primary key {t.pk}={sets[t.pk]}")
                    r.update(sets)
                    count += 1
            t._rebuild_index()
            if not self.in_tx:
                t.save()
            return ("OK", f"{count} row(s) updated")

        # --- DELETE ---
        m = re.match(r"DELETE\s+FROM\s+(\w+)(?:\s+WHERE\s+(.+))?", sql, re.I | re.S)
        if m:
            name, where_str = m.groups()
            t = self._get_table(name)
            where_fn = self._parse_where(where_str) if where_str else None
            before = len(t.rows)
            t.rows = [r for r in t.rows if not (not where_fn or where_fn(r))]
            t._rebuild_index()
            if not self.in_tx:
                t.save()
            return ("OK", f"{before - len(t.rows)} row(s) deleted")

        raise ValueError(f"Invalid SQL syntax: {sql}")