import React, { useState, useEffect } from "react";

export default function InviteCodes() {
  const [codes, setCodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function load() {
    try {
      setLoading(true);
      const r = await fetch("/api/v1/admin/invite_codes", {
        headers: { Authorization: "Bearer " + sessionStorage.getItem("admin_token") }
      });
      if (r.ok) {
        const data = await r.json();
        setCodes(data);
        setError(null);
      } else {
        setError("Failed to load invite codes");
      }
    } catch (err) {
      setError("Error loading invite codes: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function disableCode(code) {
    try {
      const r = await fetch(`/api/v1/admin/invite_codes/${code}/disable`, {
        method: "POST",
        headers: { Authorization: "Bearer " + sessionStorage.getItem("admin_token") }
      });
      if (r.ok) {
        await load(); // Reload the list
      } else {
        setError("Failed to disable code");
      }
    } catch (err) {
      setError("Error disabling code: " + err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (loading) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-semibold">Invite Codes</h2>
        <div className="mt-3">Loading...</div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold">Invite Codes</h2>
      {error && (
        <div className="mt-3 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}
      <div className="mt-3">
        {codes.length === 0 ? (
          <div className="text-gray-500">No invite codes found</div>
        ) : (
          <ul className="space-y-2">
            {codes.map((c) => (
              <li key={c.code} className="border p-3 rounded bg-white shadow-sm">
                <div className="flex justify-between items-center">
                  <div>
                    <div className="font-semibold text-lg">{c.code}</div>
                    <div className="text-sm text-gray-600">
                      Uses: {c.uses}/{c.max_uses || "∞"} | 
                      Status: {c.enabled ? "Enabled" : "Disabled"} |
                      Created: {new Date(c.created_at).toLocaleDateString()}
                    </div>
                    {c.expires_at && (
                      <div className="text-sm text-gray-500">
                        Expires: {new Date(c.expires_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                  <div>
                    {c.enabled && (
                      <button
                        className="text-sm bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700"
                        onClick={() => disableCode(c.code)}
                      >
                        Disable
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
