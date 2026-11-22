# storage.py - Table storage + PK index + JSON persistence
import json, os

DATA_DIR = "data"

class Table:
    def __init__(self, name, columns, pk=None, data_dir=DATA_DIR):
        # columns: list of (name, type) e.g. [("id","INTEGER"), ("name","TEXT")]
        self.name = name
        self.columns = columns
        self.pk = pk
        self.data_dir = data_dir
        self.rows = []  # list[dict]
        self.index = {}  # pk value -> row index in self.rows (B-tree substitute: dict = O(1))
        os.makedirs(data_dir, exist_ok=True)
        self._load()

    def _file(self):
        return os.path.join(self.data_dir, f"{self.name}.json")

    def _load(self):
        if not os.path.exists(self._file()):
            return
        try:
            with open(self._file()) as f:
                data = json.load(f)
            self.rows = data.get("rows", [])
            self._rebuild_index()
        except Exception:
            self.rows = []

    def _rebuild_index(self):
        self.index = {}
        if self.pk:
            for i, r in enumerate(self.rows):
                self.index[r.get(self.pk)] = i

    def save(self):
        with open(self._file(), "w") as f:
            json.dump({"columns": self.columns, "pk": self.pk, "rows": self.rows}, f)

    def _check_type(self, col, val):
        # Find type for col
        typ = dict(self.columns).get(col, "TEXT")
        if val is None:
            return True
        if typ == "INTEGER":
            return isinstance(val, int) and not isinstance(val, bool)
        if typ == "TEXT":
            return isinstance(val, str)
        if typ == "BOOLEAN":
            return isinstance(val, bool)
        return True

    def insert(self, row):
        # Validate columns + types + PK
        for col, val in row.items():
            if col not in dict(self.columns):
                raise ValueError(f"Unknown column {col}")
            if not self._check_type(col, val):
                raise ValueError(f"Type error: {col} expects {dict(self.columns)[col]}, got {val!r}")
        if self.pk:
            pk_val = row.get(self.pk)
            if pk_val is None:
                raise ValueError(f"Primary key {self.pk} cannot be NULL")
            if pk_val in self.index:
                raise ValueError(f"Duplicate primary key {self.pk}={pk_val}")
        self.rows.append(row)
        if self.pk:
            self.index[row[self.pk]] = len(self.rows) - 1
        return row

    def scan(self, where=None):
        # Full scan - returns matching rows
        if not where:
            return list(self.rows)
        return [r for r in self.rows if where(r)]

    def lookup_pk(self, pk_val):
        # Indexed lookup - O(1)
        if not self.pk:
            return None
        i = self.index.get(pk_val)
        return self.rows[i] if i is not None else None
