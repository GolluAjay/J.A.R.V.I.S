#!/usr/bin/env python3
"""
JARVIS RAG Knowledge Pipeline
Load your documents and query them with the LLM
"""

import os
import json
import subprocess
import glob

class KnowledgeBase:
    def __init__(self, knowledge_dir=None, work_partner=None):
        if knowledge_dir:
            self.knowledge_dir = knowledge_dir
        else:
            from jarvis.core.paths import knowledge_dir as _knowledge_dir

            self.knowledge_dir = str(_knowledge_dir())
        
        self.index_file = os.path.join(self.knowledge_dir, ".index.json")
        self.load_index()
        self._kg_error = None
        self.work_partner = work_partner
        if self.work_partner is None:
            try:
                from jarvis.graph.work_partner import WorkPartner
                self.work_partner = WorkPartner()
            except Exception as exc:
                self.work_partner = None
                self._kg_error = str(exc)
    
    def load_index(self):
        """Load or create knowledge index"""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
        else:
            self.index = {}
    
    def save_index(self):
        """Save knowledge index"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
    def add_document(self, filename, content=None):
        """Add a document to knowledge base"""
        filepath = os.path.join(self.knowledge_dir, filename)
        
        if content is None and os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()
        
        if content:
            # Simple chunking (split by paragraphs)
            chunks = self._chunk_text(content)
            self.index[filename] = {
                'chunks': chunks,
                'size': len(content)
            }
            self.save_index()
            if self.work_partner and self.work_partner.is_available():
                try:
                    self.work_partner.bootstrap_schema()
                    self.work_partner.index_document_from_text(
                        source_id=filename,
                        text=content,
                        source_type="knowledge_file",
                        chunks=chunks,
                    )
                except Exception as exc:
                    self._kg_error = str(exc)
            return f"Added {filename} with {len(chunks)} chunks"
        
        return f"Could not add {filename}"
    
    def _chunk_text(self, text, chunk_size=500):
        """Split text into chunks"""
        words = text.split()
        chunks = []
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            chunks.append(chunk)
        return chunks
    
    def query(self, question, top_k=2):
        """Query knowledge base"""
        if not self.index:
            return None

        if self.work_partner and self.work_partner.is_available():
            try:
                self.work_partner.bootstrap_schema()
                evidence, _timings = self.work_partner.hybrid_retrieve(question, top_k=top_k)
                if evidence:
                    lines = []
                    for ev in evidence:
                        lines.append(
                            f"[{ev.evidence_id}] {ev.source_id}#{ev.chunk_index} (score={ev.score:.2f})\n{ev.text}"
                        )
                    return "\n\n".join(lines)
            except Exception as exc:
                self._kg_error = str(exc)
        
        # Simple keyword matching (can be upgraded to embeddings)
        question_words = question.lower().split()
        scores = {}
        
        for doc, data in self.index.items():
            score = 0
            for chunk in data.get('chunks', []):
                chunk_words = chunk.lower().split()
                for qw in question_words:
                    if qw in chunk_words:
                        score += 1
            if score > 0:
                scores[doc] = score
        
        if not scores:
            return None
        
        # Get top results
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        context = ""
        for doc, score in sorted_docs[:top_k]:
            chunks = self.index[doc].get('chunks', [])
            if chunks:
                context += f"[From {doc}]: {chunks[0]}\n"
        
        return context.strip() if context else None

    def kg_status(self):
        """Return knowledge graph status string."""
        if self.work_partner and self.work_partner.is_available():
            return self.work_partner.status()
        if self._kg_error:
            return f"KG unavailable: {self._kg_error}"
        return "KG unavailable"
    
    def list_documents(self):
        """List all documents"""
        return list(self.index.keys())
    
    def status(self):
        """Show knowledge base status"""
        docs = self.list_documents()
        if docs:
            total = sum(self.index[d].get('size', 0) for d in docs)
            return f"{len(docs)} documents, {total} characters"
        return "Empty"


def init_knowledge():
    """Initialize knowledge base with sample docs"""
    kb = KnowledgeBase()
    
    # Create sample documents
    samples = {
        'about_me.txt': """My name is JARVIS. I am an AI assistant inspired by Tony Stark's Jarvis.
I was created to help with development tasks, smart home control, and answering questions.
I run locally using the Llama large language model.""",
        
        'commands.txt': """Available commands:
- voice: Activate voice mode
- chat: Text chat mode  
- status: Check system status
- knowledge query: Search my knowledge base
I can understand natural language and respond helpfully.""",
        
        'tech_stack.txt': """My tech stack:
- Ollama with Llama3 for AI brain
- macOS for voice input/output
- Python for core logic
- Redis for caching
I am completely local and free to use."""
    }
    
    # Write sample docs
    for filename, content in samples.items():
        filepath = os.path.join(kb.knowledge_dir, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content)
            kb.add_document(filename)
    
    return kb


if __name__ == "__main__":
    print("Initializing knowledge base...")
    kb = init_knowledge()
    print(f"Knowledge base: {kb.status()}")
    print(f"Documents: {kb.list_documents()}")