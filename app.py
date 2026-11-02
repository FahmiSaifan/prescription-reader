import streamlit as st
import io
import re
import pandas as pd
from PIL import Image

st.set_page_config(page_title="قارئ الوصفات الطبية", page_icon="💊", layout="centered")

st.markdown("""
<style>
    .stApp { direction: rtl; text-align: right; }
</style>
""", unsafe_allow_html=True)

DRUGS_DB = {
    "paracetamol": {
        "aliases": ["paracetamol", "acetaminophen", "panadol", "بنادول", "باراسيتامول"],
        "category": "مسكن وخافض حرارة",
        "max_daily_mg": 4000,
        "warnings": ["لا تتجاوز 4 غرام يومياً", "احذر في أمراض الكبد"],
    },
    "ibuprofen": {
        "aliases": ["ibuprofen", "brufen", "بروفين", "ايبوبروفين"],
        "category": "مضاد التهاب",
        "max_daily_mg": 2400,
        "warnings": ["تناوله بعد الأكل", "احذر في قرحة المعدة"],
    },
    "amoxicillin": {
        "aliases": ["amoxicillin", "amoxil", "أموكسيسيلين"],
        "category": "مضاد حيوي",
        "max_daily_mg": 3000,
        "warnings": ["أكمل الكورس كاملاً", "تحقق من حساسية البنسلين"],
    },
    "metformin": {
        "aliases": ["metformin", "glucophage", "ميتفورمين", "جلوكوفاج"],
        "category": "دواء السكري",
        "max_daily_mg": 2550,
        "warnings": ["تناوله مع الطعام", "راقب وظائف الكلى"],
    },
    "atorvastatin": {
        "aliases": ["atorvastatin", "lipitor", "أتورفاستاتين", "ليبيتور"],
        "category": "خافض كوليسترول",
        "max_daily_mg": 80,
        "warnings": ["تناوله مساءً"],
    },
    "omeprazole": {
        "aliases": ["omeprazole", "losec", "أوميبرازول", "لوسيك"],
        "category": "مثبط مضخة البروتون",
        "max_daily_mg": 40,
        "warnings": ["تناوله قبل الأكل بـ 30 دقيقة"],
    },
    "amlodipine": {
        "aliases": ["amlodipine", "norvasc", "أملوديبين"],
        "category": "خافض ضغط",
        "max_daily_mg": 10,
        "warnings": ["قد يسبب تورم الكاحلين"],
    },
    "augmentin": {
        "aliases": ["augmentin", "co-amoxiclav", "أوجمنتين"],
        "category": "مضاد حيوي مركب",
        "max_daily_mg": 3000,
        "warnings": ["أكمل الكورس كاملاً"],
    },
}

INTERACTIONS = [
    ("ibuprofen", "amlodipine", "قد يقلل تأثير خافض الضغط"),
    ("metformin", "omeprazole", "قد يؤثر على امتصاص فيتامين B12"),
]

DOSAGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|ملغ|مجم|g|غرام|ml|مل|mcg|ميكروغرام|iu)", re.IGNORECASE)

FREQ_PATTERNS = {
    "مرة يومياً": [r"\bonce daily\b", r"\bod\b", r"مرة\s*(?:في\s*)?اليوم"],
    "مرتين يومياً": [r"\btwice daily\b", r"\bbid\b", r"مرتين"],
    "3 مرات يومياً": [r"\bthree times\b", r"\btds\b", r"\btid\b", r"ثلاث\s*مرات", r"3\s*مرات"],
    "4 مرات يومياً": [r"\bqid\b", r"أربع\s*مرات"],
    "عند الحاجة": [r"\bprn\b", r"عند\s*الحاجة"],
    "قبل النوم": [r"\bhs\b", r"قبل\s*النوم"],
}

DURATION_RE = re.compile(r"(\d+)\s*(يوم|أيام|ايام|days?|أسبوع|أسابيع|weeks?|شهر|أشهر|months?)", re.IGNORECASE)


def normalize_drug_name(name):
    name_lower = name.lower().strip()
    for key, info in DRUGS_DB.items():
        if name_lower in key or any(a in name_lower for a in info["aliases"]):
            return key
    return None


def find_frequency(text):
    for label, patterns in FREQ_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return label
    return ""


def extract_medications(ocr_text):
    meds = []
    for line in ocr_text.splitlines():
        line = line.strip()
        if len(line) < 3:
            continue
        drug_key = None
        for word in re.findall(r"[\w\u0600-\u06FF]+", line):
            drug_key = normalize_drug_name(word)
            if drug_key:
                break
        if not drug_key:
            continue
        info = DRUGS_DB[drug_key]
        dosage_m = DOSAGE_RE.search(line)
        freq = find_frequency(line)
        dur_m = DURATION_RE.search(line)
        warnings = list(info["warnings"])
        if dosage_m:
            try:
                val = float(dosage_m.group(1))
                if val > info["max_daily_mg"]:
                    warnings.append("⚠️ الجرعة تتجاوز الحد الأقصى!")
            except ValueError:
                pass
        meds.append({
            "name": drug_key,
            "dosage": f"{dosage_m.group(1)} {dosage_m.group(2)}" if dosage_m else "—",
            "frequency": freq or "—",
            "duration": f"{dur_m.group(1)} {dur_m.group(2)}" if dur_m else "—",
            "category": info["category"],
            "warnings": warnings,
            "raw": line,
        })
    return meds


def run_ocr(image, lang="ara+eng"):
    try:
        import pytesseract
        text = pytesseract.image_to_string(image, lang=lang)
        if not text.strip():
            return "⚠️ لم يتم استخراج نص. جرّب صورة أوضح أو الإدخال اليدوي."
        return text
    except Exception as e:
        return f"❌ تعذر OCR: {e}\n\nاستخدم الإدخال اليدوي."


st.title("💊 قارئ الوصفات الطبية")
st.caption("ارفع صورة وصفة طبية لاستخراج الأدوية والجرعات")
st.warning("⚠️ أداة تعليمية فقط — لا تُغني عن الطبيب أو الصيدلي.")

tab1, tab2 = st.tabs(["📷 من صورة", "✏️ إدخال يدوي"])
ocr_text = ""

with tab1:
    uploaded = st.file_uploader("ارفع صورة الوصفة", type=["jpg", "jpeg", "png"])
    lang_choice = st.selectbox("لغة الوصفة", ["ara+eng", "eng", "ara"], index=0)
    if uploaded is not None:
        image = Image.open(io.BytesIO(uploaded.read()))
        st.image(image, caption="الصورة المرفوعة", use_container_width=True)
        with st.spinner("جاري القراءة..."):
            ocr_text = run_ocr(image, lang_choice)

with tab2:
    manual = st.text_area(
        "أدخل النص يدوياً",
        height=200,
        placeholder="مثال:\nPanadol 500mg twice daily 5 days\nAmoxicillin 500 mg tds 7 days",
    )
    if manual.strip():
        ocr_text = manual

if ocr_text.strip():
    st.divider()
    st.subheader("📝 النص المستخرج")
    with st.expander("عرض النص"):
        st.code(ocr_text, language="text")

    meds = extract_medications(ocr_text)
    st.subheader(f"💊 الأدوية المكتشفة ({len(meds)})")

    if not meds:
        st.info("لم يتم التعرف على أدوية. جرّب صورة أوضح أو الإدخال اليدوي.")
    else:
        df = pd.DataFrame([{
            "الدواء": m["name"],
            "الجرعة": m["dosage"],
            "التكرار": m["frequency"],
            "المدة": m["duration"],
            "الفئة": m["category"],
        } for m in meds])
        st.dataframe(df, use_container_width=True, hide_index=True)

        for m in meds:
            with st.expander(f"🔹 {m['name']}"):
                st.write(f"**السطر الأصلي:** `{m['raw']}`")
                for w in m["warnings"]:
                    st.warning(w)

        st.subheader("🔗 فحص التفاعلات")
        keys = [m["name"] for m in meds]
        found = []
        for a, b, msg in INTERACTIONS:
            if a in keys and b in keys:
                found.append(f"⚠️ {a} + {b}: {msg}")
        if found:
            for f in found:
                st.error(f)
        else:
            st.success("لا توجد تفاعلات معروفة.")
else:
    st.info("👆 ارفع صورة أو أدخل النص للبدء")
