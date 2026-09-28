import React, { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

const Login = () => {
    const [isRegister, setIsRegister] = useState(false);
    const [name, setName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [errorMsg, setErrorMsg] = useState('');
    const [successMsg, setSuccessMsg] = useState('');
    
    const { login, register } = useContext(AuthContext);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setErrorMsg('');
        setSuccessMsg('');

        if (isRegister) {
            try {
                await register({ name, email, password });
                setSuccessMsg('Registrasi berhasil! Silakan login dengan akun Anda.');
                setIsRegister(false);
                setPassword('');
            } catch (error) {
                const msg = error.response?.data?.detail || 'Registrasi gagal! Email mungkin sudah terdaftar.';
                setErrorMsg(msg);
            }
        } else {
            try {
                await login(email, password);
                navigate('/dashboard');
            } catch (error) {
                const msg = error.response?.data?.detail || 'Login gagal! Periksa email dan password Anda.';
                setErrorMsg(msg);
            }
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
            <form onSubmit={handleSubmit} className="bg-white p-8 rounded-xl shadow-lg w-full max-w-md">
                <h2 className="text-2xl font-bold mb-2 text-center text-gray-800">
                    {isRegister ? 'Daftar Akun FinTracks' : 'Login FinTracks'}
                </h2>
                <p className="text-sm text-gray-500 text-center mb-6">
                    {isRegister ? 'Buat akun baru untuk mengelola keuangan Anda' : 'Masuk ke dashboard keuangan Anda'}
                </p>

                {errorMsg && (
                    <div className="mb-4 p-3 bg-red-100 text-red-700 text-sm rounded-lg">
                        {errorMsg}
                    </div>
                )}

                {successMsg && (
                    <div className="mb-4 p-3 bg-green-100 text-green-700 text-sm rounded-lg">
                        {successMsg}
                    </div>
                )}

                {isRegister && (
                    <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-1">Nama Lengkap</label>
                        <input
                            type="text"
                            className="w-full p-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none"
                            placeholder="Budi Santoso"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                        />
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
                    {isRegister ? 'Daftar Akun' : 'Login'}
                </button>

                <div className="text-center text-sm text-gray-600">
                    {isRegister ? (
                        <span>Sudah punya akun? <button type="button" onClick={() => { setIsRegister(false); setErrorMsg(''); }} className="text-blue-600 font-semibold hover:underline">Login disini</button></span>
                    ) : (
                        <span>Belum punya akun? <button type="button" onClick={() => { setIsRegister(true); setErrorMsg(''); }} className="text-blue-600 font-semibold hover:underline">Daftar disini</button></span>
                    )}
                </div>
            </form>
        </div>
    );
};

export default Login;
