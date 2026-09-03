import createClient from "openapi-fetch";
import type { paths } from "./schema";
import type { Company } from "./types";

const client = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_URL || "http://localhost:8000",
});

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
};
