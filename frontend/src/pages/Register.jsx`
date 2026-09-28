import React, { useState, useContext } from 'react';
import { AuthContext } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

const Register = () => {
    const [formData, setFormData] = useState({
        name: '',
        email: '',
        password: '',
    });
    const { register } = useContext(AuthContext);
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            await register(formData);
            alert('Registrasi berhasil! Silakan login.');
            navigate('/login');
        } catch (error) {
            alert('Registrasi gagal! Email mungkin sudah terdaftar.');
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-100">
            <form onSubmit={handleSubmit} className="bg-white p-8 rounded-lg shadow-md w-96">
                <h2 className="text-2xl font-bold mb-6 text-center">Daftar Akun FinTracks</h2>
                <div className="mb-4">
                    <label className="block mb-2">Nama Lengkap</label>
                    <input
                        type="text"
                        className="w-full p-2 border rounded"
                        value={formData.name}
                        onChange={(e) => setFormData({...formData, name: e.target.value})}
                        required
                    />
                </div>
                <div className="mb-4">
                    <label className="block mb-2">Email</label>
                    <input
                        type="email"
                        className="w-full p-2 border rounded"
                        value={formData.email}
                        onChange={(e) => setFormData({...formData, email: e.target.value})}
                        required
                    />
                </div>
                <div className="mb-6">
                    <label className="block mb-2">Password</label>
                    <input
                        type="password"
                        className="w-full p-2 border rounded"
                        value={formData.password}
                        onChange={(e) => setFormData({...formData, password: e.target.value})}
                        required
                    />
                </div>
                <button className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">Daftar Sekarang</button>
                <p className="mt-4 text-center text-sm text-gray-600">
                    Sudah punya akun? <Link to="/login" className="text-blue-600 hover:underline">Login di sini</Link>
                </p>
            </form>
        </div>
    );
};

export default Register;
