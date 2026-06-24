"""
Database Connection Test
Quick script to verify PostgreSQL, MongoDB, and Redis are accessible.
"""
import asyncio
import asyncpg
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis


# ========================================================
# Configuration
# ========================================================
POSTGRES_URL = "postgresql://bi_user:bi_password@localhost:5432/bi_platform"
MONGO_URL = "mongodb://localhost:27017"
REDIS_URL = "redis://localhost:6379/0"


# ========================================================
# Test PostgreSQL
# ========================================================
async def test_postgres():
    """Test PostgreSQL connection."""
    print("\nTesting PostgreSQL...")
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        version = await conn.fetchval("SELECT version();")
        await conn.close()
        print(f"  [OK] PostgreSQL connected!")
        print(f"  Version: {version[:60]}...")
        return True
    except Exception as e:
        print(f"  [FAIL] PostgreSQL: {e}")
        return False


# ========================================================
# Test MongoDB
# ========================================================
async def test_mongo():
    """Test MongoDB connection."""
    print("\nTesting MongoDB...")
    try:
        client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
        info = await client.server_info()
        client.close()
        print(f"  [OK] MongoDB connected!")
        print(f"  Version: {info.get('version', 'unknown')}")
        return True
    except Exception as e:
        print(f"  [FAIL] MongoDB: {e}")
        return False


# ========================================================
# Test Redis
# ========================================================
async def test_redis():
    """Test Redis connection."""
    print("\nTesting Redis...")
    try:
        r = redis.from_url(REDIS_URL)
        await r.set("test_key", "Hello from Rawda!")
        value = await r.get("test_key")
        await r.delete("test_key")
        await r.aclose()
        print(f"  [OK] Redis connected!")
        print(f"  Test value: {value.decode()}")
        return True
    except Exception as e:
        print(f"  [FAIL] Redis: {e}")
        return False


# ========================================================
# Main
# ========================================================
async def main():
    """Run all connection tests."""
    print("=" * 60)
    print("  Database Connection Tests")
    print("=" * 60)
    
    results = await asyncio.gather(
        test_postgres(),
        test_mongo(),
        test_redis(),
    )
    
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    services = ["PostgreSQL", "MongoDB", "Redis"]
    for service, result in zip(services, results):
        status = "[OK]" if result else "[FAIL]"
        print(f"  {service:15} {status}")
    
    if all(results):
        print("\nAll databases are accessible! Ready for development.")
    else:
        print("\nSome databases failed. Check the logs above.")


if __name__ == "__main__":
    asyncio.run(main())