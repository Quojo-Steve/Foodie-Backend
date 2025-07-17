from sqlalchemy import create_engine

DATABASE_URI = "mysql+pymysql://press_user:gQphtPc&3$N3M@217.76.50.133:3306/pressbox_dev"

try:
    engine = create_engine(DATABASE_URI)
    with engine.connect() as connection:
        result = connection.execute("SELECT 1")
        print("✅ Database connected successfully!", result.scalar())
except Exception as e:
    print("❌ Database connection failed.")
    print(e)
