"""
=============================================================================
 CHARACTER ADAPTER — adapter.py (PDF Engine)
=============================================================================
Lapisan abstraksi data (Data Ingestion & Preprocessing Layer) yang membaca
dokumen PDF Ensiklopedia Karakter One Piece:
"ENSIKLOPEDIA ARSIP DATA 50 KARAKTER ONE PIECE: Studi Eksploratif Biografi,
Asal Usul, Status Bounty, Buah Iblis, dan Rekam Jejak Sejarah".

Pipeline Preprocessing:
1. Ekstraksi teks multi-halaman dari dokumen PDF menggunakan `pypdf`.
2. Normalisasi karakter (ligatur font PDF, tanda kutip, strip, dan whitespace).
3. Pembersihan header/footer halaman secara otomatis.
4. Segmentasi entitas karakter per kartu biografis dan identifikasi bagian bab.
5. Ekstraksi atribut terstruktur: ID, Nama, Julukan, Peran, Afiliasi, Asal Usul,
   Bounty, Buah Iblis, Tipe Buah Iblis, Senjata/Kemampuan Utama, dan Kisah & Rekam Jejak.
6. Pembangunan teks naratif komprehensif (text_chunk) untuk tahap chunking & embedding semantik.
=============================================================================
"""
import re
from pathlib import Path

try:
    import pypdf
except ImportError:
    pypdf = None


class CharacterAdapterError(Exception):
    """Sumber data karakter tidak tersedia atau gagal diproses."""


PDF_PATH = Path(__file__).resolve().parent.parent / "data" / "one-piece-characters.pdf"

FIELDS = (
    "ID",
    "Nama",
    "Julukan",
    "Afiliasi",
    "Peran",
    "Bagian",
    "Asal Usul",
    "Bounty (Beli)",
    "Buah Iblis",
    "Tipe Buah Iblis",
    "Kemampuan",
    "Kisah",
    "Halaman",
    "text_chunk",
)


def normalize_pdf_text(text: str) -> str:
    """
    [PREPROCESSING: Normalisasi Teks & Ligatur PDF]
    Mengubah ligatur tipografi PDF (fi, fl, ffi, dll.) dan simbol non-standar
    menjadi teks biasa agar model embedding dan pencarian teks bekerja optimal.
    """
    ligatures = {
        "\ufb00": "ff",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\ufb03": "ffi",
        "\ufb04": "ffl",
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\xa0": " ",
    }
    for k, v in ligatures.items():
        text = text.replace(k, v)
    return text


def _extract_from_pdf(pdf_path: Path) -> list[dict]:
    """Ekstraksi terstruktur dari file PDF Ensiklopedia Karakter One Piece."""
    if pypdf is None:
        raise CharacterAdapterError(
            "Library 'pypdf' belum terpasang. Jalankan: pip install pypdf"
        )

    try:
        reader = pypdf.PdfReader(str(pdf_path))
    except Exception as e:
        raise CharacterAdapterError(f"Gagal membuka file PDF {pdf_path}: {e}")

    records = []
    current_section = "Ensiklopedia One Piece"

    for page_idx, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        norm_text = normalize_pdf_text(raw_text)

        lines = norm_text.splitlines()
        clean_lines = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            # Bersihkan judul buku & penanda halaman footer
            if "ENSIKLOPEDIA ARSIP DATA 50 KARAKTER" in line_str:
                continue
            if "Studi Eksploratif Biografi" in line_str:
                continue
            if "Ensiklopedia Arsip Data 50 Karakter" in line_str and "Halaman" in line_str:
                continue
            clean_lines.append(line_str)

        page_content = "\n".join(clean_lines)

        # Segmentasi per nomor kartu karakter (mis. "1. ", "2. ", "14. ")
        chunks = re.split(r"(?m)(?=^\d+\.\s+)", page_content)

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue

            # Periksa dan tangkap header Bab/Bagian (mis. BAGIAN I, BAGIAN II)
            sec_match = re.search(r"BAGIAN\s+[IVXLCDM]+:\s*([^\n]+)", chunk)
            if sec_match:
                current_section = sec_match.group(0).strip()
                chunk = re.sub(r"BAGIAN\s+[IVXLCDM]+:\s*[^\n]+", "", chunk).strip()
                if not chunk:
                    continue

            # Verifikasi baris awal karakter
            m_header = re.match(r"^(\d+)\.\s+([^\n]+)", chunk)
            if not m_header:
                continue

            cid = m_header.group(1).strip()
            header_line = m_header.group(2).strip()

            julukan = ""
            nama = ""
            peran = ""

            # Pola 1: Nama (Julukan) Peran
            m_paren = re.match(r"^(.+?)\s*\((.+?)\)\s*(.*)$", header_line)
            if m_paren:
                nama = m_paren.group(1).strip()
                julukan = m_paren.group(2).strip()
                peran = m_paren.group(3).strip()
            else:
                # Pola 2: Nama "Julukan" Peran
                m_quote = re.match(r'^(.+?)\s*"(.+?)"\s*(.+?)\s{2,}(.+)$', header_line)
                if m_quote:
                    nama = f"{m_quote.group(1).strip()} {m_quote.group(3).strip()}"
                    julukan = m_quote.group(2).strip()
                    peran = m_quote.group(4).strip()
                else:
                    # Pola 3: Nama Peran dipisah spasi ganda (format Bagian I-V)
                    parts = re.split(r"\s{2,}", header_line)
                    if len(parts) >= 2:
                        nama = parts[0].strip()
                        peran = parts[1].strip()
                    else:
                        # Pola 4: Nama Peran TANPA pemisah spasi ganda (format Bagian VI,
                        # mis. "Charlotte Katakuri Komandan Manisan Terkuat Big Mom").
                        # Pisahkan pada kata pertama yang menandai jabatan/peran.
                        # Catatan: "Dewa" sengaja TIDAK dimasukkan sebagai kata peran
                        # karena ia bagian nama (mis. "Dewa Enel"). "Mantan Penguasa"
                        # sudah ditangkap lewat "Mantan"/"Penguasa".
                        role_kw = re.search(
                            r"\b(Komandan|Kapten|Laksamana|Vice\s+Admiral|Mantan|Pemimpin|"
                            r"Penguasa|Raja|Ratu|Putri|Putra|Pangeran|Gubernur|Kepala\s+Staf|"
                            r"Anggota|Pendiri|Jurumudi|Navigator|Dokter|Koki|Arkeolog|"
                            r"Musisi|Karpenter|Penembak|Pendekar)\b",
                            header_line,
                        )
                        if role_kw and role_kw.start() > 0:
                            nama = header_line[:role_kw.start()].strip()
                            peran = header_line[role_kw.start():].strip()
                        else:
                            nama = header_line
                            peran = ""

            body = chunk[m_header.end():].strip()

            # Asal Usul
            asal_usul = ""
            m_asal = re.search(r"Asal Usul:\s*(.*?)(?=\s*Bounty:|\n|$)", body)
            if m_asal:
                asal_usul = m_asal.group(1).strip()

            # Bounty
            bounty = ""
            m_bounty = re.search(
                r"Bounty:\s*(.*?)(?=\s*(?:Buah Iblis:|Kemampuan Utama:|Senjata\s*/|Senjata:|\n|$))",
                body,
            )
            if m_bounty:
                bounty = m_bounty.group(1).strip()

            # Buah Iblis
            buah_iblis = ""
            m_buah = re.search(
                r"Buah Iblis:\s*(.*?)(?=\s*(?:Kemampuan Utama:|Senjata\s*/|Senjata:|Kisah|\n|$))",
                body,
            )
            if m_buah:
                buah_iblis = m_buah.group(1).strip()

            # Kemampuan Utama / Senjata
            kemampuan = ""
            m_kem = re.search(
                r"(?:Kemampuan Utama|Senjata\s*/\s*Kekuatan|Senjata):\s*(.*?)(?=\s*(?:Kisah\s*&|Kisah:|\n|$))",
                body,
            )
            if m_kem:
                kemampuan = m_kem.group(1).strip()

            # Kisah & Rekam Jejak Sejarah
            kisah = ""
            m_kisah = re.search(r"(?:Kisah\s*&\s*Rekam Jejak|Kisah):\s*(.+)$", body, re.DOTALL)
            if m_kisah:
                kisah = " ".join(m_kisah.group(1).split())

            # Ekstrak tipe buah iblis jika ada tanda kurung (Paramecia, Logia, Zoan, dll.)
            tipe_buah = "-"
            if buah_iblis:
                m_tipe = re.search(r"\(([^)]+)\)", buah_iblis)
                if m_tipe:
                    tipe_buah = m_tipe.group(1).strip()

            # Petakan Afiliasi berdasarkan Bagian atau Peran
            afiliasi = ""
            if "TOPI JERAMI" in current_section:
                afiliasi = "Straw Hat Pirates"
            elif "YONKO" in current_section or "LEGENDA" in current_section:
                if "Roger" in peran or "Roger" in nama:
                    afiliasi = "Roger Pirates"
                elif "Shirohige" in peran or "Shirohige" in julukan or "Newgate" in nama:
                    afiliasi = "Whitebeard Pirates"
                elif "Beast" in peran or "Kaido" in nama:
                    afiliasi = "Beast Pirates"
                elif "Big Mom" in peran or "Totto Land" in peran or "Linlin" in nama:
                    afiliasi = "Big Mom Pirates"
                elif "Akagami" in peran or "Shanks" in nama:
                    afiliasi = "Red Hair Pirates"
                elif "Blackbeard" in peran or "Kurohige" in peran or "Teach" in nama:
                    afiliasi = "Blackbeard Pirates"
                else:
                    afiliasi = "Yonko / Legenda"
            elif "ANGKATAN LAUT" in current_section or "NAVY" in current_section:
                afiliasi = "Marines / Angkatan Laut"
            elif "PASUKAN REVOLUSI" in current_section:
                if "Pasukan Revolusi" in peran or "Dragon" in nama or "Sabo" in nama:
                    afiliasi = "Pasukan Revolusi"
                elif "Cross Guild" in peran:
                    afiliasi = "Cross Guild"
                elif "Shichibukai" in peran or "Dressrosa" in peran or "Amazon Lily" in peran:
                    afiliasi = "Mantan Shichibukai / Sekutu"
                else:
                    afiliasi = "Revolusi / Shichibukai"
            elif "TOKOH PENTING" in current_section:
                if "Big Mom" in peran:
                    afiliasi = "Big Mom Pirates"
                elif "Shirohige" in peran:
                    afiliasi = "Whitebeard Pirates"
                elif "Beast Pirates" in peran or "Kaido" in peran:
                    afiliasi = "Beast Pirates"
                elif "Bonney Pirates" in peran:
                    afiliasi = "Bonney Pirates"
                elif "Skypiea" in peran:
                    afiliasi = "Skypiea"
                elif "Alabasta" in peran:
                    afiliasi = "Kerajaan Alabasta"
                else:
                    afiliasi = "Tokoh Kunci Dunia Baru"

            # Teks narasi utuh (chunk) yang memuat seluruh dimensi data dari PDF.
            # Field yang kosong ditandai EKSPLISIT "Tidak tercatat dalam dokumen PDF"
            # (bukan dihilangkan), agar LLM tahu datanya memang tidak ada di dokumen
            # dan menjawab jujur "tidak tercatat", bukan mengarang (anti-halusinasi).
            _NA = "Tidak tercatat dalam dokumen PDF"
            narrative = (
                    f"Karakter: {nama}" + (f" (dijuluki {julukan})" if julukan else "") + f". "
                    f"Peran: {peran or _NA}. "
                    f"Bagian/Kategori Dokumen PDF: {current_section}. "
                    + (f"Afiliasi: {afiliasi}. " if afiliasi else "")
                    + f"Asal usul: {asal_usul or _NA}. "
                    + f"Bounty: {bounty or _NA}. "
                    + (f"Buah Iblis: {buah_iblis}. " if buah_iblis else "Buah Iblis: Tidak Ada. ")
                    + f"Senjata / Kemampuan utama: {kemampuan or _NA}. "
                    + (f"Kisah & Rekam Jejak Sejarah (berdasarkan PDF): {kisah}" if kisah else f"Kisah & Rekam Jejak Sejarah: {_NA}.")
                    + f" [Sumber: Dokumen PDF Halaman {page_idx}]"
                )

            records.append({
                "ID": cid,
                "Nama": nama,
                "Julukan": julukan,
                "Afiliasi": afiliasi,
                "Peran": peran,
                "Bagian": current_section,
                "Asal Usul": asal_usul,
                "Bounty (Beli)": bounty,
                "Buah Iblis": buah_iblis,
                "Tipe Buah Iblis": tipe_buah,
                "Kemampuan": kemampuan,
                "Kisah": kisah,
                "Halaman": page_idx,
                "text_chunk": narrative.strip(),
            })

    return records


def load_characters() -> list[dict]:
    """
    Titik masuk utama pembacaan data karakter untuk RAG.
    Sumber data adalah dokumen PDF 'one-piece-characters.pdf'.
    """
    if PDF_PATH.exists():
        return _extract_from_pdf(PDF_PATH)

    raise CharacterAdapterError(
        f"Sumber data karakter tidak ditemukan. Pastikan file PDF ada di: {PDF_PATH}"
    )
