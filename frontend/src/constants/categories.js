// Sumber tunggal daftar kategori transaksi untuk seluruh frontend.
// Urutannya mengikuti valid_cats di backend/app/routes/chat.py. Kalau keduanya
// berbeda, transaksi hasil chatbot bisa punya kategori yang tidak ada opsinya di
// form, dan kategori itu akan hilang saat transaksi diedit.
export const CATEGORIES = [
    'Makanan & Minuman',
    'Transportasi',
    'Belanja',
    'Pendapatan',
    'Kesehatan',
    'Hiburan',
    'Tagihan',
    'Lainnya',
];

// Pemasukan hanya wajar berkategori Pendapatan atau Lainnya.
export const INCOME_CATEGORIES = ['Pendapatan', 'Lainnya'];

// Pengeluaran boleh kategori apa pun selain Pendapatan. Ditulis sebagai turunan
// agar kategori baru di CATEGORIES otomatis ikut tanpa perlu diedit dua kali.
export const EXPENSE_CATEGORIES = CATEGORIES.filter(c => c !== 'Pendapatan');

/** Kategori yang sah untuk satu tipe transaksi ('income' | 'expense'). */
export const categoriesFor = (transactionType) =>
    transactionType === 'income' ? INCOME_CATEGORIES : EXPENSE_CATEGORIES;

export const isCategoryAllowed = (transactionType, category) =>
    categoriesFor(transactionType).includes(category);

/**
 * Kategori lama bisa jadi tidak sah setelah tipe transaksi diganti.
 * 'Lainnya' ada di kedua daftar, jadi pilihan user dipertahankan bila memungkinkan.
 */
export const defaultCategoryFor = (transactionType) =>
    transactionType === 'income' ? 'Pendapatan' : 'Lainnya';

/**
 * Versi untuk dropdown filter tabel, yang punya opsi tambahan 'all'
 * ("Semua Tipe") di luar 'income' dan 'expense'.
 */
export const categoriesForFilter = (typeFilter) =>
    typeFilter === 'all' ? CATEGORIES : categoriesFor(typeFilter);
