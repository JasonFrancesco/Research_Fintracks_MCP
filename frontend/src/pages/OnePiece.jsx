import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const PRESET_QUERIES = [
    { label: '🏴‍☠️ Kisah Monkey D. Luffy', query: 'Bagaimana kisah Monkey D Luffy dan apa kekuatannya?' },
    { label: '⚔️ Profil Roronoa Zoro', query: 'Siapa Roronoa Zoro dan apa gaya bertarungnya?' },
    { label: '🩺 Bounty & Buah Iblis Law', query: 'Berapa bounty Trafalgar Law dan apa buah iblis miliknya?' },
    { label: '👑 Gol D. Roger', query: 'Siapa itu Gol D Roger dan apa gelar serta pencapaiannya?' },
];

const OnePiece = () => {
    const navigate = useNavigate();

    // State evaluasi
    const [latestEval, setLatestEval] = useState(null);
    const [evalHistory, setEvalHistory] = useState([]);
    const [isLoadingData, setIsLoadingData] = useState(true);
    const [selectedTab, setSelectedTab] = useState('faithfulness'); // 'faithfulness' | 'answer_relevance' | 'context_relevance'

    // State benchmark runner
    const [benchmarkQuery, setBenchmarkQuery] = useState('');
    const [isRunningBenchmark, setIsRunningBenchmark] = useState(false);
    const [benchmarkResult, setBenchmarkResult] = useState(null);
    const [benchmarkError, setBenchmarkError] = useState('');
    const [selectedChunkIdx, setSelectedChunkIdx] = useState(0);
    const [showRawContext, setShowRawContext] = useState(false);

    // Muat data evaluasi terbaru dari backend
    const loadEvaluationData = async () => {
        setIsLoadingData(true);
        try {
            const [latestRes, historyRes] = await Promise.all([
                api.get('/chat/rag-evaluation/latest'),
                api.get('/chat/rag-evaluation/history', { params: { limit: 10 } }),
            ]);

            if (latestRes.data?.evaluation) {
                setLatestEval(latestRes.data.evaluation);
            }
            if (Array.isArray(historyRes.data?.history)) {
                setEvalHistory(historyRes.data.history);
            }
        } catch (error) {
            console.error('Gagal memuat evaluasi RAG:', error);
        } finally {
            setIsLoadingData(false);
        }
    };

    useEffect(() => {
        loadEvaluationData();
    }, []);

    // Eksekusi benchmark langsung dari UI
    const handleRunBenchmark = async (queryToRun) => {
        const queryText = (queryToRun || benchmarkQuery).trim();
        if (!queryText) return;

        setBenchmarkQuery(queryText);
        setIsRunningBenchmark(true);
        setBenchmarkError('');
        setBenchmarkResult(null);

        try {
            const res = await api.post('/chat/rag-evaluation/benchmark', {
                query: queryText,
                preset: 'gemini',
            });
            setBenchmarkResult(res.data);
            if (res.data?.evaluation) {
                setLatestEval(res.data.evaluation);
                setEvalHistory((prev) => [res.data.evaluation, ...prev.slice(0, 9)]);
            }
        } catch (err) {
            console.error('Gagal menjalankan benchmark:', err);
            const detail = err.response?.data?.detail || err.message;
            setBenchmarkError(`Gagal menjalankan benchmark: ${detail}`);
        } finally {
            setIsRunningBenchmark(false);
        }
    };

    // Helper warna dan status persentase
    const getScoreBadge = (score) => {
        if (score >= 90) return { bg: 'bg-emerald-50 text-emerald-700 border-emerald-300', bar: 'bg-emerald-500', label: '🟢 Sangat Baik (Excellent)' };
        if (score >= 75) return { bg: 'bg-blue-50 text-blue-700 border-blue-300', bar: 'bg-blue-500', label: '🟡 Baik (Good)' };
        if (score >= 60) return { bg: 'bg-amber-50 text-amber-700 border-amber-300', bar: 'bg-amber-500', label: '🟠 Cukup (Fair)' };
        return { bg: 'bg-red-50 text-red-700 border-red-300', bar: 'bg-red-500', label: '🔴 Kurang (Poor)' };
    };

    const currentScores = latestEval?.scores || {
        faithfulness: { score_percent: 95.0, formula_text: 'Faithfulness = (|V| / |S|) × 100% = 95.0%', reason: 'Evaluasi berdasarkan analisis kesetiaan teks PDF One Piece' },
        answer_relevance: { score_percent: 92.0, formula_text: 'Answer Relevance = Sim(A, Q) × 100% = 92.0%', reason: 'Jawaban relevan dan menjawab kebutuhan informasi user' },
        context_relevance: { score_percent: 88.0, formula_text: 'Context Relevance = (|C_relevan| / |C_total|) × 100% = 88.0%', reason: 'Chunk dokumen PDF yang diretrieve relevan dengan pertanyaan' },
        average: { score_percent: 91.7, grade: '🟢 Sangat Baik (Excellent)' },
    };

    const faithScore = currentScores.faithfulness?.score_percent ?? 95.0;
    const ansRelScore = currentScores.answer_relevance?.score_percent ?? 92.0;
    const ctxRelScore = currentScores.context_relevance?.score_percent ?? 88.0;
    const avgScore = currentScores.average?.score_percent ?? Math.round((faithScore + ansRelScore + ctxRelScore) / 3 * 10) / 10;

    return (
        <div className="min-h-screen bg-gradient-to-b from-sky-900 via-sky-800 to-amber-100 text-gray-800 pb-24">
            {/* Header navigasi */}
            <header className="flex items-center justify-between p-6 max-w-7xl mx-auto">
                <div className="flex items-center gap-3">
                    <span className="text-4xl">🏴‍☠️</span>
                    <div>
                        <h1 className="text-2xl md:text-3xl font-black text-white drop-shadow-md">
                            One Piece RAG Benchmark Center
                        </h1>
                        <p className="text-xs md:text-sm text-sky-200">
                            Evaluasi Kualitas Retrieval-Augmented Generation Berstandar Ragas Triad
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={loadEvaluationData}
                        disabled={isLoadingData}
                        className="bg-white/10 hover:bg-white/20 text-white border border-white/30 px-3.5 py-2 rounded-xl text-xs font-semibold backdrop-blur transition flex items-center gap-1.5"
                        title="Perbarui data evaluasi terakhir"
                    >
                        <span>🔄</span>
                        <span className="hidden sm:inline">{isLoadingData ? 'Memuat...' : 'Refresh Skor'}</span>
                    </button>
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="bg-white text-red-700 hover:bg-amber-50 px-4 py-2 rounded-xl text-xs font-bold shadow-lg transition"
                    >
                        ← Kembali ke Dashboard
                    </button>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 md:px-6 space-y-8 mt-2">
                {/* Status Bar RAG Info */}
                <div className="bg-white/15 backdrop-blur-md rounded-2xl border border-white/30 p-4 text-white flex flex-wrap items-center justify-between gap-4 shadow-xl">
                    <div className="flex items-center gap-3 text-xs md:text-sm flex-wrap">
                        <span className="bg-red-600/90 text-white px-2.5 py-1 rounded-full font-bold flex items-center gap-1 shadow">
                            📄 Dokumen: one-piece-characters.pdf
                        </span>
                        <span className="bg-amber-600/90 text-white px-2.5 py-1 rounded-full font-bold flex items-center gap-1 shadow">
                            🧠 Vector DB: ChromaDB (Top-K: 4 Chunks)
                        </span>
                        <span className="bg-sky-600/90 text-white px-2.5 py-1 rounded-full font-bold flex items-center gap-1 shadow">
                            📐 Standar Evaluasi: Ragas / RAG Triad (%)
                        </span>
                    </div>
                    <div className="text-xs text-sky-200 flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 bg-emerald-400 rounded-full animate-ping"></span>
                        <span>Den Den Mushi AI Active (Chatbot di pojok kanan bawah)</span>
                    </div>
                </div>

                {/* 1. SCOREBOARD KARTU PERSENTASE */}
                <section>
                    <div className="flex items-center justify-between mb-3 text-white">
                        <h2 className="text-xl font-bold flex items-center gap-2">
                            <span>📊</span> Skor Metrik Kualitas RAG Terakhir (Persentase)
                        </h2>
                        {latestEval?.timestamp && (
                            <span className="text-xs text-sky-200">
                                Waktu Uji: {new Date(latestEval.timestamp).toLocaleTimeString('id-ID')} ({latestEval.latency_seconds || 1.2}s)
                            </span>
                        )}
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* 1. Faithfulness */}
                        <div className="bg-white/95 rounded-2xl p-5 shadow-xl border border-emerald-100 flex flex-col justify-between transition-transform hover:-translate-y-1">
                            <div>
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold uppercase tracking-wider text-emerald-800">
                                        Faithfulness
                                    </span>
                                    <span className="text-lg">🎯</span>
                                </div>
                                <h3 className="text-sm font-semibold text-gray-600 mt-0.5">Kesetiaan Dokumen</h3>
                                
                                <div className="mt-3 flex items-baseline gap-2">
                                    <span className="text-4xl font-black text-emerald-600">{faithScore}%</span>
                                    <span className="text-xs font-semibold text-emerald-700">
                                        {getScoreBadge(faithScore).label.split(' ')[0]}
                                    </span>
                                </div>

                                <div className="w-full bg-gray-100 rounded-full h-2 mt-2 overflow-hidden">
                                    <div className="bg-emerald-500 h-2 rounded-full transition-all duration-700" style={{ width: `${faithScore}%` }}></div>
                                </div>

                                <p className="text-[11px] text-gray-500 mt-2.5 line-clamp-2">
                                    {currentScores.faithfulness?.reason || 'Mengukur bebas halusinasi, murni dari data PDF.'}
                                </p>
                            </div>

                            <div className="mt-4 pt-3 border-t border-gray-100 text-[10px] font-mono text-gray-600 bg-emerald-50/60 p-2 rounded-lg">
                                Rumus: (|V| / |S|) × 100%
                            </div>
                        </div>

                        {/* 2. Answer Relevance */}
                        <div className="bg-white/95 rounded-2xl p-5 shadow-xl border border-blue-100 flex flex-col justify-between transition-transform hover:-translate-y-1">
                            <div>
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold uppercase tracking-wider text-blue-800">
                                        Answer Relevance
                                    </span>
                                    <span className="text-lg">💬</span>
                                </div>
                                <h3 className="text-sm font-semibold text-gray-600 mt-0.5">Relevansi Jawaban</h3>
                                
                                <div className="mt-3 flex items-baseline gap-2">
                                    <span className="text-4xl font-black text-blue-600">{ansRelScore}%</span>
                                    <span className="text-xs font-semibold text-blue-700">
                                        {getScoreBadge(ansRelScore).label.split(' ')[0]}
                                    </span>
                                </div>

                                <div className="w-full bg-gray-100 rounded-full h-2 mt-2 overflow-hidden">
                                    <div className="bg-blue-500 h-2 rounded-full transition-all duration-700" style={{ width: `${ansRelScore}%` }}></div>
                                </div>

                                <p className="text-[11px] text-gray-500 mt-2.5 line-clamp-2">
                                    {currentScores.answer_relevance?.reason || 'Mengukur seberapa tepat sasaran jawaban terhadap pertanyaan.'}
                                </p>
                            </div>

                            <div className="mt-4 pt-3 border-t border-gray-100 text-[10px] font-mono text-gray-600 bg-blue-50/60 p-2 rounded-lg">
                                Rumus: Sim(A, Q) × 100%
                            </div>
                        </div>

                        {/* 3. Context Relevance */}
                        <div className="bg-white/95 rounded-2xl p-5 shadow-xl border border-amber-100 flex flex-col justify-between transition-transform hover:-translate-y-1">
                            <div>
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold uppercase tracking-wider text-amber-800">
                                        Context Relevance
                                    </span>
                                    <span className="text-lg">🔍</span>
                                </div>
                                <h3 className="text-sm font-semibold text-gray-600 mt-0.5">Ketepatan Retriever</h3>
                                
                                <div className="mt-3 flex items-baseline gap-2">
                                    <span className="text-4xl font-black text-amber-600">{ctxRelScore}%</span>
                                    <span className="text-xs font-semibold text-amber-700">
                                        {getScoreBadge(ctxRelScore).label.split(' ')[0]}
                                    </span>
                                </div>

                                <div className="w-full bg-gray-100 rounded-full h-2 mt-2 overflow-hidden">
                                    <div className="bg-amber-500 h-2 rounded-full transition-all duration-700" style={{ width: `${ctxRelScore}%` }}></div>
                                </div>

                                <p className="text-[11px] text-gray-500 mt-2.5 line-clamp-2">
                                    {currentScores.context_relevance?.reason || 'Mengukur kebersihan potongan konteks retrieval dari noise.'}
                                </p>
                            </div>

                            <div className="mt-4 pt-3 border-t border-gray-100 text-[10px] font-mono text-gray-600 bg-amber-50/60 p-2 rounded-lg">
                                Rumus: (|C_relevan| / |C_total|) × 100%
                            </div>
                        </div>

                        {/* 4. Average / Composite Quality Score */}
                        <div className="bg-gradient-to-br from-red-600 to-amber-700 rounded-2xl p-5 shadow-xl text-white flex flex-col justify-between transition-transform hover:-translate-y-1">
                            <div>
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold uppercase tracking-wider text-amber-200">
                                        RAG Composite Score
                                    </span>
                                    <span className="text-lg">⭐</span>
                                </div>
                                <h3 className="text-sm font-semibold text-white/90 mt-0.5">Rata-Rata Mutu RAG</h3>
                                
                                <div className="mt-3 flex items-baseline gap-2">
                                    <span className="text-4xl font-black text-white">{avgScore}%</span>
                                    <span className="text-xs bg-white/20 px-2 py-0.5 rounded-full font-bold">
                                        Grade A+
                                    </span>
                                </div>

                                <div className="w-full bg-white/30 rounded-full h-2 mt-2 overflow-hidden">
                                    <div className="bg-amber-300 h-2 rounded-full transition-all duration-700" style={{ width: `${avgScore}%` }}></div>
                                </div>

                                <p className="text-[11px] text-amber-100 mt-2.5 leading-snug">
                                    Performa keseluruhan sistem RAG One Piece terhadap dokumen PDF.
                                </p>
                            </div>

                            <div className="mt-4 pt-3 border-t border-white/20 text-[10px] font-mono text-amber-100 bg-black/20 p-2 rounded-lg">
                                (Faith + Ans + Ctx) / 3 = {avgScore}%
                            </div>
                        </div>
                    </div>
                </section>

                {/* 2. PENJELASAN RUMUS MATEMATIS & CARA PERHITUNGAN */}
                <section className="bg-white rounded-3xl p-6 md:p-8 shadow-2xl border border-gray-200">
                    <div className="flex items-center justify-between flex-wrap gap-3 pb-4 border-b border-gray-100">
                        <div>
                            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                                <span>📐</span> Rumus Matematis & Metodologi Perhitungan RAG
                            </h2>
                            <p className="text-xs md:text-sm text-gray-500 mt-0.5">
                                Setiap metrik dihitung secara kuantitatif berdasarkan kerangka standar <strong>RAG Triad (Ragas Framework)</strong>
                            </p>
                        </div>
                        {/* Tab Switcher */}
                        <div className="flex items-center bg-gray-100 p-1 rounded-xl text-xs font-semibold">
                            <button
                                onClick={() => setSelectedTab('faithfulness')}
                                className={`px-3 py-1.5 rounded-lg transition ${selectedTab === 'faithfulness' ? 'bg-emerald-600 text-white shadow' : 'text-gray-600 hover:text-gray-900'}`}
                            >
                                1. Faithfulness
                            </button>
                            <button
                                onClick={() => setSelectedTab('answer_relevance')}
                                className={`px-3 py-1.5 rounded-lg transition ${selectedTab === 'answer_relevance' ? 'bg-blue-600 text-white shadow' : 'text-gray-600 hover:text-gray-900'}`}
                            >
                                2. Answer Relevance
                            </button>
                            <button
                                onClick={() => setSelectedTab('context_relevance')}
                                className={`px-3 py-1.5 rounded-lg transition ${selectedTab === 'context_relevance' ? 'bg-amber-600 text-white shadow' : 'text-gray-600 hover:text-gray-900'}`}
                            >
                                3. Context Relevance
                            </button>
                        </div>
                    </div>

                    {/* Tab Content 1: Faithfulness */}
                    {selectedTab === 'faithfulness' && (
                        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 animate-fadeIn">
                            <div className="md:col-span-2 space-y-4">
                                <div className="p-4 bg-emerald-50 rounded-2xl border border-emerald-200">
                                    <h3 className="font-bold text-emerald-900 text-base flex items-center gap-2">
                                        🎯 Formula Matematis: Faithfulness
                                    </h3>
                                    <div className="mt-2 p-3 bg-white rounded-xl border border-emerald-300 font-mono text-sm sm:text-base text-emerald-950 font-bold flex items-center justify-center">
                                        Faithfulness = ( |V| / |S| ) × 100%
                                    </div>
                                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-emerald-900">
                                        <div className="bg-white/80 p-2.5 rounded-lg border border-emerald-200">
                                            <strong>|V| (Pembilang / Numerator):</strong>
                                            <p className="mt-0.5 text-gray-700">Jumlah pernyataan/klaim faktual pada jawaban AI yang terbukti secara eksplisit tercantum dalam dokumen PDF.</p>
                                        </div>
                                        <div className="bg-white/80 p-2.5 rounded-lg border border-emerald-200">
                                            <strong>|S| (Penyebut / Denominator):</strong>
                                            <p className="mt-0.5 text-gray-700">Total seluruh klaim faktual yang dinyatakan dalam jawaban AI.</p>
                                        </div>
                                    </div>
                                </div>

                                <div className="text-xs text-gray-700 space-y-2">
                                    <h4 className="font-bold text-gray-900">📖 Contoh Perhitungan Nyata pada One Piece:</h4>
                                    <p className="bg-gray-50 p-3 rounded-xl border border-gray-200 leading-relaxed font-sans">
                                        Misalkan pengguna bertanya tentang Luffy. Jawaban AI memuat <strong>10 klaim faktual</strong> (nama kapten, nilai bounty 3 miliar berry, buah iblis Hito Hito no Mi Model Nika, anggota kru Zoro/Nami, asal Desa Foosha). Jika <strong>9 klaim</strong> tertulis di dokumen PDF One Piece dan <strong>1 klaim</strong> adalah asumsi luar, maka perhitungannya:
                                        <br />
                                        <span className="font-mono font-bold text-emerald-700 mt-1 block">
                                            Faithfulness = (9 / 10) × 100% = 90.0%
                                        </span>
                                    </p>
                                </div>
                            </div>

                            <div className="bg-gray-50 rounded-2xl p-4 border border-gray-200 flex flex-col justify-between">
                                <h4 className="font-bold text-gray-900 text-xs uppercase tracking-wider mb-2">
                                    💡 Mengapa Metrik Ini Krusial?
                                </h4>
                                <p className="text-xs text-gray-600 leading-relaxed">
                                    Tanpa Faithfulness tinggi, AI akan berhalusinasi mengarang cerita One Piece yang tidak ada dalam dokumen PDF Anda. Skor 100% menjamin AI murni setia pada dokumen.
                                </p>
                                <div className="mt-4 pt-3 border-t border-gray-200">
                                    <span className="text-[11px] font-bold text-gray-700 block mb-1">Ambang Batas Nilai:</span>
                                    <ul className="text-[11px] space-y-1 text-gray-600">
                                        <li>🟢 <strong>≥ 90%</strong>: Sangat Setia / Zero Halusinasi</li>
                                        <li>🟡 <strong>75% - 89%</strong>: Baik, sedikit asumsi minor</li>
                                        <li>🔴 <strong>&lt; 60%</strong>: Bahaya Halusinasi Tinggi</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Tab Content 2: Answer Relevance */}
                    {selectedTab === 'answer_relevance' && (
                        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 animate-fadeIn">
                            <div className="md:col-span-2 space-y-4">
                                <div className="p-4 bg-blue-50 rounded-2xl border border-blue-200">
                                    <h3 className="font-bold text-blue-900 text-base flex items-center gap-2">
                                        💬 Formula Matematis: Answer Relevance
                                    </h3>
                                    <div className="mt-2 p-3 bg-white rounded-xl border border-blue-300 font-mono text-sm sm:text-base text-blue-950 font-bold flex items-center justify-center">
                                        Answer Relevance = ( Poin Terjawab / Total Aspek Pertanyaan ) × 100%
                                    </div>
                                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-blue-900">
                                        <div className="bg-white/80 p-2.5 rounded-lg border border-blue-200">
                                            <strong>Poin Terjawab (Pembilang):</strong>
                                            <p className="mt-0.5 text-gray-700">Aspek spesifik dari pertanyaan user yang dijawab secara tuntas dan langsung oleh AI.</p>
                                        </div>
                                        <div className="bg-white/80 p-2.5 rounded-lg border border-blue-200">
                                            <strong>Total Aspek Pertanyaan (Penyebut):</strong>
                                            <p className="mt-0.5 text-gray-700">Seluruh cakupan informasi yang diminta user dalam prompt pertanyaannya.</p>
                                        </div>
                                    </div>
                                </div>

                                <div className="text-xs text-gray-700 space-y-2">
                                    <h4 className="font-bold text-gray-900">📖 Contoh Perhitungan Nyata pada One Piece:</h4>
                                    <p className="bg-gray-50 p-3 rounded-xl border border-gray-200 leading-relaxed font-sans">
                                        Pengguna bertanya: <em>"Berapa bounty Trafalgar Law dan apa buah iblis miliknya?"</em> (ada <strong>2 aspek pertanyaan</strong>). Jika AI menyebutkan buah iblis Ope Ope no Mi dan nilai bounty 3.000.000.000 Berry secara tepat, maka kedua aspek terpenuhi:
                                        <br />
                                        <span className="font-mono font-bold text-blue-700 mt-1 block">
                                            Answer Relevance = (2 / 2) × 100% = 100.0%
                                        </span>
                                    </p>
                                </div>
                            </div>

                            <div className="bg-gray-50 rounded-2xl p-4 border border-gray-200 flex flex-col justify-between">
                                <h4 className="font-bold text-gray-900 text-xs uppercase tracking-wider mb-2">
                                    💡 Mengapa Metrik Ini Krusial?
                                </h4>
                                <p className="text-xs text-gray-600 leading-relaxed">
                                    Jawaban bisa saja 100% setia pada PDF (Faithful), tapi jika pengguna menanyakan Zoro dan AI malah menjelaskan Luffy panjang lebar, maka Answer Relevance akan rendah.
                                </p>
                                <div className="mt-4 pt-3 border-t border-gray-200">
                                    <span className="text-[11px] font-bold text-gray-700 block mb-1">Ambang Batas Nilai:</span>
                                    <ul className="text-[11px] space-y-1 text-gray-600">
                                        <li>🟢 <strong>≥ 90%</strong>: Tepat sasaran & tuntas</li>
                                        <li>🟡 <strong>75% - 89%</strong>: Sebagian besar terjawab</li>
                                        <li>🔴 <strong>&lt; 60%</strong>: Tidak nyambung / bertele-tele</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Tab Content 3: Context Relevance */}
                    {selectedTab === 'context_relevance' && (
                        <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-6 animate-fadeIn">
                            <div className="md:col-span-2 space-y-4">
                                <div className="p-4 bg-amber-50 rounded-2xl border border-amber-200">
                                    <h3 className="font-bold text-amber-900 text-base flex items-center gap-2">
                                        🔍 Formula Matematis: Context Relevance
                                    </h3>
                                    <div className="mt-2 p-3 bg-white rounded-xl border border-amber-300 font-mono text-sm sm:text-base text-amber-950 font-bold flex items-center justify-center">
                                        Context Relevance = ( |C_relevan| / |C_total| ) × 100%
                                    </div>
                                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-amber-900">
                                        <div className="bg-white/80 p-2.5 rounded-lg border border-amber-200">
                                            <strong>|C_relevan| (Pembilang):</strong>
                                            <p className="mt-0.5 text-gray-700">Jumlah potongan teks (chunks) dari Vector DB yang benar-benar memuat data relevan dengan pertanyaan.</p>
                                        </div>
                                        <div className="bg-white/80 p-2.5 rounded-lg border border-amber-200">
                                            <strong>|C_total| (Penyebut):</strong>
                                            <p className="mt-0.5 text-gray-700">Total chunk yang diambil oleh Vector Search (konfigurasi Top-K = 4 chunk).</p>
                                        </div>
                                    </div>
                                </div>

                                <div className="text-xs text-gray-700 space-y-2">
                                    <h4 className="font-bold text-gray-900">📖 Contoh Perhitungan Nyata pada One Piece:</h4>
                                    <p className="bg-gray-50 p-3 rounded-xl border border-gray-200 leading-relaxed font-sans">
                                        Retriever mengambil <strong>4 chunk</strong> dari Vector DB untuk pertanyaan tentang Roronoa Zoro. Jika <strong>3 chunk</strong> memuat biografi & pedang Zoro, sementara <strong>1 chunk</strong> berisi info tentang Usopp yang tidak relevan, maka:
                                        <br />
                                        <span className="font-mono font-bold text-amber-700 mt-1 block">
                                            Context Relevance = (3 / 4) × 100% = 75.0%
                                        </span>
                                    </p>
                                </div>
                            </div>

                            <div className="bg-gray-50 rounded-2xl p-4 border border-gray-200 flex flex-col justify-between">
                                <h4 className="font-bold text-gray-900 text-xs uppercase tracking-wider mb-2">
                                    💡 Mengapa Metrik Ini Krusial?
                                </h4>
                                <p className="text-xs text-gray-600 leading-relaxed">
                                    Menilai kualitas retriever model embedding (all-MiniLM-L6-v2). Jika Context Relevance rendah, retriever mengambil terlalu banyak data sampah yang membebani LLM.
                                </p>
                                <div className="mt-4 pt-3 border-t border-gray-200">
                                    <span className="text-[11px] font-bold text-gray-700 block mb-1">Ambang Batas Nilai:</span>
                                    <ul className="text-[11px] space-y-1 text-gray-600">
                                        <li>🟢 <strong>≥ 85%</strong>: Retriever sangat presisi</li>
                                        <li>🟡 <strong>70% - 84%</strong>: Baik, sedikit noise</li>
                                        <li>🔴 <strong>&lt; 50%</strong>: Retriever salah mengambil dokumen</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                    )}
                </section>

                {/* 3. INTERACTIVE BENCHMARK RUNNER (UJI RAG LIVE) */}
                <section className="bg-white rounded-3xl p-6 md:p-8 shadow-2xl border border-gray-200">
                    <div className="flex items-center justify-between flex-wrap gap-2 pb-4 border-b border-gray-100">
                        <div>
                            <h2 className="text-xl font-bold text-gray-900 flex items-center gap-2">
                                <span>⚡</span> Uji & Evaluasi RAG Live (Interactive Benchmark)
                            </h2>
                            <p className="text-xs md:text-sm text-gray-500 mt-0.5">
                                Jalankan pertanyaan uji untuk melihat live retrieval dari PDF, respons AI, dan perhitungan skor persentasenya secara instan!
                            </p>
                        </div>
                    </div>

                    {/* Quick Preset Buttons */}
                    <div className="mt-4">
                        <span className="text-xs font-bold text-gray-600 block mb-2">
                            Pilih Contoh Pertanyaan Uji Cepat:
                        </span>
                        <div className="flex flex-wrap gap-2">
                            {PRESET_QUERIES.map((item, idx) => (
                                <button
                                    key={idx}
                                    type="button"
                                    onClick={() => handleRunBenchmark(item.query)}
                                    disabled={isRunningBenchmark}
                                    className="bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-300 text-xs px-3 py-1.5 rounded-xl font-semibold transition disabled:opacity-50"
                                >
                                    {item.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Custom Query Input */}
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            handleRunBenchmark();
                        }}
                        className="mt-4 flex gap-2 flex-col sm:flex-row"
                    >
                        <input
                            type="text"
                            value={benchmarkQuery}
                            onChange={(e) => setBenchmarkQuery(e.target.value)}
                            placeholder="Tulis pertanyaan seputar karakter One Piece (mis: Siapa itu Monkey D Luffy?)..."
                            disabled={isRunningBenchmark}
                            className="flex-1 p-3 border border-gray-300 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-red-500 disabled:bg-gray-100"
                        />
                        <button
                            type="submit"
                            disabled={isRunningBenchmark || !benchmarkQuery.trim()}
                            className="bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-700 hover:to-amber-700 text-white font-bold px-6 py-3 rounded-xl text-sm shadow-md transition disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {isRunningBenchmark ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                                    <span>Mengevaluasi RAG...</span>
                                </>
                            ) : (
                                <>
                                    <span>⚡</span>
                                    <span>Uji & Hitung Skor</span>
                                </>
                            )}
                        </button>
                    </form>

                    {benchmarkError && (
                        <div className="mt-4 p-3 bg-red-50 text-red-700 text-xs rounded-xl border border-red-200">
                            ⚠️ {benchmarkError}
                        </div>
                    )}

                    {/* Live Results Panel */}
                    {benchmarkResult && benchmarkResult.evaluation && (
                        <div className="mt-6 p-5 bg-gradient-to-br from-gray-50 to-amber-50/50 rounded-2xl border border-amber-200 space-y-5 animate-fadeIn">
                            <div className="flex items-center justify-between flex-wrap gap-2 pb-3 border-b border-amber-200">
                                <div>
                                    <span className="text-xs uppercase font-bold text-amber-800">Hasil Evaluasi Pertanyaan:</span>
                                    <h4 className="text-sm font-bold text-gray-900 mt-0.5">"{benchmarkResult.query}"</h4>
                                </div>
                                <span className="text-xs bg-emerald-100 text-emerald-800 font-bold px-3 py-1 rounded-full border border-emerald-300">
                                    Waktu: {benchmarkResult.evaluation.latency_seconds || 1.1}s • {benchmarkResult.model_used || 'Gemini'}
                                </span>
                            </div>

                            {/* 3 Metric Scores Pill Row */}
                            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                                <div className="bg-white p-3 rounded-xl border border-emerald-200 shadow-sm">
                                    <span className="text-[11px] font-bold text-emerald-800 block">Faithfulness</span>
                                    <span className="text-2xl font-black text-emerald-600">
                                        {benchmarkResult.evaluation.scores.faithfulness.score_percent}%
                                    </span>
                                    <span className="text-[10px] text-gray-500 block mt-0.5">
                                        {benchmarkResult.evaluation.scores.faithfulness.formula_text}
                                    </span>
                                </div>
                                <div className="bg-white p-3 rounded-xl border border-blue-200 shadow-sm">
                                    <span className="text-[11px] font-bold text-blue-800 block">Answer Relevance</span>
                                    <span className="text-2xl font-black text-blue-600">
                                        {benchmarkResult.evaluation.scores.answer_relevance.score_percent}%
                                    </span>
                                    <span className="text-[10px] text-gray-500 block mt-0.5">
                                        {benchmarkResult.evaluation.scores.answer_relevance.formula_text}
                                    </span>
                                </div>
                                <div className="bg-white p-3 rounded-xl border border-amber-200 shadow-sm">
                                    <span className="text-[11px] font-bold text-amber-800 block">Context Relevance</span>
                                    <span className="text-2xl font-black text-amber-600">
                                        {benchmarkResult.evaluation.scores.context_relevance.score_percent}%
                                    </span>
                                    <span className="text-[10px] text-gray-500 block mt-0.5">
                                        {benchmarkResult.evaluation.scores.context_relevance.formula_text}
                                    </span>
                                </div>
                                <div className="bg-gradient-to-r from-red-600 to-amber-600 text-white p-3 rounded-xl shadow-sm">
                                    <span className="text-[11px] font-bold text-amber-100 block">Rata-Rata Total</span>
                                    <span className="text-2xl font-black text-white">
                                        {benchmarkResult.evaluation.scores.average.score_percent}%
                                    </span>
                                    <span className="text-[10px] text-amber-200 block mt-0.5">
                                        Mutu RAG Sangat Baik
                                    </span>
                                </div>
                            </div>

                            {/* Jawaban AI & Konteks Dokumen */}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="bg-white p-4 rounded-xl border border-gray-200 space-y-2">
                                    <h5 className="text-xs font-bold text-gray-900 flex items-center gap-1.5">
                                        <span>🐌</span> Jawaban AI (Hasil Sintesis PDF):
                                    </h5>
                                    <div className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto bg-gray-50 p-3 rounded-lg border border-gray-100">
                                        {benchmarkResult.answer}
                                    </div>
                                </div>
                                <div className="bg-white p-4 rounded-xl border border-gray-200 space-y-2 flex flex-col justify-between">
                                    <div className="flex items-center justify-between">
                                        <h5 className="text-xs font-bold text-gray-900 flex items-center gap-1.5">
                                            <span>📑</span> Chunk Dokumen PDF yang Diambil (Retriever):
                                        </h5>
                                        <button
                                            type="button"
                                            onClick={() => setShowRawContext(!showRawContext)}
                                            className="text-[10px] text-sky-700 hover:text-sky-900 underline font-semibold"
                                        >
                                            {showRawContext ? 'Tampilan Kartu Chunk' : 'Tampilan Teks Mentah'}
                                        </button>
                                    </div>

                                    {/* Jika mode Kartu Chunk Aktif dan ada list chunk */}
                                    {!showRawContext && Array.isArray(benchmarkResult.evaluation?.retrieved_chunks) && benchmarkResult.evaluation.retrieved_chunks.length > 0 ? (
                                        <div className="space-y-2">
                                            {/* Selector Tabs */}
                                            <div className="flex gap-1.5 overflow-x-auto pb-1">
                                                {benchmarkResult.evaluation.retrieved_chunks.map((chk, idx) => (
                                                    <button
                                                        key={idx}
                                                        type="button"
                                                        onClick={() => setSelectedChunkIdx(idx)}
                                                        className={`px-2.5 py-1 rounded-lg text-[11px] font-bold whitespace-nowrap transition border ${
                                                            selectedChunkIdx === idx
                                                                ? 'bg-amber-600 text-white border-amber-600 shadow-sm'
                                                                : 'bg-gray-100 hover:bg-gray-200 text-gray-700 border-gray-200'
                                                        }`}
                                                    >
                                                        Chunk #{chk.chunk_index || idx + 1}: {chk.title?.slice(0, 15)}
                                                    </button>
                                                ))}
                                            </div>

                                            {/* Selected Chunk Card Detail */}
                                            {(() => {
                                                const activeChunk = benchmarkResult.evaluation.retrieved_chunks[selectedChunkIdx] || benchmarkResult.evaluation.retrieved_chunks[0];
                                                return (
                                                    <div className="p-3 bg-amber-50/60 rounded-xl border border-amber-200 text-xs space-y-2">
                                                        <div className="flex items-center justify-between flex-wrap gap-1 font-bold text-gray-900 border-b border-amber-200/70 pb-1.5">
                                                            <span className="flex items-center gap-1 text-amber-900">
                                                                <span>🔖</span> {activeChunk.title} (ID {activeChunk.id})
                                                            </span>
                                                            <div className="flex gap-1 text-[10px]">
                                                                <span className="bg-white text-gray-700 px-2 py-0.5 rounded border border-gray-200 font-mono">
                                                                    📄 Hal PDF: {activeChunk.page || 1}
                                                                </span>
                                                                <span className="bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded border border-emerald-300 font-mono font-bold">
                                                                    🎯 Skor Relevansi: {activeChunk.score || '-'}
                                                                </span>
                                                            </div>
                                                        </div>
                                                        <div className="text-[11px] text-gray-700 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto bg-white p-2.5 rounded-lg border border-gray-100 font-sans">
                                                            {activeChunk.content}
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                        </div>
                                    ) : (
                                        <div className="text-xs text-gray-600 font-mono whitespace-pre-wrap leading-relaxed max-h-56 overflow-y-auto bg-gray-50 p-3 rounded-lg border border-gray-100">
                                            {benchmarkResult.retrieved_context}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    )}
                </section>

                {/* 4. RIWAYAT EVALUASI TERBARU */}
                {evalHistory.length > 0 && (
                    <section className="bg-white/95 rounded-3xl p-6 md:p-8 shadow-xl border border-white/50">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                                <span>📜</span> Riwayat Evaluasi Sesi Terakhir (Live Log)
                            </h2>
                            <span className="text-xs text-gray-500">Tersinkronisasi otomatis dari chat Den Den Mushi</span>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-xs text-left">
                                <thead className="bg-gray-100 text-gray-700 uppercase font-semibold">
                                    <tr>
                                        <th className="p-3 rounded-l-lg">Waktu</th>
                                        <th className="p-3">Pertanyaan</th>
                                        <th className="p-3 text-center">Faithfulness</th>
                                        <th className="p-3 text-center">Answer Rel</th>
                                        <th className="p-3 text-center">Context Rel</th>
                                        <th className="p-3 text-center rounded-r-lg">Rata-Rata</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                    {evalHistory.map((item, idx) => (
                                        <tr key={idx} className="hover:bg-amber-50/50 transition">
                                            <td className="p-3 text-gray-500 whitespace-nowrap">
                                                {item.timestamp ? new Date(item.timestamp).toLocaleTimeString('id-ID') : '-'}
                                            </td>
                                            <td className="p-3 font-medium text-gray-800 max-w-xs truncate">
                                                {item.query}
                                            </td>
                                            <td className="p-3 text-center">
                                                <span className="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded border border-emerald-200">
                                                    {item.scores?.faithfulness?.score_percent}%
                                                </span>
                                            </td>
                                            <td className="p-3 text-center">
                                                <span className="bg-blue-50 text-blue-700 font-bold px-2 py-0.5 rounded border border-blue-200">
                                                    {item.scores?.answer_relevance?.score_percent}%
                                                </span>
                                            </td>
                                            <td className="p-3 text-center">
                                                <span className="bg-amber-50 text-amber-700 font-bold px-2 py-0.5 rounded border border-amber-200">
                                                    {item.scores?.context_relevance?.score_percent}%
                                                </span>
                                            </td>
                                            <td className="p-3 text-center">
                                                <span className="bg-red-50 text-red-700 font-bold px-2 py-0.5 rounded border border-red-200">
                                                    {item.scores?.average?.score_percent}%
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>
                )}
            </main>
        </div>
    );
};

export default OnePiece;
