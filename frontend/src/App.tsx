import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './pages/Login';
import { Register } from './pages/Register';
import { Dashboard } from './pages/Dashboard';
import { Sandbox } from './pages/Sandbox';
import { KnowledgeBase } from './pages/KnowledgeBase';
import { Appointments } from './pages/Appointments';
import { AgentConfigPage } from './pages/AgentConfig';
import { Calls } from './pages/Calls';
import { SettingsPage } from './pages/Settings';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected SaaS App Routes */}
          <Route element={<ProtectedRoute />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/sandbox" element={<Sandbox />} />
            <Route path="/appointments" element={<Appointments />} />
            <Route path="/knowledge" element={<KnowledgeBase />} />
            <Route path="/agent" element={<AgentConfigPage />} />
            <Route path="/calls" element={<Calls />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
