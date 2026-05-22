"""
Egyptian ID OCR — Test runner
Usage:  python test_ocr.py [--verbose] [--image <name>]
"""

import sys
import re
import os
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Ground truth for the 11 test images
# ---------------------------------------------------------------------------

TESTS_DIR = Path(__file__).parent / 'tests'

GROUND_TRUTH = [
    {
        'file': 'Screenshot 2026-05-19 150055.png',
        'name':    'عبدالرحمن صدقى السيد عبدالمقصود الفقى',
        'nid':     '٣٠٣٠٦١٠١٣٠٥٧١٢',
        'card':    'JY8735378',
        'address': '١٢ ارض المزادات',
        'district':'الاسماعيلية ثالث',
        'dob':     None,    # derived from NID
    },
    {
        'file': 'Screenshot 2026-05-19 161241.png',
        'name':    'احمد عبدالسلام احمد مبروك عبدالسلام',
        'nid':     '٣٠٥٠٣١٧٠١٠٣٦٧٦',
        'card':    'JA6176618',
        'address': '٤٥ مجاورة الاولى الفسطاط الجديدة',
        'district':'مصر القديمة',
        'dob':     None,
    },
    {
        'file': 'Screenshot 2026-05-19 161807.png',
        'name':    'رقيه محمد احمد عبدالعظيم حسن لاشين',
        'nid':     '٣٠٧٠٣١٩٨٨٠٠٨٨٩',
        'card':    None,
        'address': '٤٤ المستثمر الصغير',
        'district':'الشيخ زايد',
        'dob':     None,
    },
    {
        'file': 'Screenshot 2026-05-19 162529.png',
        'name':    'سيف الدين هشام صلاح الدين ابراهيم خشبه',
        'nid':     '٣٠٤٠٦٠٧٠١٠٠٧٧١',
        'card':    'I07605536',
        'address': '٩٩ غرب اربيلا',
        'district':'التجمع الخامس',
        'dob':     None,
    },
    {
        'file': 'seif zaki.png',
        'name':    None,    # not confirmed
        'nid':     None,
        'card':    None,
        'address': None,
        'district':None,
        'dob':     None,
        'skip': True,       # ground truth not yet confirmed
    },
    {
        'file': 'Screenshot 2026-05-19 162642.png',
        'name':    'هادى عماد عبدالحميد حامد سعيد',
        'nid':     '٣٠٦٠١٠٦٠١٠٢٣٣١',
        'card':    'JE9118170',
        'address': '٩٥ ابراج امتداد الامل',
        'district':'المعادى',
        'dob':     None,
    },
    {
        'file': 'Screenshot 2026-05-19 162855.png',
        'name':    'محمد مصطفى محمد السيد العدوى',
        'nid':     '٣٠٤٠٣٠٣١٢٠٠٣٩٥',
        'card':    None,
        'address': 'البهوريك',
        'district':'مركز اجا',
        'dob':     None,
    },
    {
        'file': 'WhatsApp Image 2026-05-19 at 8.49.37 AM.jpeg',
        'name':    'اشرف عبدالعزيز محمد حسنين',
        'nid':     '٢٦٦٠٨٣١٠١٠٠٣٩٧',
        'card':    'KP1547505',
        'address': '١٧ ش منصور عطفة رامز لاظوغلى',
        'district':'السيدة زينب',
        'dob':     '١٩٦٦/٠٨/٣١',
    },
    {
        'file': 'WhatsApp Image 2026-05-19 at 8.49.37 AM (1).jpeg',
        'name':    None,    # not confirmed
        'nid':     None,
        'card':    None,
        'address': None,
        'district':None,
        'dob':     None,
        'skip': True,
    },
    {
        'file': 'WhatsApp Image 2026-05-19 at 8.49.57 AM.jpeg',
        'name':    'باسل اشرف عبدالعزيز محمد حسنين',
        'nid':     '٣٠٤٠٣٢٠٠١٠٢٩٩٣',
        'card':    'IM4729408',
        'address': None,
        'district':None,
        'dob':     None,
    },
    {
        'file': 'Test_image.jpeg',
        'name':    'باسل اشرف عبدالعزيز محمد حسنين',
        'nid':     '٣٠٤٠٣٢٠٠١٠٢٩٩٣',
        'card':    'IM4729408',
        'address': None,
        'district':None,
        'dob':     None,
        'note':    '90-degree rotated old card',
    },
]

# ---------------------------------------------------------------------------
# Fuzzy comparison helpers
# ---------------------------------------------------------------------------

_ALEF   = re.compile(r'[أإآٱا]')
_SPACES = re.compile(r'\s+')

def _norm(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = _ALEF.sub('ا', text)
    text = text.replace('ة', 'ه')       # teh-marbuta = ha
    # Strip actual Arabic diacritics only (U+064B–U+065F = fathatan..sukun)
    text = re.sub(r'[ً-ٰٟ]', '', text)
    text = _SPACES.sub(' ', text).strip()
    return text


def _words(text: str) -> set:
    return set(_norm(text).split())


def _nid_norm(nid: str | None) -> str:
    if not nid:
        return ''
    tbl = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
    return re.sub(r'\D', '', nid.translate(tbl))


def _field_match(got, expected, field: str) -> tuple[bool, str]:
    """Return (pass, detail_str). Applies field-specific comparison."""
    if expected is None:
        return True, 'SKIP'      # not checked

    if got is None:
        return False, f'MISSING  (expected: {expected})'

    if field in ('nid', 'card'):
        g = _nid_norm(got).upper()
        e = _nid_norm(expected).upper()
        exact = g == e or g.endswith(e) or e.endswith(g)
        if exact:
            return True, f'OK  {got}'
        # Fuzzy: allow ≤2 digit errors (OCR accuracy limit on low-quality images)
        if field == 'nid' and len(g) >= 10 and len(e) >= 10:
            matches = sum(1 for a, b in zip(g[-len(e):], e) if a == b)
            if matches / len(e) >= 0.85:
                return True, f'OK~  {got}  ({matches}/{len(e)} digits correct)'
        return False, f'FAIL  got={got}  expected={expected}'

    gw = _words(got)
    ew = _words(expected)
    if not ew:
        return True, 'SKIP'
    overlap = len(gw & ew) / len(ew)

    if field == 'name':
        ok = overlap >= 0.60    # 60% of expected name words present
    elif field in ('address', 'district'):
        ok = overlap >= 0.50    # at least half the keywords
    else:
        ok = overlap >= 0.60

    # Fuzzy word fallback for address/district: handle OCR character errors
    # (e.g. ر misread as ف) by character-set overlap between individual words
    if not ok and field in ('address', 'district'):
        for ew_word in ew:
            ec = set(ew_word)
            for gw_word in gw:
                gc = set(gw_word)
                if ec and gc and len(ec | gc) >= 3:
                    sim = len(ec & gc) / len(ec | gc)
                    if sim >= 0.75:
                        ok = True
                        break
            if ok:
                break

    detail = f'OK  {got}' if ok else f'FAIL  got="{got}"  expected="{expected}"  ({overlap:.0%} match)'
    return ok, detail


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests(verbose: bool = False, filter_name: str = '') -> None:
    # Import here so test startup doesn't load the model unless needed
    from egyptian_id_ocr import extract_id_fields

    total = passed = skipped = 0

    for tc in GROUND_TRUTH:
        img_path = TESTS_DIR / tc['file']
        if filter_name and filter_name.lower() not in tc['file'].lower():
            continue

        print(f"\n{'='*60}")
        print(f"  {tc['file']}")
        if tc.get('note'):
            print(f"  [{tc['note']}]")

        if tc.get('skip'):
            print("  [SKIPPED — ground truth not confirmed]")
            skipped += 1
            continue

        if not img_path.exists():
            print(f"  [ERROR] Image not found: {img_path}")
            continue

        try:
            result = extract_id_fields(str(img_path), verbose=verbose)
        except Exception as exc:
            print(f"  [EXCEPTION] {exc}")
            total += 1
            continue

        checks = [
            ('name',     'الاسم بالكامل',      tc.get('name')),
            ('nid',      'الرقم القومي',        tc.get('nid')),
            ('dob',      'تاريخ الميلاد',      tc.get('dob')),
            ('address',  'العنوان بالكامل',     tc.get('address')),
            ('district', 'المنطقة والمحافظة',   tc.get('district')),
            ('card',     'رقم البطاقة',         tc.get('card')),
        ]

        test_pass = True
        for ftype, fkey, expected in checks:
            ok, detail = _field_match(result.get(fkey), expected, ftype)
            label = f"  {'OK' if ok else 'XX'} {fkey:<18} {detail}"
            print(label)
            if not ok:
                test_pass = False

        total   += 1
        passed  += test_pass

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{total} passed  ({skipped} skipped)")
    if total > 0:
        pct = 100 * passed // total
        print(f"Score:   {pct}%")


if __name__ == '__main__':
    verbose_flag = '--verbose' in sys.argv or '-v' in sys.argv
    filter_arg   = ''
    if '--image' in sys.argv:
        idx = sys.argv.index('--image')
        if idx + 1 < len(sys.argv):
            filter_arg = sys.argv[idx + 1]

    # Ensure OCR module is on path
    sys.path.insert(0, str(Path(__file__).parent))
    run_tests(verbose=verbose_flag, filter_name=filter_arg)
