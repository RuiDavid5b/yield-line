import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { api, setCsrfToken } from "../api/client";

type User = {
  email: string;
};

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  verify: (email: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(
  undefined,
);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function restoreSession() {
      try {
        const currentUser = await api.me();
        setUser(currentUser);

        await api.csrf();
      } catch {
        setUser(null);
        setCsrfToken(null);
      } finally {
        setLoading(false);
      }
    }

    restoreSession();
  }, []);

  async function login(email: string, password: string) {
    const result = await api.login(email, password);

    setUser({
      email: result.email,
    });
  }

  async function register(email: string, password: string) {
    await api.register(email, password);
  }

  async function verify(email: string, code: string) {
    await api.verify(email, code);
  }

  async function logout() {
    try {
      await api.logout();
    } finally {
      setUser(null);
      setCsrfToken(null);
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        verify,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used within an AuthProvider",
    );
  }

  return context;
}
