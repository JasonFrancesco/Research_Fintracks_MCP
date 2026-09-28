import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Chatbot from './components/Chatbot';

const App = () => {
    const [showChatbot, setShowChatbot] = useState(false);

    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/" element={<Register />} />
                    <Route path="/register" element={<Register />} />
                    <Route path="/login" element={<Login />} />
                    <Route
                        path="/dashboard"
                        element={
                            <>
                                <Dashboard />
                                {showChatbot && <Chatbot />}
                                <button
                                    onClick={() => setShowChatbot(!showChatbot)}
                                    className="fixed bottom-6 right-6 bg-blue-600 text-white p-4 rounded-full shadow-xl hover:bg-blue-700 transition-all z-50 flex items-center justify-center"
                                    style={{ width: '60px', height: '60px' }}
                                >
                                    <span className="text-2xl">🤖</span>
                                </button>
                            </>
                        }
                    />
                    <Route path="*" element={<Navigate to="/" />} />
                </Routes>
            </Router>
        </AuthProvider>
    );
};

export default App;
