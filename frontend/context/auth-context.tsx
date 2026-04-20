"use client"

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import api from "@/lib/axios-config";

interface User {
  email: string;
  full_name?: string;
  disabled?: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (token: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUser = async (authToken: string) => {
    try {
      const response = await api.get("/users/me", {
        headers: { Authorization: `Bearer ${authToken}` }
      });
      setUser(response.data);
    } catch (error) {
      console.error("Failed to fetch user:", error);
      logout();
    }
  };

  useEffect(() => {
    const storedToken = localStorage.getItem("auth_token");
    if (storedToken) {
      setToken(storedToken);
      fetchUser(storedToken).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (newToken: string) => {
    localStorage.setItem("auth_token", newToken);
    setToken(newToken);
    await fetchUser(newToken);
  };

  const logout = () => {
    localStorage.removeItem("auth_token");
    setToken(null);
    setUser(null);
  };

  const value = {
    user,
    token,
    loading,
    login,
    logout,
    isAuthenticated: !!token,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
