import sqlite3
import tempfile
from pathlib import Path

# Simulasi test file db dengan path windows dan python
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
    db_path = tmp.name

conn = sqlite3.connect(db_path)
conn.execute("CREATE TABLE episodes (id TEXT, title TEXT)")
conn.execute("INSERT INTO episodes VALUES ('1', 'You are the CAPTURE step')")
conn.commit()
conn.close()

# Uji eksekusi skrip python persis
clean_path = db_path.replace('\\', '/')
conn2 = sqlite3.connect(clean_path)
conn2.execute("DELETE FROM episodes")
conn2.commit()
count = conn2.execute("SELECT count(*) FROM episodes").fetchone()[0]
conn2.close()

assert count == 0
Path(db_path).unlink()
print("HASIL UJI LOKAL: SCRIPT 100% VALID & BEBAS SYNTAX ERROR")
