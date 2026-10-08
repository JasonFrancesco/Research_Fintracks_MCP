import React, { useState, useEffect, useRef, useContext } from 'react';
import { Link } from 'react-router-dom';
import { AuthContext } from '../context/AuthContext';
import api from '../services/api';
import GatlingChatWidget from '../components/GatlingChatWidget';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell
} from 'recharts';

const GatlingDashboard = () => {
    const { logout } = useContext(AuthContext);

    // Sub-tab untuk Laporan: 'metrics', 'gatlingHtml', 'script', 'raw'
    const [reportSubTab, setReportSubTab] = useState('metrics');

    // Target URL & Configuration
    const DEFAULT_TARGET_URL = 'https://192.168.18.57:44396/';
    const [targetEndpoint, setTargetEndpoint] = useState(DEFAULT_TARGET_URL);
    const [simulationName, setSimulationName] = useState('IISGatewayStressTest');
    const [virtualUsers, setVirtualUsers] = useState(150);
    const [durationSeconds, setDurationSeconds] = useState(25);
    const [isTriggeringTest, setIsTriggeringTest] = useState(false);

    // Authentication / Login Options State
    const [useLoginAuth, setUseLoginAuth] = useState(false);
    const [loginUsername, setLoginUsername] = useState('manager_mark');
    const [loginPassword, setLoginPassword] = useState('Admin123');
    const [loginCaptcha, setLoginCaptcha] = useState('abc');

    // Live Target Ping State
    const [targetPing, setTargetPing] = useState({
        checking: false,
        online: null,
        statusCode: null,
        latencyMs: null,
        server: null,
        message: 'Belum dicek'
    });

    // Test Runs State
    const [testRuns, setTestRuns] = useState([]);
    const [loadingRuns, setLoadingRuns] = useState(true);
    const [selectedRun, setSelectedRun] = useState(null);
    const [copiedScript, setCopiedScript] = useState(false);

    // Live Execution Progress State
    const [testProgress, setTestProgress] = useState(null);
    const [showTerminalLog, setShowTerminalLog] = useState(false);
    const progressTimerRef = useRef(null);
    const progressCardRef = useRef(null);
    const terminalEndRef = useRef(null);

    // Cek Ping Target
    const checkTargetPing = async (urlToCheck = targetEndpoint) => {
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

    // Fetch History Test Runs
    const fetchTestRuns = async () => {
        try {
            setLoadingRuns(true);
            const res = await api.get('/gatling/history?limit=100');
            if (res.data && Array.isArray(res.data)) {
                setTestRuns(res.data);
                if (res.data.length > 0 && !selectedRun) {
                    setSelectedRun(res.data[0]);
                }
                return res.data;
            }
            return [];
        } catch (err) {
            console.error('Gagal memuat riwayat test:', err);
            return [];
        } finally {
            setLoadingRuns(false);
        }
    };

    useEffect(() => {
        checkTargetPing(DEFAULT_TARGET_URL);
        fetchTestRuns();
        return () => {
            if (progressTimerRef.current) clearInterval(progressTimerRef.current);
        };
    }, []);

    useEffect(() => {
        if (showTerminalLog && terminalEndRef.current) {
            terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [testProgress?.terminalLog, showTerminalLog]);

    // Helper: Finalisasi Progress saat pengujian selesai
    const finishTestProgress = async (resData, totalDuration, targetVUs, reqs) => {
        if (progressTimerRef.current) clearInterval(progressTimerRef.current);
        await fetchTestRuns();
        if (resData) {
            setSelectedRun(resData);
        }
        setReportSubTab('gatlingHtml');
        setIsTriggeringTest(false);

        setTestProgress(prev => {
            if (!prev) return null;
            return {
                ...prev,
                percent: 100,
                isCompleted: true,
                activeVUs: targetVUs,
                requestsSent: resData?.total_requests || reqs,
                phase: 'Pengujian Selesai (100%)',
                phaseDesc: 'Laporan Resmi Gatling HTML 3.15+ berhasil digenerate & siap dianalisis!',
                result: resData
            };
        });
    };

    // Helper: Selesaikan Cepat (Fast Finish)
    const handleFastFinish = async () => {
        if (progressTimerRef.current) clearInterval(progressTimerRef.current);
        try {
            const runs = await api.get('/gatling/history?limit=1');
            const latestRun = runs.data && runs.data.length > 0 ? runs.data[0] : null;
            await finishTestProgress(latestRun, durationSeconds, virtualUsers, virtualUsers * 25);
        } catch {
            setIsTriggeringTest(false);
        }
    };

    // Handler: Trigger Manual Stress Test dari Console Form dengan Animasi Progress
    const handleTriggerTest = async (e) => {
        if (e) e.preventDefault();
        if (isTriggeringTest) return;

        setIsTriggeringTest(true);

        const totalDuration = parseInt(durationSeconds, 10) || 30;
        const targetVUs = parseInt(virtualUsers, 10) || 100;
        const simName = simulationName.trim() || 'CustomStressTest';
        const targetUrl = targetEndpoint.trim();

        // 1. Inisialisasi State Progress & Log Awal
        const authLogLine = useLoginAuth
            ? `\n[${new Date().toLocaleTimeString()}] Mode Autentikasi: OIDC Identity Login (${loginUsername})`
            : '';
        const initialLog = `[${new Date().toLocaleTimeString()}] Memulai Gatling 3.15.1 Stress Test Engine...
[${new Date().toLocaleTimeString()}] Simulasi: ${simName}
[${new Date().toLocaleTimeString()}] Target: ${targetUrl}${authLogLine}
[${new Date().toLocaleTimeString()}] Konfigurasi: ${targetVUs} Virtual Users, Durasi ${totalDuration}s
[${new Date().toLocaleTimeString()}] Menginisialisasi thread pool & socket pooling...`;

        setTestProgress({
            active: true,
            isCompleted: false,
            percent: 6,
            phase: 'Tahap 1: Inisialisasi & Verifikasi Target',
            phaseDesc: useLoginAuth ? `Memvalidasi OIDC Identity Login (${loginUsername})...` : `Memvalidasi koneksi ke ${targetUrl}...`,
            elapsedSeconds: 0,
            totalSeconds: totalDuration,
            activeVUs: 5,
            targetVUs: targetVUs,
            requestsSent: 0,
            throughput: 0,
            simulationName: simName,
            targetEndpoint: targetUrl,
            terminalLog: initialLog,
            result: null,
            error: null
        });

        // Scroll perlahan ke monitor progress
        setTimeout(() => {
            progressCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }, 150);

        // 2. Pemicuan Backend API
        const payload = {
            simulation_name: simName,
            target_queue: targetUrl,
            virtual_users: targetVUs,
            duration_seconds: totalDuration,
            scenario_description: useLoginAuth
                ? `Login OIDC test (${loginUsername}) ke ${targetUrl} dengan ${targetVUs} VUs selama ${totalDuration}s`
                : `Stress test ke ${targetUrl} dengan ${targetVUs} VUs selama ${totalDuration}s`,
            login_username: useLoginAuth ? loginUsername : undefined,
            login_password: useLoginAuth ? loginPassword : undefined,
            login_captcha: useLoginAuth ? loginCaptcha : undefined
        };

        let backendResult = null;

        const apiPromise = api.post('/gatling/trigger', payload)
            .then(res => {
                backendResult = res.data;
                return res.data;
            })
            .catch(err => {
                throw err;
            });

        // 3. Durasi animasi riil 1:1 mengikuti durasi pengujian Gatling
        const animTotalMs = totalDuration * 1000;
        const intervalMs = 250;
        const totalSteps = Math.max(1, animTotalMs / intervalMs);
        let currentStep = 0;

        if (progressTimerRef.current) clearInterval(progressTimerRef.current);

        progressTimerRef.current = setInterval(async () => {
            currentStep++;
            const progressRatio = Math.min(1, currentStep / totalSteps);
            const currentPercent = Math.min(99, Math.round(progressRatio * 100));
            const elapsed = Math.min(totalDuration, Math.round((currentStep * intervalMs) / 1000));

            let vus = 0;
            let phase = '';
            let phaseDesc = '';

            if (progressRatio < 0.25) {
                phase = 'Tahap 1: Inisialisasi & Probe Endpoint';
                phaseDesc = `Memvalidasi handshake TLS & socket ke ${targetUrl}...`;
                vus = Math.round(targetVUs * (progressRatio / 0.25) * 0.4);
            } else if (progressRatio < 0.55) {
                phase = 'Tahap 2: Ramp-up Virtual Users';
                phaseDesc = `Menaikkan koneksi bersamaan ke ${targetVUs} Virtual Users...`;
                vus = Math.round(targetVUs * (0.4 + (progressRatio - 0.25) / 0.30 * 0.6));
            } else if (progressRatio < 0.85) {
                phase = 'Tahap 3: Sustained Stress Load Injection';
                phaseDesc = `Injeksi beban penuh secara berkelanjutan & sampling latency...`;
                vus = targetVUs;
            } else {
                phase = 'Tahap 4: Agregasi Statistik & Generate Report';
                phaseDesc = `Merekam simulation.log & menyusun Laporan Resmi Gatling HTML...`;
                vus = targetVUs;
            }

            const estRps = Math.max(10, Math.round(targetVUs * 1.6));
            const reqs = Math.round(estRps * elapsed);
            const currentThroughput = elapsed > 0 ? Math.round(reqs / elapsed) : estRps;

            const timeStr = new Date().toLocaleTimeString();
            let newLogLine = '';
            if (currentStep % 4 === 0) {
                newLogLine = `\n[${timeStr}] [INFO] Elapsed: ${elapsed}s/${totalDuration}s | Active VUs: ${vus}/${targetVUs} | Requests: ${reqs.toLocaleString()} | Throughput: ${currentThroughput} req/s`;
            }

            setTestProgress(prev => {
                if (!prev || prev.isCompleted) return prev;
                return {
                    ...prev,
                    percent: currentPercent,
                    phase,
                    phaseDesc,
                    elapsedSeconds: elapsed,
                    activeVUs: vus,
                    requestsSent: reqs,
                    throughput: currentThroughput,
                    terminalLog: newLogLine ? prev.terminalLog + newLogLine : prev.terminalLog
                };
            });

            // Selesai mencapai ujung durasi penuh
            if (currentStep >= totalSteps) {
                clearInterval(progressTimerRef.current);
                try {
                    const resData = backendResult || await apiPromise;
                    await finishTestProgress(resData, totalDuration, targetVUs, reqs);
                } catch (err) {
                    setTestProgress(prev => ({
                        ...prev,
                        error: err.response?.data?.detail || err.message,
                        phase: 'Pengujian Gagal',
                        phaseDesc: 'Terjadi kendala saat memicu pengujian Gatling.'
                    }));
                    setIsTriggeringTest(false);
                }
            }
        }, intervalMs);
    };

    // Handler: Hapus Catatan Test
    const handleDeleteRun = async (id, e) => {
        e.stopPropagation();
        if (!window.confirm(`Hapus catatan test run #${id}?`)) return;
        try {
            await api.delete(`/gatling/test/${id}`);
            setTestRuns(prev => prev.filter(r => r.id !== id));
            if (selectedRun && selectedRun.id === id) {
                setSelectedRun(testRuns.find(r => r.id !== id) || null);
            }
        } catch (err) {
            alert('Gagal menghapus test run.');
        }
    };

    // Salin Skrip ke Clipboard
    const handleCopyScript = (script) => {
        if (!script) return;
        navigator.clipboard.writeText(script);
        setCopiedScript(true);
        setTimeout(() => setCopiedScript(false), 2000);
    };

    // Download Skrip sebagai file .scala
    const handleDownloadScript = (run) => {
        if (!run || !run.generated_script) return;
        const blob = new Blob([run.generated_script], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${run.simulation_name || 'GatlingSimulation'}.scala`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    // Parsing Detail JSON Report
    const parsedSummary = selectedRun && selectedRun.report_summary
        ? (() => {
            try {
                return JSON.parse(selectedRun.report_summary);
            } catch {
                return null;
            }
        })()
        : null;

    // Data Grafik Latensi untuk Recharts
    const latencyChartData = selectedRun && parsedSummary?.response_times_ms
        ? [
            { name: 'Min', latency: parsedSummary.response_times_ms.min || 0, fill: '#10b981' },
            { name: 'Mean', latency: selectedRun.mean_response_time || 0, fill: '#3b82f6' },
            { name: 'P95', latency: selectedRun.p95_response_time || 0, fill: '#8b5cf6' },
            { name: 'P99', latency: selectedRun.p99_response_time || 0, fill: '#f59e0b' },
            { name: 'Max', latency: parsedSummary.response_times_ms.max || 0, fill: '#ef4444' }
        ]
        : selectedRun
            ? [
                { name: 'Mean', latency: selectedRun.mean_response_time || 0, fill: '#3b82f6' },
                { name: 'P95', latency: selectedRun.p95_response_time || 0, fill: '#8b5cf6' },
                { name: 'P99', latency: selectedRun.p99_response_time || 0, fill: '#f59e0b' }
            ]
            : [];

    // KPI Metrics Agregat
    const totalRuns = testRuns.length;
    const avgP95 = totalRuns > 0
        ? (testRuns.reduce((sum, r) => sum + (parseFloat(r.p95_response_time) || 0), 0) / totalRuns).toFixed(1)
        : 0;
    const totalRequestsCount = testRuns.reduce((sum, r) => sum + (parseInt(r.total_requests, 10) || 0), 0);
    const avgErrorRate = totalRuns > 0
        ? (testRuns.reduce((sum, r) => sum + (parseFloat(r.error_rate) || 0), 0) / totalRuns).toFixed(2)
        : '0.00';

    return (
        <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100 flex flex-col font-sans">
            {/* Top Navigation Bar */}
            <header className="sticky top-0 z-40 bg-slate-900/90 border-b border-slate-800/80 backdrop-blur-md px-4 py-3">
                <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
                    {/* Brand */}
                    <div className="flex items-center gap-3 w-full sm:w-auto justify-between sm:justify-start">
                        <div className="flex items-center gap-2.5">
                            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-600 to-red-500 flex items-center justify-center shadow-lg shadow-orange-500/20 text-white font-black text-lg">
                                ⚡
                            </div>
                            <div>
                                <div className="flex items-center gap-2">
                                    <h1 className="font-extrabold text-base tracking-tight text-white">
                                        Gatling AI Performance Studio
                                    </h1>
                                    <span className="bg-orange-500/15 text-orange-400 border border-orange-500/30 text-[10px] font-semibold px-2 py-0.5 rounded-full">
                                        Manual Console
                                    </span>
                                </div>
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
                            <div className="px-3 py-1.5 text-xs font-bold rounded-lg bg-orange-600 text-white shadow-md shadow-orange-600/30 flex items-center gap-1.5">
                                <span>⚡</span>
                                <span>Manual Test</span>
                            </div>
                            <Link
                                to="/gatling/copilot"
                                className="px-3 py-1.5 text-xs font-semibold rounded-lg text-slate-400 hover:text-white hover:bg-slate-850 transition flex items-center gap-1.5 group"
                                title="Buka Halaman Baru AI Copilot"
                            >
                                <span>🤖</span>
                                <span>AI Copilot</span>
                                <span className="bg-orange-500/20 text-orange-400 group-hover:text-orange-300 text-[9px] px-1.5 py-0.2 rounded-full font-mono border border-orange-500/30">
                                    Baru
                                </span>
                            </Link>
                        </div>

                        {/* Target Ping Badge */}
                        <div className="hidden lg:flex items-center gap-2 bg-slate-950/80 border border-slate-800 px-3 py-1.5 rounded-xl text-xs">
                            <span className="text-slate-400 font-medium">Target:</span>
                            <span className="font-mono text-orange-400 font-semibold truncate max-w-[150px]" title={targetEndpoint}>
                                {targetEndpoint}
                            </span>
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                                targetPing.online === true
                                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                    : 'bg-rose-500/15 text-rose-400 border-rose-500/30'
                            }`}>
                                <span className={`h-1.5 w-1.5 rounded-full ${targetPing.online ? 'bg-emerald-400 animate-ping' : 'bg-rose-400'}`}></span>
                                {targetPing.checking ? '...' : targetPing.online ? 'Online' : 'Offline'}
                            </span>
                            <button
                                onClick={() => checkTargetPing(targetEndpoint)}
                                disabled={targetPing.checking}
                                className="text-slate-400 hover:text-white text-xs p-1 transition"
                                title="Cek status koneksi ulang"
                            >
                                ↻
                            </button>
                        </div>

                        {/* Logout */}
                        <button
                            onClick={logout}
                            className="bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 px-3 py-1.5 rounded-xl text-xs font-semibold transition"
                        >
                            Logout
                        </button>
                    </div>
                </div>
            </header>

            {/* Main Content Area */}
            <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 flex flex-col gap-6">
                {/* Clean Banner: Announcement of Separate AI Copilot */}
                <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-slate-900 border border-slate-800/80 rounded-2xl p-4 md:p-5 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2">
                            <span className="text-orange-400 font-bold text-sm">
                                Gatling Manual Stress Testing Studio
                            </span>
                        </div>
                    </div>
                    <Link
                        to="/gatling/copilot"
                        className="self-start md:self-auto shrink-0 bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500 hover:from-orange-500 hover:to-amber-500 text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-lg shadow-orange-600/20 transition flex items-center gap-2"
                    >
                        <span>🤖 Buka Halaman AI Copilot</span>
                        <span>↗</span>
                    </Link>
                </div>

                {/* Metrik Overview Stat Cards */}
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
                    <div title="Total seluruh pengujian beban yang telah Anda lakukan dan terekam di database." className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur relative overflow-hidden group hover:border-orange-500/40 transition cursor-help">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Test Runs</span>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl md:text-3xl font-black text-white">{totalRuns}</span>
                        </div>
                    </div>

                    <div title="Rata-rata waktu respons untuk 95% permintaan (Persentil ke-95) di seluruh test." className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur relative overflow-hidden group hover:border-blue-500/40 transition cursor-help">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Avg Latency (P95)</span>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl md:text-3xl font-black text-blue-400">{avgP95}</span>
                            <span className="text-xs font-semibold text-slate-400">ms</span>
                        </div>
                    </div>

                    <div title="Akumulasi total permintaan (requests) yang dikirim selama seluruh pengujian." className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur relative overflow-hidden group hover:border-purple-500/40 transition cursor-help">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Total Throughput</span>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className="text-2xl md:text-3xl font-black text-purple-400">
                                {totalRequestsCount.toLocaleString('id-ID')}
                            </span>
                        </div>
                    </div>

                    <div title="Rata-rata persentase kegagalan (HTTP 4xx/5xx atau timeout) pada seluruh test." className="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 shadow-xl backdrop-blur relative overflow-hidden group hover:border-emerald-500/40 transition cursor-help">
                        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Avg Error Rate</span>
                        <div className="mt-2 flex items-baseline gap-2">
                            <span className={`text-2xl md:text-3xl font-black ${parseFloat(avgErrorRate) > 2 ? 'text-rose-400' : 'text-emerald-400'}`}>
                                {avgErrorRate}%
                            </span>
                        </div>
                    </div>
                </div>

                {/* 1. Quick Stress Test Launch Console (Clean & Full-Width 2-Column Grid) */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 md:p-6 shadow-2xl backdrop-blur">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
                        <div>
                            <h2 className="text-base font-bold text-white flex items-center gap-2">
                                Interactive Gatling Stress Test Console
                            </h2>
                        </div>
                        <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-400">Target Type:</span>
                            <span className={`text-[11px] font-bold px-2.5 py-0.5 rounded-full border ${
                                targetEndpoint.startsWith('http')
                                    ? 'bg-blue-500/10 text-blue-400 border-blue-500/30'
                                    : 'bg-orange-500/10 text-orange-400 border-orange-500/30'
                            }`}>
                                {targetEndpoint.startsWith('http') ? 'HTTPS Web API' : 'RabbitMQ AMQP'}
                            </span>
                        </div>
                    </div>

                    <form onSubmit={handleTriggerTest} className="mt-5 space-y-5">
                        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
                            {/* Column 1: Target Endpoint & Presets */}
                            <div className="lg:col-span-6 space-y-3">
                                <div className="flex items-center justify-between">
                                    <label className="text-xs font-semibold text-slate-200">
                                        Target URL / Antrean RabbitMQ:
                                    </label>
                                    <button
                                        type="button"
                                        onClick={() => checkTargetPing(targetEndpoint)}
                                        className="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1 font-medium transition"
                                    >
                                        <span>⚡</span> Cek Koneksi Endpoint
                                    </button>
                                </div>

                                <input
                                    type="text"
                                    value={targetEndpoint}
                                    onChange={(e) => setTargetEndpoint(e.target.value)}
                                    placeholder="https://192.168.18.57:44396/ atau fintracks.orders"
                                    className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-xs font-mono text-orange-300 placeholder-slate-600 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500 transition"
                                    required
                                />

                                {/* Preset Chips */}
                                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                                    <span className="text-[11px] text-slate-500">Preset:</span>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setTargetEndpoint(DEFAULT_TARGET_URL);
                                            setSimulationName('MTFEProcLoginSimulation');
                                            setUseLoginAuth(true);
                                            setLoginUsername('manager_mark');
                                            setLoginPassword('Admin123');
                                            setLoginCaptcha('abc');
                                            checkTargetPing(DEFAULT_TARGET_URL);
                                        }}
                                        className={`text-[11px] border px-2.5 py-1 rounded-lg transition ${useLoginAuth ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/40 font-semibold' : 'bg-slate-800 hover:bg-slate-750 text-emerald-400 border-emerald-500/30'}`}
                                    >
                                        Login MTF ({loginUsername})
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setTargetEndpoint(DEFAULT_TARGET_URL);
                                            setSimulationName('IISGatewayStressTest');
                                            setUseLoginAuth(false);
                                            checkTargetPing(DEFAULT_TARGET_URL);
                                        }}
                                        className="text-[11px] bg-slate-800 hover:bg-slate-750 text-orange-300 border border-slate-700 px-2.5 py-1 rounded-lg transition"
                                    >
                                        IIS Raw ({DEFAULT_TARGET_URL})
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setTargetEndpoint('fintracks.orders');
                                            setSimulationName('OrderQueueLoadTest');
                                            setUseLoginAuth(false);
                                        }}
                                        className="text-[11px] bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 px-2.5 py-1 rounded-lg transition"
                                    >
                                        Queue: fintracks.orders
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => {
                                            setTargetEndpoint('fintracks.transactions');
                                            setSimulationName('TransactionStreamTest');
                                            setUseLoginAuth(false);
                                        }}
                                        className="text-[11px] bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 px-2.5 py-1 rounded-lg transition"
                                    >
                                        Queue: fintracks.transactions
                                    </button>
                                </div>

                                {/* Ping Indicator Callout */}
                                {targetEndpoint.startsWith('http') && (
                                    <div className={`p-3 rounded-xl border text-xs flex items-center justify-between ${
                                        targetPing.online === true
                                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                                            : targetPing.online === false
                                                ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                                                : 'bg-slate-950 border-slate-800 text-slate-400'
                                    }`}>
                                        <div className="flex items-center gap-2.5">
                                            <span className={`h-2.5 w-2.5 rounded-full ${targetPing.online ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`}></span>
                                            <span className="font-medium">
                                                {targetPing.checking ? 'Sedang memeriksa konektivitas...' : targetPing.message}
                                            </span>
                                        </div>
                                        {targetPing.server && (
                                            <span className="text-[11px] font-mono text-slate-400">
                                                Server: {targetPing.server}
                                            </span>
                                        )}
                                    </div>
                                )}

                                {/* Opsi Login / Autentikasi e-Procurement IdentityServer3 */}
                                {targetEndpoint.startsWith('http') && (
                                    <div className={`rounded-xl border transition p-3.5 space-y-3 ${useLoginAuth ? 'bg-slate-950/90 border-emerald-500/40 shadow-inner' : 'bg-slate-950/40 border-slate-800'}`}>
                                        <div className="flex items-center justify-between">
                                            <label className="flex items-center gap-2.5 cursor-pointer select-none">
                                                <input
                                                    type="checkbox"
                                                    checked={useLoginAuth}
                                                    onChange={(e) => {
                                                        const checked = e.target.checked;
                                                        setUseLoginAuth(checked);
                                                        if (checked && !simulationName.includes('Login')) {
                                                            setSimulationName('MTFEProcLoginSimulation');
                                                        }
                                                    }}
                                                    className="accent-emerald-500 h-4 w-4 rounded cursor-pointer"
                                                />
                                                <span className="text-xs font-bold text-white flex items-center gap-1.5">
                                                    <span>🔐</span>
                                                    <span>Skenario Login Terotentikasi (OIDC Identity)</span>
                                                </span>
                                            </label>
                                            <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${useLoginAuth ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40' : 'bg-slate-800 text-slate-400 border-slate-700'}`}>
                                                {useLoginAuth ? 'Aktif' : 'Non-Aktif'}
                                            </span>
                                        </div>

                                        {useLoginAuth && (
                                            <div className="space-y-3 pt-2 border-t border-slate-800/80">
                                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                                                    <div>
                                                        <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                                                            Login ID:
                                                        </label>
                                                        <input
                                                            type="text"
                                                            value={loginUsername}
                                                            onChange={(e) => setLoginUsername(e.target.value)}
                                                            placeholder="manager_mark"
                                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-emerald-300 font-mono focus:outline-none focus:border-emerald-500 transition"
                                                            required={useLoginAuth}
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                                                            Password:
                                                        </label>
                                                        <input
                                                            type="password"
                                                            value={loginPassword}
                                                            onChange={(e) => setLoginPassword(e.target.value)}
                                                            placeholder="Admin123"
                                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-emerald-500 transition"
                                                            required={useLoginAuth}
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-[11px] font-semibold text-slate-300 block mb-1">
                                                            Captcha:
                                                        </label>
                                                        <input
                                                            type="text"
                                                            value={loginCaptcha}
                                                            onChange={(e) => setLoginCaptcha(e.target.value)}
                                                            placeholder="abc"
                                                            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-amber-300 font-mono focus:outline-none focus:border-emerald-500 transition"
                                                            required={useLoginAuth}
                                                        />
                                                    </div>
                                                </div>
                                                <div className="text-[10px] text-slate-400 leading-relaxed bg-emerald-950/20 p-2.5 rounded-lg border border-emerald-500/20 flex items-start gap-2">
                                                    <span className="text-emerald-400 text-sm leading-none">💡</span>
                                                    <span>
                                                        Otomatis mengekstrak <strong>idsrv.xsrf</strong> CSRF token &amp; Captcha Key GUID, menyusun format username komposit <strong>{loginUsername}#{loginCaptcha}#[guid]</strong>, dan memvalidasi sesi cookie <code className="text-emerald-300 font-mono">.AspNet.Cookies</code>.
                                                    </span>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Column 2: Parameters Grid */}
                            <div className="lg:col-span-6 space-y-4">
                                <div>
                                    <label className="text-xs font-semibold text-slate-200 block mb-1.5">
                                        Nama Simulasi Gatling:
                                    </label>
                                    <input
                                        type="text"
                                        value={simulationName}
                                        onChange={(e) => setSimulationName(e.target.value)}
                                        placeholder="Nama Simulasi (misal: IISGatewayStressTest)"
                                        className="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-2 text-xs text-white focus:outline-none focus:border-orange-500 transition font-mono"
                                    />
                                </div>

                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                    {/* Virtual Users Slider */}
                                    <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <label className="text-xs font-semibold text-slate-300">
                                                Virtual Users (VU):
                                            </label>
                                            <span className="text-xs font-mono font-bold text-orange-400 bg-orange-500/10 px-2 py-0.5 rounded border border-orange-500/20">
                                                {virtualUsers} VUs
                                            </span>
                                        </div>
                                        <input
                                            type="range"
                                            min="20"
                                            max="1000"
                                            step="10"
                                            value={virtualUsers}
                                            onChange={(e) => setVirtualUsers(Number(e.target.value))}
                                            className="w-full accent-orange-500 cursor-pointer"
                                        />
                                        <div className="flex gap-1 pt-1">
                                            {[50, 150, 300, 500].map(v => (
                                                <button
                                                    key={v}
                                                    type="button"
                                                    onClick={() => setVirtualUsers(v)}
                                                    className={`flex-1 text-[10px] py-0.5 rounded border transition ${virtualUsers === v ? 'bg-orange-600 text-white border-orange-500' : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-white'}`}
                                                >
                                                    {v}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    {/* Duration Slider */}
                                    <div className="bg-slate-950/60 p-3.5 rounded-xl border border-slate-800 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <label className="text-xs font-semibold text-slate-300">
                                                Durasi Pengujian:
                                            </label>
                                            <span className="text-xs font-mono font-bold text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/20">
                                                {durationSeconds} Detik
                                            </span>
                                        </div>
                                        <input
                                            type="range"
                                            min="10"
                                            max="120"
                                            step="5"
                                            value={durationSeconds}
                                            onChange={(e) => setDurationSeconds(Number(e.target.value))}
                                            className="w-full accent-blue-500 cursor-pointer"
                                        />
                                        <div className="flex gap-1 pt-1">
                                            {[10, 25, 60, 120].map(d => (
                                                <button
                                                    key={d}
                                                    type="button"
                                                    onClick={() => setDurationSeconds(d)}
                                                    className={`flex-1 text-[10px] py-0.5 rounded border transition ${durationSeconds === d ? 'bg-blue-600 text-white border-blue-500' : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-white'}`}
                                                >
                                                    {d}s
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Trigger Action Bar */}
                        <div className="pt-2 flex items-center justify-between border-t border-slate-800">
                            <span className="text-xs text-slate-400 hidden sm:inline">
                                Mesin Gatling akan menjalankan simulasi <strong>{simulationName}</strong> dengan <strong>{virtualUsers} VUs</strong> selama <strong>{durationSeconds} detik</strong>.
                            </span>
                            <button
                                type="submit"
                                disabled={isTriggeringTest}
                                className="w-full sm:w-auto bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500 hover:from-orange-500 hover:to-amber-500 text-white font-bold px-7 py-3 rounded-xl text-xs shadow-xl shadow-orange-600/25 flex items-center justify-center gap-2 transition disabled:opacity-75 cursor-pointer ml-auto"
                            >
                                {isTriggeringTest ? (
                                    <>
                                        <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                        <span>Simulasi Gatling Berjalan ({testProgress?.percent || 0}%)...</span>
                                    </>
                                ) : (
                                    <>
                                        <span>⚡</span>
                                        <span>Jalankan Stress Test Sekarang</span>
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                </div>

                {/* --- GATLING LIVE STRESS TEST PROGRESS MONITOR --- */}
                {testProgress && (
                    <div
                        ref={progressCardRef}
                        className={`rounded-2xl p-5 md:p-6 shadow-2xl backdrop-blur relative overflow-hidden transition-all duration-500 border ${
                            testProgress.isCompleted
                                ? 'bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border-emerald-500/50 shadow-emerald-950/40'
                                : 'bg-gradient-to-b from-slate-900 via-slate-950 to-slate-900 border-orange-500/50 shadow-orange-950/40'
                        }`}
                    >
                        {/* Animated Top Glow Strip */}
                        <div
                            className={`absolute top-0 left-0 right-0 h-1 transition-all duration-500 ${
                                testProgress.isCompleted
                                    ? 'bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-500 animate-pulse'
                                    : 'bg-gradient-to-r from-orange-500 via-amber-400 to-orange-500 animate-pulse'
                            }`}
                        />

                        {/* Header Bar Monitor */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
                            <div className="flex items-center gap-3">
                                {testProgress.isCompleted ? (
                                    <div className="h-9 w-9 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-lg shadow-lg shadow-emerald-500/10">
                                        ✅
                                    </div>
                                ) : (
                                    <div className="h-9 w-9 rounded-xl bg-orange-500/20 border border-orange-500/40 flex items-center justify-center text-lg relative shadow-lg shadow-orange-500/10">
                                        <span className="animate-spin text-base">⚡</span>
                                        <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-red-500 animate-ping" />
                                        <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-red-500" />
                                    </div>
                                )}
                                <div>
                                    <div className="flex items-center gap-2">
                                        <span className={`text-xs font-bold uppercase tracking-wider px-2 py-0.5 rounded-full ${
                                            testProgress.isCompleted
                                                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                                : 'bg-orange-500/20 text-orange-400 border border-orange-500/30 animate-pulse'
                                        }`}>
                                            {testProgress.isCompleted ? 'STRESS TEST COMPLETED' : 'GATLING LIVE IN PROGRESS'}
                                        </span>
                                        <span className="text-white font-mono text-xs font-semibold">
                                            {testProgress.simulationName}
                                        </span>
                                    </div>
                                    <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5 font-mono">
                                        <span>Target:</span>
                                        <span className="text-slate-200 underline underline-offset-2">{testProgress.targetEndpoint}</span>
                                    </p>
                                </div>
                            </div>

                            {/* Timer & Fast Finish Button */}
                            <div className="flex items-center gap-2 self-start sm:self-auto">
                                <div className="bg-slate-950 px-3 py-1.5 rounded-xl border border-slate-800 font-mono text-xs flex items-center gap-2">
                                    <span className="text-slate-500">⏱ Waktu:</span>
                                    <span className="text-amber-400 font-bold">
                                        {testProgress.elapsedSeconds}s / {testProgress.totalSeconds}s
                                    </span>
                                </div>
                                {!testProgress.isCompleted && (
                                    <button
                                        onClick={handleFastFinish}
                                        className="bg-slate-800 hover:bg-slate-700 text-amber-300 hover:text-amber-200 border border-slate-700 text-xs font-semibold px-3 py-1.5 rounded-xl transition flex items-center gap-1 cursor-pointer"
                                        title="Percepat proses dan tampilkan hasil langsung"
                                    >
                                        <span>⚡</span>
                                        <span>Selesaikan Cepat</span>
                                    </button>
                                )}
                                {testProgress.isCompleted && (
                                    <button
                                        onClick={() => setTestProgress(null)}
                                        className="text-slate-400 hover:text-white text-xs px-2.5 py-1 rounded-lg hover:bg-slate-800 transition cursor-pointer"
                                        title="Tutup monitor progress"
                                    >
                                        ✕ Tutup
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* Progress Bar & Phase Section */}
                        <div className="py-4 space-y-2">
                            <div className="flex items-center justify-between text-xs">
                                <div className="flex items-center gap-2">
                                    <span className={`font-bold ${testProgress.isCompleted ? 'text-emerald-400' : 'text-orange-400'}`}>
                                        {testProgress.phase}
                                    </span>
                                    <span className="text-slate-500">•</span>
                                    <span className="text-slate-400 text-[11px] hidden sm:inline">
                                        {testProgress.phaseDesc}
                                    </span>
                                </div>
                                <div className="font-mono font-extrabold text-sm text-white flex items-center gap-1">
                                    <span className={testProgress.isCompleted ? 'text-emerald-400' : 'text-amber-400'}>
                                        {testProgress.percent}%
                                    </span>
                                </div>
                            </div>

                            {/* Big Progress Track */}
                            <div className="w-full h-4 bg-slate-950 rounded-full border border-slate-800 p-0.5 overflow-hidden shadow-inner relative">
                                <div
                                    style={{ width: `${testProgress.percent}%` }}
                                    className={`h-full rounded-full transition-all duration-300 relative ${
                                        testProgress.isCompleted
                                            ? 'bg-gradient-to-r from-emerald-500 via-teal-400 to-emerald-400 shadow-lg shadow-emerald-500/40'
                                            : 'bg-gradient-to-r from-orange-600 via-amber-500 to-emerald-400 shadow-lg shadow-orange-500/40'
                                    }`}
                                >
                                    <div className="absolute inset-0 bg-white/20 animate-pulse rounded-full" />
                                </div>
                            </div>
                        </div>

                        {/* 4 Live Metrics Gauges */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 py-2">
                            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col justify-between">
                                <span className="text-[11px] text-slate-400 flex items-center gap-1">
                                    <span>👥</span> Virtual Users (VU)
                                </span>
                                <div className="mt-1 flex items-baseline gap-1">
                                    <span className="text-lg font-bold font-mono text-orange-400">
                                        {testProgress.activeVUs}
                                    </span>
                                    <span className="text-xs text-slate-500 font-mono">
                                        / {testProgress.targetVUs} VUs
                                    </span>
                                </div>
                            </div>

                            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col justify-between">
                                <span className="text-[11px] text-slate-400 flex items-center gap-1">
                                    <span>📤</span> Requests Dispatched
                                </span>
                                <div className="mt-1 flex items-baseline gap-1">
                                    <span className="text-lg font-bold font-mono text-white">
                                        {testProgress.requestsSent.toLocaleString()}
                                    </span>
                                    <span className="text-[11px] text-emerald-400 font-mono">
                                        (OK)
                                    </span>
                                </div>
                            </div>

                            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col justify-between">
                                <span className="text-[11px] text-slate-400 flex items-center gap-1">
                                    <span>⚡</span> Throughput Rate
                                </span>
                                <div className="mt-1 flex items-baseline gap-1">
                                    <span className="text-lg font-bold font-mono text-amber-400">
                                        {testProgress.throughput}
                                    </span>
                                    <span className="text-xs text-slate-500 font-mono">req/s</span>
                                </div>
                            </div>

                            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col justify-between">
                                <span className="text-[11px] text-slate-400 flex items-center gap-1">
                                    <span>🎯</span> Target Response
                                </span>
                                <div className="mt-1 flex items-baseline gap-1">
                                    <span className="text-lg font-bold font-mono text-emerald-400">
                                        {targetPing.online ? `${targetPing.latencyMs || 120}ms` : 'Active'}
                                    </span>
                                    <span className="text-xs text-slate-500 font-mono">
                                        {targetPing.statusCode ? `[HTTP ${targetPing.statusCode}]` : '[OK]'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Live Gatling CLI Terminal Output */}
                        <div className="mt-3">
                            <div className="flex items-center justify-between pb-2 text-[11px] text-slate-400">
                                <div className="flex items-center gap-2 font-mono">
                                    <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
                                    <span className="text-slate-300 font-bold">Gatling Engine CLI Log Stream</span>
                                </div>
                                <button
                                    onClick={() => setShowTerminalLog(!showTerminalLog)}
                                    className="text-slate-400 hover:text-white transition text-[10px] underline underline-offset-2 cursor-pointer"
                                >
                                    {showTerminalLog ? 'Sembunyikan Terminal ▲' : 'Tampilkan Terminal ▼'}
                                </button>
                            </div>

                            {showTerminalLog && (
                                <div className="bg-black/95 rounded-xl border border-slate-800 p-3 font-mono text-[11px] text-emerald-400 shadow-inner h-36 overflow-y-auto space-y-1">
                                    <div className="flex items-center gap-1.5 pb-2 border-b border-slate-800/80 text-[10px] text-slate-500">
                                        <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
                                        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
                                        <span className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
                                        <span className="ml-2">gatling-runner@fintracks:~ (simulating load)</span>
                                    </div>
                                    <pre className="whitespace-pre-wrap leading-relaxed font-mono text-[11px] text-emerald-400/90 pt-1">
                                        {testProgress.terminalLog}
                                    </pre>
                                    <div ref={terminalEndRef} />
                                </div>
                            )}
                        </div>

                        {/* Completion Action Banner */}
                        {testProgress.isCompleted && (
                            <div className="mt-4 p-4 rounded-xl bg-gradient-to-r from-emerald-950/60 via-slate-900 to-slate-950 border border-emerald-500/40 flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-fadeIn">
                                <div className="space-y-0.5">
                                    <div className="flex items-center gap-2">
                                        <span className="text-emerald-400 font-bold text-xs">
                                            🎉 Uji Beban Berhasil Diselesaikan!
                                        </span>
                                        <span className="bg-emerald-500/20 text-emerald-300 font-mono text-[10px] px-2 py-0.5 rounded-full border border-emerald-500/30">
                                            100% Selesai
                                        </span>
                                    </div>
                                    <p className="text-[11px] text-slate-300">
                                        Laporan resmi Gatling HTML 3.15+ telah dibuat dan dapat langsung dilihat di bawah.
                                    </p>
                                </div>

                                <div className="flex flex-wrap items-center gap-2">
                                    {testProgress.result?.id && (
                                        <>
                                            <a
                                                href={`http://localhost:8000/gatling/report/${testProgress.result.id}/html`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="bg-gradient-to-r from-orange-600 via-amber-600 to-orange-500 hover:from-orange-500 hover:to-amber-500 text-white font-bold text-xs px-3.5 py-2 rounded-xl transition shadow-lg shadow-orange-600/30 flex items-center gap-1.5 cursor-pointer"
                                            >
                                                <span>🌐</span>
                                                <span>Buka Gatling .HTML ↗</span>
                                            </a>
                                            <a
                                                href={`http://localhost:8000/gatling/report/${testProgress.result.id}/download-zip`}
                                                className="bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 font-bold text-xs px-3 py-2 rounded-xl transition flex items-center gap-1 cursor-pointer"
                                            >
                                                <span>📦</span>
                                                <span>Unduh ZIP</span>
                                            </a>
                                        </>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* 2. Gatling Stress Test Performance Report Inspector (Full Width & Spacious) */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 md:p-6 shadow-2xl backdrop-blur">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-lg">📈</span>
                                <h3 className="text-sm font-bold text-white">
                                    Laporan Hasil Pengujian Gatling
                                </h3>
                                {selectedRun && (
                                    <span className="bg-slate-800 text-slate-300 font-mono text-[10px] px-2 py-0.5 rounded-full border border-slate-700">
                                        ID #{selectedRun.id}
                                    </span>
                                )}
                            </div>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                                {selectedRun
                                    ? `Simulasi: ${selectedRun.simulation_name} | Target: ${selectedRun.target_queue}`
                                    : 'Pilih hasil tes untuk melihat rincian laporan metrik'}
                            </p>
                        </div>

                        {/* Sub-Tabs untuk Report: Metrik, Preview HTML Gatling, Skrip Scala, Raw JSON */}
                        {selectedRun && (
                            <div className="flex flex-wrap items-center gap-2 self-start sm:self-auto">
                                <div className="flex items-center bg-slate-950 p-1 rounded-xl border border-slate-800">
                                    <button
                                        onClick={() => setReportSubTab('metrics')}
                                        className={`px-3 py-1 text-xs font-semibold rounded-lg transition ${
                                            reportSubTab === 'metrics'
                                                ? 'bg-orange-600 text-white shadow-sm'
                                                : 'text-slate-400 hover:text-slate-200'
                                        }`}
                                    >
                                        Grafik & Metrik
                                    </button>
                                    <button
                                        onClick={() => setReportSubTab('gatlingHtml')}
                                        className={`px-3 py-1 text-xs font-semibold rounded-lg transition ${
                                            reportSubTab === 'gatlingHtml'
                                                ? 'bg-orange-600 text-white shadow-sm'
                                                : 'text-slate-400 hover:text-slate-200'
                                        }`}
                                    >
                                        📄 Gatling HTML
                                    </button>
                                    <button
                                        onClick={() => setReportSubTab('script')}
                                        className={`px-3 py-1 text-xs font-semibold rounded-lg transition ${
                                            reportSubTab === 'script'
                                                ? 'bg-orange-600 text-white shadow-sm'
                                                : 'text-slate-400 hover:text-slate-200'
                                        }`}
                                    >
                                        Skrip Scala
                                    </button>
                                    <button
                                        onClick={() => setReportSubTab('raw')}
                                        className={`px-3 py-1 text-xs font-semibold rounded-lg transition ${
                                            reportSubTab === 'raw'
                                                ? 'bg-orange-600 text-white shadow-sm'
                                                : 'text-slate-400 hover:text-slate-200'
                                        }`}
                                    >
                                        JSON Report
                                    </button>
                                </div>

                                <a
                                    href={`http://localhost:8000/gatling/report/${selectedRun.id}/html`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 text-white font-bold text-xs px-3 py-1.5 rounded-xl transition shadow-lg shadow-orange-600/20 flex items-center gap-1.5"
                                    title="Buka laporan resmi Gatling (.html) di peramban"
                                >
                                    <span>🌐</span>
                                    <span className="hidden sm:inline">Buka Report</span> .HTML ↗
                                </a>

                                <a
                                    href={`http://localhost:8000/gatling/report/${selectedRun.id}/download`}
                                    className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-bold text-xs px-3 py-1.5 rounded-xl transition flex items-center gap-1"
                                    title="Unduh berkas Gatling .html mandiri"
                                >
                                    <span>⬇</span>
                                    <span className="hidden sm:inline">HTML</span>
                                </a>

                                <a
                                    href={`http://localhost:8000/gatling/report/${selectedRun.id}/download-zip`}
                                    className="bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 font-bold text-xs px-3 py-1.5 rounded-xl transition flex items-center gap-1"
                                    title="Unduh full offline Gatling report folder (.zip)"
                                >
                                    <span>📦</span>
                                    <span className="hidden sm:inline">ZIP Bundle</span>
                                </a>
                            </div>
                        )}
                    </div>

                    {/* Report Content Body */}
                    {!selectedRun ? (
                        <div className="h-48 flex flex-col items-center justify-center text-center p-6 text-slate-500 text-xs">
                            <span className="text-3xl mb-2">📊</span>
                            <p className="text-slate-400 font-medium">Belum ada laporan pengujian yang dipilih.</p>
                            <p className="text-[11px] text-slate-600 mt-1">
                                Jalankan tes baru melalui console di atas atau pilih salah satu dari tabel riwayat di bawah.
                            </p>
                        </div>
                    ) : (
                        <div className="mt-4 space-y-4">
                            {/* TAB 1: METRICS & VISUAL GRAPHS */}
                            {reportSubTab === 'metrics' && (
                                <div className="space-y-4">
                                    {/* Key Metrics Grid */}
                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                        <div title="Jumlah total request yang dikirimkan pada sesi pengujian ini (OK + KO)." className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 cursor-help transition hover:border-slate-600">
                                            <span className="text-[10px] text-slate-500 uppercase font-semibold">Total Request</span>
                                            <div className="text-xl font-black text-white mt-1">
                                                {selectedRun.total_requests.toLocaleString('id-ID')}
                                            </div>
                                            <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                                                {selectedRun.successful_requests} OK • {selectedRun.failed_requests} KO
                                            </div>
                                        </div>

                                        <div title="95% dari seluruh request diselesaikan dalam waktu ini (Persentil 95)." className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 cursor-help transition hover:border-indigo-600/50">
                                            <span className="text-[10px] text-slate-500 uppercase font-semibold">P95 Response Time</span>
                                            <div className="text-xl font-black text-indigo-400 mt-1">
                                                {selectedRun.p95_response_time} ms
                                            </div>
                                            <div className="text-[10px] text-emerald-400 font-medium mt-0.5">
                                                Target SLA &lt; 500ms
                                            </div>
                                        </div>

                                        <div title="Rata-rata waktu latensi dari semua request pada sesi ini." className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 cursor-help transition hover:border-blue-600/50">
                                            <span className="text-[10px] text-slate-500 uppercase font-semibold">Mean Response Time</span>
                                            <div className="text-xl font-black text-blue-400 mt-1">
                                                {selectedRun.mean_response_time} ms
                                            </div>
                                            <div className="text-[10px] text-slate-400 mt-0.5">
                                                Rata-rata latensi
                                            </div>
                                        </div>

                                        <div title="Persentase request yang gagal (KO) dibandingkan total request." className="bg-slate-950 p-3.5 rounded-xl border border-slate-800 cursor-help transition hover:border-rose-600/50">
                                            <span className="text-[10px] text-slate-500 uppercase font-semibold">Error Rate</span>
                                            <div className={`text-xl font-black mt-1 ${parseFloat(selectedRun.error_rate) > 2 ? 'text-rose-400' : 'text-emerald-400'}`}>
                                                {selectedRun.error_rate}%
                                            </div>
                                            <div className="text-[10px] text-slate-400 mt-0.5">
                                                {selectedRun.failed_requests > 0 ? `${selectedRun.failed_requests} gagal` : '0 error terdeteksi'}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Detailed Latency Distribution Metrics */}
                                    {parsedSummary?.response_times_ms && (
                                        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                                            <div className="text-xs font-bold text-white mb-3 flex items-center justify-between">
                                                <span>Distribusi Persentil Waktu Respon Lengkap (ms)</span>
                                                <span className="text-[10px] text-slate-500 font-normal">Dari official Gatling engine</span>
                                            </div>
                                            <div className="grid grid-cols-2 sm:grid-cols-7 gap-2 text-center text-xs">
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">Min</span>
                                                    <div className="font-bold text-emerald-400 mt-0.5">{parsedSummary.response_times_ms.min}ms</div>
                                                </div>
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">P50 (Median)</span>
                                                    <div className="font-bold text-blue-400 mt-0.5">{parsedSummary.response_times_ms.p50}ms</div>
                                                </div>
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">P75</span>
                                                    <div className="font-bold text-blue-300 mt-0.5">{parsedSummary.response_times_ms.p75}ms</div>
                                                </div>
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">P95</span>
                                                    <div className="font-bold text-indigo-400 mt-0.5">{parsedSummary.response_times_ms.p95}ms</div>
                                                </div>
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">P99</span>
                                                    <div className="font-bold text-amber-400 mt-0.5">{parsedSummary.response_times_ms.p99}ms</div>
                                                </div>
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">Max</span>
                                                    <div className="font-bold text-rose-400 mt-0.5">{parsedSummary.response_times_ms.max}ms</div>
                                                </div>
                                                <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500 font-mono">Std Dev</span>
                                                    <div className="font-bold text-slate-300 mt-0.5">{parsedSummary.response_times_ms.std_dev}ms</div>
                                                </div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Recharts Bar Chart: Distribusi Latensi */}
                                    {latencyChartData.length > 0 && (
                                        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                                            <div className="flex items-center justify-between mb-3">
                                                <div className="text-xs font-bold text-white flex items-center gap-2">
                                                    <span>📊</span> Visualisasi Latensi Response Time (ms)
                                                </div>
                                                <span className="text-[10px] text-slate-500">Semakin rendah semakin responsif</span>
                                            </div>
                                            <div className="h-56 w-full">
                                                <ResponsiveContainer width="100%" height="100%">
                                                    <BarChart data={latencyChartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                                                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                                                        <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 11 }} />
                                                        <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit="ms" />
                                                        <Tooltip
                                                            contentStyle={{
                                                                backgroundColor: '#0f172a',
                                                                borderColor: '#334155',
                                                                borderRadius: '0.75rem',
                                                                fontSize: '11px',
                                                                color: '#f8fafc'
                                                            }}
                                                            formatter={(value) => [`${value} ms`, 'Latensi']}
                                                        />
                                                        <Bar dataKey="latency" radius={[6, 6, 0, 0]}>
                                                            {latencyChartData.map((entry, index) => (
                                                                <Cell key={`cell-${index}`} fill={entry.fill} />
                                                            ))}
                                                        </Bar>
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        </div>
                                    )}

                                    {/* Request Throughput & Status Breakdown */}
                                    {parsedSummary?.requests_count && (
                                        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                                            <div className="text-xs font-bold text-white mb-2 flex items-center justify-between">
                                                <span>⚡ Ringkasan Volume & Status Permintaan</span>
                                                <span className="text-[10px] text-slate-500 font-mono">Duration: {selectedRun.duration_seconds}s</span>
                                            </div>
                                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                                                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500">Total Requests</span>
                                                    <div className="font-bold text-white mt-0.5">{parsedSummary.requests_count.total?.toLocaleString('id-ID')}</div>
                                                </div>
                                                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500">Success Rate (OK)</span>
                                                    <div className="font-bold text-emerald-400 mt-0.5">
                                                        {parsedSummary.requests_count.ok_percent || ((selectedRun.successful_requests / selectedRun.total_requests) * 100).toFixed(1)}%
                                                    </div>
                                                </div>
                                                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500">Failed (KO)</span>
                                                    <div className="font-bold text-rose-400 mt-0.5">
                                                        {parsedSummary.requests_count.ko?.toLocaleString('id-ID')}
                                                    </div>
                                                </div>
                                                <div className="bg-slate-900/60 p-2.5 rounded-lg border border-slate-800">
                                                    <span className="text-[10px] text-slate-500">Peak Throughput</span>
                                                    <div className="font-bold text-purple-400 mt-0.5">
                                                        {parsedSummary.requests_per_sec?.mean || Math.round(selectedRun.total_requests / (selectedRun.duration_seconds || 1))} req/s
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* TAB 2: LIVE GATLING HTML EMBEDDED PREVIEW */}
                            {reportSubTab === 'gatlingHtml' && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between pb-2 text-xs text-slate-400">
                                        <div className="flex items-center gap-2">
                                            <span className="text-emerald-400 font-semibold">● Live Gatling HTML Report Preview</span>
                                            <span className="text-slate-600">|</span>
                                            <span className="font-mono text-[11px] text-slate-300">
                                                http://localhost:8000/gatling/report/{selectedRun.id}/html
                                            </span>
                                        </div>
                                        <a
                                            href={`http://localhost:8000/gatling/report/${selectedRun.id}/html`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-orange-400 hover:text-orange-300 text-xs font-semibold flex items-center gap-1 transition"
                                        >
                                            <span>Buka Layar Penuh ↗</span>
                                        </a>
                                    </div>
                                    <div className="w-full bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-2xl relative">
                                        <iframe
                                            src={`http://localhost:8000/gatling/report/${selectedRun.id}/html`}
                                            title={`Gatling HTML Report #${selectedRun.id}`}
                                            className="w-full h-[650px] border-0 bg-white"
                                            loading="lazy"
                                        />
                                    </div>
                                </div>
                            )}

                            {/* TAB 3: GENERATED SCALA SCRIPT */}
                            {reportSubTab === 'script' && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between pb-2">
                                        <span className="text-xs text-slate-400 font-mono">
                                            Simulation: {selectedRun.simulation_name}.scala
                                        </span>
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => handleCopyScript(selectedRun.generated_script)}
                                                className="bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold px-3 py-1 rounded-lg transition"
                                            >
                                                {copiedScript ? '✓ Tersalin' : 'Salin Skrip'}
                                            </button>
                                            <button
                                                onClick={() => handleDownloadScript(selectedRun)}
                                                className="bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold px-3 py-1 rounded-lg transition flex items-center gap-1"
                                            >
                                                <span>⬇</span>
                                                <span>Download .scala</span>
                                            </button>
                                        </div>
                                    </div>
                                    <pre className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-[11px] text-slate-300 overflow-x-auto max-h-96 leading-relaxed">
                                        {selectedRun.generated_script || '// Tidak ada skrip yang tercatat.'}
                                    </pre>
                                </div>
                            )}

                            {/* TAB 4: RAW JSON REPORT */}
                            {reportSubTab === 'raw' && (
                                <div className="space-y-2">
                                    <div className="text-xs text-slate-400">
                                        Struktur JSON tersimpan di kolom `report_summary` database:
                                    </div>
                                    <pre className="bg-slate-950 p-4 rounded-xl border border-slate-800 font-mono text-[11px] text-emerald-400 overflow-x-auto max-h-96 leading-relaxed">
                                        {selectedRun.report_summary || '{}'}
                                    </pre>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* 3. Test Execution History Table (Full Width) */}
                <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 md:p-6 shadow-2xl backdrop-blur">
                    <div className="flex items-center justify-between pb-4 border-b border-slate-800">
                        <div>
                            <h3 className="text-sm font-bold text-white flex items-center gap-2">
                                <span>📜</span> Riwayat Seluruh Pengujian Beban
                            </h3>
                            <p className="text-xs text-slate-400 mt-0.5">
                                Pilih baris manapun untuk menampilkan laporannya pada panel inspeksi di atas
                            </p>
                        </div>
                        <button
                            onClick={fetchTestRuns}
                            className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 px-3 py-1.5 rounded-lg transition"
                        >
                            ↻ Refresh
                        </button>
                    </div>

                    <div className="overflow-x-auto mt-4">
                        {loadingRuns ? (
                            <div className="h-32 flex items-center justify-center text-xs text-slate-500">
                                Memuat riwayat pengujian...
                            </div>
                        ) : testRuns.length === 0 ? (
                            <div className="h-32 flex flex-col items-center justify-center text-center text-slate-500 text-xs">
                                <p>Belum ada tes yang tercatat.</p>
                                <p className="text-[11px] text-slate-600 mt-1">Jalankan tes pertama Anda menggunakan console di atas!</p>
                            </div>
                        ) : (
                            <table className="w-full text-left text-xs">
                                <thead>
                                    <tr className="text-slate-400 border-b border-slate-800 text-[11px]">
                                        <th className="py-2.5 px-3">ID</th>
                                        <th className="py-2.5 px-3">Simulasi</th>
                                        <th className="py-2.5 px-3">Target</th>
                                        <th className="py-2.5 px-3">VUs / Durasi</th>
                                        <th className="py-2.5 px-3">P95</th>
                                        <th className="py-2.5 px-3">Error</th>
                                        <th className="py-2.5 px-3 text-right">Aksi</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/60">
                                    {testRuns.map((r) => {
                                        const isSelected = selectedRun && selectedRun.id === r.id;
                                        const isUrl = r.target_queue?.startsWith('http');
                                        return (
                                            <tr
                                                key={r.id}
                                                onClick={() => {
                                                    setSelectedRun(r);
                                                    setReportSubTab('metrics');
                                                }}
                                                className={`cursor-pointer transition group ${
                                                    isSelected
                                                        ? 'bg-orange-600/15 border-l-4 border-orange-500'
                                                        : 'hover:bg-slate-800/40'
                                                }`}
                                            >
                                                <td className="py-3 px-3 font-mono text-slate-400">#{r.id}</td>
                                                <td className="py-3 px-3 font-semibold text-white">
                                                    {r.simulation_name}
                                                </td>
                                                <td className="py-3 px-3">
                                                    <div className="flex items-center gap-1.5">
                                                        <span className={`text-[9px] px-1.5 py-0.2 rounded font-bold uppercase ${
                                                            isUrl ? 'bg-blue-500/20 text-blue-400' : 'bg-orange-500/20 text-orange-400'
                                                        }`}>
                                                            {isUrl ? 'URL' : 'AMQP'}
                                                        </span>
                                                        <span className="font-mono text-[11px] text-slate-300 truncate max-w-[180px]" title={r.target_queue}>
                                                            {r.target_queue}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="py-3 px-3 text-slate-300">
                                                    {r.virtual_users} VUs ({r.duration_seconds}s)
                                                </td>
                                                <td className="py-3 px-3 font-mono text-indigo-400">
                                                    {r.p95_response_time}ms
                                                </td>
                                                <td className="py-3 px-3">
                                                    <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                                        parseFloat(r.error_rate) > 2
                                                            ? 'bg-rose-500/20 text-rose-400'
                                                            : 'bg-emerald-500/20 text-emerald-400'
                                                    }`}>
                                                        {r.error_rate}%
                                                    </span>
                                                </td>
                                                <td className="py-3 px-3 text-right">
                                                    <div className="flex items-center justify-end gap-1.5">
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setSelectedRun(r);
                                                                setReportSubTab('metrics');
                                                            }}
                                                            className="bg-slate-800 group-hover:bg-orange-600 text-slate-200 group-hover:text-white px-2.5 py-1 rounded-lg text-[11px] font-semibold transition"
                                                        >
                                                            Buka
                                                        </button>
                                                        <a
                                                            href={`http://localhost:8000/gatling/report/${r.id}/html`}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            onClick={(e) => e.stopPropagation()}
                                                            className="bg-orange-500/15 hover:bg-orange-600 text-orange-400 hover:text-white border border-orange-500/30 px-2 py-1 rounded-lg text-[10px] font-bold transition flex items-center gap-1"
                                                            title="Buka laporan resmi Gatling (.html) di peramban"
                                                        >
                                                            <span>HTML ↗</span>
                                                        </a>
                                                        <button
                                                            onClick={(e) => handleDeleteRun(r.id, e)}
                                                            className="text-slate-500 hover:text-rose-400 p-1 transition"
                                                            title="Hapus rekaman tes ini"
                                                        >
                                                            ✕
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>
            </main>

            {/* Collapsible Floating AI Chatbot Widget (Bottom Right) */}
            <GatlingChatWidget onTestTriggered={fetchTestRuns} />
        </div>
    );
};

export default GatlingDashboard;
