import React, { useState } from 'react';

const TransactionTable = ({ transactions, onDelete, onEdit }) => {
    return (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full text-left">
                <thead className="bg-gray-50 border-b border-gray-100">
                    <tr>
                        <th className="p-4 font-semibold text-sm text-gray-600">Tanggal</th>
                        <th className="p-4 font-semibold text-sm text-gray-600">Judul</th>
                        <th className="p-4 font-semibold text-sm text-gray-600">Kategori</th>
                        <th className="p-4 font-semibold text-sm text-gray-600 text-right">Nominal</th>
                        <th className="p-4 font-semibold text-sm text-gray-600 text-center">Aksi</th>
                    </tr>
                </thead>
                <tbody>
                    {transactions.map((t) => (
                        <tr key={t.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                            <td className="p-4 text-sm">{new Date(t.transaction_date).toLocaleDateString('id-ID')}</td>
                            <td className="p-4 text-sm font-medium">{t.title}</td>
                            <td className="p-4 text-sm text-gray-500">{t.category}</td>
                            <td className={`p-4 text-sm text-right font-bold ${t.transaction_type === 'income' ? 'text-green-600' : 'text-red-600'}`}>
                                {t.transaction_type === 'income' ? '+' : '-'} Rp {t.amount.toLocaleString('id-ID')}
                            </td>
                            <td className="p-4 text-center">
                                <div className="flex justify-center gap-2">
                                    <button
                                        onClick={() => onEdit(t)}
                                        className="p-2 text-blue-500 hover:bg-blue-50 rounded-full transition-colors"
                                        title="Edit Transaksi"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                        </svg>
                                    </button>
                                    <button
                                        onClick={() => onDelete(t.id)}
                                        className="p-2 text-red-500 hover:bg-red-50 rounded-full transition-colors"
                                        title="Hapus Transaksi"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    ))}
                    {transactions.length === 0 && (
                        <tr>
                            <td colSpan="5" className="p-8 text-center text-gray-400">Belum ada transaksi.</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};

export default TransactionTable;
