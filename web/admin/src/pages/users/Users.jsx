import React, { useState, useEffect } from "react";

export default function Users() {
  const [q, setQ] = useState("");
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function search() {
    try {
      setLoading(true);
      const r = await fetch(`/api/v1/admin/users?q=${encodeURIComponent(q)}`, {
        headers: { Authorization: "Bearer " + sessionStorage.getItem("admin_token") }
      });
      if (r.ok) {
        const data = await r.json();
        setUsers(data);
        setError(null);
      } else {
        const txt = await r.text().catch(() => null);
        setError(`Failed to search users: ${r.status} ${txt || ''}`);
        return;
      }
    } catch (err) {
      setError("Error searching users: " + err.message);
    } finally {
      setLoading(false);
    }
  }

  async function freezeUser(userId) {
    try {
      const r = await fetch(`/api/v1/admin/users/${userId}/freeze`, {
        method: "POST",
        headers: { 
          Authorization: "Bearer " + sessionStorage.getItem("admin_token"),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ reason: "Manual freeze" })
      });
      if (r.ok) {
        await search(); // Reload the list
      } else {
        setError("Failed to freeze user");
      }
    } catch (err) {
      setError("Error freezing user: " + err.message);
    }
  }

  async function unfreezeUser(userId) {
    try {
      const r = await fetch(`/api/v1/admin/users/${userId}/unfreeze`, {
        method: "POST",
        headers: { 
          Authorization: "Bearer " + sessionStorage.getItem("admin_token"),
          "Content-Type": "application/json"
        }
      });
      if (r.ok) {
        await search(); // Reload the list
      } else {
        setError("Failed to unfreeze user");
      }
    } catch (err) {
      setError("Error unfreezing user: " + err.message);
    }
  }

  useEffect(() => {
    search();
  }, []);

  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold">Users</h2>
      <div className="my-4">
        <div className="flex gap-2">
          <input
            className="border border-gray-300 px-3 py-2 rounded-md flex-1"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search by username or telegram ID..."
          />
          <button
            className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700"
            onClick={search}
          >
            Search
          </button>
        </div>
      </div>
      {error && (
        <div className="mt-3 p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          {error}
        </div>
      )}
      {loading ? (
        <div className="mt-3">Loading...</div>
      ) : (
        <div className="mt-3">
          {users.length === 0 ? (
            <div className="text-gray-500">No users found</div>
          ) : (
            <ul className="space-y-2">
              {users.map((u) => (
                <li key={u.id} className="border p-3 rounded bg-white shadow-sm">
                  <div className="flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-lg">{u.username}</div>
                      <div className="text-sm text-gray-600">
                        Telegram ID: {u.telegram_id} | 
                        Status: <span className={`font-medium ${u.status === 'ACTIVE' ? 'text-green-600' : 'text-red-600'}`}>
                          {u.status}
                        </span> |
                        Created: {new Date(u.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="space-x-2">
                      <a
                        className="text-blue-600 hover:text-blue-800"
                        href={`#user/${u.id}`}
                      >
                        View Details
                      </a>
                      {u.status === 'ACTIVE' ? (
                        <button
                          className="text-sm bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700"
                          onClick={() => freezeUser(u.id)}
                        >
                          Freeze
                        </button>
                      ) : (
                        <button
                          className="text-sm bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
                          onClick={() => unfreezeUser(u.id)}
                        >
                          Unfreeze
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
