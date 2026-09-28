import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const TransactionChart = ({ data }) => {
    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 h-80">
            <h3 className="text-lg font-semibold mb-4">Analisis Pengeluaran vs Pemasukan</h3>
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" />
                    <YAxis />
                    <Tooltip
                        formatter={(value) => `Rp ${value.toLocaleString('id-ID')}`}
                    />
                    <Bar dataKey="amount">
                        {data.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.type === 'income' ? '#22c55e' : '#ef4444'} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default TransactionChart;
