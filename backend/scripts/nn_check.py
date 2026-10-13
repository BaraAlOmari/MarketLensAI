"""Stage 2 acceptance report: coverage, index use, and nearest-neighbor sanity -> docs/.

Three checks:
1. Query probes (EN and AR): do the 10 nearest listings belong to the expected category?
2. Cross-lingual: the same probes searched only among listings in the OTHER language.
3. Near-duplicates: is each repost's original among its 5 nearest listings? (no API calls)

Costs one embedding request per probe query (12 in total).

Usage (from backend/): .venv/Scripts/python scripts/nn_check.py
"""

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import REPO_DIR, get_settings  # noqa: E402
from app.ingestion.embed_job import to_pgvector  # noqa: E402
from app.providers.embeddings import get_embedding_provider  # noqa: E402

REPORT = REPO_DIR / "docs" / "stage2-nn-check.md"
QUERY_CACHE = REPO_DIR / "data" / "cache" / "probe_query_embeddings.jsonl"
DATASET = REPO_DIR / "data" / "listings.jsonl"
K = 10

PROBES = [  # (query, query language, expected category)
    ("used iPhone 15 Pro in good condition", "en", "phones"),
    ("MacBook Air for a university student", "en", "laptops"),
    ("Toyota Land Cruiser 2020 low mileage", "en", "cars"),
    ("comfortable sofa for the living room", "en", "furniture"),
    ("2 bedroom apartment for rent in Lusail", "en", "apartments"),
    ("villa with a private pool in Al Waab", "en", "villas"),
    ("ايفون 15 برو مستعمل بحالة ممتازة", "ar", "phones"),
    ("لابتوب للدراسة الجامعية", "ar", "laptops"),
    ("لاند كروزر موديل 2020 ممشى قليل", "ar", "cars"),
    ("كنب مريح للصالة", "ar", "furniture"),
    ("شقة غرفتين للإيجار في لوسيل", "ar", "apartments"),
    ("فيلا مع مسبح خاص في الوعب", "ar", "villas"),
]

THRESHOLDS = {"same_language": 0.9, "cross_lingual": 0.8, "near_duplicates": 0.8}

NEAREST = f"""
select id, external_id, category, language, title,
       1 - (embedding operator(extensions.<=>) $1::extensions.vector) as similarity
from listings
where embedding is not null and ($2::text is null or language <> $2)
order by embedding operator(extensions.<=>) $1::extensions.vector
limit {K}
"""


def table(headers: list[str], rows: list[list]) -> str:
    def cell(v) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


async def cached_query_vector(provider, query: str) -> list[float]:
    """Probe vectors are cached on disk so re-running the report costs no quota."""
    key = f"{provider.model}|{provider.dimension}|{provider.query_input(query)}"
    if QUERY_CACHE.exists():
        for line in QUERY_CACHE.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            if entry["key"] == key:
                return entry["vector"]
    vector = await provider.embed_query(query)
    QUERY_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with QUERY_CACHE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "vector": vector}, ensure_ascii=False) + "\n")
    return vector


def near_duplicate_pairs() -> list[tuple[str, str]]:
    pairs = []
    for line in DATASET.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if original := record["meta"].get("near_duplicate_of"):
            pairs.append((record["external_id"], original))
    return pairs


async def main() -> int:
    settings = get_settings()
    provider = get_embedding_provider(settings)
    conn = await asyncpg.connect(
        settings.database_url.get_secret_value(), statement_cache_size=0, timeout=15
    )
    try:
        await conn.execute("set hnsw.iterative_scan = 'relaxed_order'")
        total = await conn.fetchval("select count(*) from listings")
        models = await conn.fetch(
            "select coalesce(embedding_model, '(none)') as m, count(*) as n "
            "from listings group by 1 order by 2 desc"
        )
        embedded = await conn.fetchval("select count(*) from listings where embedding is not null")
        has_index = bool(await conn.fetchval("select to_regclass('listings_embedding_hnsw_idx')"))

        probe_rows, details, same_scores, cross_scores = [], [], [], []
        first_vector = None
        for query, lang, expected in PROBES:
            vector = to_pgvector(await cached_query_vector(provider, query))
            first_vector = first_vector or vector
            same = await conn.fetch(NEAREST, vector, None)
            cross = await conn.fetch(NEAREST, vector, lang)
            p_same = sum(r["category"] == expected for r in same) / max(len(same), 1)
            p_cross = sum(r["category"] == expected for r in cross) / max(len(cross), 1)
            same_scores.append(p_same)
            cross_scores.append(p_cross)
            other = sum(r["language"] != lang for r in same)
            probe_rows.append(
                [query, lang, expected, f"{p_same:.0%}", f"{other}/{len(same)}", f"{p_cross:.0%}"]
            )
            details.append((query, same[:3], cross[:3]))

        plan = await conn.fetch(
            "explain " + NEAREST.replace("($2::text is null or language <> $2)", "true"),
            first_vector,
        )

        # Near-duplicate recall@5 from stored vectors only.
        found = checked = 0
        for dup, original in near_duplicate_pairs():
            neighbours = await conn.fetch(
                """select n.external_id from listings d, lateral (
                       select external_id from listings x
                       where x.id <> d.id and x.embedding is not null
                       order by x.embedding operator(extensions.<=>) d.embedding limit 5) n
                   where d.external_id = $1 and d.embedding is not null""",
                dup,
            )
            original_embedded = await conn.fetchval(
                "select embedding is not null from listings where external_id = $1", original
            )
            if neighbours and original_embedded:
                checked += 1
                found += original in {r["external_id"] for r in neighbours}
    finally:
        await conn.close()

    scores = {
        "same_language": sum(same_scores) / len(same_scores),
        "cross_lingual": sum(cross_scores) / len(cross_scores),
        "near_duplicates": found / checked if checked else 0.0,
    }
    complete = embedded == total
    ok = complete and all(scores[k] >= v for k, v in THRESHOLDS.items())
    index_line = next((r[0] for r in plan if "Index" in r[0] or "Seq Scan" in r[0]), plan[0][0])

    out = [
        "# Stage 2 Nearest-Neighbor Check",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `backend/scripts/nn_check.py`. "
        f"Model `{provider.model}`, {provider.dimension} dimensions, cosine distance.",
        "",
        "## Acceptance",
        "",
        table(
            ["Check", "Result", "Target"],
            [
                ["Rows embedded", f"{embedded} / {total} {'✅' if complete else '❌'}", "all"],
                ["HNSW index", "present ✅" if has_index else "not built yet ❌", "present"],
                ["Query plan", index_line.strip(), "index scan"],
                *[
                    [
                        name.replace("_", " ")
                        + (
                            " (recall@5)"
                            if name == "near_duplicates"
                            else " (category precision@10)"
                        ),
                        f"{scores[name]:.0%} {'✅' if scores[name] >= t else '❌'}",
                        f">= {t:.0%}",
                    ]
                    for name, t in THRESHOLDS.items()
                ],
                ["Overall", "PASS ✅" if ok else "NOT YET ❌", ""],
            ],
        ),  # fmt: skip
        "",
        f"Near-duplicate pairs checked: {checked} (pairs where both rows are embedded).",
        "",
        "**embedding_model per row**",
        "",
        table(["embedding_model", "rows"], [[r["m"], r["n"]] for r in models]),
        "",
        "## Query probes",
        "",
        "*Precision* = share of the 10 nearest listings in the expected category. "
        "*Other-lang* = how many of those 10 are in a different language than the query. "
        "*Cross-lingual* = precision when searching only listings in the other language.",
        "",
        table(
            ["query", "lang", "expected", "precision@10", "other-lang", "cross-lingual"],
            probe_rows,
        ),
        "",
        "## Top results",
        "",
    ]
    for query, same, cross in details:
        out += [f"**{query}**", ""]
        out += [
            f"- {r['similarity']:.3f} · {r['category']} · {r['language']} · {r['title'][:80]}"
            for r in same
        ]
        out += ["- *other language only:*"]
        out += [
            f"  - {r['similarity']:.3f} · {r['category']} · {r['language']} · {r['title'][:80]}"
            for r in cross
        ]
        out.append("")
    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(
        f"{'PASS' if ok else 'NOT YET'}: embedded {embedded}/{total}, index={has_index}, "
        + ", ".join(f"{k}={v:.0%}" for k, v in scores.items())
        + f"; report written to {REPORT}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
