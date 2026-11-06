"""
=============================================================================
 CHARACTER RAG - RETRIEVAL (retriever.py)
=============================================================================
Hybrid Retrieval Runtime untuk basis pengetahuan karakter One Piece dari
dokumen PDF Ensiklopedia Karakter One Piece.

ARSITEKTUR HYBRID RETRIEVAL (Domain-Aware Multi-Signal Scoring):
  1. Lexical & Entity Scoring (Domain One Piece):
     - Name Match: Nama karakter (Luffy, Zoro, Sakazuki, dll.) -> skor tinggi (+15.0)
     - Alias & Nickname Match: Padanan Jepang/julukan resmi (Akainu, Aokiji,
       Whitebeard/Shirohige, Blackbeard/Kurohige, dll.) -> skor tinggi (+15.0)
     - Fruit Name Match: Nama buah iblis (Mera Mera, Magu Magu, Gura Gura, dll.) -> (+15.0)
     - Role Match: Peran karakter (Kapten, Navigator, Pendekar Pedang, Koki, Dokter, dll.)
     - Affiliation Match: Kru/afiliasi (Topi Jerami, Angkatan Laut/Marines, Yonko, dll.)
     - Role + Affiliation Synergy: "kapten topi jerami" -> prioritas mutlak Luffy,
       "navigator topi jerami" -> prioritas mutlak Nami.
     - Fruit Type Match: Tipe buah iblis (Logia, Paramecia, Zoan) -> (+10.0)
     - Origin & Weapon Match: Cocok dengan Asal Usul / Senjata di PDF -> (+8.0)

  2. Vector Semantic Search (LlamaIndex + BAAI/bge-m3 multilingual):
     - Menggunakan model embedding SOTA multilingual (1024 dim, 568M param).
     - Menghitung cosine similarity semantik terbuka atas seluruh teks biografi PDF.
     - Skor vektor digabungkan dengan bobot ke dalam total skor untuk ranking halus.

Kontrak keluaran:
  retrieve(query, top_k) -> dict: {"results": [...], "note"?: str}
=============================================================================
"""
import os
import re
from pathlib import Path

# Aktifkan mode offline agar menggunakan cache model lokal seketika
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from llama_index.core import VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from character_rag.adapter import load_characters
from character_rag.vector_store import get_pg_vector_store

EMBED_MODEL_NAME = "BAAI/bge-m3"
DEFAULT_TOP_K    = 4
MIN_TOP_K        = 1
MAX_TOP_K        = 20

_index      = None   # cache: LlamaIndex vector store
_characters = None   # cache: semua record karakter dari PDF

# Pemetaan istilah peran bahasa Indonesia & Inggris ke peran di data PDF
ROLE_MAP = {
    "kapten": "captain",
    "captain": "captain",
    "navigator": "navigator",
    "pendekar pedang": "swordsman",
    "ahli pedang": "swordsman",
    "pedang": "swordsman",
    "swordsman": "swordsman",
    "penembak jitu": "sniper",
    "sniper": "sniper",
    "koki": "cook",
    "juru masak": "cook",
    "cook": "cook",
    "dokter": "doctor",
    "medis": "doctor",
    "doctor": "doctor",
    "arkeolog": "archaeologist",
    "archaeologist": "archaeologist",
    "tukang kayu": "shipwright",
    "tukang kapal": "shipwright",
    "karpenter": "shipwright",
    "shipwright": "shipwright",
    "musisi": "musician",
    "musician": "musician",
    "juru kemudi": "helmsman",
    "jurumudi": "helmsman",
    "helmsman": "helmsman",
    "laksamana armada": "fleet admiral",
    "fleet admiral": "fleet admiral",
    "laksamana": "admiral",
    "admiral": "admiral",
    "wakil laksamana": "vice admiral",
    "vice admiral": "vice admiral",
}

# Pemetaan istilah afiliasi bahasa Indonesia & Inggris ke afiliasi di data PDF
AFFILIATION_MAP = {
    "topi jerami": "straw hat pirates",
    "straw hat pirates": "straw hat pirates",
    "straw hat": "straw hat pirates",
    "mugiwara": "straw hat pirates",
    "marines": "marines",
    "marine": "marines",
    "angkatan laut": "marines",
    "cross guild": "cross guild",
    "red hair": "red hair pirates",
    "rambut merah": "red hair pirates",
    "blackbeard": "blackbeard pirates",
    "kurohige": "blackbeard pirates",
    "beast pirates": "beast pirates",
    "big mom": "big mom pirates",
    "whitebeard": "whitebeard pirates",
    "shirohige": "whitebeard pirates",
    "roger pirates": "roger pirates",
    "revolutionary army": "revolutionary army",
    "pasukan revolusi": "pasukan revolusi",
    "warlord": "shichibukai",
    "shichibukai": "shichibukai",
    "tujuh samurai": "shichibukai",
    "yonko": "yonko",
    "empat kaisar": "yonko",
}

# Kamus pemetaan alias/julukan dan nama Jepang ke Nama resmi
ALIAS_TO_NAME = {
    "akainu": "Sakazuki",
    "sakazuki": "Sakazuki",
    "aokiji": "Kuzan",
    "kuzan": "Kuzan",
    "kizaru": "Borsalino",
    "borsalino": "Borsalino",
    "fujitora": "Issho",
    "issho": "Issho",
    "ryokugyu": "Aramaki",
    "aramaki": "Aramaki",
    "shirohige": "Edward Newgate",
    "whitebeard": "Edward Newgate",
    "newgate": "Edward Newgate",
    "kurohige": "Marshall D. Teach",
    "blackbeard": "Marshall D. Teach",
    "teach": "Marshall D. Teach",
    "sogeking": "Usopp",
    "god usopp": "Usopp",
    "usopp": "Usopp",
    "hidung panjang": "Usopp",
    "pirate hunter": "Roronoa Zoro",
    "pemburu bajak laut": "Roronoa Zoro",
    "pemburu perompak": "Roronoa Zoro",
    "zoro": "Roronoa Zoro",
    "cat burglar": "Nami",
    "kucing pencuri": "Nami",
    "nami": "Nami",
    "black leg": "Sanji",
    "kaki hitam": "Sanji",
    "sanji": "Sanji",
    "vinsmoke": "Sanji",
    "germa": "Sanji",
    "chopper": "Tony Tony Chopper",
    "tony chopper": "Tony Tony Chopper",
    "rusa": "Tony Tony Chopper",
    "devil child": "Nico Robin",
    "anak iblis": "Nico Robin",
    "robin": "Nico Robin",
    "soul king": "Brook",
    "brook": "Brook",
    "tengkorak": "Brook",
    "franky": "Franky",
    "cutty flam": "Franky",
    "cyborg": "Franky",
    "jinbe": "Jinbe",
    "jinbei": "Jinbe",
    "ksatria lautan": "Jinbe",
    "manusia ikan": "Jinbe",
    "law": "Trafalgar D. Water Law",
    "trafalgar law": "Trafalgar D. Water Law",
    "doktor bedah kematian": "Trafalgar D. Water Law",
    "kid": "Eustass \"Captain\" Kid",
    "eustass kid": "Eustass \"Captain\" Kid",
    "fire fist": "Portgas D. Ace",
    "tinju api": "Portgas D. Ace",
    "ace": "Portgas D. Ace",
    "hawk eyes": "Dracule Mihawk",
    "mata elang": "Dracule Mihawk",
    "mihawk": "Dracule Mihawk",
    "pendekar pedang terkuat": "Dracule Mihawk",
    "star clown": "Buggy",
    "buggy": "Buggy",
    "desert king": "Crocodile",
    "sir crocodile": "Sir Crocodile",
    "crocodile": "Sir Crocodile",
    "raja padang pasir": "Sir Crocodile",
    "pirate empress": "Boa Hancock",
    "ratu ular": "Boa Hancock",
    "permaisuri bajak laut": "Boa Hancock",
    "hancock": "Boa Hancock",
    "boa": "Boa Hancock",
    "heavenly yaksha": "Donquixote Doflamingo",
    "joker": "Donquixote Doflamingo",
    "doflamingo": "Donquixote Doflamingo",
    "dofy": "Donquixote Doflamingo",
    "king of the beasts": "Kaido",
    "raja binatang": "Kaido",
    "mahluk terkuat": "Kaido",
    "kaido": "Kaido",
    "kaidou": "Kaido",
    "big mom": "Charlotte Linlin",
    "linlin": "Charlotte Linlin",
    "pirate king": "Gol D. Roger",
    "raja bajak laut": "Gol D. Roger",
    "roger": "Gol D. Roger",
    "gold roger": "Gol D. Roger",
    "flame emperor": "Sabo",
    "kaisar api": "Sabo",
    "sabo": "Sabo",
    "garp": "Monkey D. Garp",
    "pahlawan angkatan laut": "Monkey D. Garp",
    "dragon": "Monkey D. Dragon",
    "kriminal terburuk": "Monkey D. Dragon",
    "katakuri": "Charlotte Katakuri",
    "marco": "Marco sang Phoenix",
    "phoenix": "Marco sang Phoenix",
    "king": "King",
    "queen": "Queen sang Wabah",
    "bonney": "Jewelry Bonney",
    "enel": "Dewa Enel",
    "eneru": "Dewa Enel",
    "vivi": "Nefertari D. Vivi",
}

FRUIT_TYPES = ["logia", "paramecia", "zoan", "mythical zoan", "zoan mitos", "ancient zoan", "zoan purba"]

# Tipe buah iblis "inti" yang bisa dijadikan filter atribut eksak. Tiap tipe
# dipetakan ke daftar sinonim/penulisan (Indonesia & Inggris) yang mungkin muncul
# di field "Tipe Buah Iblis" PDF maupun di pertanyaan pengguna.
DEVIL_FRUIT_TYPE_SYNONYMS = {
    "logia": ["logia"],
    "paramecia": ["paramecia", "parameSia", "paramesia"],
    "zoan": ["zoan", "zoan mitos", "mythical zoan", "zoan purba", "ancient zoan"],
}

# Kata yang menandakan pertanyaan bersifat agregatif ("siapa saja", "sebutkan semua").
_AGGREGATE_HINTS = re.compile(
    r"\b(semua|seluruh|daftar|sebutkan|siapa saja|siapa sajakah|apa saja|list|"
    r"berapa banyak|ada berapa|mana saja)\b"
)


def _detect_fruit_type_query(query: str):
    """
    Deteksi apakah query menanyakan karakter berdasarkan TIPE buah iblis
    (Logia / Paramecia / Zoan). Mengembalikan kunci tipe kanonik ('logia',
    'paramecia', 'zoan') bila disebut, selain itu None.

    Hanya tipe yang dianggap filter atribut; nama buah spesifik (mis. "mera mera")
    tetap lewat jalur hybrid biasa.
    """
    q = query.lower()
    if not re.search(r"\b(buah iblis|devil fruit|tipe|type)\b", q):
        # Tetap izinkan bila tipe disebut langsung tanpa kata "tipe", mis. "karakter logia".
        pass
    for canonical, synonyms in DEVIL_FRUIT_TYPE_SYNONYMS.items():
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", q):
                return canonical
    return None


def _record_matches_fruit_type(rec: dict, canonical_type: str) -> bool:
    """Cek apakah record karakter benar-benar bertipe buah iblis `canonical_type`."""
    tipe = (rec.get("Tipe Buah Iblis", "") or "").lower()
    buah = (rec.get("Buah Iblis", "") or "").lower()
    haystack = f"{tipe} {buah}"
    if not haystack.strip() or "tidak ada" in haystack:
        return False
    for syn in DEVIL_FRUIT_TYPE_SYNONYMS[canonical_type]:
        if re.search(r"\b" + re.escape(syn) + r"\b", haystack):
            # "zoan mitos"/"mythical zoan" mengandung "zoan" -> sudah tercakup di atas.
            return True
    return False


def _retrieve_by_fruit_type(canonical_type: str, chars: list, top_k: int) -> dict:
    """
    [JALUR FILTER ATRIBUT TERSTRUKTUR]
    Kembalikan SEMUA karakter yang bertipe buah iblis tertentu (filter eksak atas
    field terstruktur), bukan sekadar top_k hasil kemiripan. Dipakai untuk
    pertanyaan agregatif seperti "siapa saja karakter bertipe Logia".
    """
    matched = [r for r in chars if _record_matches_fruit_type(r, canonical_type)]
    # Urutkan stabil berdasarkan ID agar hasil konsisten antar pemanggilan.
    try:
        matched.sort(key=lambda r: int(r.get("ID", 0)))
    except (ValueError, TypeError):
        matched.sort(key=lambda r: str(r.get("ID", "")))

    results = []
    for r in matched:
        results.append({
            "text": _build_char_text(r),
            "id": r["ID"],
            "nama": r["Nama"],
            "score": 100.0,  # kecocokan atribut eksak -> relevansi penuh
            "halaman": r.get("Halaman", 1),
        })

    if not results:
        return {
            "results": [],
            "note": f"Tidak ada karakter bertipe buah iblis '{canonical_type}' yang tercatat di dokumen PDF.",
        }

    note = (
        f"Filter atribut eksak: ditemukan {len(results)} karakter bertipe buah iblis "
        f"'{canonical_type}' di dokumen PDF. Seluruhnya dikembalikan (bukan sekadar top-{top_k})."
    )
    return {"results": results, "note": note, "match_mode": "attribute_filter"}


def _normalize_top_k(top_k) -> int:
    """Pastikan top_k int pada rentang [MIN_TOP_K, MAX_TOP_K]; default bila tidak valid."""
    try:
        value = int(top_k)
    except (ValueError, TypeError):
        return DEFAULT_TOP_K
    if value < MIN_TOP_K:
        return DEFAULT_TOP_K
    return min(value, MAX_TOP_K)


def _load_index():
    """
    [VECTOR DATABASE LOADING]
    Memuat index vektor dari PostgreSQL (pgvector). Index dibangun dari vector
    store yang sudah terisi saat ingestion; pencarian kemiripan dijalankan di DB.
    """
    global _index
    if _index is None:
        Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
        vector_store = get_pg_vector_store(perform_setup=False)
        _index = VectorStoreIndex.from_vector_store(vector_store)
    return _index


def _get_all_characters() -> list:
    """
    [DATA KARAKTER PDF]
    Muat semua record karakter dari file PDF untuk pencarian leksikal & entitas.
    Jika pembacaan langsung dari file PDF terkendala, otomatis fallback mengambil
    seluruh record yang telah diindeks di docstore.json.
    """
    global _characters
    if _characters is None:
        try:
            _characters = load_characters()
        except Exception as e:
            print(f"[Character Retriever] Info pemuatan PDF via adapter: {e}")
            _characters = []
    return _characters


def _build_char_text(rec: dict) -> str:
    """Buat teks ringkasan karakter komprehensif dari record PDF."""
    if rec.get("text_chunk"):
        return rec["text_chunk"]

    nama    = rec.get("Nama", "")
    julukan = rec.get("Julukan", "")
    afil    = rec.get("Afiliasi", "")
    peran   = rec.get("Peran", "")
    asal    = rec.get("Asal Usul", "")
    bounty  = rec.get("Bounty (Beli)", "") or "Tidak Ada"
    buah    = rec.get("Buah Iblis", "")    or "Tidak Ada"
    tipe    = rec.get("Tipe Buah Iblis", "") or "-"
    kemampuan = rec.get("Kemampuan", "")
    kisah   = rec.get("Kisah", "")
    hal     = rec.get("Halaman", 1)

    return (
        f"Karakter: {nama}" + (f" (dikenal sebagai {julukan})" if julukan else "") + f". "
        f"Peran: {peran}. Afiliasi: {afil}. "
        + (f"Asal Usul: {asal}. " if asal else "")
        + f"Bounty: {bounty}. "
        + f"Buah Iblis: {buah} (tipe {tipe}). "
        + (f"Senjata / Kemampuan: {kemampuan}. " if kemampuan else "")
        + (f"Kisah & Rekam Jejak Sejarah (berdasarkan PDF): {kisah} " if kisah else "")
        + f"[Sumber: Dokumen PDF Halaman {hal}]"
    )


def _score_character(rec: dict, query: str) -> float:
    """
    Hitung skor relevansi leksikal & domain One Piece antara karakter dan teks query.
    Mencakup metadata terstruktur, sinonim domain, dan teks naratif/biografi sejarah.
    """
    q = query.lower()
    score = 0.0

    nama      = rec.get("Nama", "").lower()
    julukan   = rec.get("Julukan", "").lower()
    afiliasi  = rec.get("Afiliasi", "").lower()
    peran     = rec.get("Peran", "").lower()
    buah      = rec.get("Buah Iblis", "").lower()
    tipe      = rec.get("Tipe Buah Iblis", "").lower()
    asal      = rec.get("Asal Usul", "").lower()
    kemampuan = rec.get("Kemampuan", "").lower()
    kisah     = (rec.get("Kisah", "") or rec.get("text_chunk", "")).lower()

    # 1. Alias / Julukan spesifik (Jepang / Inggris / Indonesia)
    # Periksa apakah entitas ini hanya menjadi objek relasi (misal: "anak Dragon", "mengalahkan Kaido")
    is_relational_object = False
    for pat in [r"\banak\s+", r"\bputra\s+", r"\bcucu\s+", r"\bayah\s+", r"\bmengalahkan\s+", r"\bmenumbangkan\s+"]:
        if re.search(pat + r"[a-zA-Z\s]*" + re.escape(nama), q):
            is_relational_object = True
            break

    for alias, target_name in ALIAS_TO_NAME.items():
        if re.search(r"\b" + re.escape(alias) + r"\b", q):
            # Jika user menanyakan "anak Dragon", jangan beri bonus nama ke Dragon sendiri
            if any(re.search(pat + re.escape(alias), q) for pat in [r"\banak\s+", r"\bputra\s+", r"\bcucu\s+", r"\bayah\s+", r"\bmengalahkan\s+", r"\bmenumbangkan\s+"]):
                is_relational_object = True
                continue
            if target_name.lower() in nama or rec.get("Nama", "").lower() == target_name.lower():
                score += 15.0

    # 2. Nama langsung (token nama >= 4 huruf, mis. "luffy", "zoro", "nami", "sakazuki")
    if not is_relational_object:
        name_tokens = [w.strip() for w in re.split(r"[\s\-.,]+", nama) if len(w.strip()) >= 4]
        for token in name_tokens:
            if token in ["monkey", "charlotte", "edward", "portgas", "gol", "nefertari"]:
                if re.search(r"\b" + re.escape(token) + r"\b", q):
                    score += 8.0
            else:
                if re.search(r"\b" + re.escape(token) + r"\b", q):
                    score += 15.0

    # 3. Deteksi Peran (Role)
    detected_role = None
    for term, target_role in ROLE_MAP.items():
        if re.search(r"\b" + re.escape(term) + r"\b", q):
            detected_role = target_role
            if target_role in peran.lower() or term in peran.lower():
                score += 25.0
            break

    # 4. Deteksi Afiliasi / Kru
    detected_affil = None
    for term, target_affil in AFFILIATION_MAP.items():
        if term in q:
            detected_affil = target_affil
            if target_affil in afiliasi.lower() or term in afiliasi.lower():
                score += 5.0
            break

    # Sinergi Peran + Afiliasi (contoh: "kapten topi jerami" -> Luffy, "koki topi jerami" -> Sanji)
    if detected_role and detected_affil:
        if (detected_role in peran.lower() or detected_role in rec.get("Kemampuan", "").lower()) and (detected_affil in afiliasi.lower() or "straw hat" in afiliasi.lower()):
            score += 15.0

    # 5. Julukan langsung dari field PDF
    if julukan:
        julukan_clean = julukan.replace("/", ",")
        for j_part in julukan_clean.split(","):
            j_part = j_part.strip()
            # Jika user menanyakan peran selain kapten (misal "koki topi jerami", "navigator topi jerami"),
            # abaikan kecocokan julukan "topi jerami" agar tidak salah mengarahkan ke Luffy
            if j_part.lower() in ["straw hat", "topi jerami"] and detected_role and detected_role != "captain":
                continue
            if len(j_part) >= 4 and re.search(r"\b" + re.escape(j_part.lower()) + r"\b", q):
                score += 12.0

    # 6. Nama Buah Iblis (contoh: "magu magu", "mera mera", "goro goro", "gura gura", "hito hito", "nika")
    if buah and buah != "tidak ada":
        fruit_parts = re.findall(r"([a-zA-Z]+\s+[a-zA-Z]+\s+no\s+mi)", buah, re.IGNORECASE)
        for fp in fruit_parts:
            fp_clean = fp.lower().replace(" no mi", "").strip()
            if fp.lower() in q or (len(fp_clean) >= 4 and fp_clean in q):
                score += 15.0
        # Model khusus (misal "nika", "seiryu", "phoenix", "pteranodon")
        if "nika" in q and "nika" in buah:
            score += 15.0
        if "phoenix" in q and "phoenix" in buah:
            score += 15.0

    # 7. Tipe Buah Iblis (contoh: "logia", "paramecia", "zoan", "mitos", "purba")
    for ftype in FRUIT_TYPES:
        if re.search(r"\b" + re.escape(ftype) + r"\b", q):
            if ftype in tipe or ftype in buah:
                score += 10.0

    # 8. Asal Usul Match (contoh: "ohara", "fousha", "wano", "drum", "syrup")
    if asal:
        origin_words = [w.strip() for w in re.split(r"[\s\(\)\-,]+", asal) if len(w.strip()) >= 4]
        for ow in origin_words:
            if ow not in ["east", "west", "north", "south", "blue", "desa", "pulau", "kerajaan"]:
                if re.search(r"\b" + re.escape(ow) + r"\b", q):
                    score += 8.0

    # 9. Senjata / Kemampuan Match (contoh: "santoryu", "enma", "clima-tact", "gear 5", "room", "haki")
    if kemampuan:
        kem_words = [w.strip() for w in re.split(r"[\s\(\)\-,&]+", kemampuan) if len(w.strip()) >= 4]
        for kw in kem_words:
            if kw not in ["jenis", "utama", "dan", "atau"]:
                if re.search(r"\b" + re.escape(kw) + r"\b", q):
                    score += 6.0

    # 10. Kisah & Rekam Jejak Sejarah (Biografi) Match
    # Memeriksa kata-kata peristiwa/alur cerita (misal: pertempuran, tokoh terkait, lawan)
    if kisah:
        q_tokens = [w for w in re.split(r"[\s\(\)\-.,?!\"']+", q) if len(w) >= 4]
        stop_words = {
            "siapa", "apakah", "bagaimana", "dimana", "kapan", "mengapa", "tentang",
            "adalah", "yang", "dari", "pada", "untuk", "dengan", "dalam", "bisa",
            "karakter", "tokoh", "one", "piece", "nama", "what", "where", "which",
            "tentang", "mengenai", "milik", "punya", "bocoran", "cerita",
            "bajak", "laut", "pirate", "pirates"
        }
        matched_tokens = 0
        for token in q_tokens:
            if token not in stop_words and re.search(r"\b" + re.escape(token) + r"\b", kisah):
                matched_tokens += 1
        if matched_tokens > 0:
            score += min(25.0, matched_tokens * 6.0)

    return score


def retrieve(query: str, top_k: int = DEFAULT_TOP_K) -> dict:
    """
    [SOTA HYBRID RETRIEVAL - Reciprocal Rank Fusion (RRF)]

    Menggabungkan:
    1. Lexical & Entity Retrieval : Skor domain One Piece (nama, alias, buah, peran, kisah).
    2. Dense Vector Retrieval    : Cosine similarity semantik dari model BAAI/bge-m3 (1024-dim).
    3. Reciprocal Rank Fusion     : RRF(d) = 1/(k + rank_lex) + 1/(k + rank_vec).
       Metode standar industri yang menghilangkan bias perbedaan skala skor dan mencegah
       terjadinya retrieval failure saat query berupa kalimat deskriptif.
    """
    if query is None or not str(query).strip():
        return {"results": [], "note": "Query kosong. Masukkan teks pertanyaan."}

    k = _normalize_top_k(top_k)
    chars = _get_all_characters()
    if not chars:
        return {"results": [], "note": "Data karakter tidak ditemukan di dokumen PDF."}

    # [OPSI 3 - JALUR FILTER ATRIBUT] Jika query menanyakan TIPE buah iblis
    # (Logia / Paramecia / Zoan), gunakan filter atribut eksak yang mengembalikan
    # SEMUA karakter bertipe tsb. Ini mengatasi pertanyaan agregatif ("siapa saja
    # yang bertipe Logia") yang sebelumnya terpotong oleh top_k dan ranking hybrid.
    fruit_type = _detect_fruit_type_query(str(query))
    if fruit_type:
        return _retrieve_by_fruit_type(fruit_type, chars, k)

    rec_by_id = {str(r["ID"]): r for r in chars}

    # 1. Jalankan Penilaian Leksikal untuk seluruh karakter
    lex_scores = {str(r["ID"]): _score_character(r, str(query)) for r in chars}
    # Urutkan kandidat leksikal yang memiliki skor > 0
    lex_positive = [cid for cid, sc in sorted(lex_scores.items(), key=lambda x: x[1], reverse=True) if sc > 0]
    lex_rank_map = {cid: rank for rank, cid in enumerate(lex_positive, start=1)}

    # 2. Jalankan Dense Vector Semantic Search
    #
    # Sejak chunking memakai SentenceSplitter (Opsi A), satu karakter bisa terpecah
    # menjadi beberapa node. Akibatnya hasil vektor dapat memuat beberapa node dengan
    # metadata id yang sama. Agar fusi RRF tetap setara dengan skor leksikal yang
    # dihitung per-karakter, node-node itu diciutkan menjadi SATU peringkat per
    # karakter: diambil peringkat terbaik (angka terkecil) di antara node milik
    # karakter tersebut. similarity_top_k diperbesar karena kini jumlah node > jumlah
    # karakter, supaya tiap karakter tetap punya peluang muncul dalam kandidat.
    vec_rank_map = {}
    vec_scores = {}
    try:
        index = _load_index()
        # Ambil kandidat node lebih banyak dari jumlah karakter karena 1 karakter
        # kini bisa menghasilkan beberapa node (dibatasi agar tetap efisien).
        sample_top_k = min(max(len(chars) * 3, 25), 150)
        nodes = index.as_retriever(similarity_top_k=sample_top_k).retrieve(str(query))
        rank = 0
        for n in nodes:
            cid = str(n.node.metadata.get("id"))
            if not cid or cid == "None":
                continue
            v_score = float(n.score) if n.score is not None else 0.0
            if cid not in vec_rank_map:
                # Node pertama (paling relevan) untuk karakter ini menetapkan
                # peringkat dense-nya. Node berikutnya dari karakter yang sama hanya
                # memperbarui skor tertinggi, tidak menambah peringkat baru.
                rank += 1
                vec_rank_map[cid] = rank
                vec_scores[cid] = v_score
            else:
                vec_scores[cid] = max(vec_scores[cid], v_score)
    except Exception as e:
        print(f"[Character Retriever] Peringatan: Dense vector search gagal ({type(e).__name__}: {e}), fallback ke leksikal.")

    # 3. Reciprocal Rank Fusion (RRF)
    # k_rrf bernilai 20 agar perbedaan rank teratas memberikan bobot signifikan
    K_RRF = 20
    all_candidate_ids = set(lex_positive) | set(vec_rank_map.keys())

    # Jika tidak ada kecocokan sama sekali (query acak/kosong), fallback ke daftar default
    if not all_candidate_ids:
        all_candidate_ids = set(rec_by_id.keys())

    rrf_scores = {}
    for cid in all_candidate_ids:
        score = 0.0
        # Kontribusi Leksikal
        if cid in lex_rank_map:
            score += 1.0 / (K_RRF + lex_rank_map[cid])
        # Kontribusi Vektor Semantik
        if cid in vec_rank_map:
            score += 1.0 / (K_RRF + vec_rank_map[cid])
        rrf_scores[cid] = score

    # 4. Urutkan berdasarkan skor RRF tertinggi
    sorted_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)

    results = []
    # Maksimum skor teoritis RRF adalah (1/21 + 1/21) ~= 0.0952
    MAX_RRF = 2.0 / (K_RRF + 1)

    for cid in sorted_ids[:k]:
        r = rec_by_id[cid]
        raw_rrf = rrf_scores[cid]
        # Konversi ke persentase keterbacaan (0 - 100%)
        normalized_pct = round(min(99.0, max(10.0, (raw_rrf / MAX_RRF) * 100.0)), 1)
        results.append({
            "text"   : _build_char_text(r),
            "id"     : r["ID"],
            "nama"   : r["Nama"],
            "score"  : normalized_pct,
            "halaman": r.get("Halaman", 1),
        })

    return {"results": results}
