from app import get_db

try:
    db = get_db()
    cur = db.cursor()

    cur.execute("SHOW TABLES")

    print("Aiven connection successful!")
    for table in cur.fetchall():
        print(table[0])

    cur.close()
    db.close()

except Exception as e:
    print("Connection error:", e)