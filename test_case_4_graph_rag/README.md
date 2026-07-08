# Graph RAG Concept (Konsep Graph RAG)

---

## English Version

1. **What is Graph RAG?**
   Graph RAG combines Retrieval-Augmented Generation with Knowledge Graphs. Instead of just searching flat vector spaces, it retrieves structured information from a graph database containing entities (nodes) and their semantic connections (edges).

2. **How Neo4j Improves Retrieval and Reasoning**
   Neo4j stores relationships as first-class citizens. Unlike pure vector search, Neo4j allows multi-hop querying (e.g., finding connections across multiple nodes) and structural traversal. This improves factual reasoning, tracks provenance, and uncovers non-obvious linkages that vector embeddings alone often miss.

3. **Example of Context Enhancement**
   Consider the query *"What frameworks did Harrison Chase create?"*
   - **Vector DB**: Retrieves documents mentioning "Harrison Chase" or "LangChain" based on semantic similarity.
   - **Neo4j**: Directly traverses the structured relation:
     `(Harrison Chase:Person) -[:CREATED]-> (LangChain:Framework)`
     The context passed to the LLM is precise, structured, and factual, showing the direct relationship without relying on proximity calculations.

---

## Versi Bahasa Indonesia

1. **Apa itu Graph RAG?**
   Graph RAG menggabungkan Retrieval-Augmented Generation (RAG) dengan Knowledge Graphs. Alih-alih hanya mencari di ruang vektor yang datar (flat), metode ini mengambil informasi terstruktur dari database grafik yang berisi entitas (node) dan hubungan semantiknya (edge).

2. **Bagaimana Neo4j Meningkatkan Pencarian dan Penalaran**
   Neo4j menyimpan hubungan antar-data sebagai entitas utama (*first-class citizens*). Berbeda dengan pencarian vektor murni, Neo4j memungkinkan pencarian *multi-hop* (menghubungkan beberapa node sekaligus) dan penelusuran struktural. Hal ini meningkatkan penalaran faktual, melacak asal-usul data (*provenance*), dan menemukan hubungan tersembunyi yang sering kali terlewatkan oleh vektor embedding biasa.

3. **Contoh Peningkatan Konteks**
   Misalkan ada query: *"Framework apa yang dibuat oleh Harrison Chase?"*
   - **Vector DB**: Mengambil dokumen acak yang mirip secara semantik seputar "Harrison Chase" atau "LangChain".
   - **Neo4j**: Langsung menelusuri hubungan terstruktur yang pasti: 
     `(Harrison Chase:Person) -[:CREATED]-> (LangChain:Framework)`
     Konteks yang dikirim ke LLM menjadi sangat presisi, terstruktur, dan faktual tanpa bergantung pada kalkulasi kedekatan jarak vektor.
