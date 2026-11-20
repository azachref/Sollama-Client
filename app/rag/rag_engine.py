import os
import math
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.database import get_db
from app.ollama_client import OllamaClient

class RAGEngine:
    """Document parser, chunker, vector & lexical hybrid search engine."""

    @classmethod
    def extract_text(cls, file_path: Path) -> str:
        """Extract plain text from supported document types."""
        suffix = file_path.suffix.lower()
        
        # 1. PDF
        if suffix == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            pages = []
            for p in reader.pages:
                text = p.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)

        # 2. DOCX
        elif suffix in [".docx", ".doc"]:
            import docx
            doc = docx.Document(str(file_path))
            return "\n".join([p.text for p in doc.paragraphs if p.text])

        # 3. Plain text / Markdown / Code / JSON / CSV
        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    @classmethod
    def chunk_text(cls, text: str, chunk_size: int = 700, overlap: int = 150) -> List[str]:
        """Split text into overlapping chunks respecting linebreaks where possible."""
        if not text:
            return []

        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            p_len = len(para)
            if current_length + p_len <= chunk_size:
                current_chunk.append(para)
                current_length += p_len
            else:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                # Start new chunk with overlap if needed
                if p_len > chunk_size:
                    # Very large paragraph, split by sentences or slice
                    for i in range(0, p_len, chunk_size - overlap):
                        chunks.append(para[i:i + chunk_size])
                    current_chunk = []
                    current_length = 0
                else:
                    current_chunk = [para]
                    current_length = p_len

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return [c for c in chunks if len(c.strip()) > 30]

    @classmethod
    async def process_and_index_file(
        cls,
        file_path: Path,
        filename: str,
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> int:
        """Parse file, generate chunks, compute embeddings, and insert into database."""
        text = cls.extract_text(file_path)
        chunks = cls.chunk_text(text)
        if not chunks:
            return 0

        now = datetime.now().isoformat()
        conn = get_db()
        cursor = conn.cursor()

        indexed_count = 0
        for idx, chunk in enumerate(chunks):
            # Compute embedding
            embedding = await OllamaClient.get_embedding(chunk)
            chunk_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO rag_documents (id, project_id, chat_id, filename, file_type, file_path, chunk_index, text_content, embedding_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id,
                project_id,
                chat_id,
                filename,
                file_path.suffix.lower(),
                str(file_path),
                idx,
                chunk,
                json.dumps(embedding),
                now
            ))
            indexed_count += 1

        conn.commit()
        conn.close()
        return indexed_count

    @classmethod
    def _cosine_similarity(cls, vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two numeric vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @classmethod
    async def search(
        cls,
        query: str,
        project_id: Optional[str] = None,
        chat_id: Optional[str] = None,
        top_k: int = 4
    ) -> List[Dict[str, Any]]:
        """Hybrid semantic + keyword search over indexed documents."""
        query_embedding = await OllamaClient.get_embedding(query)
        keywords = [k.lower() for k in query.split() if len(k) > 2]

        conn = get_db()
        cursor = conn.cursor()

        # Build query filter based on project or chat
        where_clauses = []
        params = []
        if project_id:
            where_clauses.append("project_id = ?")
            params.append(project_id)
        if chat_id:
            where_clauses.append("chat_id = ?")
            params.append(chat_id)

        where_sql = "WHERE " + " OR ".join(where_clauses) if where_clauses else ""
        cursor.execute(f"SELECT id, filename, chunk_index, text_content, embedding_json FROM rag_documents {where_sql}", tuple(params))
        rows = cursor.fetchall()
        conn.close()

        scored_chunks = []
        for r in rows:
            text = r["text_content"]
            emb_str = r["embedding_json"]
            
            # Semantic score
            sem_score = 0.0
            if query_embedding and emb_str:
                try:
                    emb = json.loads(emb_str)
                    if emb:
                        sem_score = cls._cosine_similarity(query_embedding, emb)
                except Exception:
                    pass

            # Keyword lexical score
            kw_hits = sum(1 for kw in keywords if kw in text.lower())
            lex_score = kw_hits / (len(keywords) if keywords else 1)

            # Combined hybrid score (0.7 semantic, 0.3 lexical)
            final_score = (sem_score * 0.7) + (lex_score * 0.3)
            
            scored_chunks.append({
                "id": r["id"],
                "filename": r["filename"],
                "chunk_index": r["chunk_index"],
                "text": text,
                "score": final_score
            })

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:top_k]

    @classmethod
    def format_rag_context(cls, results: List[Dict[str, Any]]) -> str:
        """Format retrieved chunks into a prompt context block."""
        if not results:
            return ""

        context_lines = ["\n[RETRIEVED KNOWLEDGE BASE CONTEXT]"]
        for idx, item in enumerate(results):
            context_lines.append(f"--- Document: {item['filename']} (Section {item['chunk_index'] + 1}) ---")
            context_lines.append(item["text"].strip())
        context_lines.append("[END KNOWLEDGE BASE CONTEXT]\n")
        return "\n".join(context_lines)
