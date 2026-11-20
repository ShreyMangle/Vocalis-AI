/**
 * VoxAI Authentication Context
 * Manages active session, tenant profile, and RBAC state.
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { Tenant, User, UserRole } from '../types';

interface AuthContextType {
  user: User | null;
  tenant: Tenant | null;
  role: UserRole | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; full_name: string; tenant_name: string; phone_number?: string }) => Promise<void>;
  logout: () => void;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [role, setRole] = useState<UserRole | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshProfile = async () => {
    const token = localStorage.getItem('token');
    if (!token) {
      setUser(null);
      setTenant(null);
      setRole(null);
      setIsLoading(false);
      return;
    }

    try {
      const data = await api.getMe();
      setUser(data.user);
      setTenant(data.tenant);
      setRole(data.role as UserRole);
    } catch (err) {
      console.error('Failed to restore session:', err);
      localStorage.removeItem('token');
      localStorage.removeItem('refreshToken');
      setUser(null);
      setTenant(null);
      setRole(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshProfile();
  }, []);

  const login = async (email: string, password: string) => {
    setIsLoading(true);
    try {
      const res = await api.login({ email, password });
      localStorage.setItem('token', res.access_token);
      localStorage.setItem('refreshToken', res.refresh_token);
      await refreshProfile();
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (data: {
    email: string;
    password: string;
    full_name: string;
    tenant_name: string;
    phone_number?: string;
  }) => {
    setIsLoading(true);
    try {
      const res = await api.register(data);
      localStorage.setItem('token', res.tokens.access_token);
      localStorage.setItem('refreshToken', res.tokens.refresh_token);
      setUser(res.user);
      setTenant(res.tenant);
      setRole('OWNER');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('refreshToken');
    setUser(null);
    setTenant(null);
    setRole(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        tenant,
        role,
        isAuthenticated: !!user,
        isLoading,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
