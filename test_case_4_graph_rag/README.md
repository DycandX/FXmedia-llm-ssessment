# Graph RAG Concept

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
