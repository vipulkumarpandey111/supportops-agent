# RAG — Retrieval-Augmented Generation

A from-first-principles reference for everything we build in Phase 3, with
every concept tied back to exactly where it appears in this codebase. This
file gets updated as Phase 3 is implemented — code references point to real
files, not hypotheticals.

---

## 1. What RAG actually is

An LLM's knowledge is **parametric** — baked into its weights at training
time, frozen, and general-purpose. It knows nothing about *your* product's
refund policy, because that policy didn't exist when the model was trained
(and never will, since it's private to you).

**RAG's core idea:** before asking the LLM to answer, retrieve the small
number of relevant facts from an external knowledge source and paste them
into the prompt. The LLM then answers using that pasted context instead of
guessing from its frozen training data.

```
Without RAG:  User question ──────────────────────► LLM ──► Answer (may hallucinate)

With RAG:     User question ──► Retrieve relevant docs ──► LLM (question + docs) ──► Grounded answer
```

This is *why* RAG is the most-cited term in agentic AI: almost every
business use case needs the model to answer using **private, current,
verifiable** information — not what it memorized from the public internet
during pretraining.

**Why not just fine-tune the model on your docs instead?**
- Fine-tuning bakes facts into weights — expensive to redo every time a
  policy changes, and models still hallucinate even on data they were
  fine-tuned on (there's no way to make an LLM "cite its source" reliably
  from weights alone).
- RAG keeps facts in an external, swappable store. Change a policy doc →
  re-embed it → the agent immediately uses the new version. No retraining.
- This is why fine-tuning (Phase 9, optional) and RAG (Phase 3, core) solve
  *different* problems: RAG for facts/knowledge, fine-tuning for *behavior/
  style/format* the model should adopt.

---

## 2. The full pipeline, stage by stage

```
[Raw docs] → [Chunking] → [Embedding] → [Vector store] → [Retrieval] → [Prompt assembly] → [LLM generation]
```

### 2.1 Chunking — breaking docs into retrievable pieces

You can't embed a whole 10-page policy document as one vector — it would
be too coarse (a query about refunds would also "match" on unrelated
sections) and too big to fit usefully in a prompt.

- **Fixed-size chunking**: split by character/token count (e.g. 500 tokens),
  usually with some overlap between chunks so a sentence split across a
  boundary doesn't lose meaning. Simple, works okay for uniform text.
- **Semantic chunking**: split at natural meaning boundaries (headings,
  paragraphs, topic shifts) rather than a fixed size. Better retrieval
  quality, more implementation effort.
- **Parent-child chunking**: embed small precise chunks for matching, but
  retrieve the larger parent section around a match for context. Used when
  small chunks match well but lack surrounding context to answer fully.

**In this project**: `app/rag/ingest.py` (Phase 3) chunks by markdown
section (split on `##` headings) — a cheap form of semantic chunking that
works well for short structured policy docs, without needing a dedicated
chunking library.

### 2.2 Embeddings — turning text into meaning-vectors

An **embedding model** converts text into a fixed-length vector of numbers
(e.g. 768 dimensions) such that texts with *similar meaning* end up as
vectors that are *close together* in that 768-dimensional space — even if
they don't share any of the same words.

Example: "I want my money back" and "Requesting a refund" use completely
different words but should embed to nearby vectors, because a similarity
search needs to find the refund policy for both phrasings.

This is a **different model from your chat LLM** — embedding models are
smaller, specialized, and only do one thing: text → vector. They are *not*
generative.

**In this project**: we use `nomic-embed-text` served locally through the
same Ollama instance as `qwen2.5:7b` — one runtime, two model types. See
`app/rag/embeddings.py`.

### 2.3 Vector storage & indexing

Once every chunk is a vector, you need to store it and later ask "which
stored vectors are closest to *this* query vector?" — that's a **nearest
neighbor search**.

- At small scale (thousands of vectors), you could brute-force compare a
  query vector against every stored vector. This is exactly what `pgvector`
  does by default, and it's plenty fast for our corpus size.
- At large scale (millions+), brute force is too slow, so vector DBs use
  **approximate nearest neighbor (ANN) indexes** like **HNSW** (Hierarchical
  Navigable Small World graphs) — trading a small amount of accuracy for
  huge speed gains. `pgvector` supports HNSW indexes too, for when you
  outgrow brute force.
- **Why pgvector specifically** (vs. a dedicated vector DB like
  Qdrant/Milvus): you already run Postgres, get vector search *and*
  relational joins/filtering in one system, and it's one less service to
  operate. Dedicated vector DBs win at very large scale or when you need
  vector-DB-specific features pgvector doesn't have — not a concern at our
  scale.

**In this project**: a `ticket_docs` table in the `secdevagent-postgres`
container (Phase 0), with a `vector` column added via the `pgvector`
extension we already enabled.

### 2.4 Similarity metrics

To measure "closeness" between two vectors, common choices are:
- **Cosine similarity** — measures the *angle* between two vectors,
  ignoring their magnitude. Standard choice for text embeddings, because
  what matters is direction (meaning), not vector length.
- **Dot product** — related to cosine similarity but also affected by
  magnitude; used when the embedding model is specifically trained for it.
- **Euclidean (L2) distance** — straight-line distance; less common for
  text embeddings.

**In this project**: cosine similarity, via `pgvector`'s `<=>` operator —
the standard choice unless your embedding model's docs say otherwise.

### 2.5 Retrieval

Given a user's query, embed it with the *same* embedding model used for the
corpus, then ask the vector store for the **top-k** closest chunks (e.g.
top 3-5).

- **Metadata filtering**: you can narrow the search *before* similarity
  ranking — e.g. only search chunks tagged `category=billing`. This is
  exactly where Phase 2's Classifier output becomes useful: classify the
  ticket first, then filter retrieval to that category's docs, so a billing
  question never accidentally retrieves an unrelated technical-troubleshooting
  chunk that happens to score similarly.
- **Hybrid search**: combining vector similarity with classic keyword
  search (e.g. Postgres full-text search or BM25), useful when exact terms
  (product names, error codes) matter more than semantic similarity alone.
  Not implemented here initially — flagged as a real technique to know
  exists, not something every RAG system needs on day one.

### 2.6 Re-ranking (a market-standard refinement, not core-mandatory)

Vector similarity search is optimized for **recall** (don't miss relevant
chunks) more than **precision** (rank the single best chunk first). A
**re-ranker** — often a cross-encoder model (e.g. BGE-Rerank, Cohere
Rerank) — takes the initial top-k candidates and re-scores them more
carefully (it actually reads the query and each chunk together, rather than
comparing pre-computed vectors), producing a better final ordering before
the LLM sees them.

**In this project**: not implemented in Phase 3's MVP (our corpus is small
enough that plain top-k similarity is good enough) — but this is worth
knowing as the standard next step once retrieval quality matters more, or
corpus size grows.

### 2.7 Prompt assembly ("stuffing")

The retrieved chunks get concatenated into the prompt alongside the user's
question, usually with instructions like "answer using only the context
below; if the answer isn't in the context, say you don't know" — this
instruction is what suppresses hallucination when retrieval comes up empty,
and is just as important as the retrieval mechanism itself.

For large numbers of chunks that don't fit in context, more advanced
patterns exist (map-reduce summarization, iterative refinement) — not
needed at our scale (a handful of short policy docs).

### 2.8 Generation

The LLM (our existing `llm_client.generate()` from Phase 1) produces the
final answer, now grounded in the injected context instead of its frozen
training data.

---

## 3. Agentic RAG vs. naive RAG

**Naive RAG** (what's described above) is a single-shot pipeline: retrieve
once, generate once, done. It has a real failure mode — if the first
retrieval doesn't surface the right chunk (bad query phrasing, sparse
corpus, ambiguous ticket), the LLM either hallucinates or gives a low-
confidence non-answer, and nothing corrects that.

**Agentic RAG** turns this into a *loop* the agent controls:
1. Retrieve.
2. The agent evaluates: "is this context actually sufficient to answer?"
3. If not: rewrite the query (e.g. expand an abbreviation, try a different
   phrasing) and retrieve again — or ask a clarifying question back to the
   user — instead of blindly generating from insufficient context.
4. Only generate the final answer once the agent is confident the context
   is adequate.

This is precisely why Phase 3 (RAG) exists *before* Phase 4 (LangGraph
orchestration) in our roadmap, not merged into it: Phase 3 builds the
retrieval mechanism as a standalone, testable function. Phase 4 is where it
becomes a *loop* — the `retrieve → analyze → decide` graph with a
conditional loop-back edge is literally agentic RAG's self-correction step,
implemented as a LangGraph conditional edge.

---

## 4. Common failure modes (worth recognizing when debugging)

- **Retrieval mismatch**: the query and the relevant chunk are conceptually
  related but embed far apart (e.g. very different vocabulary) — the
  single most common RAG bug, and why testing retrieval quality in
  isolation (before adding generation on top) matters.
- **Lost-in-the-middle**: LLMs pay less attention to information buried in
  the middle of a long prompt than to the start/end — relevant with many
  retrieved chunks stuffed into one prompt.
- **Chunk boundary cuts**: a chunk boundary falls exactly where the answer
  was, splitting it across two chunks, neither of which alone answers the
  question — why chunk overlap and parent-child chunking exist.
- **Stale index**: a doc changes but its embedding wasn't regenerated — the
  agent confidently answers with outdated policy. Requires a re-ingestion
  step whenever source docs change (a real operational concern in
  production RAG systems).

---

## 5. How this maps to our project, concretely

| Concept | Where it lives in this repo |
|---|---|
| Source docs (fictional product) | `data/docs/*.md` (Phase 3) |
| Chunking | `app/rag/ingest.py` — splits markdown by `##` heading |
| Embedding model | `nomic-embed-text` via the same local Ollama server |
| Embedding client | `app/rag/embeddings.py` |
| Vector storage | `pgvector` extension, `ticket_docs` table in `secdevagent-postgres` |
| Similarity metric | Cosine similarity (`<=>` operator) |
| Retrieval + metadata filter | `app/rag/retriever.py` — filters by the Classifier's `category` output |
| Prompt assembly + generation | Reuses `app/llm_client.py` from Phase 1 |
| Agentic loop (retry/rewrite) | Deferred to Phase 4's LangGraph graph |
| Re-ranking, hybrid search | Known, deliberately deferred — corpus too small to need them yet |

## 6. Evaluation preview (formalized properly in Phase 7)

Two separate things get evaluated in a RAG system, and it's a common
mistake to only check one:
- **Retrieval quality**: did we fetch the right chunk at all? (precision@k,
  recall@k — "was the correct doc in the top-k results?")
- **Generation quality**: given the retrieved chunk, did the LLM actually
  produce a correct, faithful answer? (faithfulness — does the answer
  actually follow from the retrieved text, or did the model still add
  unsupported claims on top of good context?)

A RAG pipeline can fail at either stage independently — good retrieval with
bad generation, or bad retrieval that generation can't recover from no
matter how good the LLM is. Phase 7 (Ragas/DeepEval) measures both.
