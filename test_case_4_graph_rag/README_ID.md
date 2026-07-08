# Konsep Graph RAG

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
