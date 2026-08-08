import argparse
import asyncio
from pathlib import Path

from app.db.session import SessionLocal, engine
from app.services.problem_import import import_problem_seed, load_seed_document


async def run(path: Path) -> None:
    document = load_seed_document(path)
    async with SessionLocal() as db:
        result = await import_problem_seed(db, document)
    await engine.dispose()
    print(result.model_dump_json())


def main() -> None:
    parser = argparse.ArgumentParser(description="幂等导入 CodeArena 题目种子")
    parser.add_argument("path", type=Path, help="YAML 或 JSON 种子文件路径")
    args = parser.parse_args()
    asyncio.run(run(args.path))


if __name__ == "__main__":
    main()
