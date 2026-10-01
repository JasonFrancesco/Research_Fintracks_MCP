import React, { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';

const Login = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errorMsg, setErrorMsg] = useState('');

    const { login } = useContext(AuthContext);
    const navigate = useNavigate();
    // Ditandai oleh interceptor di services/api.js saat sebuah request dijawab 401.
    const [searchParams] = useSearchParams();
    const sessionExpired = searchParams.get('expired') === '1';

    const handleSubmit = async (e) => {
        e.preventDefault();
        setErrorMsg('');

        try {
            await login(email, password);
            navigate('/dashboard');
        } catch (error) {
            const msg = error.response?.data?.detail || 'Login gagal! Periksa email dan password Anda.';
            setErrorMsg(msg);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
            <form onSubmit={handleSubmit} className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
                <h2 className="text-2xl font-bold mb-2 text-center text-gray-800">
                    Login FinTracks
                </h2>
                <p className="text-sm text-gray-500 text-center mb-6">
                    Masuk ke dashboard keuangan Anda
                </p>

                {sessionExpired && !errorMsg && (
                    <div className="mb-4 p-3 bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg" role="status">
                        Sesi Anda sudah berakhir. Silakan login kembali untuk melanjutkan.
                    </div>
                )}

                {errorMsg && (
                    <div className="mb-4 p-3 bg-red-100 text-red-700 text-sm rounded-lg" role="alert">
                        {errorMsg}
                    </div>
                )}

                <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
                    <input
                        type="email"
                        className="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                        placeholder="email@contoh.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                    />
                </div>

                <div className="mb-6">
                    <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
                    <input
                        type="password"
                        className="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                        placeholder="••••••••"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />
                </div>

                <button
                    type="submit"
                    className="w-full bg-blue-600 text-white py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors shadow-sm mb-4"
                >
                    Login
                </button>

                <div className="text-center text-sm text-gray-600">
                    Belum punya akun?{' '}
                    <Link to="/register" className="text-blue-600 font-semibold hover:underline">
                        Daftar di sini
                    </Link>
                </div>
            </form>
        </div>
    );
};

export default Login;

