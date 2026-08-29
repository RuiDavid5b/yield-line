import createClient from "openapi-fetch";
import type { paths } from "./schema";

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

  prices: async (cik: string) => {
    const { data, error } = await client.GET(
      "/companies/{cik}/prices",
      {
        params: {
          path: { cik },
        },
      },
    );

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

  askAgent: async (question: string) => {
    const { data, error } = await client.POST("/agent/ask", {
      body: {
        question,
      },
    });

    if (error) {
      throw new Error("Failed to ask agent");
    }

    return data;
  },
};
