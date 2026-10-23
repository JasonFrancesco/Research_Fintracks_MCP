import React, { useState } from 'react';

// Format nilai angka menjadi Rupiah. Nilai non-angka jatuh ke 'Rp -'
// agar kartu tetap render meski data harga rusak.
const formatIDR = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return 'Rp -';
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        maximumFractionDigits: 0,
    }).format(n);
};

const FigureProductCard = ({ figure }) => {
    const [imgFailed, setImgFailed] = useState(false);
    const stok = Number(figure.stok) || 0;

    return (
        <div className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-sm text-sm">
            {!imgFailed && figure.image_url ? (
                <img
                    src={figure.image_url}
                    alt={figure.nama}
                    className="w-full h-32 object-cover bg-gray-100"
                    onError={() => setImgFailed(true)}
                />
            ) : (
                <div className="w-full h-32 flex items-center justify-center bg-gray-100 text-gray-400 text-xs">
                    Gambar tidak tersedia
                </div>
            )}
            <div className="p-2 space-y-1">
                <p className="font-semibold text-gray-800 leading-snug">{figure.nama}</p>
                <p className="text-[11px] text-gray-500">
                    {[figure.karakter, figure.brand, figure.skala].filter(Boolean).join(' · ')}
                </p>
                <p className="font-bold text-red-700">{formatIDR(figure.harga)}</p>
                <p className={`text-[11px] ${stok > 0 ? 'text-green-600' : 'text-gray-400'}`}>
                    {stok > 0 ? `Tersedia (${stok})` : 'Habis'}
                </p>
                {figure.shopee_url && (
                    <a
                        href={figure.shopee_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Lihat ${figure.nama} di Shopee`}
                        className="inline-block mt-1 px-2 py-1 rounded bg-orange-600 hover:bg-orange-700 text-white text-[11px] font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-300"
                    >
                        Lihat di Shopee
                    </a>
                )}
            </div>
        </div>
    );
};

export default FigureProductCard;
