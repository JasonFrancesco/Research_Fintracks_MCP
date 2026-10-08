import React, { useState, useEffect, useRef } from 'react';
import api from '../services/api';

// Clipboard API hanya tersedia di secure context (https atau localhost).
// Kalau frontend dibuka lewat IP LAN, misalnya http://192.168.x.x:3000,
// navigator.clipboard tidak ada, jadi dipakai cara lama lewat textarea.
const copyToClipboard = async (text) => {
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('readonly', '');
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        if (!document.execCommand('copy')) throw new Error('execCommand copy gagal');
    } finally {
        document.body.removeChild(textarea);
    }
};

// Pesan hari ini cukup jamnya ("14:05"). Pesan dari hari lain diberi tanggal
// ("29 Sep 14:05"), karena riwayat chat bisa berumur beberapa hari dan jam saja
// tidak menjelaskan kapan pesan itu dikirim.
const formatChatTime = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';

    const time = date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    const now = new Date();
    const sameDay = date.toDateString() === now.toDateString();
    if (sameDay) return time;

    const day = date.toLocaleDateString('id-ID', {
        day: 'numeric',
        month: 'short',
        ...(date.getFullYear() !== now.getFullYear() && { year: 'numeric' }),
    });
    return `${day} ${time}`;
};

const CopyButton = ({ text, isUser }) => {
    const [status, setStatus] = useState('idle'); // 'idle' | 'copied' | 'error'
    const timerRef = useRef(null);

    useEffect(() => () => clearTimeout(timerRef.current), []);

    const handleCopy = async () => {
        try {
            await copyToClipboard(text);
            setStatus('copied');
        } catch (error) {
            console.error('Gagal menyalin pesan:', error);
            setStatus('error');
        }
        clearTimeout(timerRef.current);
        timerRef.current = setTimeout(() => setStatus('idle'), 2000);
    };

    const label = status === 'copied' ? 'Tersalin' : status === 'error' ? 'Gagal' : 'Salin';

    return (
        <button
            type="button"
            onClick={handleCopy}
            className={`mt-1 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                status === 'copied'
                    ? 'text-green-600'
                    : status === 'error'
                        ? 'text-red-500'
                        : 'text-gray-400 hover:text-gray-700 hover:bg-gray-100'
            } ${isUser ? 'self-end' : 'self-start'}`}
            aria-label={status === 'copied' ? 'Pesan tersalin' : 'Salin pesan'}
            title="Salin pesan"
        >
            {status === 'copied' ? (
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
            ) : (
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
            )}
            <span aria-live="polite">{label}</span>
        </button>
    );
};

const Chatbot = () => {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isFetchingHistory, setIsFetchingHistory] = useState(true);
    const [selectedModel, setSelectedModel] = useState(() => {
        const saved = localStorage.getItem('fintracks_model_mode');
        return !saved || saved === 'cloud' || saved === 'local' ? 'gemini' : saved;
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

                // Default ke model online (gemini atau settingan backend)
                const saved = localStorage.getItem('fintracks_model_mode');
                const defaultModel = res.data?.default || 'gemini';
                if (!saved || saved === 'local' || !options.some((m) => m.id === saved)) {
                    setSelectedModel(defaultModel);
                    localStorage.setItem('fintracks_model_mode', defaultModel);
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

    // Dipanggil saat pengguna menekan "Kirim" atau Enter. Ini TITIK AWAL alur chat.
    const handleSend = async (e) => {
        e.preventDefault();           // cegah form me-reload halaman
        if (!input.trim()) return;    // abaikan kalau input kosong / hanya spasi

        // Pesan baru belum punya created_at dari database, jadi dicap jam lokal.
        // Setelah halaman dimuat ulang, jam diambil dari riwayat di backend.
        const userMessage = { role: 'user', text: input, created_at: new Date().toISOString() };
        setMessages(prev => [...prev, userMessage]);  // tampilkan pesan user langsung (optimistic)
        setInput('');                 // kosongkan kolom input
        setIsLoading(true);           // tampilkan indikator "sedang berpikir..."

        try {
            // Kirim ke backend. api = axios yang otomatis menempel token JWT.
            // Jawaban baru datang setelah backend selesai: LLM -> MCP -> LLM.
            const response = await api.post('/chat/', {
                message: input,
                model: selectedModel  // preset model yang dipilih di dropdown
            });
            // Tambahkan balasan AI ke daftar pesan supaya muncul di layar.
            setMessages(prev => [...prev, { role: 'ai', text: response.data.response, created_at: new Date().toISOString() }]);
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
            setMessages(prev => [...prev, { role: 'ai', text, created_at: new Date().toISOString() }]);
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
                        <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                            <div className={`max-w-[85%] p-3 rounded-2xl text-sm whitespace-pre-wrap leading-relaxed ${
                                msg.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white text-gray-800 border border-gray-200 rounded-tl-none shadow-sm'
                            }`}>
                                {msg.text}
                            </div>
                            <div className={`flex items-center gap-1 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                                {formatChatTime(msg.created_at) && (
                                    <time
                                        dateTime={msg.created_at}
                                        title={new Date(msg.created_at).toLocaleString('id-ID')}
                                        className="mt-1 px-1 text-[11px] text-gray-400"
                                    >
                                        {formatChatTime(msg.created_at)}
                                    </time>
                                )}
                                {msg.text && <CopyButton text={msg.text} isUser={msg.role === 'user'} />}
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


