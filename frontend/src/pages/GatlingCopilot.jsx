import React, { useState, useEffect, useRef, useContext } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import api from '../services/api';

const GatlingCopilot = () => {
    const { logout } = useContext(AuthContext);
    const navigate = useNavigate();

    const DEFAULT_TARGET_URL = 'https://192.168.18.57:44396/';

    // Target Ping State
    const [targetPing, setTargetPing] = useState({
        checking: false,
        online: null,
        statusCode: null,
        latencyMs: null,
        server: null,
        message: 'Belum dicek'
    });

    // Chatbot State with localStorage cache fallback for instant page navigation
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
    const [activeModelName, setActiveModelName] = useState('Memuat Konfigurasi...');

    // Quick Prompts Categorized
    const promptCategories = [
        {
            title: '⚡ Pembuatan Skrip & Pengujian IIS',
            prompts: [
                'Uji login https://192.168.18.57:44396/ user: manager_mark pass: Admin123 captcha: abc',
                `Buatkan skrip Gatling HTTP untuk menguji ${DEFAULT_TARGET_URL}`,
                `Simulasikan 200 Virtual Users ke ${DEFAULT_TARGET_URL} selama 30 detik`,
                `Buatkan skrip uji beban REST API FinTracks dengan ramp-up 50 VU dalam 10 detik`
            ]
        },
        {
            title: '🐰 Pengujian Antrean RabbitMQ',
            prompts: [
                'Stress test antrean RabbitMQ fintracks.orders dengan 100 VU selama 20 detik',
                'Simulasi lonjakan pesan pada antrean fintracks.transactions dengan 300 pesan/detik',
                'Periksa status koneksi dan kesehatan antrean RabbitMQ fintracks'
            ]
        },
        {
            title: '📊 Analisis Metrik & Bottleneck',
            prompts: [
                'Bagaimana cara mengoptimalkan latensi P95 agar di bawah 500ms?',
                'Analisis hasil pengujian Gatling terakhir dan jelaskan penyebab error rate',
                'Jelaskan rekomendasi tuning throughput untuk ASP.NET Gateway dan RabbitMQ'
            ]
        }
    ];

    // Cek Ping Target
    const checkTargetPing = async (urlToCheck = DEFAULT_TARGET_URL) => {
        if (!urlToCheck || !urlToCheck.startsWith('http')) {
            setTargetPing({
                checking: false,
                online: null,
                statusCode: null,
                latencyMs: null,
                server: null,
                message: 'Target AMQP (Bukan HTTP Ping)'
            });
            return;
        }

        setTargetPing(prev => ({ ...prev, checking: true, message: 'Memeriksa...' }));
        try {
            const res = await api.get(`/gatling/ping-target?url=${encodeURIComponent(urlToCheck)}`);
            setTargetPing({
                checking: false,
                online: res.data.online,
                statusCode: res.data.status_code,
                latencyMs: res.data.latency_ms,
                server: res.data.server,
                message: res.data.online
                    ? `Online (${res.data.status_code || 200}) ~${res.data.latency_ms}ms`
                    : (res.data.message || 'Offline')
            });
        } catch (err) {
            setTargetPing({
                checking: false,
                online: false,
                statusCode: null,
                latencyMs: null,
                server: null,
                message: 'Gagal terhubung ke endpoint target'
            });
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
                    // ignore storage error
                }
            }
        } catch (err) {
            console.error('Gagal memuat chat history:', err);
        } finally {
            setIsFetchingChat(false);
        }
    };

    const fetchActiveModel = async () => {
        try {
            const res = await api.get('/chat/models');
            if (res.data && res.data.default) {
                const defaultId = res.data.default;
                const activeModel = res.data.models.find(m => m.id === defaultId);
                if (activeModel) {
                    let displayName = activeModel.name;
                    if (activeModel.provider === 'ollama') {
                        // Display dynamically the ollama endpoint as local info
                        displayName = `Ollama (${activeModel.model})`;
                    }
                    setActiveModelName(displayName);
                }
            }
        } catch (err) {
            console.error('Gagal memuat info model:', err);
            setActiveModelName('AI Engine Aktif');
        }
    };

    useEffect(() => {
        checkTargetPing();
        fetchChatHistory();
        fetchActiveModel();
        return () => {
            if (chatTimerRef.current) clearInterval(chatTimerRef.current);
        };
    }, []);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isChatLoading]);

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
                model: 'gemini'
            });

            setMessages(prev => {
                const next = [
                    ...prev,
                    { role: 'ai', text: res.data.response, created_at: new Date().toISOString() }
                ];
                try { localStorage.setItem('fintracks_gatling_chat_cache', JSON.stringify(next)); } catch (e) {}
                return next;
            });
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

    // Copy text snippet helper
    const handleCopyText = (text, index) => {
        navigator.clipboard.writeText(text);
        setCopiedIndex(index);
        setTimeout(() => setCopiedIndex(null), 2000);
    };

    // Format Message Content with Code Blocks extraction
    const renderFormattedMessage = (text, msgIndex) => {
        // Simple regex parser for markdown code blocks ```...```
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
                    <div key={pIdx} className="my-2.5 rounded-xl overflow-hidden border border-slate-700/80 bg-slate-950 font-mono text-[11px] shadow-lg">
                        <div className="bg-slate-900/90 px-3 py-1.5 border-b border-slate-800 flex items-center justify-between text-slate-400">
                            <span className="text-[10px] uppercase font-bold text-orange-400 font-mono tracking-wider">
                                {language}
                            </span>
                            <button
                                onClick={() => handleCopyText(codeContent, snippetId)}
                                className="text-[10px] text-slate-300 hover:text-white px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 transition"
                            >
                                {copiedIndex === snippetId ? '✓ Tersalin!' : 'Salin Kode'}
                            </button>
                        </div>
                        <pre className="p-3.5 overflow-x-auto text-emerald-400 leading-relaxed max-h-96">
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
        <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col font-sans">
            {/* Top Navigation Bar */}
            <header className="sticky top-0 z-40 bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md px-4 py-3">
                <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
                    {/* Brand */}
                    <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-start">
                        <div className="flex items-center gap-2.5">
                            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-red-500 flex items-center justify-center shadow-lg shadow-orange-500/20 text-white font-black text-lg">
                                🤖
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h1 className="font-extrabold text-base tracking-tight text-white">
                                        FinTracks Performance Studio
                                    </h1>
                                    <span className="bg-orange-500/15 text-orange-400 border border-orange-500/30 text-[10px] font-semibold px-2 py-0.5 rounded-full">
                                        AI Copilot
                                    </span>
                                </div>
                                <p className="text-[11px] text-slate-400 hidden sm:block">
                                    Asisten Cerdas Gatling 3.15 & RabbitMQ Orchestration
                                </p>
                            </div>
                        </div>

                        {/* Mobile Status */}
                        <div className="sm:hidden flex items-center">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                targetPing.online
                                    ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                                    : 'bg-red-500/10 text-red-400 border-red-500/30'
                            }`}>
                                <span className={`h-1.5 w-1.5 rounded-full ${targetPing.online ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`}></span>
                                {targetPing.online ? 'Online' : 'Offline'}
                            </span>
                        </div>
                    </div>

                    {/* Navigation Tabs & Actions */}
                    <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
                        {/* Tab Switcher: Manual vs Copilot */}
                        <div className="bg-slate-950 p-1 rounded-xl border border-slate-800 flex items-center gap-1 shadow-inner">
                            <Link
                                to="/gatling"
                                className="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-850 transition flex items-center gap-1.5"
                                title="Buka Dashboard Manual Stress Test"
                            >
                                <span>⚡</span>
                                <span>Manual Test</span>
                            </Link>
                            <div className="px-3 py-1.5 text-xs font-bold rounded-lg bg-gradient-to-r from-orange-600 to-amber-600 text-white shadow-md shadow-orange-600/30 flex items-center gap-1.5">
                                <span>🤖</span>
                                <span>AI Copilot</span>
                                <span className="bg-white/20 text-white text-[9px] px-1.5 py-0.2 rounded-full font-mono">
                                    Gemini 3.1
                                </span>
                            </div>
                        </div>

                        {/* Target Ping Badge */}
                        <div className="hidden lg:flex items-center gap-2 bg-slate-950/80 border border-slate-800 px-3 py-1.5 rounded-xl text-xs">
                            <span className="text-slate-400 font-medium">Target:</span>
                            <span className="font-mono text-orange-400 font-semibold truncate max-w-[150px]" title={DEFAULT_TARGET_URL}>
                                {DEFAULT_TARGET_URL}
                            </span>
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                targetPing.online === true
                                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                    : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                            }`}>
                                <span className={`h-1.5 w-1.5 rounded-full ${targetPing.online ? 'bg-emerald-400 animate-ping' : 'bg-rose-400'}`}></span>
                                {targetPing.checking ? '...' : targetPing.online ? 'Online' : 'Offline'}
                            </span>
                        </div>

                        {/* Financial App & Logout */}
                        <Link
                            to="/dashboard"
                            className="hidden md:inline-flex items-center gap-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/80 px-3 py-1.5 rounded-xl text-xs font-semibold transition"
                        >
                            <span>💳</span>
                            <span>Financial</span>
                        </Link>
                        <button
                            onClick={logout}
                            className="bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-xl text-xs font-semibold transition"
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Workspace */}
            <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 flex flex-col lg:flex-row gap-6">
                {/* LEFT SIDEBAR: Capabilities, Presets & Controls */}
                <div className="lg:w-80 flex flex-col gap-4 shrink-0">
                    {/* Model Info Card */}
                    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur space-y-3">
                        <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
                            <div className="flex items-center gap-2">
                                <span className="text-xl">🧠</span>
                                <div>
                                    <h3 className="text-xs font-bold text-white">AI Engine Status</h3>
                                    <p className="text-[10px] text-slate-400">{activeModelName} + FastMCP</p>
                                </div>
                            </div>
                            <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[9px] font-bold px-2 py-0.5 rounded-full">
                                Ready
                            </span>
                        </div>

                        <div className="text-[11px] text-slate-300 space-y-1.5 leading-relaxed">
                            <p>
                                AI Copilot memiliki akses langsung ke mesin <strong>Gatling 3.15</strong> dan message broker <strong>RabbitMQ</strong> melalui protokol MCP (Model Context Protocol).
                            </p>
                        </div>

                        {/* Available MCP Tools list */}
                        <div className="pt-1">
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">
                                Akses Alat MCP Aktif:
                            </span>
                            <div className="flex flex-wrap gap-1.5">
                                <span className="text-[10px] bg-slate-950 text-orange-300 border border-slate-800 px-2 py-0.5 rounded-md font-mono">
                                    ⚡ Gatling Runner
                                </span>
                                <span className="text-[10px] bg-slate-950 text-blue-300 border border-slate-800 px-2 py-0.5 rounded-md font-mono">
                                    🐰 RabbitMQ AMQP
                                </span>
                                <span className="text-[10px] bg-slate-950 text-emerald-300 border border-slate-800 px-2 py-0.5 rounded-md font-mono">
                                    📄 HTML Reports
                                </span>
                                <span className="text-[10px] bg-slate-950 text-purple-300 border border-slate-800 px-2 py-0.5 rounded-md font-mono">
                                    📊 P95 Analyzer
                                </span>
                            </div>
                        </div>

                        {/* Quick switch to manual */}
                        <div className="pt-2 border-t border-slate-800">
                            <Link
                                to="/gatling"
                                className="w-full bg-slate-800/80 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold py-2 px-3 rounded-xl transition flex items-center justify-center gap-2"
                            >
                                <span>⚡</span>
                                <span>Buka Manual Test Console ↗</span>
                            </Link>
                        </div>
                    </div>

                    {/* Quick Preset Prompts by Category */}
                    <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur flex-1 flex flex-col">
                        <div className="flex items-center justify-between pb-2.5 border-b border-slate-800">
                            <span className="text-xs font-bold text-white flex items-center gap-1.5">
                                <span>💡</span> Contoh Prompt Cepat
                            </span>
                            <span className="text-[10px] text-slate-500">Klik untuk kirim</span>
                        </div>

                        <div className="mt-3 space-y-4 overflow-y-auto max-h-[360px] pr-1">
                            {promptCategories.map((cat, cIdx) => (
                                <div key={cIdx} className="space-y-1.5">
                                    <span className="text-[10px] font-semibold text-orange-400 tracking-wide block">
                                        {cat.title}
                                    </span>
                                    <div className="space-y-1.5">
                                        {cat.prompts.map((p, pIdx) => (
                                            <button
                                                key={pIdx}
                                                onClick={() => handleSendMessage(p)}
                                                disabled={isChatLoading}
                                                className="w-full text-left text-[11px] bg-slate-950/80 hover:bg-orange-600/15 hover:border-orange-500/40 text-slate-300 hover:text-orange-200 border border-slate-800 p-2 rounded-xl transition leading-snug group disabled:opacity-40"
                                            >
                                                <span className="text-orange-500 group-hover:text-orange-400 mr-1.5">›</span>
                                                {p}
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Clear Chat Button */}
                        {messages.length > 0 && (
                            <div className="mt-auto pt-3 border-t border-slate-800">
                                <button
                                    onClick={handleClearHistory}
                                    className="w-full text-[11px] text-slate-400 hover:text-red-400 bg-slate-950/60 hover:bg-red-500/10 border border-slate-800 hover:border-red-500/30 py-1.5 px-3 rounded-xl transition flex items-center justify-center gap-1.5"
                                >
                                    <span>🗑️</span>
                                    <span>Hapus Riwayat Chat</span>
                                </button>
                            </div>
                        )}
                    </div>
                </div>

                {/* RIGHT/CENTER: Dedicated Chat Workspace */}
                <div className="flex-1 bg-slate-900/80 border border-slate-800 rounded-2xl flex flex-col shadow-2xl backdrop-blur overflow-hidden h-[750px]">
                    {/* Chat Header Bar */}
                    <div className="p-3.5 bg-slate-850 border-b border-slate-800 flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                            <div className="h-8 w-8 rounded-lg bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-base">
                                💬
                            </div>
                            <div>
                                <h2 className="text-xs font-bold text-white flex items-center gap-1.5">
                                    FinTracks Gatling Performance Copilot
                                    <span className="bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-[9px] px-1.5 py-0.2 rounded font-mono">
                                        Online
                                    </span>
                                </h2>
                                <p className="text-[10px] text-slate-400">
                                    Tanya skrip Scala, instruksikan pengujian beban, atau analisis hasil laporan
                                </p>
                            </div>
                        </div>

                        <div className="flex items-center gap-2">
                            <button
                                onClick={fetchChatHistory}
                                className="text-xs text-slate-400 hover:text-white bg-slate-800 px-2.5 py-1 rounded-lg transition"
                                title="Muat ulang riwayat"
                            >
                                ↻ Refresh
                            </button>
                            {messages.length > 0 && (
                                <button
                                    onClick={handleClearHistory}
                                    className="text-xs text-slate-400 hover:text-red-400 bg-slate-800 px-2.5 py-1 rounded-lg transition"
                                    title="Bersihkan riwayat percakapan"
                                >
                                    Bersihkan
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Messages Area */}
                    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 text-xs bg-slate-950/40">
                        {isFetchingChat ? (
                            <div className="h-full flex items-center justify-center text-slate-500 text-xs">
                                <span className="animate-pulse">Memuat riwayat percakapan Copilot...</span>
                            </div>
                        ) : messages.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-500 space-y-4 max-w-lg mx-auto">
                                <div className="h-14 w-14 rounded-2xl bg-gradient-to-tr from-orange-600 to-amber-500 flex items-center justify-center text-2xl text-white shadow-xl shadow-orange-600/20">
                                    ⚡
                                </div>
                                <div>
                                    <h3 className="font-bold text-sm text-white">Selamat Datang di Gatling AI Copilot</h3>
                                    <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                                        Gunakan bahasa alami untuk mengotomasi pengujian performa FinTracks, membuat skrip Scala Gatling, atau menganalisis bottleneck sistem IIS & RabbitMQ.
                                    </p>
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full text-left pt-2">
                                    <button
                                        onClick={() => handleSendMessage(`Jalankan stress test ke ${DEFAULT_TARGET_URL} dengan 150 VU selama 20 detik`)}
                                        className="bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-orange-500/40 p-3 rounded-xl transition text-xs group"
                                    >
                                        <div className="font-semibold text-orange-400 flex items-center gap-1 mb-1">
                                            <span>🚀</span> Stress Test IIS
                                        </div>
                                        <p className="text-[11px] text-slate-400">
                                            Uji beban gateway ASP.NET / IIS dengan 150 VU
                                        </p>
                                    </button>

                                    <button
                                        onClick={() => handleSendMessage('Buatkan skrip Gatling untuk uji antrean RabbitMQ fintracks.orders')}
                                        className="bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-orange-500/40 p-3 rounded-xl transition text-xs group"
                                    >
                                        <div className="font-semibold text-amber-400 flex items-center gap-1 mb-1">
                                            <span>🐰</span> Skrip RabbitMQ
                                        </div>
                                        <p className="text-[11px] text-slate-400">
                                            Buat skrip Scala AMQP untuk antrean order
                                        </p>
                                    </button>
                                </div>
                            </div>
                        ) : (
                            messages.map((m, i) => {
                                const isUser = m.role === 'user';
                                return (
                                    <div key={i} className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
                                        {!isUser && (
                                            <div className="h-7 w-7 rounded-lg bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-xs shrink-0 mt-1">
                                                🤖
                                            </div>
                                        )}
                                        <div className={`max-w-[85%] md:max-w-[75%] space-y-1`}>
                                            <div
                                                className={`p-4 rounded-2xl shadow-md ${
                                                    isUser
                                                        ? 'bg-gradient-to-r from-orange-600 to-amber-600 text-white rounded-tr-none'
                                                        : 'bg-slate-900 text-slate-200 border border-slate-800 rounded-tl-none font-sans text-xs leading-relaxed'
                                                }`}
                                            >
                                                {renderFormattedMessage(m.text, i)}
                                            </div>
                                            <div className={`text-[10px] text-slate-500 px-1 flex items-center gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
                                                <span>{isUser ? 'Anda' : 'Gatling Copilot'}</span>
                                                {m.created_at && (
                                                    <span>• {new Date(m.created_at).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</span>
                                                )}
                                            </div>
                                        </div>
                                        {isUser && (
                                            <div className="h-7 w-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center text-xs shrink-0 mt-1 text-slate-300">
                                                👤
                                            </div>
                                        )}
                                    </div>
                                );
                            })
                        )}

                        {/* Active Execution Banner with Live Timer */}
                        {isChatLoading && (
                            <div className="flex gap-3">
                                <div className="h-7 w-7 rounded-lg bg-orange-600/20 border border-orange-500/30 flex items-center justify-center text-xs shrink-0 mt-1">
                                    🤖
                                </div>
                                <div className="max-w-[80%] bg-slate-900 border border-orange-500/30 rounded-2xl rounded-tl-none p-4 shadow-xl space-y-2">
                                    <div className="flex items-center gap-2 text-orange-400 font-semibold text-xs">
                                        <span className="h-2 w-2 bg-orange-400 rounded-full animate-ping"></span>
                                        <span>
                                            {chatElapsedSeconds > 0
                                                ? `Mesin Gatling sedang mengeksekusi pengujian (${chatElapsedSeconds} detik berjalan)...`
                                                : 'AI sedang menginisialisasi skrip pengujian Gatling...'}
                                        </span>
                                    </div>
                                    <p className="text-[11px] text-slate-400 leading-relaxed">
                                        Asisten menunggu hingga durasi uji beban selesai sepenuhnya dieksekusi oleh mesin Gatling sebelum menyusun dan mengembalikan laporan metrik akurat.
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
                        className="p-3.5 bg-slate-900 border-t border-slate-800 flex gap-2.5 items-center"
                    >
                        <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            disabled={isChatLoading}
                            placeholder="Ketik instruksi pengujian (misal: 'Stress test 250 VU selama 30 detik')..."
                            className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition"
                        />
                        <button
                            type="submit"
                            disabled={isChatLoading || !chatInput.trim()}
                            className="bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white px-5 py-2.5 rounded-xl text-xs font-bold shadow-lg shadow-orange-600/20 disabled:opacity-40 transition flex items-center gap-1.5 cursor-pointer"
                        >
                            <span>Kirim</span>
                            <span>➤</span>
                        </button>
                    </form>
                </div>
            </main>
        </div>
    );
};

export default GatlingCopilot;
