import React, { useEffect, useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import api from '../services/api';
import StatCard from '../components/StatCard';
import TransactionChart from '../components/TransactionChart';
import TransactionTable from '../components/TransactionTable';
import { categoriesFor, isCategoryAllowed, defaultCategoryFor } from '../constants/categories';

const Dashboard = () => {
    const navigate = useNavigate();
    const { logout } = useContext(AuthContext);
    const [transactions, setTransactions] = useState([]);
    const [stats, setStats] = useState({ balance: 0, income: 0, expense: 0 });
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [isEditModalOpen, setIsEditModalOpen] = useState(false);
    const [formData, setFormData] = useState({
        title: '',
        amount: '',
        category: 'Lainnya',
        transaction_type: 'expense',
        transaction_date: new Date().toISOString().split('T')[0],
        note: ''
    });
    const [editData, setEditData] = useState(null);

    const fetchTransactions = async () => {
        try {
            const response = await api.get('/transactions/');
            const data = response.data;
            setTransactions(data);

            // Hitung statistik
            const income = data
                .filter(t => t.transaction_type === 'income')
                .reduce((sum, t) => sum + t.amount, 0);
            const expense = data
                .filter(t => t.transaction_type === 'expense')
                .reduce((sum, t) => sum + t.amount, 0);

            setStats({
                income,
                expense,
                balance: income - expense
            });
        } catch (error) {
            console.error('Error fetching data:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchTransactions();
    }, []);

    const handleDelete = async (id) => {
        if (window.confirm('Hapus transaksi ini?')) {
            try {
                await api.delete(`/transactions/${id}`);
                fetchTransactions(); // Refresh data
            } catch (error) {
                alert('Gagal menghapus transaksi');
            }
        }
    };

    const handleEditClick = (transaction) => {
        // Data lama atau hasil chatbot bisa memuat kombinasi tipe dan kategori yang
        // tidak sah, misalnya income berkategori 'Belanja'. Kategori dikosongkan agar
        // user memilih ulang secara sadar, bukan diganti diam-diam oleh aplikasi.
        const categoryIsValid = isCategoryAllowed(transaction.transaction_type, transaction.category);
        setEditData({
            ...transaction,
            category: categoryIsValid ? transaction.category : '',
            transaction_date: transaction.transaction_date ? transaction.transaction_date.split('T')[0] : new Date().toISOString().split('T')[0]
        });
        setIsEditModalOpen(true);
    };

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => {
            const next = { ...prev, [name]: value };
            // Ganti tipe transaksi bisa membuat kategori yang sedang terpilih
            // tidak lagi sah, misalnya 'Pendapatan' pada pengeluaran.
            if (name === 'transaction_type' && !isCategoryAllowed(value, prev.category)) {
                next.category = defaultCategoryFor(value);
            }
            return next;
        });
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await api.post('/transactions/', {
                ...formData,
                amount: parseFloat(formData.amount)
            });
            setIsModalOpen(false);
            setFormData({
                title: '',
                amount: '',
                category: 'Lainnya',
                transaction_type: 'expense',
                transaction_date: new Date().toISOString().split('T')[0],
                note: ''
            });
            fetchTransactions(); // Refresh data
        } catch (error) {
            alert('Gagal menambah transaksi. Pastikan data benar.');
            console.error(error);
        }
    };

    const handleUpdateSubmit = async (e) => {
        e.preventDefault();
        try {
            await api.put(`/transactions/${editData.id}`, {
                ...editData,
                amount: parseFloat(editData.amount)
            });
            setIsEditModalOpen(false);
            setEditData(null);
            fetchTransactions(); // Refresh data
        } catch (error) {
            alert('Gagal memperbarui transaksi.');
            console.error(error);
        }
    };

    const handleEditInputChange = (e) => {
        const { name, value } = e.target;
        setEditData(prev => {
            const next = { ...prev, [name]: value };
            if (name === 'transaction_type' && !isCategoryAllowed(value, prev.category)) {
                next.category = defaultCategoryFor(value);
            }
            return next;
        });
    };

    if (loading) return <div className="flex h-screen items-center justify-center">Loading...</div>;

    return (
        <div className="min-h-screen bg-gray-50 p-6">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-3xl font-bold text-gray-800">Financial Dashboard</h1>
                    <div className="flex gap-3 items-center">
                        <button
                            onClick={() => navigate('/gatling')}
                            className="bg-gradient-to-r from-orange-500 to-amber-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:from-orange-600 hover:to-amber-700 transition-all shadow-sm flex items-center gap-2"
                        >
                            <span>⚡</span> Gatling Studio
                        </button>
                        <button
                            onClick={() => navigate('/gatling/copilot')}
                            className="bg-slate-900 hover:bg-slate-800 text-orange-400 border border-slate-700 px-3.5 py-2 rounded-lg text-sm font-semibold transition-all shadow-sm flex items-center gap-1.5"
                            title="Buka FinTracks Gatling AI Copilot"
                        >
                            <span>🤖</span> AI Copilot
                        </button>
                        <button
                            onClick={() => setIsModalOpen(true)}
                            className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                        >
                            + Tambah Transaksi
                        </button>
                        <button
                            onClick={logout}
                            className="bg-white border border-gray-300 px-4 py-2 rounded-lg text-sm font-medium hover:bg-gray-50"
                        >
                            Logout
                        </button>
                    </div>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                    <StatCard title="Total Saldo" amount={stats.balance} type="balance" />
                    <StatCard title="Total Pemasukan" amount={stats.income} type="income" />
                    <StatCard title="Total Pengeluaran" amount={stats.expense} type="expense" />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Chart Section */}
                    <div className="lg:col-span-1">
                        <TransactionChart data={transactions.slice(0, 10).map(t => ({
                            name: t.title,
                            amount: t.amount,
                            type: t.transaction_type
                        }))} />
                    </div>

                    {/* Table Section */}
                    <div className="lg:col-span-2">
                        <TransactionTable transactions={transactions} onDelete={handleDelete} onEdit={handleEditClick} />
                    </div>
                </div>

                {/* Add Transaction Modal */}
                {isModalOpen && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                        <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xl font-bold text-gray-800">Tambah Transaksi</h2>
                                <button onClick={() => setIsModalOpen(false)} className="text-gray-400 hover:text-gray-600">✕</button>
                            </div>
                            <form onSubmit={handleSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Judul</label>
                                    <input
                                        type="text"
                                        name="title"
                                        value={formData.title}
                                        onChange={handleInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        placeholder="Contoh: Makan Siang"
                                        required
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Nominal</label>
                                        <input
                                            type="number"
                                            name="amount"
                                            value={formData.amount}
                                            onChange={handleInputChange}
                                            className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder="0"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Tipe</label>
                                        <select
                                            name="transaction_type"
                                            value={formData.transaction_type}
                                            onChange={handleInputChange}
                                            className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        >
                                            <option value="expense">Pengeluaran</option>
                                            <option value="income">Pemasukan</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Kategori</label>
                                    <select
                                        name="category"
                                        value={formData.category}
                                        onChange={handleInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        required
                                    >
                                        {!isCategoryAllowed(formData.transaction_type, formData.category) && (
                                            <option value="">— Pilih kategori —</option>
                                        )}
                                        {categoriesFor(formData.transaction_type).map(c => (
                                            <option key={c} value={c}>{c}</option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Tanggal</label>
                                    <input
                                        type="date"
                                        name="transaction_date"
                                        value={formData.transaction_date}
                                        onChange={handleInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Catatan (Opsional)</label>
                                    <textarea
                                        name="note"
                                        value={formData.note}
                                        onChange={handleInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        rows="2"
                                    ></textarea>
                                </div>
                                <div className="flex gap-3 pt-2">
                                    <button
                                        type="button"
                                        onClick={() => setIsModalOpen(false)}
                                        className="flex-1 py-2 px-4 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50"
                                    >
                                        Batal
                                    </button>
                                    <button
                                        type="submit"
                                        className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                                    >
                                        Simpan Transaksi
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}

                {/* Edit Transaction Modal */}
                {isEditModalOpen && editData && (
                    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
                        <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl">
                            <div className="flex justify-between items-center mb-4">
                                <h2 className="text-xl font-bold text-gray-800">Edit Transaksi</h2>
                                <button onClick={() => setIsEditModalOpen(false)} className="text-gray-400 hover:text-gray-600">✕</button>
                            </div>
                            <form onSubmit={handleUpdateSubmit} className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Judul</label>
                                    <input
                                        type="text"
                                        name="title"
                                        value={editData.title}
                                        onChange={handleEditInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        required
                                    />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Nominal</label>
                                        <input
                                            type="number"
                                            name="amount"
                                            value={editData.amount}
                                            onChange={handleEditInputChange}
                                            className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-sm font-medium text-gray-700 mb-1">Tipe</label>
                                        <select
                                            name="transaction_type"
                                            value={editData.transaction_type}
                                            onChange={handleEditInputChange}
                                            className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        >
                                            <option value="expense">Pengeluaran</option>
                                            <option value="income">Pemasukan</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Kategori</label>
                                    <select
                                        name="category"
                                        value={editData.category}
                                        onChange={handleEditInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        required
                                    >
                                        {!isCategoryAllowed(editData.transaction_type, editData.category) && (
                                            <option value="">— Pilih kategori —</option>
                                        )}
                                        {categoriesFor(editData.transaction_type).map(c => (
                                            <option key={c} value={c}>{c}</option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Tanggal</label>
                                    <input
                                        type="date"
                                        name="transaction_date"
                                        value={editData.transaction_date}
                                        onChange={handleEditInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        required
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-gray-700 mb-1">Catatan (Opsional)</label>
                                    <textarea
                                        name="note"
                                        value={editData.note}
                                        onChange={handleEditInputChange}
                                        className="w-full p-2 border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
                                        rows="2"
                                    ></textarea>
                                </div>
                                <div className="flex gap-3 pt-2">
                                    <button
                                        type="button"
                                        onClick={() => setIsEditModalOpen(false)}
                                        className="flex-1 py-2 px-4 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50"
                                    >
                                        Batal
                                    </button>
                                    <button
                                        type="submit"
                                        className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                                    >
                                        Simpan Perubahan
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default Dashboard;
