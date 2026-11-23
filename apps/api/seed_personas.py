import sqlite3
import datetime

conn = sqlite3.connect('d:/Projects/AgriPredict-AI anti/apps/api/preview.db')
cur = conn.cursor()

now = datetime.datetime.now(datetime.timezone.utc).isoformat()

personas = [
    ('+919876500001', 'farmer', 'Ramesh Patil'),
    ('+919876500002', 'transport_provider', 'Sunil Freight'),
    ('+919876500003', 'storage_provider', 'Sahyadri Agro Warehouse'),
    ('+919876500004', 'buyer', 'Kisan Mart Procurement'),
]

for phone, role, name in personas:
    cur.execute("SELECT id FROM users WHERE phone_e164 = ?", (phone,))
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO users (phone_e164, status, preferred_locale, display_name) VALUES (?, 'active', 'en', ?)",
            (phone, name)
        )
        uid = cur.lastrowid
        cur.execute(
            "INSERT INTO user_roles (user_id, role, granted_at) VALUES (?, ?, ?)",
            (uid, role, now)
        )
        print(f"Created user {phone} ({name}) with role {role} (ID: {uid})")
    else:
        uid = row[0]
        cur.execute("SELECT role FROM user_roles WHERE user_id = ? AND role = ?", (uid, role))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO user_roles (user_id, role, granted_at) VALUES (?, ?, ?)",
                (uid, role, now)
            )
            print(f"Added role {role} to existing user {phone} (ID: {uid})")
        else:
            print(f"User {phone} already verified with role {role} (ID: {uid})")

conn.commit()
print("All 4 persona roles successfully seeded and verified in preview.db!")
