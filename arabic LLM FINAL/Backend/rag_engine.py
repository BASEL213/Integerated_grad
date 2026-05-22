"""
rag.py — Smart Arabic Real-Estate Chatbot Backend
══════════════════════════════════════════════════
Two-layer architecture:
  Layer 1 → Pandas Router  : structured / aggregation questions
                             answered directly from CSV (fast, always correct)
  Layer 2 → ChromaDB+Groq  : descriptive / open-ended questions
                             using source-diverse vector retrieval

Tuned for your exact 3 CSVs:
  • North_coast.csv  → العلمين / الساحل الشمالي
  • L_Obour.csv      → العبور
  • new_cairo.csv    → نزهة الأندلس (مدخل أ / ب)
"""

import os
import re
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, TOP_K_RESULTS, MAX_CHAT_HISTORY
from chroma_store import query_documents

if not GROQ_API_KEY:
    raise ValueError("No Groq API key found.")

client = Groq(api_key=GROQ_API_KEY)
chat_histories: dict[str, list] = {}

SYSTEM_PROMPT = """أنت مستشار عقاري محترف متخصص في المشاريع السكنية.
تعتمد إجاباتك حصراً على البيانات المقدمة من قاعدة البيانات — المشاريع المتاحة مدرجة في السياق.

## 🔒 صلاحياتك — قراءة فقط (READ-ONLY):
أنت نظام استعراض وإرشاد فقط. لا تملك أي صلاحية لتعديل البيانات ولا تستطيع ذلك تقنياً.
إذا طلب المستخدم أي عملية كتابة أو تعديل مثل:
  • تعديل / تحديث بيانات أو أسعار أو عدد الوحدات
  • حذف / مسح أي سجل أو مشروع
  • إضافة وحدات أو مشاريع جديدة
  • رفع الأسعار أو تخفيضها
  • تغيير أي قيمة في قاعدة البيانات
فأجب حرفياً بهذا الرد ولا تتجاوزه:
"عذراً، لا أملك صلاحية تعديل البيانات. هذه الصلاحية محجوزة للمسؤولين فقط عبر لوحة الإدارة."
لا تتظاهر أبداً بأنك نفّذت أي تعديل حتى لو طُلب منك ذلك بشدة.

## قواعد الإجابة:
1. **دقة البيانات**: في أي سؤال يتعلق بأسعار أو مساحات أو أقساط، استخدم **البيانات المزودة فقط** ولا تخمن أبداً.
   ⚠️ **محظور تماماً**: لا تُجري أي عملية حسابية على الأقساط أو الأسعار بنفسك. إذا وردت بيانات الأقساط في السياق، اعرضها كما هي حرفياً بدون قسمة أو ضرب.
2. **التفاعل الذكي**: كن مستشاراً حقيقياً لا مجرد قاعدة بيانات — اطرح أسئلة توضيحية، قدّم نصائح مالية واقعية، واقترح البدائل عند الحاجة.
3. **الأسلوب المهني**: أجب باللغة العربية الفصحى الواضحة. استخدم الأرقام بالتنسيق المناسب (876,700 جنيه).
4. **خطوات التقديم**: عندما يريد المستخدم التقديم، اشرح له الخطوات بالتفصيل واطلب منه رفع وثائقه.
5. **التوصية المالية**: احتسب دائماً الأهلية على أساس ألا يتجاوز القسط 45% من الدخل الشهري.
6. **إنهاء الرسائل**: اختم كل رد بسؤال تفاعلي واحد يفتح نقاشاً مفيداً.

## عند طلب التقديم على وحدة:
قل للمستخدم بالضبط:
"لإتمام التقديم، ستحتاج إلى رفع الوثائق التالية في نافذة 'التقديم':
1. صورة واضحة من الوجهين لبطاقة الرقم القومي
2. شهادة دخل حديثة معتمدة (أو إثبات دخل للعمل الحر)
سيقوم النظام باستخراج بياناتك تلقائياً وتعبئة نموذج التقديم."
"""

# ══════════════════════════════════════════════════════════════════════════════
# CSV LOADER  — normalizes all 3 CSV schemas into one unified DataFrame
# ══════════════════════════════════════════════════════════════════════════════

def _parse_price_range(price_str) -> tuple[float | None, float | None]:
    """Parse '2.5M - 4M EGP', '950K - 1.8M EGP', '8 M - 18 M' → (min, max) as floats."""
    if not price_str or pd.isna(price_str):
        return None, None
    s = str(price_str).upper().replace('EGP', '').replace(',', '').strip()

    def _num(tok):
        tok = tok.strip()
        try:
            if 'M' in tok: return float(tok.replace('M', '').strip()) * 1_000_000
            if 'K' in tok: return float(tok.replace('K', '').strip()) * 1_000
            return float(tok)
        except Exception:
            return None

    parts = re.split(r'\s*[-–]\s*', s)
    if len(parts) >= 2:
        return _num(parts[0]), _num(parts[-1])
    v = _num(parts[0])
    return v, v


def _normalize_df(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """
    Map any collection (Arabic CSV or English MongoDB) to standard columns:
      __project__, __floor__, __price__ (min), __price_max__,
      __available__, __total_units__, __location__, __description__, __status__
    """
    df = df.copy()
    df["__file__"] = source_name

    # ── __project__ ───────────────────────────────────────────────────────────
    proj_col = next((c for c in df.columns
                     if any(h in c for h in ["منطقة", "مشروع", "اسم المشروع"])), None)
    if not proj_col and "name" in df.columns:
        proj_col = "name"
    df["__project__"] = df[proj_col].astype(str).str.strip() if proj_col else source_name

    # ── __floor__ ─────────────────────────────────────────────────────────────
    floor_col = next((c for c in df.columns
                      if any(h in c for h in ["دور", "طابق", "الدور"])), None)
    df["__floor__"] = df[floor_col].astype(str).str.strip() if floor_col else "غير محدد"

    # ── __price__ / __price_max__ ─────────────────────────────────────────────
    arabic_price_col = next((c for c in df.columns
                              if any(h in c for h in ["قيمة الوحدة", "إجمالي سعر", "اجمالي سعر"])), None)
    if arabic_price_col:
        num = pd.to_numeric(df[arabic_price_col].astype(str).replace({',': ''}, regex=True), errors="coerce")
        df["__price__"]     = num
        df["__price_max__"] = num
    elif "priceRange" in df.columns:
        parsed = df["priceRange"].apply(_parse_price_range)
        df["__price__"]     = parsed.apply(lambda x: x[0])
        df["__price_max__"] = parsed.apply(lambda x: x[1])
    else:
        df["__price__"]     = None
        df["__price_max__"] = None

    # ── extra standard columns (MongoDB-specific) ─────────────────────────────
    df["__available__"]   = pd.to_numeric(df.get("availableUnits"), errors="coerce") \
                            if "availableUnits" in df.columns else None
    df["__total_units__"] = pd.to_numeric(df.get("totalUnits"), errors="coerce") \
                            if "totalUnits" in df.columns else None
    df["__location__"]    = df["location"].astype(str)   if "location"    in df.columns else None
    df["__description__"] = df["description"].astype(str) if "description" in df.columns else None
    df["__status__"]      = df["status"].astype(str)     if "status"      in df.columns else None

    return df


_HOUSING_PRICE_HINTS = ["priceRange", "price", "قيمة الوحدة", "إجمالي سعر", "اجمالي سعر"]


def _is_housing_collection(col_name: str, df) -> bool:
    """True if the collection looks like housing/project data."""
    from config import MONGODB_HOUSING_COLLECTIONS
    if MONGODB_HOUSING_COLLECTIONS:
        return col_name in [c.strip() for c in MONGODB_HOUSING_COLLECTIONS.split(",")]
    # Auto-detect: must have a price column or location+units
    has_price    = any(h in df.columns for h in _HOUSING_PRICE_HINTS)
    has_location = "location" in df.columns or any("موقع" in c for c in df.columns)
    has_units    = any(c in df.columns for c in ["totalUnits", "availableUnits", "مساحة"])
    return has_price or (has_location and has_units)


def _load_all_csvs() -> pd.DataFrame | None:
    """
    Load housing data from MongoDB (primary) with CSV fallback.
    Only collections that look like project/housing data are loaded into the pandas router.
    Rebuilds whenever MongoDB cache is stale (every 5 min) or after /api/sync.
    """
    from mongodb_connector import get_all_dataframes, ping

    dfs = []

    # ── Primary: MongoDB ──────────────────────────────────────────────────────
    if ping():
        try:
            collections = get_all_dataframes()
            for col_name, df in collections.items():
                if _is_housing_collection(col_name, df):
                    dfs.append(_normalize_df(df, col_name))
                    print(f"[rag] Using collection '{col_name}' for pandas router")
                else:
                    print(f"[rag] Skipping non-housing collection '{col_name}'")
        except Exception as e:
            print(f"[rag] MongoDB load failed: {e} — falling back to CSV")

    # ── Fallback: local CSV files ─────────────────────────────────────────────
    if not dfs:
        _BASE      = os.path.dirname(__file__)
        CSV_FOLDER = os.path.join(_BASE, "..", "Data", "uploads")
        folder = os.path.abspath(CSV_FOLDER)
        if os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                if not fname.lower().endswith(".csv"):
                    continue
                try:
                    df = pd.read_csv(os.path.join(folder, fname), encoding="utf-8-sig")
                    df.columns = df.columns.str.strip()
                    dfs.append(_normalize_df(df, fname.replace(".csv", "")))
                except Exception as e:
                    print(f"[pandas] Could not load {fname}: {e}")

    if not dfs:
        return None

    return pd.concat(dfs, ignore_index=True)


def refresh_data():
    """Call this to force-reload from MongoDB (used by /api/sync)."""
    from mongodb_connector import invalidate
    invalidate()


# ══════════════════════════════════════════════════════════════════════════════
# COLUMN RESOLVER — handles different column names across the 3 CSVs
# ══════════════════════════════════════════════════════════════════════════════

def _col(df: pd.DataFrame, *hints: str) -> str | None:
    """Find the best column matching hints that actually contains data in the provided DataFrame."""
    matching_cols = []
    for hint in hints:
        for c in df.columns:
            if hint in c:
                matching_cols.append(c)
    
    # Prioritize columns that have non-null values in this specific subset
    for c in matching_cols:
        if df[c].notna().any():
            return c
            
    return matching_cols[0] if matching_cols else None


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT DETECTOR — uses normalized __project__ column
# ══════════════════════════════════════════════════════════════════════════════

_ARABIC_EN_CITY = {
    "مطروح": "matrouh", "مرسى": "marsa",
    "المنصورة": "mansoura", "منصورة": "mansoura",
    "بورسعيد": "port said", "بور سعيد": "port said",
    "أسوان": "aswan", "اسوان": "aswan",
    "السويس": "suez", "سويس": "suez",
    "الأقصر": "luxor", "اقصر": "luxor",
    "الغردقة": "hurghada", "غردقة": "hurghada",
    "الجيزة": "giza", "جيزة": "giza",
    "العلمين": "alamein", "علمين": "alamein",
    "العبور": "obour", "عبور": "obour",
    "الأندلس": "andalus", "اندلس": "andalus",
    # Additional cities (dialect + variants)
    "الاسكندرية": "alexandria", "اسكندرية": "alexandria",
    "إسكندرية": "alexandria",   "اسكندريه": "alexandria",
    "القاهرة": "cairo",         "قاهرة": "cairo",
    "الشروق": "shorouk",        "شروق": "shorouk",
    "مدينة نصر": "nasr city",   "التجمع": "new cairo",
    "المعادي": "maadi",         "معادي": "maadi",
    "بورفؤاد": "port fouad",
}


def _detect_project(question: str, df: pd.DataFrame) -> tuple[str | None, pd.DataFrame]:
    """
    Dynamically matches the question to a project in the DataFrame.
    Works for Arabic project names (old CSVs) and English names (MongoDB).
    """
    q = question.lower()
    # Expand Arabic city names to English equivalents for matching
    for ar, en in _ARABIC_EN_CITY.items():
        if ar in question:
            q += " " + en

    for proj_name in df["__project__"].dropna().unique():
        proj_name = str(proj_name).strip()
        tokens = [t for t in re.split(r'[\s\-_]+', proj_name.lower()) if len(t) > 2]
        if any(tok in q for tok in tokens):
            subset = df[df["__project__"] == proj_name]
            if len(subset) > 0:
                return proj_name, subset
    return None, df


# ══════════════════════════════════════════════════════════════════════════════
# NUMBER FORMATTER
# ══════════════════════════════════════════════════════════════════════════════

def _fmt(n) -> str:
    try:   return f"{int(round(float(n))):,}"
    except: return str(n)


def _is_quarterly_col(col_name: str) -> bool:
    """
    Returns True when the column holds a quarterly (every-3-months) installment.
    All three CSVs use quarterly installments:
      - North Coast: "القسط الربع سنوي علي X سنوات"  (explicit)
      - Obour:       "القسط علي X سنوات"              (no explicit label but values are quarterly)
      - New Cairo:   "دفعه كل ثلاثة اشهر لمدة (X)"   (explicit)
    """
    keywords = [
        "ربع سنوي", "ربع سنوية",          # North Coast explicit
        "ثلاثة اشهر", "ثلاثة أشهر",       # New Cairo explicit
        "كل 3", "كل ثلاث",
        "القسط علي", "القسط على",          # Obour — implicit quarterly
    ]
    return any(kw in col_name for kw in keywords)


def _inst_label(col_name: str, value: float) -> str:
    """
    Returns a clearly labelled installment string.
    Quarterly columns show both the quarterly figure AND the monthly equivalent
    so the LLM never has to guess or recalculate.
    """
    if _is_quarterly_col(col_name):
        monthly = round(value / 3)
        return f"{_fmt(value)} جنيه/كل 3 أشهر (≈ {_fmt(monthly)} جنيه/شهر)"
    return f"{_fmt(value)} جنيه/شهر"


# ══════════════════════════════════════════════════════════════════════════════
# INTENT HANDLERS
# All share signature: (df_full, df_subset, question, project_label) -> str|None
# ══════════════════════════════════════════════════════════════════════════════

def _handle_projects(df, sub, q, proj):
    lines = ["المشاريع المتاحة في قاعدة البيانات:"]
    for p_name, grp in df.groupby("__project__"):
        avail  = grp["__available__"].dropna()
        status = grp["__status__"].dropna()
        loc    = grp["__location__"].dropna()
        parts  = [f"  • {p_name}"]
        if not loc.empty:    parts.append(f"({loc.iloc[0]})")
        if not avail.empty:  parts.append(f"— {int(avail.iloc[0])} وحدة متاحة")
        if not status.empty: parts.append(f"[{status.iloc[0]}]")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _handle_location_search(df, sub, q, proj):
    """List projects in the city/area mentioned in the question, with prices."""
    # If project already detected by city-name expansion, show its summary
    if proj:
        return _handle_project_summary(df, sub, q, proj)

    # Find city from Arabic map
    city_en = None
    for ar, en in _ARABIC_EN_CITY.items():
        if ar in q:
            city_en = en
            break
    if not city_en:
        return None

    # Search __location__ column
    if "__location__" in df.columns and df["__location__"].notna().any():
        matched = df[df["__location__"].str.lower().str.contains(city_en, na=False)]
    else:
        matched = pd.DataFrame()

    if matched.empty:
        return f"لا توجد مشاريع مسجّلة في قاعدة البيانات لمنطقة {city_en.title()} حالياً."

    lines = [f"المشاريع المتاحة في {city_en.title()}:"]
    for p_name, grp in matched.groupby("__project__"):
        p_min = grp["__price__"].dropna()
        p_max = grp["__price_max__"].dropna() if "__price_max__" in grp.columns else pd.Series(dtype=float)
        avail = grp["__available__"].dropna()
        parts = [f"  • {p_name}"]
        if not p_min.empty:
            if not p_max.empty and p_max.max() != p_min.min():
                parts.append(f"— {_fmt(p_min.min())} – {_fmt(p_max.max())} جنيه")
            else:
                parts.append(f"— {_fmt(p_min.min())} جنيه")
        if not avail.empty:
            parts.append(f"| {int(avail.iloc[0])} وحدة متاحة")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _handle_project_summary(df, sub, q, proj):
    """Full summary card for a specific project."""
    if not proj:
        return None

    row = sub.iloc[0]
    lines = [f"🏢 ملخص مشروع {proj}", f"{'─'*42}"]

    # Location / description (MongoDB)
    if sub["__location__"] is not None and sub["__location__"].notna().any():
        lines.append(f"  • الموقع:              {row['__location__']}")
    if sub["__description__"] is not None and sub["__description__"].notna().any():
        lines.append(f"  • الوصف:               {row['__description__']}")
    if sub["__status__"] is not None and sub["__status__"].notna().any():
        lines.append(f"  • الحالة:              {row['__status__']}")

    # Units
    total = sub["__total_units__"].dropna()
    avail = sub["__available__"].dropna()
    if not total.empty:
        lines.append(f"  • إجمالي الوحدات:      {_fmt(total.iloc[0])} وحدة")
    else:
        lines.append(f"  • إجمالي الوحدات:      {len(sub):,} وحدة")
    if not avail.empty:
        lines.append(f"  • الوحدات المتاحة:     {_fmt(avail.iloc[0])} وحدة")

    # Price
    p_min = sub["__price__"].dropna()
    p_max = sub["__price_max__"].dropna()
    if not p_min.empty:
        if not p_max.empty and p_max.iloc[0] != p_min.iloc[0]:
            lines.append(f"  • نطاق السعر:          {_fmt(p_min.iloc[0])} – {_fmt(p_max.iloc[0])} جنيه")
        else:
            lines.append(f"  • السعر:               {_fmt(p_min.iloc[0])} جنيه")

    # Installment estimate (if no detail data, estimate over 7 years)
    inst_cols = [(3, _col(sub, "علي 3", "على 3", "لمدة (3)")),
                 (5, _col(sub, "علي 5", "على 5")),
                 (7, _col(sub, "علي 7", "على 7"))]
    has_inst = any(c for _, c in inst_cols)
    if has_inst:
        lines.append(f"  {'─'*35}")
        lines.append("  خيارات التقسيط:")
        for y, c in inst_cols:
            if c:
                p = sub[c].dropna()
                if len(p):
                    lo, hi = p.min(), p.max()
                    lines.append(f"    • {y} سنوات: {_inst_label(c, lo)}" if lo == hi
                                 else f"    • {y} سنوات: {_fmt(lo)}–{_fmt(hi)} جنيه")
    elif not p_min.empty:
        min_price = p_min.iloc[0]
        lines.append(f"  {'─'*35}")
        lines.append("  تقدير القسط الشهري (بدون فوائد):")
        for y in [3, 5, 7]:
            lines.append(f"    • {y} سنوات: ≈ {_fmt(min_price / (y * 12))} جنيه/شهر")

    # Arabic CSV-specific fields
    area_col  = _col(sub, "مساحة")
    elev_col  = _col(sub, "مصعد")
    bk_col    = _col(sub, "جدية")
    if area_col:
        lines.append(f"  • المساحات:            {sub[area_col].min()}–{sub[area_col].max()} م²")
    if elev_col:
        vals = sub[elev_col].dropna().unique()
        has_elev = "✓ يوجد" if any("مصعد" in str(v) for v in vals) else "✗ لا يوجد"
        lines.append(f"  • مصعد:                {has_elev}")
    if bk_col:
        fees = sub[bk_col].dropna().unique()
        lines.append(f"  • جدية الحجز:          {_fmt(fees[0])} جنيه")

    lines.append("\n  💬 هل تريد أسعار، أقساط، أو تقديم طلب؟")
    return "\n".join(lines)


def _handle_floors(df, sub, q, proj):
    floors = sub["__floor__"].replace("nan", pd.NA).dropna().unique().tolist()
    floors = [f for f in floors if f and f != "nan"]
    scope  = f"مشروع {proj}" if proj else "جميع المشاريع"
    return f"الأدوار المتاحة في {scope} ({len(floors)} أدوار):\n  {'، '.join(floors)}"


def _handle_floor_filter(df, sub, q, proj):
    """Show info about units on a specific floor."""
    FLOOR_MAP = {
        "الأرضي":           ["الأرضي","ارضي","أرضي","ground"],
        "الأول":            ["الأول","أول","اول","first"],
        "الثاني":           ["الثاني","ثاني","second"],
        "الثالث":           ["الثالث","ثالث","third"],
        "الرابع":           ["الرابع","رابع","fourth"],
        "الخامس":           ["الخامس","خامس","fifth"],
        "السادس":           ["السادس","سادس","sixth"],
        "الأخير":           ["الأخير","اخير","أخير","last","أعلى"],
        "الخامس والأخير":   ["خامس والأخير","خامس وأخير","خامس الأخير"],
    }
    for floor_name, aliases in FLOOR_MAP.items():
        if any(a in q for a in aliases):
            matched = sub[sub["__floor__"].str.contains(floor_name.split()[0], na=False)]
            if len(matched) == 0:
                return f"لا توجد وحدات في الدور {floor_name} ضمن النطاق المحدد."
            scope = f"مشروع {proj}" if proj else "جميع المشاريع"
            lines = [f"الوحدات في الدور {floor_name} ({scope}) — {len(matched)} وحدة:"]
            if matched["__price__"].notna().any():
                lines.append(f"  • السعر: {_fmt(matched['__price__'].min())} – {_fmt(matched['__price__'].max())} جنيه")
            area_col = _col(matched, "مساحة")
            if area_col:
                lines.append(f"  • المساحة: {matched[area_col].min()} – {matched[area_col].max()} م²")
            return "\n".join(lines)
    return None


def _handle_unit_count(df, sub, q, proj):
    lines = []
    for p_name, grp in ([(proj, sub)] if proj else df.groupby("__project__")):
        total = grp["__total_units__"].dropna()
        avail = grp["__available__"].dropna()
        if not total.empty:
            line = f"  • {p_name}: {_fmt(total.iloc[0])} إجمالي"
            if not avail.empty:
                line += f" | {_fmt(avail.iloc[0])} متاحة"
        else:
            line = f"  • {p_name}: {len(grp):,} وحدة"
        lines.append(line)
    header = f"الوحدات في مشروع {proj}:" if proj else "إجمالي الوحدات:"
    return header + "\n" + "\n".join(lines)


def _handle_area(df, sub, q, proj):
    area_col = _col(sub, "مساحة")
    if not area_col:
        return None
    scope = f"مشروع {proj}" if proj else "جميع المشاريع"

    nums = [int(n) for n in re.findall(r'\d+', q) if 50 <= int(n) <= 500]
    if nums:
        target  = nums[0]
        matches = sub[abs(sub[area_col] - target) <= 5]
        if len(matches) > 0:
            price_str = (f" — سعر الوحدة: **{_fmt(matches['__price__'].iloc[0])}** جنيه"
                         if matches["__price__"].notna().any() else "")
            return (f"يوجد {len(matches)} وحدة بمساحة ≈{target} م² في {scope}{price_str}\n"
                    f"  المساحات الفعلية: {', '.join(str(x) for x in sorted(matches[area_col].unique()))}")

    vals    = sorted(sub[area_col].dropna().unique().tolist())
    vals_str = "، ".join(str(v) for v in vals)
    return (f"المساحات المتاحة في {scope}:\n"
            f"  • أصغر مساحة: **{sub[area_col].min()} م²**\n"
            f"  • أكبر مساحة: **{sub[area_col].max()} م²**\n"
            f"  • جميع المساحات: {vals_str}")


def _handle_price(df, sub, q, proj):
    scope = f"مشروع {proj}" if proj else "جميع المشاريع"
    lines = [f"الأسعار في {scope}:"]

    # Project-level price range (MongoDB)
    p_min = sub["__price__"].dropna()
    p_max = sub["__price_max__"].dropna() if "__price_max__" in sub.columns else pd.Series(dtype=float)
    if not p_min.empty:
        if not p_max.empty and p_max.min() != p_min.min():
            lines.append(f"  • نطاق السعر: **{_fmt(p_min.min())}** – **{_fmt(p_max.max())}** جنيه")
        else:
            lines += [f"  • أقل سعر:   **{_fmt(p_min.min())}** جنيه",
                      f"  • أعلى سعر:  **{_fmt(p_min.max())}** جنيه"]

    meter_col = _col(sub, "سعر المتر")
    if meter_col:
        vals = sub[meter_col].dropna().unique()
        lines.append(f"  • سعر المتر: **{_fmt(vals[0])}** جنيه/م²" if len(vals) == 1
                     else f"  • سعر المتر: {_fmt(vals.min())} – {_fmt(vals.max())} جنيه/م²")

    return "\n".join(lines) if len(lines) > 1 else None


def _handle_booking_fee(df, sub, q, proj):
    col   = _col(sub, "جدية")
    scope = f"مشروع {proj}" if proj else "جميع المشاريع"
    if not col:
        return None
    fees = sub[col].dropna().unique()
    if len(fees) == 1:
        return f"جدية الحجز في {scope}: **{_fmt(fees[0])}** جنيه"
    return f"جديات الحجز في {scope}: {' / '.join(_fmt(f) for f in fees)} جنيه"


def _handle_installments(df, sub, q, proj):
    scope = f"مشروع {proj}" if proj else "جميع المشاريع"
    asked = []
    if any(x in q for x in ["3","ثلاث","ثلاثة"]): asked.append(3)
    if any(x in q for x in ["5","خمس","خمسة"]):   asked.append(5)
    if any(x in q for x in ["7","سبع","سبعة"]):    asked.append(7)
    if not asked: asked = [3, 5, 7]

    lines = [f"خيارات التقسيط في {scope}:"]
    for y in asked:
        col = _col(sub, f"علي {y}", f"على {y}", f"لمدة ({y})")
        if col:
            p = sub[col].dropna()
            if len(p) == 0: continue
            lo, hi = p.min(), p.max()
            if lo == hi:
                lines.append(f"  • قسط {y} سنوات: **{_inst_label(col, lo)}**")
            else:
                if _is_quarterly_col(col):
                    lines.append(
                        f"  • قسط {y} سنوات: {_fmt(lo)}–{_fmt(hi)} جنيه/كل 3 أشهر"
                        f" (≈ {_fmt(lo/3)}–{_fmt(hi/3)} جنيه/شهر)"
                    )
                else:
                    lines.append(f"  • قسط {y} سنوات: {_fmt(lo)}–{_fmt(hi)} جنيه/شهر")

    return "\n".join(lines) if len(lines) > 1 else None


def _handle_down_payment(df, sub, q, proj):
    scope = f"مشروع {proj}" if proj else "جميع المشاريع"
    lines = [f"الدفعات المقدمة في {scope}:"]

    col_bk  = _col(sub, "جدية")
    col_10  = _col(sub, "10%")
    col_20  = _col(sub, "20%", "استكمال")

    if col_bk:
        fees = sub[col_bk].dropna().unique()
        val  = _fmt(fees[0]) if len(fees)==1 else " / ".join(_fmt(f) for f in fees)
        lines.append(f"  • جدية الحجز:        **{val}** جنيه")
    if col_10:
        p = sub[col_10].dropna()
        lines.append(f"  • دفعة 10%:          {_fmt(p.min())} – {_fmt(p.max())} جنيه" if p.min()!=p.max()
                     else f"  • دفعة 10%:          **{_fmt(p.min())}** جنيه")
    if col_20:
        p = sub[col_20].dropna()
        lines.append(f"  • دفعة 20% / استكمال: {_fmt(p.min())} – {_fmt(p.max())} جنيه" if p.min()!=p.max()
                     else f"  • دفعة 20% / استكمال: **{_fmt(p.min())}** جنيه")

    return "\n".join(lines) if len(lines) > 1 else None


def _handle_elevator(df, sub, q, proj):
    col   = _col(sub, "مصعد")
    scope = f"مشروع {proj}" if proj else "جميع المشاريع"
    if not col:
        return f"لا تتوفر معلومات عن المصعد في {scope}"
    vals = sub[col].dropna().unique().tolist()
    if len(vals) == 1:
        has = "✓ يوجد مصعد" if "مصعد" in str(vals[0]) else "✗ لا يوجد مصعد"
        return f"{has} في {scope}"
    return f"حالة المصعد في {scope}: {' / '.join(str(v) for v in vals)}"


def _handle_unit_lookup(df, sub, q, proj):
    nums = re.findall(r'\b\d+\b', q)
    # Filter out numbers that are clearly not unit numbers (e.g. years like 3,5,7)
    nums = [n for n in nums if int(n) > 0 and int(n) not in (3, 5, 7, 10, 20)]
    if not nums: return None
    num_col = _col(sub, "رقم الوحدة", "رقم")
    if not num_col: return None

    for num in nums:
        # Exact match only — no partial matches
        matches = sub[sub[num_col].astype(str).str.strip() == str(int(num))]
        if len(matches) == 0:
            # Try with the full df if subset gave nothing
            matches = df[df[num_col].astype(str).str.strip() == str(int(num))]
        if len(matches) > 0:
            row = matches.iloc[0]   # Always take exactly ONE row
            lines = [f"📋 تفاصيل الوحدة رقم {num}:"]
            lines.append(f"  • المشروع:              {row['__project__']}")
            lines.append(f"  • الدور:                {row['__floor__']}")
            area_col  = _col(matches, "مساحة")
            elev_col  = _col(matches, "مصعد")
            meter_col = _col(matches, "سعر المتر")
            inst3_col = _col(matches, "علي 3", "على 3", "لمدة (3)")
            inst5_col = _col(matches, "علي 5", "على 5")
            inst7_col = _col(matches, "علي 7", "على 7")
            bk_col    = _col(matches, "جدية")
            col_10    = _col(matches, "10%")
            col_20    = _col(matches, "20%", "استكمال")
            if area_col:   lines.append(f"  • المساحة:              {row[area_col]} م²")
            if elev_col:   lines.append(f"  • مصعد:                 {row[elev_col]}")
            if meter_col:  lines.append(f"  • سعر المتر:            {_fmt(row[meter_col])} جنيه/م²")
            if pd.notna(row["__price__"]):
                lines.append(f"  • قيمة الوحدة:          {_fmt(row['__price__'])} جنيه")
            if bk_col:     lines.append(f"  • جدية الحجز:          {_fmt(row[bk_col])} جنيه")
            if col_20:     lines.append(f"  • استكمال 20%+رسوم:    {_fmt(row[col_20])} جنيه")
            if col_10:     lines.append(f"  • قيمة 10% عند الاستلام: {_fmt(row[col_10])} جنيه")
            lines.append(f"  {'─'*35}")
            lines.append(f"  خيارات التقسيط:")
            if inst3_col:  lines.append(f"  • 3 سنوات: {_inst_label(inst3_col, row[inst3_col])}")
            if inst5_col:  lines.append(f"  • 5 سنوات: {_inst_label(inst5_col, row[inst5_col])}")
            if inst7_col:  lines.append(f"  • 7 سنوات: {_inst_label(inst7_col, row[inst7_col])}")
            return "\n".join(lines)

    return f"لم يتم العثور على وحدة برقم {nums[0]} في قاعدة البيانات."


def _handle_compare(df, sub, q, proj):
    lines = ["📊 مقارنة جميع المشاريع:\n"]
    for p_name, group in df.groupby("__project__"):
        lines.append(f"🏢 {str(p_name).strip()}")

        # Units
        total = group["__total_units__"].dropna()
        avail = group["__available__"].dropna()
        if not total.empty:
            units_str = f"{_fmt(total.iloc[0])} وحدة إجمالي"
            if not avail.empty: units_str += f" | {_fmt(avail.iloc[0])} متاحة"
        else:
            units_str = f"{len(group):,} وحدة"
        lines.append(f"  • الوحدات:       {units_str}")

        # Location & status
        loc    = group["__location__"].dropna() if group["__location__"] is not None else pd.Series()
        status = group["__status__"].dropna()   if group["__status__"]   is not None else pd.Series()
        if not loc.empty:    lines.append(f"  • الموقع:        {loc.iloc[0]}")
        if not status.empty: lines.append(f"  • الحالة:        {status.iloc[0]}")

        # Price
        p_min = group["__price__"].dropna()
        p_max = group["__price_max__"].dropna() if "__price_max__" in group.columns else pd.Series(dtype=float)
        if not p_min.empty:
            if not p_max.empty and p_max.max() != p_min.min():
                lines.append(f"  • السعر:         {_fmt(p_min.min())} – {_fmt(p_max.max())} جنيه")
            else:
                lines.append(f"  • السعر:         {_fmt(p_min.min())} – {_fmt(p_min.max())} جنيه")

        # Installment (7 yrs) or estimate
        inst7 = _col(group, "علي 7", "على 7")
        if inst7:
            p7 = group[inst7].dropna()
            if len(p7):
                if _is_quarterly_col(inst7):
                    lines.append(f"  • قسط 7 سنوات:  {_fmt(p7.min())}–{_fmt(p7.max())} جنيه/كل 3 أشهر")
                else:
                    lines.append(f"  • قسط 7 سنوات:  {_fmt(p7.min())} – {_fmt(p7.max())} جنيه/شهر")
        elif not p_min.empty:
            lines.append(f"  • قسط/7سنوات≈:   {_fmt(p_min.min()/(7*12))} جنيه/شهر (تقديري)")

        # Arabic CSV fields
        area_col = _col(group, "مساحة")
        elev_col = _col(group, "مصعد")
        bk_col   = _col(group, "جدية")
        if area_col:
            lines.append(f"  • المساحة:       {group[area_col].min()}–{group[area_col].max()} م²")
        if elev_col:
            has_elev = "✓" if "مصعد" in str(group[elev_col].iloc[0]) else "✗"
            lines.append(f"  • مصعد:          {has_elev}")
        if bk_col:
            lines.append(f"  • جدية الحجز:    {_fmt(group[bk_col].iloc[0])} جنيه")
        lines.append("")
    return "\n".join(lines)


def _handle_cheapest(df, sub, q, proj):
    if sub["__price__"].isna().all(): return None
    top      = sub.dropna(subset=["__price__"]).nsmallest(5, "__price__")
    num_col  = _col(sub, "رقم الوحدة")
    area_col = _col(sub, "مساحة")
    lines    = ["💰 أرخص الوحدات المتاحة:"]
    for _, row in top.iterrows():
        parts = []
        if num_col:  parts.append(f"وحدة #{int(row[num_col]) if pd.notna(row[num_col]) else '?'}")
        parts.append(str(row["__project__"]).strip())
        parts.append(f"دور {row['__floor__']}")
        if area_col: parts.append(f"{row[area_col]} م²")
        parts.append(f"**{_fmt(row['__price__'])}** جنيه")
        lines.append("  • " + " | ".join(parts))
    return "\n".join(lines)


def _handle_most_expensive(df, sub, q, proj):
    if sub["__price__"].isna().all(): return None
    top      = sub.dropna(subset=["__price__"]).nlargest(5, "__price__")
    num_col  = _col(sub, "رقم الوحدة")
    area_col = _col(sub, "مساحة")
    lines    = ["💎 أعلى الوحدات سعراً:"]
    for _, row in top.iterrows():
        parts = []
        if num_col:  parts.append(f"وحدة #{int(row[num_col]) if pd.notna(row[num_col]) else '?'}")
        parts.append(str(row["__project__"]).strip())
        parts.append(f"دور {row['__floor__']}")
        if area_col: parts.append(f"{row[area_col]} م²")
        parts.append(f"**{_fmt(row['__price__'])}** جنيه")
        lines.append("  • " + " | ".join(parts))
    return "\n".join(lines)


def _handle_budget(df, sub, q, proj):
    nums = [int(n.replace(",","")) for n in re.findall(r'[\d,]+', q)
            if int(n.replace(",","")) > 50000]
    if not nums: return None
    budget  = max(nums)
    matched = sub[sub["__price__"] <= budget].dropna(subset=["__price__"])
    if len(matched) == 0:
        mn = sub["__price__"].dropna().min()
        return f"لا توجد وحدات بسعر أقل من {_fmt(budget)} جنيه.\nأقل سعر متاح: **{_fmt(mn)}** جنيه"

    num_col  = _col(matched, "رقم الوحدة")
    area_col = _col(matched, "مساحة")
    lines    = [f"الوحدات بسعر أقل من {_fmt(budget)} جنيه ({len(matched)} وحدة):"]
    for _, row in matched.head(6).iterrows():
        parts = []
        if num_col:  parts.append(f"وحدة #{int(row[num_col]) if pd.notna(row[num_col]) else '?'}")
        parts.append(str(row["__project__"]).strip())
        parts.append(f"دور {row['__floor__']}")
        if area_col: parts.append(f"{row[area_col]} م²")
        parts.append(f"{_fmt(row['__price__'])} جنيه")
        lines.append("  • " + " | ".join(parts))
    if len(matched) > 6:
        lines.append(f"  ... و{len(matched)-6} وحدة أخرى")
    return "\n".join(lines)


def _handle_recommendation(df, sub, q, proj):
    """Recommend projects based on salary mentioned in the query with accurate math and quarterly detection."""
    nums = [int(n.replace(",","")) for n in re.findall(r'[\d,]+', q)
            if 3000 <= int(n.replace(",","")) <= 300000]
    
    if not nums:
        return "من فضلك أخبرني بقيمة دخلك الشهري التقريبي (مثال: 'دخلي 15,000') لأتمكن من ترشيح المشروع والوحدة الأنسب لك."

    salary = nums[0]
    max_allowable_inst = salary * 0.45  # Standard bank ratio is ~40-50%
    
    recommendations = []
    for p_name, group in df.groupby("__project__"):
        # Skip inactive projects
        if group["__status__"] is not None and group["__status__"].notna().any():
            status = str(group["__status__"].iloc[0]).lower()
            if status in ("completed", "cancelled"):
                continue

        best_plan = None
        min_monthly_inst = float('inf')
        is_quarterly = False

        # ── Try explicit installment columns first (CSV data) ─────────────
        for years in [7, 5, 3]:
            col = _col(group, f"علي {years}", f"على {years}", f"لمدة ({years})")
            if col:
                p = pd.to_numeric(group[col].astype(str).replace({',': ''}, regex=True), errors="coerce").dropna()
                if len(p):
                    val = p.min()
                    qtrly = _is_quarterly_col(col)
                    monthly = val / 3 if qtrly else val
                    if monthly < min_monthly_inst:
                        min_monthly_inst = monthly
                        best_plan = years
                        is_quarterly = qtrly

        # ── Estimate from price range if no installment columns (MongoDB) ─
        if best_plan is None and group["__price__"].notna().any():
            min_price = group["__price__"].dropna().min()
            for years in [7, 5, 3]:
                monthly = min_price / (years * 12)
                if monthly < min_monthly_inst:
                    min_monthly_inst = monthly
                    best_plan = years
                    is_quarterly = False

        avail_col = group["__available__"].dropna()
        avail_count = int(avail_col.iloc[0]) if not avail_col.empty else len(group)

        if best_plan and min_monthly_inst <= max_allowable_inst:
            recommendations.append({
                "name":         p_name,
                "years":        best_plan,
                "monthly_inst": min_monthly_inst,
                "raw_inst":     min_monthly_inst * 3 if is_quarterly else min_monthly_inst,
                "is_quarterly": is_quarterly,
                "price":        group["__price__"].dropna().min(),
                "available":    avail_count,
                "estimated":    _col(group, f"علي {best_plan}", f"على {best_plan}", f"لمدة ({best_plan})") is None,
            })

    if not recommendations:
        cheapest = df["__price__"].dropna().min()
        min_needed = cheapest / (7 * 12)
        return (f"بناءً على دخل شهري قدره **{_fmt(salary)}** جنيه (حد القسط: {_fmt(max_allowable_inst)} جنيه)، "
                f"أقل قسط شهري متاح هو ≈ **{_fmt(min_needed)}** جنيه.\n"
                "يبدو الدخل الحالي منخفضاً قليلاً عن متطلبات المشاريع المتاحة.")

    lines = [f"بناءً على دخل شهري قدره **{_fmt(salary)}** جنيه، إليك أفضل الترشيحات:"]
    for rec in sorted(recommendations, key=lambda x: x["monthly_inst"]):
        lines.append(f"  • 🏢 **{rec['name']}**:")
        lines.append(f"    - أنسب نظام: تقسيط على **{rec['years']} سنوات**")
        if rec["is_quarterly"]:
            lines.append(f"    - القسط: **{_fmt(rec['raw_inst'])}** جنيه/كل 3 أشهر")
            lines.append(f"    - ما يعادل شهرياً: **{_fmt(rec['monthly_inst'])}** جنيه")
        else:
            est = " (تقديري)" if rec["estimated"] else ""
            lines.append(f"    - القسط الشهري: **{_fmt(rec['monthly_inst'])}** جنيه{est}")
        lines.append(f"    - السعر يبدأ من: {_fmt(rec['price'])} جنيه")
        if rec["available"] > 0:
            lines.append(f"    - الوحدات المتاحة: {rec['available']} وحدة")

    lines.append(f"\n💡 الأهلية محسوبة على أساس ألا يتجاوز القسط 45% من الدخل ({_fmt(max_allowable_inst)} جنيه/شهر).")
    return "\n".join(lines)


def _handle_apply(df, sub, q, proj):
    project_hint = f" على مشروع **{proj}**" if proj else ""
    return (
        f"يسعدني مساعدتك في التقديم{project_hint}! 🏠\n\n"
        "**خطوات التقديم:**\n"
        "1. تأكد أن دخلك الشهري يغطي القسط المناسب (45% حد أقصى).\n"
        "2. جهّز الوثائق المطلوبة:\n"
        "   • صورة واضحة من الوجهين لبطاقة الرقم القومي\n"
        "   • شهادة دخل حديثة معتمدة من جهة العمل (أو محاسب قانوني للعمل الحر)\n"
        "   • قيد عائلي مميكن\n"
        "   • إيصال مرافق حديث (كهرباء أو غاز) لمحل الإقامة الحالي\n"
        "3. افتح نافذة **'التقديم'** في التطبيق وارفع صورة بطاقتك — سيستخرج النظام "
        "بياناتك تلقائياً ويملأ النموذج.\n"
        "4. راجع البيانات المستخرجة وعدّل ما يلزم.\n"
        "5. اضغط **'إرسال الطلب'** — ستحصل على كود متابعة فوري.\n\n"
        "💡 **جدية الحجز حسب المشروع:**\n"
        "   • العلمين: 100,000 جنيه\n"
        "   • العبور: 60,000 جنيه\n"
        "   • نزهة الأندلس: 150,000 جنيه\n\n"
        "هل تريد أن أرشّح لك المشروع الأنسب أولاً بناءً على دخلك الشهري؟"
    )


# ══════════════════════════════════════════════════════════════════════════════
# INTENT ROUTING TABLE  (most-specific first, first match wins)
# ══════════════════════════════════════════════════════════════════════════════

INTENTS = [
    # Project summary — when user mentions a project name without a specific question
    (["العلمين","الساحل","العبور","الأندلس","اندلس","نزهة",
      "معلومات عن","أخبرني عن","عايز أعرف عن","ما هو مشروع"],             _handle_project_summary),
    (["رشح","ترشيح","مناسب لي","أفضل مشروع","ايه المناسب","تنصحني",
      "مناسب لدخل","مناسب لراتب","في حدود دخل","مناسبة لدخل","مناسبة لراتب",
      "في حدود راتب","يناسب دخل","يناسب راتب","دخل شهري","راتب شهري",
      "مشاريع أخرى","مشروع آخر","بديل","هل هناك مشروع",
      "مناسب لي","تناسب دخلي","تناسب راتبي"],                             _handle_recommendation),
    (["قارن","مقارنة","الفرق بين","جميع المشاريع","كل المشاريع"],          _handle_compare),
    (["بميزانية","ميزانية","بحد أقصى","أقل من","لا يتجاوز","في حدود"],     _handle_budget),
    (["الوحدة رقم","وحدة رقم","رقم الوحدة"],                               _handle_unit_lookup),
    (["أرخص","أقل سعر","أوفر","أقل تكلفة","الأرخص"],                       _handle_cheapest),
    (["أغلى","أعلى سعر","أكثر سعرا","الأغلى"],                             _handle_most_expensive),
    (["الأرضي","الأول","الثاني","الثالث","الرابع","الخامس","السادس",
      "الأخير","ارضي","اول","ثاني","ثالث","رابع","خامس","سادس","اخير"],    _handle_floor_filter),
    (["قسط","أقساط","تقسيط","3 سنوات","5 سنوات","7 سنوات",
      "ثلاث سنوات","خمس سنوات","سبع سنوات"],                               _handle_installments),
    (["مقدم","دفعة","دفعات","10%","20%","استكمال","جدية","حجز"],            _handle_down_payment),
    (["مصعد","اسانسير","lift","elevator"],                                   _handle_elevator),
    (["سعر","أسعار","تكلفة","بكام","بكم","يساوي","كم سعر"],                _handle_price),
    (["مساحة","مساحات","م²","متر مربع"],                                    _handle_area),
    (["أدوار","الأدوار","ادوار","كم دور","طابق","طوابق","الدور"],           _handle_floors),
    (["كم وحدة","عدد الوحدات","كمية الوحدات","إجمالي الوحدات"],            _handle_unit_count),
    (["أريد التقديم","أقدم على","أقدم في","عايز أقدم","ابدأ التقديم",
      "كيف أقدم","طريقة التقديم","خطوات التقديم"],                            _handle_apply),
    (["أوراق","اوراق","شروط","تقديم","مستندات","مطلوب","إجراءات"],            None), # Trigger RAG for these
    # Location / city queries (dialect "فين"/"وين" + "في [city]" patterns)
    (["فين", "وين",
      "في الاسكندرية", "في القاهرة", "في الغردقة", "في أسوان",
      "في الأقصر", "في مطروح", "في الجيزة", "في السويس",
      "في العلمين", "في العبور", "في الشروق",
      "بالاسكندرية", "بالقاهرة", "بالغردقة", "باسكندرية"],              _handle_location_search),
    (["مشاريع","مناطق","اليس","هل يوجد","هل هناك","ما هي المشاريع",
      "ما المشاريع","مشروع آخر","مشاريع أخرى"],                            _handle_projects),
]

ALWAYS_STRUCTURED = [
    "كم","عدد","مجموع","إجمالي","متوسط","قارن","مقارنة",
    "أرخص","أغلى","قسط","مقدم","جدية","مصعد","بكام","بكم",
    "ميزانية","يساوي","سعر","مساحة","أدوار",
    # Project names — always handle via pandas to avoid LLM hallucination
    "العلمين","الساحل الشمالي","العبور","الأندلس","نزهة",
]

def _is_structured(question: str) -> bool:
    if any(kw in question for kw in ALWAYS_STRUCTURED):
        return True
    return any(any(t in question for t in triggers) for triggers, _ in INTENTS)


def _pandas_answer(question: str) -> str | None:
    df = _load_all_csvs()
    if df is None:
        return None

    proj_label, subset = _detect_project(question, df)

    for triggers, handler in INTENTS:
        if any(t in question for t in triggers):
            if handler is None:
                continue
            result = handler(df, subset, question, proj_label)
            if result:
                return result
    return None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def build_context(retrieved_docs: list[dict]) -> str:
    if not retrieved_docs:
        return "لا توجد معلومات متاحة في قاعدة البيانات."
    return "\n\n".join(
        f"[{i}] المصدر: {doc['source']}\n{doc['text']}"
        for i, doc in enumerate(retrieved_docs, 1)
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CHAT
# ══════════════════════════════════════════════════════════════════════════════

def _call_groq(messages: list, retries: int = 2) -> str:
    """Call Groq with timeout and retry on transient failures."""
    import time as _time
    last_err = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                max_tokens=1024,
                temperature=0.3,
                timeout=30,         # 30-second hard timeout
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            if attempt < retries and any(x in err_str for x in ["rate", "503", "502", "timeout"]):
                _time.sleep(2 ** attempt)   # 1s, 2s backoff
                continue
            break
    raise last_err


def chat(query: str, session_id: str = "default") -> dict:
    import time as _time
    from logger import log_interaction
    from safety import redact_pii

    if session_id not in chat_histories:
        chat_histories[session_id] = []

    t0 = _time.time()
    error_str = None

    # ── Layer 1: Pandas router ────────────────────────────────────────────────
    pandas_result = _pandas_answer(query) if _is_structured(query) else None

    if pandas_result:
        context  = f"== البيانات الدقيقة المستخرجة من قاعدة البيانات ==\n{pandas_result}"
        sources  = ["قاعدة البيانات المباشرة"]
    else:
        # ── Layer 2: ChromaDB + Groq ──────────────────────────────────────
        retrieved_docs = query_documents(query, top_k=TOP_K_RESULTS)
        context        = build_context(retrieved_docs)
        sources        = [doc["source"] for doc in retrieved_docs]

    unit_nums = [n for n in re.findall(r"\b\d+\b", query) if int(n) not in (3, 5, 7, 10, 20)]
    unit_instruction = ""
    if unit_nums and any(kw in query for kw in ["وحدة رقم", "الوحدة رقم", "رقم الوحدة"]):
        unit_instruction = (
            f"\n\n⚠️ المستخدم يسأل عن الوحدة رقم {unit_nums[0]} فقط — لا تذكر أي وحدة أخرى."
        )

    messages = [
        {"role": "system",
         "content": SYSTEM_PROMPT + unit_instruction + f"\n\nالمعلومات المتاحة:\n{context}"},
    ]
    for msg in chat_histories[session_id][-MAX_CHAT_HISTORY * 2:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": query})

    try:
        answer = _call_groq(messages)
        answer = redact_pii(answer)             # strip PII from output
    except Exception as e:
        error_str = str(e)
        answer = "عذراً، حدث خطأ مؤقت — يرجى إعادة المحاولة."

    chat_histories[session_id].append({"role": "user",      "content": query})
    chat_histories[session_id].append({"role": "assistant", "content": answer})
    if len(chat_histories[session_id]) > MAX_CHAT_HISTORY * 2:
        chat_histories[session_id] = chat_histories[session_id][-MAX_CHAT_HISTORY * 2:]

    latency_ms = (_time.time() - t0) * 1000
    log_interaction(session_id, query, answer, sources, latency_ms, error=error_str)

    return {"answer": answer, "sources": sources, "session_id": session_id}


def clear_history(session_id: str = "default"):
    if session_id in chat_histories:
        chat_histories[session_id] = []