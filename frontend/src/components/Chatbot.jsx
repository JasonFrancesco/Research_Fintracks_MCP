import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';

const Chatbot = () => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isFetchingHistory, setIsFetchingHistory] = useState(true);
    const [selectedModel, setSelectedModel] = useState(() => {
        const saved = localStorage.getItem('fintracks_model_mode');
        // 'cloud' adalah nilai lama sebelum ada preset bernama
        return !saved || saved === 'cloud' ? 'local' : saved;
    });
    const [modelOptions, setModelOptions] = useState([]);
    const scrollRef = useRef(null);

    const activeOption = modelOptions.find((m) => m.id === selectedModel) || null;

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const response = await api.get('/chat/history');
                if (Array.isArray(response.data)) {
                    setMessages(response.data);
                }
            } catch (error) {
                console.error('Gagal memuat riwayat percakapan:', error);
            } finally {
                setIsFetchingHistory(false);
            }
        };

        const fetchModels = async () => {
            try {
                const res = await api.get('/chat/models');
                const options = Array.isArray(res.data?.models) ? res.data.models : [];
                setModelOptions(options);

                // Kalau preset tersimpan sudah tidak ada di backend, pakai default
                const saved = localStorage.getItem('fintracks_model_mode');
                if (options.length > 0 && !options.some((m) => m.id === saved)) {
                    const fallback = res.data?.default || options[0].id;
                    setSelectedModel(fallback);
                    localStorage.setItem('fintracks_model_mode', fallback);
                }
            } catch (error) {
                console.error('Gagal memuat info model:', error);
            }
        };

        fetchHistory();
        fetchModels();
    }, []);

    useEffect(() => {
        scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]);

    const handleModelChange = (e) => {
        const newMode = e.target.value;
        setSelectedModel(newMode);
        localStorage.setItem('fintracks_model_mode', newMode);
    };

    const handleSend = async (e) => {
        e.preventDefault();
        if (!input.trim()) return;

        const userMessage = { role: 'user', text: input };
        setMessages(prev => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);

        try {
            const response = await api.post('/chat/', {
                message: input,
                model: selectedModel
            });
            setMessages(prev => [...prev, { role: 'ai', text: response.data.response }]);
        } catch (error) {
            // Pesan seragam "gagal menghubungi AI" menyembunyikan penyebab sebenarnya.
            // Sebagian besar kegagalan di sini bukan soal AI: sesi habis, backend mati,
            // atau MCP Server belum jalan.
            console.error('Gagal mengirim pesan ke chatbot:', error);
            const status = error.response?.status;
            const detail = error.response?.data?.detail;

            let text;
            if (status === 401) {
                text = '🔒 Sesi Anda sudah berakhir. Silakan login ulang, lalu kirim pesan ini kembali.';
            } else if (!error.response) {
                text = '🔌 Tidak bisa terhubung ke backend di http://localhost:8000. Pastikan backend sedang berjalan.';
            } else if (status >= 500) {
                text = `⚠️ Backend mengalami error (HTTP ${status}). Periksa terminal backend untuk detailnya.${detail ? `\n\n${detail}` : ''}`;
            } else {
                text = `⚠️ Permintaan ditolak (HTTP ${status}).${detail ? `\n\n${detail}` : ''}`;
            }
            setMessages(prev => [...prev, { role: 'ai', text }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleClearHistory = async () => {
        if (!window.confirm('Apakah Anda yakin ingin menghapus seluruh riwayat chat?')) return;
        try {
            await api.delete('/chat/history');
            setMessages([]);
        } catch (error) {
            console.error('Gagal menghapus riwayat chat:', error);
        }
    };

    return (
        <div className="fixed bottom-24 right-6 w-96 h-[520px] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden z-40">
            {/* Header */}
            <div className="bg-blue-600 p-3.5 text-white flex flex-col gap-2 shadow">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 bg-green-400 rounded-full animate-pulse"></div>
                        <span className="font-bold text-sm">FinTracks AI</span>
                    </div>
                    {messages.length > 0 && (
                        <button
                            onClick={handleClearHistory}
                            className="text-[11px] bg-blue-700 hover:bg-blue-800 text-white px-2 py-0.5 rounded transition"
                            title="Hapus Riwayat Chat"
                        >
                            Hapus Chat
                        </button>
                    )}
                </div>

                {/* Model Switcher Bar */}
                <div className="bg-blue-700/80 p-1.5 rounded-lg border border-blue-500/50 space-y-1">
                    <div className="flex items-center justify-between text-xs gap-2">
                        <label htmlFor="model-preset" className="text-blue-100 text-[11px] font-medium shrink-0">
                            Model AI:
                        </label>
                        <select
                            id="model-preset"
                            value={selectedModel}
                            onChange={handleModelChange}
                            disabled={isLoading || modelOptions.length === 0}
                            className="bg-blue-800 text-white text-[11px] font-semibold py-0.5 px-2 rounded cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-300 border border-blue-400 disabled:opacity-60 max-w-[15rem] truncate"
                        >
                            {modelOptions.length === 0 ? (
                                <option value={selectedModel}>Memuat model...</option>
                            ) : (
                                modelOptions.map((m) => (
                                    <option key={m.id} value={m.id}>
                                        {m.name}
                                        {m.available === false ? ' — belum siap' : ''}
                                    </option>
                                ))
                            )}
                        </select>
                    </div>

                    {activeOption && (
                        <p className="text-[10px] text-blue-100/90 leading-snug">
                            {activeOption.available === false
                                ? `⚠️ ${activeOption.hint || 'API Key belum diisi.'}`
                                : `${activeOption.model} · ${activeOption.description || ''}`}
                        </p>
                    )}
                </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
                {isFetchingHistory ? (
                    <div className="flex justify-center items-center h-full text-xs text-gray-400">
                        Memuat riwayat chat...
                    </div>
                ) : messages.length === 0 ? (
                    <div className="text-center text-gray-400 text-xs mt-10">
                        Belum ada percakapan. Silakan sapa atau tanya sesuatu!
                    </div>
                ) : (
                    messages.map((msg, i) => (
                        <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                            <div className={`max-w-[85%] p-3 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                                msg.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white text-gray-800 border border-gray-200 rounded-tl-none shadow-sm'
                            }`}>
                                {msg.text}
                            </div>
                        </div>
                    ))
                )}
                {isLoading && (
                    <div className="flex justify-start">
                        <div className="bg-white p-3 rounded-2xl border border-gray-200 rounded-tl-none animate-pulse text-gray-400 text-sm flex items-center gap-2">
                            <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></span>
                            {activeOption?.model || selectedModel} sedang berpikir...
                        </div>
                    </div>
                )}
                <div ref={scrollRef}></div>
            </div>

            {/* Input */}
            <form onSubmit={handleSend} className="p-3 bg-white border-t border-gray-100 flex gap-2">
                <input
                    type="text"
                    className="flex-1 p-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder={`Tanya saldo (${selectedModel})...`}
                    aria-label="Pesan untuk FinTracks AI"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    disabled={isLoading}
                />
                <button
                    type="submit"
                    className="bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700 disabled:bg-gray-400 transition"
                    disabled={isLoading}
                >
                    Kirim
                </button>
            </form>
        </div>
    );
};

export default Chatbot;


