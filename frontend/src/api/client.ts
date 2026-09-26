import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { Company } from "./types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export type LLMProvider =
  paths["/auth/me/api-key"]["put"]["requestBody"]["content"]["application/json"]["provider"];

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

const client = createClient<paths>({
  baseUrl: API_URL,
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
  },
  fetch: async (request) => {
    const method = request.method.toUpperCase();

    if (
      csrfToken &&
      ["POST", "PUT", "PATCH", "DELETE"].includes(method)
    ) {
      request.headers.set("X-CSRF-Token", csrfToken);
    }

    return fetch(request);
  },
});

function errorMessage(
  detail: unknown,
  fallback: string,
): string {
  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .filter(
        (item): item is { msg: string } =>
          typeof item === "object" &&
          item !== null &&
          "msg" in item &&
          typeof item.msg === "string",
      )
      .map((item) => item.msg);

    if (messages.length > 0) {
      return messages.join(", ");
    }
  }

  return fallback;
}

export const api = {
  listCompanies: async () => {
    const { data, error } = await client.GET("/companies");

    if (error) {
      throw new Error("Failed to fetch companies");
    }

    return data;
  },

  resolveCompany: async (query: string) => {
    const { data, error } = await client.GET("/companies/resolve", {
      params: {
        query: { query },
      },
    });

    if (error) {
      throw new Error("Failed to resolve company");
    }

    return data;
  },

  latestDigest: async () => {
    const { data, error } = await client.GET("/digest/latest");

    if (error) {
      throw new Error("Failed to fetch latest digest");
    }

    return data;
  },

  digestForDate: async (date: string) => {
    const { data, error } = await client.GET("/digest/{date}", {
      params: {
        path: { date },
      },
    });
    if (error) {
      throw new Error("Failed to fetch digest for date");
    }
    return data;
  },

  periodReturns: async (start: string, end: string) => {
    const { data, error } = await client.GET("/companies/returns", {
      params: {
        query: {
          start_date: start,
          end_date: end,
        },
      },
    });

    if (error) {
      throw new Error("Failed to fetch returns");
    }

    return data;
  },

  latestPrices: async () => {
    const { data, error } = await client.GET("/companies/latest-prices");
    if (error) throw new Error("Failed to fetch latest prices");
    return data;
  },

  prices: async (cik: string, start?: string, end?: string) => {
    const { data, error } = await client.GET("/companies/{cik}/prices", {
      params: {
        path: { cik },
        query: { start_date: start, end_date: end },
      },
    });
    if (error) {
      throw new Error("Failed to fetch prices");
    }
    return data;
  },

  anomalies: async (
    cik: string,
    start: string,
    end: string,
  ) => {
    const { data, error } = await client.GET(
      "/companies/{cik}/anomalies",
      {
        params: {
          path: { cik },
          query: {
            start_date: start,
            end_date: end,
            limit: 50,
          },
        },
      },
    );

    if (error) {
      throw new Error("Failed to fetch anomalies");
    }

    return data;
  },

  latestAnomalies: async () => {
    const { data, error } =
      await client.GET("/anomalies/latest");

    if (error) {
      throw new Error("Failed to fetch latest anomalies");
    }

    return data;
  },

  askAgent: async (question: string, threadId: string, selectedCompany: Company | null) => {
    const { data, error } = await client.POST("/agent/ask", {
      body: {
        question,
        thread_id: threadId,
        selected_company: selectedCompany
          ? { cik: selectedCompany.cik, ticker: selectedCompany.ticker, name: selectedCompany.name }
          : null,
      },
    });
    if (error) {
      throw new Error("Failed to ask agent");
    }
    return data;
  },

  register: async (email: string, password: string) => {
    const { data, error } = await client.POST("/auth/register", {
      body: {
        email,
        password,
      },
    });

    if (error) {
      throw new Error(
        errorMessage(error.detail, "Registration failed"),
      );
    }

    return data;
  },

  verify: async (email: string, code: string) => {
    const { data, error } = await client.POST("/auth/verify", {
      body: {
        email,
        code,
      },
    });

    if (error) {
      throw new Error(
        errorMessage(error.detail, "Verification failed"),
      );
    }

    return data;
  },

  login: async (email: string, password: string) => {
    const { data, error } = await client.POST("/auth/login", {
      body: {
        email,
        password,
      },
    });

    if (error) {
      throw new Error(
        errorMessage(error.detail, "Login failed"),
      );
    }

    setCsrfToken(data.csrf_token);

    return data;
  },

  me: async () => {
    const { data, error } = await client.GET("/auth/me");

    if (error) {
      throw new Error("Not authenticated");
    }

    return data;
  },

  csrf: async () => {
    const { data, error } = await client.GET("/auth/csrf");

    if (error) {
      throw new Error("Failed to get CSRF token");
    }

    setCsrfToken(data.csrf_token);

    return data;
  },

  logout: async () => {
    const { data, error } = await client.POST("/auth/logout");

    if (error) {
      throw new Error(
        errorMessage(error.detail, "Logout failed"),
      );
    }

    setCsrfToken(null);

    return data;
  },

  getApiKeyStatus: async () => {
    const { data, error } = await client.GET("/auth/me/api-key");
    if (error) throw new Error("Failed to fetch API key status");
    return data;
  },
  
  setApiKey: async (provider: LLMProvider, model: string, apiKey: string) => {
    const { data, error } = await client.PUT("/auth/me/api-key", {
      body: { provider, model, api_key: apiKey },
    });
    if (error) throw new Error(errorMessage(error.detail, "Failed to save API key"));
    return data;
  },
  
  deleteApiKey: async () => {
    const { data, error } = await client.DELETE("/auth/me/api-key");
    if (error) throw new Error(errorMessage(error.detail, "Failed to remove API key"));
    return data;
  },
};
