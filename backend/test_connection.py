"""
Quick standalone connectivity test. NOT part of the DataEase app —
delete this file once you're done debugging.

Usage:
  python test_connection.py
      Tests the DATABASE_URL currently set in your .env file.

  python test_connection.py "postgresql://postgres.xxxx:PASSWORD@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres"
      Tests a specific URL you pass in directly — use this to try
      the Transaction pooler (port 6543) as an alternative.

The script only ever prints the host/port/database part of the URL
it's testing, never the credentials, and psycopg2's own error
messages don't echo the password either — so it's safe to paste the
full output back.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATABASE_URL")

if not url:
    print("No DATABASE_URL found in .env, and none was passed as an argument.")
    sys.exit(1)

# Show only what's after '@' (host/port/db) — never the user:password part.
safe_target = url.split("@")[-1] if "@" in url else url
print(f"Testing connection to: {safe_target}")

try:
    conn = psycopg2.connect(url, connect_timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT 1;")
    result = cur.fetchone()
    print(f"SUCCESS — connected and SELECT 1 returned: {result}")
    cur.close()
    conn.close()
except Exception as exc:
    print(f"FAILED — {type(exc).__name__}: {exc}")