import asyncio

from database import create_engine, init_db


async def main() -> None:
    engine = create_engine("postgresql+asyncpg://postgres:postgres@db:5432/onboarding")
    await init_db(engine)
    await engine.dispose()
    print("init_ok")


if __name__ == "__main__":
    asyncio.run(main())
