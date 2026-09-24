import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

type VerifyLocationState = {
  email?: string;
};

export default function VerifyPage() {
  const { verify } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const state = location.state as VerifyLocationState | null;

  const [email, setEmail] = useState(state?.email ?? "");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setSubmitting(true);

    try {
      await verify(email, code);

      navigate("/login", {
        state: {
          message: "Your email has been verified. You can now log in.",
        },
      });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Verification failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-card">
        <h1>Verify your email</h1>

        <p className="auth-description">
          Enter the verification code sent to your email address.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="verify-email">
            Email
          </label>

          <input
            id="verify-email"
            name="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            required
            disabled={submitting}
          />

          <label htmlFor="verification-code">
            Verification code
          </label>

          <input
            id="verification-code"
            name="code"
            type="text"
            value={code}
            onChange={(event) => setCode(event.target.value)}
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            disabled={submitting}
          />

          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="auth-submit"
            disabled={submitting}
          >
            {submitting ? "Verifying..." : "Verify email"}
          </button>
        </form>

        <p className="auth-footer">
          Already verified?{" "}
          <Link to="/login">
            Log in
          </Link>
        </p>
      </section>
    </main>
  );
}
