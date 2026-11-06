import React, { useState } from 'react';

const RagEvaluationBadge = ({ evaluation }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [showChunks, setShowChunks] = useState(false);

    if (!evaluation || !evaluation.scores) return null;

    const { scores, eval_mode, latency_seconds, summary } = evaluation;
    const faith = scores.faithfulness?.score_percent ?? 0;
    const ansRel = scores.answer_relevance?.score_percent ?? 0;
    const ctxRel = scores.context_relevance?.score_percent ?? 0;
    const avg = scores.average?.score_percent ?? Math.round((faith + ansRel + ctxRel) / 3);

    const getScoreColor = (score) => {
        if (score >= 90) return 'text-emerald-700 bg-emerald-50 border-emerald-300';
        if (score >= 75) return 'text-blue-700 bg-blue-50 border-blue-300';
        if (score >= 60) return 'text-amber-700 bg-amber-50 border-amber-300';
        return 'text-red-700 bg-red-50 border-red-300';
    };

    const getBarColor = (score) => {
        if (score >= 90) return 'bg-emerald-500';
        if (score >= 75) return 'bg-blue-500';
        if (score >= 60) return 'bg-amber-500';
        return 'bg-red-500';
    };

    return (
        <div className="mt-2.5 w-full text-xs font-sans rounded-xl border border-amber-200 bg-gradient-to-r from-amber-50/80 via-white to-sky-50/80 shadow-sm overflow-hidden">
            {/* Header / Summary row */}
            <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full flex items-center justify-between p-2.5 text-left hover:bg-amber-100/50 transition-colors"
                title="Klik untuk melihat rumus & rincian evaluasi RAG"
            >
                <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-bold text-amber-900 flex items-center gap-1">
                        📊 <span className="underline decoration-amber-400">Skor RAG</span>
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold border ${getScoreColor(faith)}`}>
                        Faith: {faith}%
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold border ${getScoreColor(ansRel)}`}>
                        Ans Rel: {ansRel}%
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-[11px] font-semibold border ${getScoreColor(ctxRel)}`}>
                        Ctx Rel: {ctxRel}%
                    </span>
                    <span className="text-[11px] font-bold text-gray-700 bg-gray-100 px-1.5 py-0.5 rounded border border-gray-200">
                        Avg: {avg}%
                    </span>
                </div>
                <div className="text-gray-500 text-xs shrink-0 ml-1">
                    {isExpanded ? '▲ Tutup' : '▼ Rumus & Detail'}
                </div>
            </button>

            {/* Collapsible detail */}
            {isExpanded && (
                <div className="p-3 border-t border-amber-200/70 bg-white/95 space-y-3">
                    <div className="text-[11px] text-gray-500 flex justify-between items-center pb-1 border-b border-gray-100">
                        <span>Evaluator: <strong>{eval_mode || 'LLM-as-Judge'}</strong></span>
                        {latency_seconds && <span>Waktu: {latency_seconds}s</span>}
                    </div>

                    {/* 1. Faithfulness */}
                    <div className="space-y-1">
                        <div className="flex justify-between items-center text-[11px]">
                            <span className="font-semibold text-gray-800">
                                1. Faithfulness (Kesetiaan terhadap PDF)
                            </span>
                            <span className="font-bold text-emerald-700">{faith}%</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                            <div className={`${getBarColor(faith)} h-1.5 rounded-full`} style={{ width: `${faith}%` }}></div>
                        </div>
                        <div className="text-[10px] text-gray-600 font-mono bg-gray-50 p-1 rounded border border-gray-100">
                            {scores.faithfulness?.formula_text || 'Rumus: (|V| / |S|) × 100%'}
                        </div>
                        {scores.faithfulness?.reason && (
                            <p className="text-[10.5px] text-gray-600 leading-tight">
                                ℹ️ {scores.faithfulness.reason}
                            </p>
                        )}
                    </div>

                    {/* 2. Answer Relevance */}
                    <div className="space-y-1">
                        <div className="flex justify-between items-center text-[11px]">
                            <span className="font-semibold text-gray-800">
                                2. Answer Relevance (Relevansi terhadap Pertanyaan)
                            </span>
                            <span className="font-bold text-blue-700">{ansRel}%</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                            <div className={`${getBarColor(ansRel)} h-1.5 rounded-full`} style={{ width: `${ansRel}%` }}></div>
                        </div>
                        <div className="text-[10px] text-gray-600 font-mono bg-gray-50 p-1 rounded border border-gray-100">
                            {scores.answer_relevance?.formula_text || 'Rumus: Sim(A, Q) × 100%'}
                        </div>
                        {scores.answer_relevance?.reason && (
                            <p className="text-[10.5px] text-gray-600 leading-tight">
                                ℹ️ {scores.answer_relevance.reason}
                            </p>
                        )}
                    </div>

                    {/* 3. Context Relevance */}
                    <div className="space-y-1">
                        <div className="flex justify-between items-center text-[11px]">
                            <span className="font-semibold text-gray-800">
                                3. Context Relevance (Ketepatan Konteks Retriever)
                            </span>
                            <span className="font-bold text-amber-700">{ctxRel}%</span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-1.5 overflow-hidden">
                            <div className={`${getBarColor(ctxRel)} h-1.5 rounded-full`} style={{ width: `${ctxRel}%` }}></div>
                        </div>
                        <div className="text-[10px] text-gray-600 font-mono bg-gray-50 p-1 rounded border border-gray-100">
                            {scores.context_relevance?.formula_text || 'Rumus: (|C_relevan| / |C_total|) × 100%'}
                        </div>
                        {scores.context_relevance?.reason && (
                            <p className="text-[10.5px] text-gray-600 leading-tight">
                                ℹ️ {scores.context_relevance.reason}
                            </p>
                        )}
                    </div>

                    {summary && (
                        <div className="mt-2 p-2 bg-amber-50 rounded-lg border border-amber-200/80 text-[11px] text-amber-900 leading-snug">
                            <strong>Ringkasan:</strong> {summary}
                        </div>
                    )}

                    {/* Section Lihat Chunk Dokumen PDF yang Diambil */}
                    {Array.isArray(evaluation.retrieved_chunks) && evaluation.retrieved_chunks.length > 0 && (
                        <div className="mt-3 pt-2 border-t border-amber-200/60">
                            <button
                                type="button"
                                onClick={() => setShowChunks(!showChunks)}
                                className="w-full flex items-center justify-between px-2.5 py-1.5 bg-sky-50 hover:bg-sky-100 text-sky-900 rounded-lg font-semibold text-[11px] border border-sky-200 transition-colors"
                            >
                                <span className="flex items-center gap-1.5">
                                    <span>📑</span>
                                    <span>Chunk Dokumen yang Diambil ({evaluation.retrieved_chunks.length} Chunk)</span>
                                </span>
                                <span>{showChunks ? '▲ Sembunyikan' : '▼ Lihat Chunk'}</span>
                            </button>

                            {showChunks && (
                                <div className="mt-2 space-y-2 max-h-60 overflow-y-auto pr-1">
                                    {evaluation.retrieved_chunks.map((chk, cIdx) => (
                                        <div key={cIdx} className="p-2.5 bg-gray-50 rounded-lg border border-gray-200 text-[11px] space-y-1">
                                            <div className="flex items-center justify-between font-bold text-gray-800">
                                                <span>[{chk.chunk_index || cIdx + 1}] {chk.title}</span>
                                                <span className="text-[10px] bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded font-mono">
                                                    Hal {chk.page || 1} • Skor: {chk.score || '-'}
                                                </span>
                                            </div>
                                            <div className="text-[10.5px] text-gray-600 whitespace-pre-wrap font-sans bg-white p-2 rounded border border-gray-100 leading-relaxed max-h-36 overflow-y-auto">
                                                {chk.content}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default RagEvaluationBadge;
