import React, { useState, useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, AuthContext } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import Chatbot from './components/Chatbot';

const ProtectedRoute = ({ children }) => {
    const { user, loading } = useContext(AuthContext);
    if (loading) return <div className="flex h-screen items-center justify-center text-gray-500 font-medium">Loading FinTracks...</div>;
    return user ? children : <Navigate to="/login" replace />;
};

const PublicRoute = ({ children }) => {
    const { user, loading } = useContext(AuthContext);
    if (loading) return <div className="flex h-screen items-center justify-center text-gray-500 font-medium">Loading FinTracks...</div>;
    return user ? <Navigate to="/dashboard" replace /> : children;
};

const DashboardLayout = () => {
    const [showChatbot, setShowChatbot] = useState(false);
    return (
        <div className="relative">
            <Dashboard />
            {showChatbot && <Chatbot />}
            <button
                onClick={() => setShowChatbot(!showChatbot)}
                className="fixed bottom-6 right-6 bg-blue-600 text-white p-4 rounded-full shadow-2xl hover:bg-blue-700 transition-all z-50 flex items-center justify-center hover:scale-105 active:scale-95"
                style={{ width: '60px', height: '60px' }}
                title="FinTracks AI Chatbot"
            >
                <span className="text-2xl">🤖</span>
            </button>
        </div>
    );
};

const App = () => {
    return (
        <AuthProvider>
            <Router>
                <Routes>
                    <Route path="/" element={<PublicRoute><Login /></PublicRoute>} />
                    <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
                    <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />
                    <Route
                        path="/dashboard"
                        element={
                            <ProtectedRoute>
                                <DashboardLayout />
                            </ProtectedRoute>
                        }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </Router>
        </AuthProvider>
    );
};

export default App;

