import os
import tempfile
import httpx
from supabase import create_client

from ai.config import settings
from ai.document_processing.extractor import extract_text
from ai.document_processing.chunker import chunk_text
from ai.embedding_service.embeddings import generate_embeddings


def get_supabase():
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


async def process_document(document_id: str, file_path: str | None = None):
    """
    Full document ingestion pipeline:
    1. Download file from Supabase storage (if no local path)
    2. Extract text
    3. Chunk text
    4. Generate embeddings with bge-m3
    5. Store chunks + embeddings in document_chunks table
    6. Update document status
    """
    supabase = get_supabase()

    # Get document record
    doc = supabase.table("documents").select("*").eq("id", document_id).single().execute()
    if not doc.data:
        raise ValueError(f"Document {document_id} not found")

    doc_data = doc.data
    local_path = file_path

    # Download file if no local path provided
    if not local_path:
        local_path = await _download_from_storage(doc_data["file_url"], doc_data["file_name"])

    try:
        # Step 1: Extract text
        text = extract_text(local_path)
        if not text.strip():
            raise ValueError("No text could be extracted from the document")

        # Step 2: Chunk text
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("Text chunking produced no chunks")

        # Step 3: Generate embeddings (in batches of 32)
        all_embeddings = []
        batch_size = 32
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = generate_embeddings(batch)
            all_embeddings.extend(embeddings)

        # Step 4: Delete existing chunks for this document (re-processing)
        supabase.table("document_chunks").delete().eq("document_id", document_id).execute()

        # Step 5: Store chunks with embeddings
        chunk_records = []
        for idx, (chunk_content, embedding) in enumerate(zip(chunks, all_embeddings)):
            chunk_records.append({
                "document_id": document_id,
                "content": chunk_content,
                "embedding": embedding,
                "chunk_index": idx,
                "metadata": {
                    "source": doc_data["file_name"],
                    "title": doc_data["title"],
                },
            })

        # Insert in batches of 50
        for i in range(0, len(chunk_records), 50):
            batch = chunk_records[i : i + 50]
            supabase.table("document_chunks").insert(batch).execute()

        # Step 6: Update document status
        supabase.table("documents").update({
            "is_processed": True,
            "chunk_count": len(chunks),
        }).eq("id", document_id).execute()

        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "status": "processed",
        }

    finally:
        # Clean up temp file if we downloaded it
        if not file_path and local_path and os.path.exists(local_path):
            os.unlink(local_path)


async def _download_from_storage(file_url: str, file_name: str) -> str:
    """Download a file from Supabase storage to a temp location."""
    ext = os.path.splitext(file_name)[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

    async with httpx.AsyncClient() as client:
        response = await client.get(file_url)
        response.raise_for_status()
        tmp.write(response.content)

    tmp.close()
    return tmp.name


async def process_all_unprocessed():
    """Process all documents that haven't been processed yet."""
    supabase = get_supabase()

    docs = (
        supabase.table("documents")
        .select("id")
        .eq("is_processed", False)
        .execute()
    )

    results = []
    for doc in docs.data or []:
        try:
            result = await process_document(doc["id"])
            results.append(result)
        except Exception as e:
            results.append({
                "document_id": doc["id"],
                "status": "error",
                "error": str(e),
            })

    return results
