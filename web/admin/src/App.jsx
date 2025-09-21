import React, { useState, useEffect } from "react";
import Login from "./pages/Login";
import Deposits from "./pages/finance/Deposits";
import Withdrawals from "./pages/finance/Withdrawals";
import Audit from "./pages/finance/Audit";

export default function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [currentPage, setCurrentPage] = useState("login");

  useEffect(() => {
    const token = sessionStorage.getItem("admin_token");
    if (token) {
      setIsLoggedIn(true);
      // Check hash for page routing
      const hash = window.location.hash.substring(1);
      if (hash && ["deposits", "withdrawals", "audit"].includes(hash)) {
        setCurrentPage(hash);
      } else {
        setCurrentPage("deposits");
      }
    }
  }, []);

  const handleLogout = () => {
    sessionStorage.removeItem("admin_token");
    setIsLoggedIn(false);
    setCurrentPage("login");
    window.location.hash = "";
  };

  if (!isLoggedIn) {
    return <div className="min-h-screen flex items-center justify-center"><Login/></div>;
  }

  const renderPage = () => {
    switch (currentPage) {
      case "deposits":
        return <Deposits />;
      case "withdrawals":
        return <Withdrawals />;
      case "audit":
        return <Audit />;
      default:
        return <Deposits />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center">
                <h1 className="text-xl font-semibold">CricAlgo Admin</h1>
              </div>
              <div className="hidden sm:ml-6 sm:flex sm:space-x-8">
                <a
                  href="#deposits"
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    currentPage === "deposits"
                      ? "border-blue-500 text-gray-900"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}
                  onClick={() => setCurrentPage("deposits")}
                >
                  Deposits
                </a>
                <a
                  href="#withdrawals"
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    currentPage === "withdrawals"
                      ? "border-blue-500 text-gray-900"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}
                  onClick={() => setCurrentPage("withdrawals")}
                >
                  Withdrawals
                </a>
                <a
                  href="#audit"
                  className={`inline-flex items-center px-1 pt-1 border-b-2 text-sm font-medium ${
                    currentPage === "audit"
                      ? "border-blue-500 text-gray-900"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}
                  onClick={() => setCurrentPage("audit")}
                >
                  Audit
                </a>
              </div>
            </div>
            <div className="flex items-center">
              <button
                onClick={handleLogout}
                className="bg-red-600 text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-red-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {renderPage()}
      </main>
    </div>
  );
}
