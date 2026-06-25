from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any

from app.knowledge.embedder import embed_texts, embedding_dim
from app.knowledge.ingestion import load_policy_faq_records


logger = logging.getLogger(__name__)

POINT_NAMESPACE = uuid.UUID("4f6c0a06-5e7d-4f76-9b3b-2d4d3eb83bf2")


def _point_id_for_record_id(record_id: str) -> str:
    return str(uuid.uuid5(POINT_NAMESPACE, record_id))


def main() -> int:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    api_key = os.getenv("QDRANT_API_KEY") or None
    collection_name = os.getenv("KNOWLEDGE_QDRANT_COLLECTION", "knowledge_documents_v1")
    dim = embedding_dim()

    client = QdrantClient(host=host, port=port, api_key=api_key, timeout=30.0)
    logger.info("connecting to qdrant at %s:%s, collection=%s", host, port, collection_name)

    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )

    # Only ingest policy/FAQ records. Product knowledge belongs to the recommender's
    # product_variants_v1 collection (CLIP embeddings) and must not be duplicated here.
    records = load_policy_faq_records()
    if not records:
        logger.warning("no knowledge records found")
        return 1

    texts = [_text_for_record(record) for record in records]
    logger.info("embedding %d records", len(records))
    vectors = embed_texts(texts)

    points = [
        models.PointStruct(
            id=_point_id_for_record_id(record.id),
            vector=vector,
            payload={
                "recordId": record.id,
                "collection": record.collection,
                "sourceId": record.source_id,
                "sourceType": record.source_type,
                "title": record.title,
                "locale": record.locale,
                "chunkIndex": record.chunk_index,
                "body": record.text,
                **{k: v for k, v in record.metadata.items() if isinstance(v, (str, int, float, bool, list))},
            },
        )
        for record, vector in zip(records, vectors)
    ]

    client.upsert(collection_name=collection_name, points=points)
    logger.info("upserted %d points into %s", len(points), collection_name)
    return 0


def _text_for_record(record: Any) -> str:
    return f"{record.title}\n\n{record.text}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
