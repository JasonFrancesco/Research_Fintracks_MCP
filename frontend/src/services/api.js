import axios from 'axios';

const api = axios.create({
    baseURL: 'http://localhost:8000',
});

// Endpoint yang 401-nya berarti "kredensial salah", bukan "sesi habis".
// Tanpa pengecualian ini, salah password saat login akan memicu redirect
// dan pesan error di halaman Login tidak pernah terlihat.
const CREDENTIAL_PATHS = ['/auth/login', '/auth/register'];

// Interceptor untuk menambahkan JWT Token secara otomatis ke setiap request
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

// Token JWT kedaluwarsa sesuai ACCESS_TOKEN_EXPIRE_MINUTES di backend/.env.
// Sebelumnya tidak ada yang menangani 401, sehingga tab yang sudah lama terbuka
// tetap menampilkan dashboard sementara seluruh request gagal tanpa penjelasan.
api.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error.response?.status;
        const url = error.config?.url || '';
        const isCredentialAttempt = CREDENTIAL_PATHS.some((p) => url.startsWith(p));

        if (status === 401 && !isCredentialAttempt) {
            localStorage.removeItem('token');
            if (!window.location.pathname.startsWith('/login')) {
                window.location.replace('/login?expired=1');
            }
        }

        return Promise.reject(error);
    }
);

export default api;
