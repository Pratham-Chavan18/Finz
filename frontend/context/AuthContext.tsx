"use client";

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  apiFetch,
  setAccessToken,
  setOnAuthFailure,
  refreshAccessToken,
  API_BASE_URL,
} from "@/lib/api";

export interface User {
  id: number;
  email: string;
  name: string;
  role: "USER" | "ADMIN" | string;
  is_active: boolean;
  created_at?: string;
  last_login_at?: string;
}

export interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: { email: string; password: string }) => Promise<{ success: boolean; error?: string }>;
  register: (data: { name: string; email: string; password: string }) => Promise<{ success: boolean; error?: string }>;
  logout: () => Promise<void>;
  checkSession: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Restore session on initial load or reload by reusing shared refreshAccessToken flow
  const checkSession = useCallback(async (): Promise<boolean> => {
    try {
      const refreshData = await refreshAccessToken();

      if (!refreshData?.access_token) {
        setAccessToken(null);
        setUser(null);
        setIsLoading(false);
        return false;
      }

      setAccessToken(refreshData.access_token);
      if (refreshData.user) {
        setUser(refreshData.user);
        setIsLoading(false);
        return true;
      }

      // Fetch user profile if not directly provided in refresh payload
      const meRes = await apiFetch("/api/v1/auth/me");
      if (meRes.ok) {
        const userData = await meRes.json();
        setUser(userData);
        setIsLoading(false);
        return true;
      }

      setAccessToken(null);
      setUser(null);
      setIsLoading(false);
      return false;
    } catch {
      setAccessToken(null);
      setUser(null);
      setIsLoading(false);
      return false;
    }
  }, []);

  useEffect(() => {
    // Register global auth failure listener to clear state
    setOnAuthFailure(() => {
      setUser(null);
    });

    checkSession();
  }, [checkSession]);

  const login = async (credentials: { email: string; password: string }) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(credentials),
        credentials: "include",
      });

      const data = await res.json();
      if (!res.ok) {
        setIsLoading(false);
        return { success: false, error: data.detail || "Authentication failed. Please check your credentials." };
      }

      setAccessToken(data.access_token);
      setUser(data.user);
      setIsLoading(false);
      return { success: true };
    } catch (err: any) {
      setIsLoading(false);
      return { success: false, error: "Network error. Could not connect to authentication server." };
    }
  };

  const register = async (data: { name: string; email: string; password: string }) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        credentials: "include",
      });

      const resData = await res.json();
      if (!res.ok) {
        setIsLoading(false);
        return { success: false, error: resData.detail || "Registration failed." };
      }

      setAccessToken(resData.access_token);
      setUser(resData.user);
      setIsLoading(false);
      return { success: true };
    } catch (err: any) {
      setIsLoading(false);
      return { success: false, error: "Network error. Could not reach server." };
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {
      // Ignore network errors during logout
    } finally {
      setAccessToken(null);
      setUser(null);
      setIsLoading(false);
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        register,
        logout,
        checkSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
