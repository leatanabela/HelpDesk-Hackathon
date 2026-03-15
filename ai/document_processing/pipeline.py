import os
import tempfile
import httpx
from supabase import create_client

from ai.config import settings
from ai.document_processing.extractor import extract_text
from ai.document_processing.chunker import chunk_text
from ai.embedding_service.embeddings import generate_embeddings

#creierul, asambleaza tot ce am facut pana acum intr-un singur loc, pentru a procesa un document de la A la Z, fara sa ne mai batem capul cu detaliile tehnice

def get_supabase():
    """Inițializează clientul pentru baza de date Supabase."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

async def process_document(document_id: str, file_path: str | None = None):
    """
    Pipeline complet de procesare a unui document:
    1. Descărcare -> 2. Extracție Text -> 3. Chunking -> 4. Embeddings -> 5. Salvare DB
    """
    supabase = get_supabase()

    # Pasul 0: Verificăm dacă documentul există în baza de date
    doc = supabase.table("documents").select("*").eq("id", document_id).single().execute()
    if not doc.data:
        raise ValueError(f"Documentul {document_id} nu a fost găsit")

    doc_data = doc.data
    local_path = file_path

    # Dacă nu avem fișierul local, îl descărcăm din storage-ul Supabase
    if not local_path:
        local_path = await _download_from_storage(doc_data["file_url"], doc_data["file_name"])

    try:
        # Pasul 1: Extracția textului brut din document folosind extractorul nostru
        text = extract_text(local_path)
        if not text.strip():
            raise ValueError("Nu s-a putut extrage text din document")

        # Pasul 2: Împărțirea în bucăți (folosind splitter-ul tău)
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("Procesul de chunking a eșuat")

        # Pasul 3: Generarea de "embeddings" (reprezentări numerice ale textului)
        # Se procesează în seturi de câte 32 pentru a nu bloca memoria/API-ul
        all_embeddings = []
        batch_size = 32
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            embeddings = generate_embeddings(batch)
            all_embeddings.extend(embeddings)

        # Pasul 4: Curățăm vechile date dacă re-procesăm documentul
        supabase.table("document_chunks").delete().eq("document_id", document_id).execute()

        # Pasul 5: Pregătim înregistrările pentru baza de date (text + vector numeric)
        chunk_records = []
        for idx, (chunk_content, embedding) in enumerate(zip(chunks, all_embeddings)):
            chunk_records.append({
                "document_id": document_id,
                "content": chunk_content,
                "embedding": embedding, # Vectorul care permite căutarea semantică
                "chunk_index": idx,
                "metadata": {
                    "source": doc_data["file_name"],
                    "title": doc_data["title"],
                },
            })

        # Inserăm bucățile în baza de date în seturi de câte 50
        for i in range(0, len(chunk_records), 50):
            batch = chunk_records[i : i + 50]
            supabase.table("document_chunks").insert(batch).execute()

        # Pasul 6: Marcăm documentul ca "procesat" cu succes
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
        # Ștergem fișierul temporar de pe disc pentru a nu ocupa spațiu degeaba
        if not file_path and local_path and os.path.exists(local_path):
            os.unlink(local_path)


async def _download_from_storage(file_url: str, file_name: str) -> str:
    """Descarcă un fișier de la un URL într-o locație temporară locală."""
    ext = os.path.splitext(file_name)[1]#Extrage extensia fișierului (ex: .pdf sau .docx). E important să știm ce fel de fișier descărcăm.
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)#Creează un fișier temporar pe hard disk. delete=False îi spune calculatorului: 
    #„Nu-l șterge imediat ce îl închid, am nevoie de el pentru procesare!”.

    async with httpx.AsyncClient() as client:#Deschide un „browser” invizibil și rapid (client HTTP) pentru a descărca fișierul.
        response = await client.get(file_url)#Trimite cererea către adresa unde e stocat fișierul și așteaptă să primească datele.
        response.raise_for_status()#Verifică dacă descărcarea a reușit. Dacă link-ul e mort sau serverul e picat, „țipă” (aruncă o eroare) și se oprește.
        tmp.write(response.content)#rie tot conținutul primit (biții și octeții fișierului) în fișierul temporar creat anterior.

    tmp.close()
    return tmp.name#Trimite înapoi calea exactă de pe hard disk (ex: C:\Temp\tmp_123.pdf) unde a fost salvat fișierul.


async def process_all_unprocessed():
    """Funcție utilitară care procesează automat toate documentele noi din DB."""
    supabase = get_supabase()#Se conectează la baza de date.

    # Căutăm documentele care au is_processed = False
    #Aceasta este o interogare. Spune bazei de date:
    #  „Dă-mi ID-urile tuturor documentelor care au eticheta is_processed setată pe False (adică cele noi, necitite)”.
    docs = (
        supabase.table("documents")
        .select("id")
        .eq("is_processed", False)
        .execute()
    )

    results = []
    for doc in docs.data or []:#Ia fiecare document găsit, unul câte unul și îl trimite la funcția de procesare.
        # Dacă ceva nu merge bine, prinde eroarea și o adaugă în rezultate, astfel încât să știm ce s-a întâmplat.
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
# -----------------.