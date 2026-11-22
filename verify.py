from engine import MiniSQL
db = MiniSQL(data_dir='test_data')
print(db.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)"))
print(db.execute("INSERT INTO users VALUES (1, 'Ada')"))
print(db.execute("SELECT * FROM users"))
print(db.execute("SELECT * FROM users WHERE id = 1"))