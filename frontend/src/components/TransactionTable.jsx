import React, { useMemo, useState, useEffect } from 'react';
import { categoriesForFilter } from '../constants/categories';

const PAGE_SIZE_OPTIONS = [5, 10, 25, 50];

const COLUMNS = [
    { key: 'transaction_date', label: 'Tanggal', sortable: true, align: 'left' },
    { key: 'title', label: 'Judul', sortable: true, align: 'left' },
    { key: 'category', label: 'Kategori', sortable: true, align: 'left' },
    { key: 'amount', label: 'Nominal', sortable: true, align: 'right' },
    { key: 'actions', label: 'Aksi', sortable: false, align: 'center' },
];

const SortIcon = ({ direction }) => {
    if (!direction) {
        return (
            <svg className="h-3.5 w-3.5 text-gray-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l4-4 4 4M8 15l4 4 4-4" />
            </svg>
        );
    }
    return (
        <svg className="h-3.5 w-3.5 text-blue-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
            {direction === 'asc' ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 14l4-4 4 4" />
            ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10l4 4 4-4" />
            )}
        </svg>
    );
};

const getComparableValue = (row, key) => {
    switch (key) {
        case 'transaction_date':
            return new Date(row.transaction_date).getTime() || 0;
        case 'amount':
            // Pemasukan positif, pengeluaran negatif agar urutan sesuai arah arus kas
            return row.transaction_type === 'income' ? row.amount : -row.amount;
        default:
            return (row[key] ?? '').toString().toLowerCase();
    }
};

const TransactionTable = ({ transactions, onDelete, onEdit }) => {
    const [search, setSearch] = useState('');
    const [typeFilter, setTypeFilter] = useState('all');
    const [categoryFilter, setCategoryFilter] = useState('all');
    const [sort, setSort] = useState({ key: 'transaction_date', direction: 'desc' });
    const [pageSize, setPageSize] = useState(10);
    const [page, setPage] = useState(1);

    // Opsi kategori mengikuti tipe yang dipilih, bukan kategori yang kebetulan ada
    // di data. Memilih Pemasukan tidak boleh menyisakan opsi seperti 'Belanja'.
    const categories = useMemo(() => categoriesForFilter(typeFilter), [typeFilter]);

    const handleTypeFilterChange = (value) => {
        setTypeFilter(value);
        // Kategori yang sedang aktif bisa jadi tidak tersedia lagi pada tipe baru.
        // Dibiarkan akan membuat select tanpa opsi yang cocok dan tabel kosong.
        if (value !== 'all' && !categoriesForFilter(value).includes(categoryFilter)) {
            setCategoryFilter('all');
        }
        setPage(1);
    };

    const filtered = useMemo(() => {
        const keyword = search.trim().toLowerCase();
        return transactions.filter(t => {
            if (typeFilter !== 'all' && t.transaction_type !== typeFilter) return false;
            if (categoryFilter !== 'all' && t.category !== categoryFilter) return false;
            if (!keyword) return true;
            return [t.title, t.category, t.note]
                .filter(Boolean)
                .some(field => field.toString().toLowerCase().includes(keyword));
        });
    }, [transactions, search, typeFilter, categoryFilter]);

    const sorted = useMemo(() => {
        const rows = [...filtered];
        rows.sort((a, b) => {
            const left = getComparableValue(a, sort.key);
            const right = getComparableValue(b, sort.key);
            if (left < right) return sort.direction === 'asc' ? -1 : 1;
            if (left > right) return sort.direction === 'asc' ? 1 : -1;
            return 0;
        });
        return rows;
    }, [filtered, sort]);

    const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));

    // Jaga agar halaman aktif tetap valid saat filter/page size berubah
    useEffect(() => {
        if (page > totalPages) setPage(totalPages);
    }, [page, totalPages]);

    const startIndex = (page - 1) * pageSize;
    const paginated = sorted.slice(startIndex, startIndex + pageSize);

    const handleSort = (key) => {
        setSort(prev => {
            if (prev.key !== key) {
                // Default: tanggal & nominal mulai dari terbesar, teks dari A-Z
                return { key, direction: key === 'title' || key === 'category' ? 'asc' : 'desc' };
            }
            return { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' };
        });
        setPage(1);
    };

    const resetFilters = () => {
        setSearch('');
        setTypeFilter('all');
        setCategoryFilter('all');
        setPage(1);
    };

    const hasActiveFilter = search.trim() !== '' || typeFilter !== 'all' || categoryFilter !== 'all';
    const alignClass = { left: 'text-left', right: 'text-right', center: 'text-center' };

    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            {/* Toolbar */}
            <div className="p-4 border-b border-gray-100 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="relative flex-1 lg:max-w-xs">
                    <label htmlFor="transaction-search" className="sr-only">Cari transaksi</label>
                    <svg
                        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
                        viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true"
                    >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
                    </svg>
                    <input
                        id="transaction-search"
                        type="search"
                        value={search}
                        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                        placeholder="Cari judul, kategori, catatan..."
                        className="w-full rounded-lg border border-gray-200 py-2 pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                    />
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <label htmlFor="type-filter" className="sr-only">Filter tipe transaksi</label>
                    <select
                        id="type-filter"
                        value={typeFilter}
                        onChange={(e) => handleTypeFilterChange(e.target.value)}
                        className="rounded-lg border border-gray-200 py-2 px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                    >
                        <option value="all">Semua Tipe</option>
                        <option value="income">Pemasukan</option>
                        <option value="expense">Pengeluaran</option>
                    </select>

                    <label htmlFor="category-filter" className="sr-only">Filter kategori</label>
                    <select
                        id="category-filter"
                        value={categoryFilter}
                        onChange={(e) => { setCategoryFilter(e.target.value); setPage(1); }}
                        className="rounded-lg border border-gray-200 py-2 px-3 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                    >
                        <option value="all">Semua Kategori</option>
                        {categories.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>

                    {hasActiveFilter && (
                        <button
                            type="button"
                            onClick={resetFilters}
                            className="rounded-lg border border-gray-200 py-2 px-3 text-sm text-gray-600 hover:bg-gray-50 transition-colors"
                        >
                            Reset
                        </button>
                    )}
                </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
                <table className="w-full text-left">
                    <caption className="sr-only">
                        Daftar transaksi, dapat dicari, difilter, dan diurutkan per kolom
                    </caption>
                    <thead className="bg-gray-50 border-b border-gray-100">
                        <tr>
                            {COLUMNS.map(col => {
                                const isActive = sort.key === col.key;
                                return (
                                    <th
                                        key={col.key}
                                        scope="col"
                                        className={`p-4 font-semibold text-sm text-gray-600 ${alignClass[col.align]}`}
                                        aria-sort={col.sortable ? (isActive ? (sort.direction === 'asc' ? 'ascending' : 'descending') : 'none') : undefined}
                                    >
                                        {col.sortable ? (
                                            <button
                                                type="button"
                                                onClick={() => handleSort(col.key)}
                                                className={`inline-flex items-center gap-1.5 rounded hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${col.align === 'right' ? 'flex-row-reverse' : ''}`}
                                                title={`Urutkan berdasarkan ${col.label}`}
                                            >
                                                <span>{col.label}</span>
                                                <SortIcon direction={isActive ? sort.direction : null} />
                                            </button>
                                        ) : (
                                            col.label
                                        )}
                                    </th>
                                );
                            })}
                        </tr>
                    </thead>
                    <tbody>
                        {paginated.map((t) => (
                            <tr key={t.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                                <td className="p-4 text-sm whitespace-nowrap">{new Date(t.transaction_date).toLocaleDateString('id-ID')}</td>
                                <td className="p-4 text-sm font-medium">{t.title}</td>
                                <td className="p-4 text-sm text-gray-500">{t.category}</td>
                                <td className={`p-4 text-sm text-right font-bold whitespace-nowrap ${t.transaction_type === 'income' ? 'text-green-600' : 'text-red-600'}`}>
                                    {t.transaction_type === 'income' ? '+' : '-'} Rp {t.amount.toLocaleString('id-ID')}
                                </td>
                                <td className="p-4 text-center">
                                    <div className="flex justify-center gap-2">
                                        <button
                                            onClick={() => onEdit(t)}
                                            className="p-2 text-blue-500 hover:bg-blue-50 rounded-full transition-colors"
                                            title="Edit Transaksi"
                                            aria-label={`Edit transaksi ${t.title}`}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                            </svg>
                                        </button>
                                        <button
                                            onClick={() => onDelete(t.id)}
                                            className="p-2 text-red-500 hover:bg-red-50 rounded-full transition-colors"
                                            title="Hapus Transaksi"
                                            aria-label={`Hapus transaksi ${t.title}`}
                                        >
                                            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                            </svg>
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        ))}
                        {paginated.length === 0 && (
                            <tr>
                                <td colSpan={COLUMNS.length} className="p-8 text-center text-gray-400">
                                    {transactions.length === 0
                                        ? 'Belum ada transaksi.'
                                        : 'Tidak ada transaksi yang cocok dengan filter.'}
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {/* Pagination */}
            <div className="p-4 border-t border-gray-100 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                    <span aria-live="polite">
                        {sorted.length === 0
                            ? '0 transaksi'
                            : `${startIndex + 1}-${Math.min(startIndex + pageSize, sorted.length)} dari ${sorted.length} transaksi`}
                    </span>
                    <label htmlFor="page-size" className="sr-only">Jumlah baris per halaman</label>
                    <select
                        id="page-size"
                        value={pageSize}
                        onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
                        className="rounded-lg border border-gray-200 py-1 px-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
                    >
                        {PAGE_SIZE_OPTIONS.map(size => (
                            <option key={size} value={size}>{size} / halaman</option>
                        ))}
                    </select>
                </div>

                <div className="flex items-center gap-1">
                    <button
                        type="button"
                        onClick={() => setPage(p => Math.max(1, p - 1))}
                        disabled={page === 1}
                        className="rounded-lg border border-gray-200 py-1.5 px-3 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                        aria-label="Halaman sebelumnya"
                    >
                        Sebelumnya
                    </button>
                    <span className="px-3 text-sm text-gray-600">
                        Hal. {page} / {totalPages}
                    </span>
                    <button
                        type="button"
                        onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                        className="rounded-lg border border-gray-200 py-1.5 px-3 text-sm text-gray-600 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                        aria-label="Halaman berikutnya"
                    >
                        Berikutnya
                    </button>
                </div>
            </div>
        </div>
    );
};

export default TransactionTable;
