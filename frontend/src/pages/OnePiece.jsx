import React from 'react';
import { useNavigate } from 'react-router-dom';

const OnePiece = () => {
    const navigate = useNavigate();

    return (
        <div className="min-h-screen bg-gradient-to-b from-sky-700 via-sky-500 to-amber-200">
            <header className="flex items-center justify-between p-6">
                <h1 className="text-3xl font-bold text-white drop-shadow">One Piece</h1>
                <button
                    onClick={() => navigate('/dashboard')}
                    className="bg-white/90 text-red-700 px-4 py-2 rounded-lg text-sm font-semibold hover:bg-white transition"
                >
                    ← Kembali ke Dashboard
                </button>
            </header>

            {/* Konten bertema One Piece (re-skin visual saja) */}
            <main className="max-w-5xl mx-auto px-6 pb-16">
                {/* Hero / banner */}
                <section className="bg-white/10 backdrop-blur-sm rounded-3xl border border-white/30 p-10 text-center shadow-xl mt-4">
                    <div className="text-6xl mb-4">🏴‍☠️</div>
                    <h2 className="text-4xl font-black text-white drop-shadow mb-3">
                        Selamat Datang di Grand Line
                    </h2>
                    <p className="text-white/90 text-lg max-w-2xl mx-auto">
                        Jelajahi lautan luas bersama kru bajak laut favoritmu. Buka AI Assistant
                        di pojok kanan bawah untuk mulai berpetualang.
                    </p>
                </section>

                {/* Dekorasi kartu bertema */}
                <section className="grid grid-cols-1 sm:grid-cols-3 gap-6 mt-8">
                    <div className="bg-amber-100/90 rounded-2xl p-6 text-center shadow-lg border border-amber-300">
                        <div className="text-5xl mb-3">⚓</div>
                        <h3 className="font-bold text-red-800 text-lg">Set Sail</h3>
                        <p className="text-amber-900/80 text-sm mt-1">Angkat jangkar dan arungi samudra.</p>
                    </div>
                    <div className="bg-amber-100/90 rounded-2xl p-6 text-center shadow-lg border border-amber-300">
                        <div className="text-5xl mb-3">🗺️</div>
                        <h3 className="font-bold text-red-800 text-lg">One Piece</h3>
                        <p className="text-amber-900/80 text-sm mt-1">Harta karun legendaris menanti.</p>
                    </div>
                    <div className="bg-amber-100/90 rounded-2xl p-6 text-center shadow-lg border border-amber-300">
                        <div className="text-5xl mb-3">🐌</div>
                        <h3 className="font-bold text-red-800 text-lg">Den Den Mushi</h3>
                        <p className="text-amber-900/80 text-sm mt-1">Panggil AI Assistant kapan saja.</p>
                    </div>
                </section>
            </main>
        </div>
    );
};

export default OnePiece;
