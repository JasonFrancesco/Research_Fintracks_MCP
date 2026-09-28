import React from 'react';

const StatCard = ({ title, amount, type }) => {
    const colorClass = type === 'income' ? 'text-green-600' : type === 'expense' ? 'text-red-600' : 'text-blue-600';

    return (
        <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
            <p className="text-sm text-gray-500 font-medium">{title}</p>
            <p className={`text-2xl font-bold ${colorClass}`}>
                Rp {amount.toLocaleString('id-ID')}
            </p>
        </div>
    );
};

export default StatCard;
