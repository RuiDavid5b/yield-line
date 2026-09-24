import { BrowserRouter, Route, Routes } from "react-router-dom";

import Navbar from "./components/Navbar";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />

      <Routes>
        <Route path="/" element={<DashboardPage />} />

        <Route
          path="/login"
          element={<LoginPage />}
        />

        <Route
          path="/register"
          element={<div>Register page coming next</div>}
        />

        <Route
          path="/verify"
          element={<div>Verify page coming next</div>}
        />
      </Routes>
    </BrowserRouter>
  );
}
