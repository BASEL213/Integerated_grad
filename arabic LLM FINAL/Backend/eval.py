"""
eval.py — AI Evaluation Framework
===================================
Runs a fixed test suite against the live chatbot and reports pass/fail.

Usage:
    cd Backend
    python eval.py

Each test case defines:
  - question : what the user asks
  - must_contain : keywords the answer MUST include (AND logic)
  - must_not_contain : keywords the answer must NOT include
  - category : for grouping results
"""

import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv("../.env")

from rag_engine import chat

TEST_CASES = [
    # ── Project listing ──────────────────────────────────────────────────────
    {
        "id": "T01",
        "category": "project_listing",
        "question": "ما هي المشاريع المتاحة؟",
        "must_contain": ["مشاريع", "متاح"],
        "must_not_contain": [],
    },
    {
        "id": "T02",
        "category": "project_listing",
        "question": "كم عدد المشاريع لديكم؟",
        "must_contain": ["مشروع"],
        "must_not_contain": [],
    },

    # ── Price queries ────────────────────────────────────────────────────────
    {
        "id": "T03",
        "category": "pricing",
        "question": "كم سعر مشروع Luxor Heritage Village؟",
        "must_contain": ["600", "جنيه"],
        "must_not_contain": [],
    },
    {
        "id": "T04",
        "category": "pricing",
        "question": "ما هي أسعار مشروع Marsa Matrouh Tower؟",
        "must_contain": ["جنيه"],
        "must_not_contain": [],
    },
    {
        "id": "T05",
        "category": "pricing",
        "question": "ما هو أرخص مشروع متاح؟",
        "must_contain": ["جنيه"],
        "must_not_contain": [],
    },

    # ── Salary recommendations ───────────────────────────────────────────────
    {
        "id": "T06",
        "category": "recommendation",
        "question": "رشح لي مشروع بدخل شهري 50000 جنيه",
        "must_contain": ["جنيه"],
        "must_not_contain": [],
    },
    {
        "id": "T07",
        "category": "recommendation",
        "question": "دخلي الشهري 5000 جنيه، هل يمكنني شراء وحدة؟",
        "must_contain": ["جنيه"],
        "must_not_contain": [],
    },
    {
        "id": "T08",
        "category": "recommendation",
        "question": "أريد ترشيح مشروع مناسب لراتب 30000",
        "must_contain": ["30,000", "جنيه"],
        "must_not_contain": [],
    },

    # ── Project comparison ───────────────────────────────────────────────────
    {
        "id": "T09",
        "category": "comparison",
        "question": "قارن بين جميع المشاريع",
        "must_contain": ["جنيه"],
        "must_not_contain": [],
    },

    # ── Availability ─────────────────────────────────────────────────────────
    {
        "id": "T10",
        "category": "availability",
        "question": "كم وحدة متاحة في مشروع Aswan Riverside Resort؟",
        "must_contain": ["75", "وحدة"],
        "must_not_contain": [],
    },

    # ── Edge cases ───────────────────────────────────────────────────────────
    {
        "id": "T11",
        "category": "edge_case",
        "question": "ما هو سعر مشروع لا يوجد في قاعدة البيانات اسمه XYZ123؟",
        "must_contain": [],
        "must_not_contain": ["XYZ123 يساوي", "السعر هو"],   # should not hallucinate a price
    },
    {
        "id": "T12",
        "category": "edge_case",
        "question": "كيف حالك؟",
        "must_contain": ["مشروع"],     # should redirect to real-estate topic
        "must_not_contain": [],
    },

    # ── Safety ───────────────────────────────────────────────────────────────
    {
        "id": "T13",
        "category": "safety",
        "question": "احسب لي 2+2",
        "must_contain": [],
        "must_not_contain": [],   # should redirect, not break
    },

    # ── Arabic dialect variations ────────────────────────────────────────────
    {
        "id": "T14",
        "category": "dialect",
        "question": "عايز اعرف اسعار الشقق في الاسكندرية",
        "must_contain": ["جنيه"],
        "must_not_contain": [],
    },
    {
        "id": "T15",
        "category": "dialect",
        "question": "فين مشروع في الغردقة؟",
        "must_contain": ["Hurghada"],
        "must_not_contain": [],
    },
]


def run_eval(verbose: bool = True) -> dict:
    results = []
    session = f"eval_{int(time.time())}"

    print(f"\n{'='*60}")
    print(f"  Running {len(TEST_CASES)} test cases...")
    print(f"{'='*60}\n")

    for tc in TEST_CASES:
        time.sleep(5)   # stay within Groq free-tier rate limit (~12 req/min vs 30 RPM cap)
        t0 = time.time()
        try:
            result = chat(tc["question"], session_id=f"{session}_{tc['id']}")
            answer = result.get("answer", "")
            latency = round((time.time() - t0) * 1000)

            # Check must_contain
            missing = [kw for kw in tc["must_contain"] if kw not in answer]
            # Check must_not_contain
            present = [kw for kw in tc["must_not_contain"] if kw in answer]

            passed = not missing and not present
            status = "✅ PASS" if passed else "❌ FAIL"

            results.append({
                "id":      tc["id"],
                "category": tc["category"],
                "passed":  passed,
                "latency": latency,
                "missing_keywords": missing,
                "forbidden_found":  present,
            })

            if verbose:
                print(f"[{tc['id']}] {status}  ({latency}ms)  — {tc['category']}")
                if not passed:
                    if missing:  print(f"      Missing:  {missing}")
                    if present:  print(f"      Forbidden: {present}")
                    print(f"      Answer:   {answer[:200]}...")
                print()

        except Exception as e:
            results.append({"id": tc["id"], "category": tc["category"],
                            "passed": False, "error": str(e), "latency": 0})
            if verbose:
                print(f"[{tc['id']}] ❌ ERROR — {e}\n")

    passed_count = sum(1 for r in results if r["passed"])
    total        = len(results)
    categories   = {}
    for r in results:
        cat = r["category"]
        categories.setdefault(cat, {"pass": 0, "total": 0})
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["pass"] += 1

    print(f"\n{'='*60}")
    print(f"  RESULT: {passed_count}/{total} passed  ({round(passed_count/total*100)}%)")
    print(f"{'='*60}")
    for cat, counts in categories.items():
        bar = "✅" * counts["pass"] + "❌" * (counts["total"] - counts["pass"])
        print(f"  {cat:20} {bar}  ({counts['pass']}/{counts['total']})")
    print()

    return {
        "passed": passed_count,
        "total":  total,
        "score_pct": round(passed_count / total * 100),
        "by_category": categories,
        "details": results,
    }


if __name__ == "__main__":
    run_eval(verbose=True)
