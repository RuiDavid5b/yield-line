import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import logo from "../assets/logo_extended.svg";

export default function Navbar() {
  const { user, logout, apiKeyStatus } = useAuth();
  const navigate = useNavigate();

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;

    function handleClickOutside(event: MouseEvent) {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node)
      ) {
        setMenuOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMenuOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [menuOpen]);

  async function handleLogout() {
    setMenuOpen(false);

    try {
      await logout();
      navigate("/login");
    } catch {
      navigate("/login");
    }
  }

  const needsApiKey = apiKeyStatus !== null && !apiKeyStatus.has_key;

  return (
    <header className="navbar">
      <Link to="/" className="navbar-brand">
        <img src={logo} alt="YieldLine" />
      </Link>

      <nav className="navbar-actions" aria-label="Account navigation">
        {user ? (
          <div className="profile-menu" ref={menuRef}>
            <button
              type="button"
              className="profile-button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              aria-label="Open account menu"
            >
              <span className="profile-avatar" aria-hidden="true">
                {user.email.charAt(0).toUpperCase()}
              </span>
              {needsApiKey && <span className="settings-badge" aria-hidden="true" />}
            </button>

            {menuOpen && (
              <div className="profile-dropdown" role="menu">
                <div className="profile-email">
                  {user.email}
                </div>

                <div className="profile-divider" />

                <Link
                  to="/settings"
                  className="profile-menu-item"
                  role="menuitem"
                  onClick={() => setMenuOpen(false)}
                >
                  Settings
                  {needsApiKey && (
                    <span
                      className="settings-badge"
                      title="Add an API key to use chat"
                      aria-label="API key required"
                    />
                  )}
                </Link>

                <button
                  type="button"
                  className="profile-menu-item"
                  role="menuitem"
                  onClick={handleLogout}
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        ) : (
          <>
            <Link to="/login" className="navbar-link">
              Login
            </Link>

            <Link to="/register" className="navbar-register">
              Register
            </Link>
          </>
        )}
      </nav>
    </header>
  );
}
