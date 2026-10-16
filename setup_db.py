import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'LexAI')
TEST_DB_NAME = 'LexAI_test'

def setup_databases():
    print(f"Connecting to MySQL at {DB_HOST}:{DB_PORT} as '{DB_USER}'...")
    try:
        # Connect without selecting a database
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        
        print(f"Creating database '{DB_NAME}' if it doesn't exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        
        print(f"Creating database '{TEST_DB_NAME}' if it doesn't exist...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {TEST_DB_NAME}")
        
        conn.commit()
        conn.close()
        print("Databases created successfully.")
        
    except pymysql.err.OperationalError as e:
        print(f"\n[ERROR] Connection failed: {e}")
        print("Please check your DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT in .env.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    setup_databases()
