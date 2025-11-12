"""
Test Database Connection
Save as: test_db.py
Run: python test_db.py
"""
import pymysql

# Test connection without database
print("Testing connection to LOCAL MySQL server...")
print("=" * 60)
print("\nTesting connection...")
print("-" * 60)

try:
    connection = pymysql.connect(
        host="127.0.0.1",
        port=3306,
        user="root",
        password="",
        database="lpelk_panveliq_db"
    )
    print("✅ CONNECTION SUCCESSFUL!")
    
    cursor = connection.cursor()
    
    # Show all tables in lpelk_panveliq_db
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print(f"\n📋 Tables in lpelk_panveliq_db:")
    if tables:
        for table in tables:
            print(f"  - {table[0]}")
    else:
        print("  (No tables found)")
    
    # Show row count for each table
    print(f"\n📊 Table row counts:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  - {table[0]}: {count} rows")
    
    cursor.close()
    connection.close()
    
except Exception as e:
    print(f"❌ CONNECTION FAILED!")
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("Test completed!")
print("=" * 60)