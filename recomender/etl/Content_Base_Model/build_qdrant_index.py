from __future__ import annotations

import argparse
import logging

from .qdrant_vector_store import QdrantVectorStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Qdrant collection from hybrid embeddings")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and rebuild the collection even if it already exists",
    )
    args = parser.parse_args()

    store = QdrantVectorStore()
    store.ensure_collection(recreate=args.recreate)

    logger.info(
        "Qdrant collection ready: collection=%s size=%s",
        store.config.COLLECTION,
        store.collection_size(),
    )


if __name__ == "__main__":
    main()
