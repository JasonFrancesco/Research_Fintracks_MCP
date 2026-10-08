import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import api from '../services/api';

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

const formatChatTime = (value) => {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
};

const GatlingChatWidget = ({ onTestTriggered }) => {
    const [isOpen, setIsOpen] = useState(false);
    const DEFAULT_TARGET_URL = 'https://192.168.18.57:44396/';

    // Messages State with localStorage cache
    const [messages, setMessages] = useState(() => {
        try {
            const cached = localStorage.getItem('fintracks_gatling_chat_cache');
            return cached ? JSON.parse(cached) : [];
        } catch {
            return [];
        }
    });

    const [chatInput, setChatInput] = useState('');
    const [isChatLoading, setIsChatLoading] = useState(false);
    const [chatElapsedSeconds, setChatElapsedSeconds] = useState(0);
    const chatTimerRef = useRef(null);
    const [isFetchingChat, setIsFetchingChat] = useState(false);
    const chatEndRef = useRef(null);
    const [copiedIndex, setCopiedIndex] = useState(null);

    const [availableModels, setAvailableModels] = useState([]);
    const [selectedModel, setSelectedModel] = useState('local');

    // Preset Prompts Cepat
    const quickPrompts = [
        'Uji login https://192.168.18.57:44396/ user: manager_mark pass: Admin123 captcha: abc',
        `Stress test ${DEFAULT_TARGET_URL} dengan 200 VU selama 30 detik`,
        'Uji antrean RabbitMQ fintracks.orders dengan 100 VU selama 20 detik',
        'Bagaimana cara mengoptimalkan latensi P95 agar di bawah 500ms?',
        'Periksa status koneksi dan antrean RabbitMQ'
    ];

    const fetchModels = async () => {
        try {
            const res = await api.get('/chat/models');
            if (res.data && Array.isArray(res.data.models)) {
                setAvailableModels(res.data.models);
                if (res.data.default) {
                    setSelectedModel(res.data.default);
                }
            }
        } catch (err) {
            console.error('Gagal memuat list model:', err);
        }
    };

    // Fetch Chat History dari Backend PostgreSQL
    const fetchChatHistory = async () => {
        try {
            setIsFetchingChat(true);
            const res = await api.get('/gatling/chat/history');
            const dataList = Array.isArray(res.data)
                ? res.data
                : Array.isArray(res.data?.messages)
                    ? res.data.messages
                    : null;

            if (dataList) {
                setMessages(dataList);
                try {
                    localStorage.setItem('fintracks_gatling_chat_cache', JSON.stringify(dataList));
                } catch (e) {
                    // ignore
                }
            }
        } catch (err) {
            console.error('Gagal memuat chat history:', err);
        } finally {
            setIsFetchingChat(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            fetchChatHistory();
            if (availableModels.length === 0) {
                fetchModels();
            }
        }
    }, [isOpen]);

    useEffect(() => {
        if (isOpen) {
            chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }
    }, [messages, isChatLoading, isOpen]);

    // Send Message Handler
    const handleSendMessage = async (textToSend = null) => {
        const query = (textToSend || chatInput).trim();
        if (!query || isChatLoading) return;

        const userMsg = { role: 'user', text: query, created_at: new Date().toISOString() };
        setMessages(prev => {
            const next = [...prev, userMsg];
            try { localStorage.setItem('fintracks_gatling_chat_cache', JSON.stringify(next)); } catch (e) {}
            return next;
        });

        setChatInput('');
        setIsChatLoading(true);
        setChatElapsedSeconds(0);

        if (chatTimerRef.current) clearInterval(chatTimerRef.current);
        chatTimerRef.current = setInterval(() => {
            setChatElapsedSeconds(prev => prev + 1);
        }, 1000);

        try {
            const res = await api.post('/gatling/chat', {
                message: query,
                model: selectedModel
            });

            setMessages(prev => {
                const next = [
                    ...prev,
                    { role: 'ai', text: res.data.response, created_at: new Date().toISOString() }
                ];
                try { localStorage.setItem('fintracks_gatling_chat_cache', JSON.stringify(next)); } catch (e) {}
                return next;
            });

            if (onTestTriggered) {
                onTestTriggered();
            }
        } catch (err) {
            setMessages(prev => {
                const next = [
                    ...prev,
                    {
                        role: 'ai',
                        text: '⚠️ Terjadi kendala saat memproses permintaan load test. Pastikan backend server dan MCP tools aktif.',
                        created_at: new Date().toISOString()
                    }
                ];
                try { localStorage.setItem('fintracks_gatling_chat_cache', JSON.stringify(next)); } catch (e) {}
                return next;
            });
        } finally {
            if (chatTimerRef.current) clearInterval(chatTimerRef.current);
            setIsChatLoading(false);
        }
    };

    // Clear Chat History
    const handleClearHistory = async () => {
        if (!window.confirm('Hapus seluruh riwayat percakapan AI Copilot?')) return;
        try {
            await api.delete('/gatling/chat/history');
            localStorage.removeItem('fintracks_gatling_chat_cache');
            setMessages([]);
        } catch (err) {
            alert('Gagal membersihkan riwayat percakapan.');
        }
    };

    // Copy text handler
    const handleCopyText = async (text, snippetId) => {
        await copyToClipboard(text);
        setCopiedIndex(snippetId);
        setTimeout(() => setCopiedIndex(null), 2000);
    };

    // Format Message Content with Code Blocks extraction
    const renderFormattedMessage = (text, msgIndex) => {
        const parts = text.split(/(```[\s\S]*?```)/g);
        return parts.map((part, pIdx) => {
            if (part.startsWith('```') && part.endsWith('```')) {
                const lines = part.slice(3, -3).trim().split('\n');
                let language = 'code';
                let codeContent = part.slice(3, -3);
                if (lines.length > 1 && /^[a-zA-Z0-9_-]+$/.test(lines[0].trim())) {
                    language = lines[0].trim();
                    codeContent = lines.slice(1).join('\n');
                }
                const snippetId = `${msgIndex}-${pIdx}`;
                return (
                    <div key={pIdx} className="my-2 rounded-xl overflow-hidden border border-slate-700/80 bg-slate-950 font-mono text-[11px] shadow-lg">
                        <div className="bg-slate-900/90 px-3 py-1.5 border-b border-slate-800 flex items-center justify-between text-slate-400">
                            <span className="text-[10px] uppercase font-bold text-orange-400 font-mono tracking-wider">
                                {language}
                            </span>
                            <button
                                onClick={() => handleCopyText(codeContent, snippetId)}
                                className="text-[10px] text-slate-300 hover:text-white px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 transition"
                            >
                                {copiedIndex === snippetId ? '✓ Tersalin' : 'Salin'}
                            </button>
                        </div>
                        <pre className="p-3 overflow-x-auto text-emerald-400 leading-relaxed max-h-60">
                            {codeContent}
                        </pre>
                    </div>
                );
            }
            return (
                <span key={pIdx} className="whitespace-pre-wrap">
                    {part}
                </span>
            );
        });
    };

    return (
        <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
            {/* EXPANDED CHATBOT WINDOW */}
            {isOpen && (
                <div className="mb-3 w-[92vw] sm:w-[460px] md:w-[490px] h-[580px] max-h-[82vh] bg-slate-900/95 border border-slate-700/90 rounded-2xl shadow-2xl backdrop-blur-xl flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200">
                    {/* Header */}
                    <div className="p-3.5 bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border-b border-slate-800 flex items-center justify-between text-white">
                        <div className="flex items-center gap-2.5">
                            <div className="h-8 w-8 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-red-500 flex items-center justify-center text-sm shadow-md shadow-orange-500/20">
                                🤖
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h3 className="text-xs font-bold text-white tracking-wide">
                                        Gatling AI Copilot
                                    </h3>
                                    {availableModels.length > 0 ? (
                                        <select
                                            value={selectedModel}
                                            onChange={(e) => setSelectedModel(e.target.value)}
                                            className="bg-slate-800 text-orange-400 border border-slate-700 text-[10px] px-1.5 py-0.5 rounded focus:outline-none focus:border-orange-500"
                                        >
                                            {availableModels.map(m => (
                                                <option key={m.id} value={m.id}>
                                                    {m.name} {m.provider === 'ollama' ? '(Lokal)' : ''}
                                                </option>
                                            ))}
                                        </select>
                                    ) : (
                                        <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[9px] px-1.5 py-0.2 rounded font-mono">
                                            Memuat...
                                        </span>
                                    )}
                                </div>
                                <p className="text-[10px] text-slate-400">
                                    Otomasi uji beban & RabbitMQ
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-1.5">
                            {/* Link to Fullpage Copilot */}
                            <Link
                                to="/gatling/copilot"
                                className="text-slate-400 hover:text-orange-400 p-1.5 rounded-lg hover:bg-slate-800 transition text-[11px]"
                                title="Buka di halaman penuh"
                            >
                                <span>↗</span>
                            </Link>

                            {/* Refresh */}
                            <button
                                onClick={fetchChatHistory}
                                className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition text-[11px]"
                                title="Muat ulang riwayat"
                            >
                                ↻
                            </button>

                            {/* Clear History */}
                            {messages.length > 0 && (
                                <button
                                    onClick={handleClearHistory}
                                    className="text-slate-400 hover:text-rose-400 p-1.5 rounded-lg hover:bg-slate-800 transition text-[11px]"
                                    title="Bersihkan riwayat percakapan"
                                >
                                    🗑️
                                </button>
                            )}

                            {/* Collapse / Close Button */}
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition text-sm ml-1"
                                title="Kecilkan Chatbot (Collapse)"
                            >
                                ✕
                            </button>
                        </div>
                    </div>

                    {/* Quick Prompts Bar */}
                    <div className="bg-slate-950/80 p-2 border-b border-slate-800 overflow-x-auto flex gap-1.5 no-scrollbar shrink-0">
                        {quickPrompts.map((p, pIdx) => (
                            <button
                                key={pIdx}
                                onClick={() => handleSendMessage(p)}
                                disabled={isChatLoading}
                                className="text-[10px] shrink-0 bg-slate-900 hover:bg-orange-600/20 hover:border-orange-500/40 hover:text-orange-300 border border-slate-800 text-slate-300 px-2.5 py-1 rounded-full transition disabled:opacity-40"
                            >
                                ⚡ {p.length > 35 ? p.substring(0, 32) + '...' : p}
                            </button>
                        ))}
                    </div>

                    {/* Messages Body */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs bg-slate-950/50">
                        {isFetchingChat && messages.length === 0 ? (
                            <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                                <span className="animate-pulse">Memuat riwayat percakapan...</span>
                            </div>
                        ) : messages.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center p-4 text-slate-500 space-y-2.5">
                                <span className="text-3xl opacity-60">⚡</span>
                                <div>
                                    <p className="font-semibold text-slate-200 text-xs">Asisten Uji Beban Gatling</p>
                                    <p className="text-[11px] text-slate-400 mt-1 max-w-xs">
                                        Perintahkan AI untuk mengeksekusi beban atau membuat skrip Scala simulasi:
                                    </p>
                                </div>
                                <div className="space-y-1 text-[11px] text-left bg-slate-900 p-2.5 rounded-xl border border-slate-800 w-full max-w-xs">
                                    <div className="text-orange-400 font-semibold font-mono text-[10px]">Contoh Perintah:</div>
                                    <div className="text-slate-300 cursor-pointer hover:text-orange-300" onClick={() => handleSendMessage(`Stress test ${DEFAULT_TARGET_URL} dengan 200 VU`)}>
                                        › "Stress test {DEFAULT_TARGET_URL} dengan 200 VU"
                                    </div>
                                    <div className="text-slate-300 cursor-pointer hover:text-orange-300" onClick={() => handleSendMessage('Uji antrean fintracks.orders 30 detik')}>
                                        › "Uji antrean fintracks.orders 30 detik"
                                    </div>
                                </div>
                            </div>
                        ) : (
                            messages.map((m, i) => {
                                const isUser = m.role === 'user';
                                return (
                                    <div key={i} className={`flex gap-2.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
                                        {!isUser && (
                                            <div className="h-6 w-6 rounded-lg bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                                                🤖
                                            </div>
                                        )}
                                        <div className="max-w-[85%] space-y-0.5">
                                            <div
                                                className={`p-3 rounded-2xl shadow-sm ${
                                                    isUser
                                                        ? 'bg-gradient-to-r from-orange-600 to-amber-600 text-white rounded-tr-none'
                                                        : 'bg-slate-900 text-slate-200 border border-slate-800 rounded-tl-none font-sans text-xs leading-relaxed'
                                                }`}
                                            >
                                                {renderFormattedMessage(m.text, i)}
                                            </div>
                                            <div className={`text-[9px] text-slate-500 px-1 flex items-center gap-1.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
                                                <span>{isUser ? 'Anda' : 'Copilot'}</span>
                                                {m.created_at && (
                                                    <span>• {formatChatTime(m.created_at)}</span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                );
                            })
                        )}

                        {/* Live Timer Indicator during load test execution */}
                        {isChatLoading && (
                            <div className="flex gap-2">
                                <div className="h-6 w-6 rounded-lg bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-[10px] shrink-0 mt-0.5">
                                    🤖
                                </div>
                                <div className="bg-slate-900 border border-orange-500/30 rounded-2xl rounded-tl-none p-3 text-xs space-y-1 shadow-lg">
                                    <div className="flex items-center gap-2 text-orange-400 font-semibold text-[11px]">
                                        <span className="h-2 w-2 bg-orange-400 rounded-full animate-ping"></span>
                                        <span>
                                            {chatElapsedSeconds > 0
                                                ? `Gatling sedang menguji target (${chatElapsedSeconds}s)...`
                                                : 'Menyiapkan simulasi Gatling...'}
                                        </span>
                                    </div>
                                    <p className="text-[10px] text-slate-400 leading-snug">
                                        Menunggu durasi pengujian selesai penuh di mesin Gatling sebelum menyusun laporan.
                                    </p>
                                </div>
                            </div>
                        )}
                        <div ref={chatEndRef} />
                    </div>

                    {/* Chat Input Bar */}
                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            handleSendMessage();
                        }}
                        className="p-3 bg-slate-900 border-t border-slate-800 flex gap-2 items-center"
                    >
                        <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            disabled={isChatLoading}
                            placeholder="Ketik instruksi (misal: 'Jalankan 200 VU')..."
                            className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition"
                        />
                        <button
                            type="submit"
                            disabled={isChatLoading || !chatInput.trim()}
                            className="bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white px-3.5 py-2 rounded-xl text-xs font-bold shadow-md shadow-orange-600/20 disabled:opacity-40 transition cursor-pointer shrink-0"
                        >
                            <span>Kirim</span>
                        </button>
                    </form>
                </div>
            )}

            {/* COLLAPSED FLOATING TRIGGER BUTTON */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={`group flex items-center gap-2.5 px-4 py-3 rounded-full shadow-2xl transition-all duration-300 hover:scale-105 active:scale-95 cursor-pointer border ${
                    isOpen
                        ? 'bg-slate-800 hover:bg-slate-750 text-slate-200 border-slate-700 shadow-slate-900/60'
                        : 'bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500 hover:from-orange-500 hover:to-amber-500 text-white border-orange-400/40 shadow-orange-600/30'
                }`}
                title="FinTracks Gatling AI Copilot"
            >
                <div className="relative flex items-center justify-center">
                    <span className="text-xl group-hover:rotate-12 transition-transform duration-300">
                        {isOpen ? '✕' : '🤖'}
                    </span>
                    {!isOpen && (
                        <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400"></span>
                        </span>
                    )}
                </div>
                <div className="text-left">
                    <div className="text-xs font-bold leading-tight flex items-center gap-1.5">
                        <span>{isOpen ? 'Tutup Copilot' : 'AI Copilot'}</span>
                        {!isOpen && (
                            <span className="bg-white/20 text-[9px] px-1.5 py-0.2 rounded font-mono">
                                Gatling
                            </span>
                        )}
                    </div>
                    {!isOpen && (
                        <p className="text-[10px] text-orange-100/90 leading-tight">
                            Tanya skrip / Uji beban
                        </p>
                    )}
                </div>
            </button>
        </div>
    );
};

export default GatlingChatWidget;
