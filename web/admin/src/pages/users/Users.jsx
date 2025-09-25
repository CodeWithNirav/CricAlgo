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
        const errorData = await r.json().catch(() => null);
        setError(`Failed to search users: ${r.status} ${errorData?.detail?.error || errorData?.detail || ''}`);
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
        const errorData = await r.json().catch(() => null);
        setError(`Failed to freeze user: ${errorData?.detail?.error || errorData?.detail || ''}`);
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
        const errorData = await r.json().catch(() => null);
        setError(`Failed to unfreeze user: ${errorData?.detail?.error || errorData?.detail || ''}`);
      }
    } catch (err) {
      setError("Error unfreezing user: " + err.message);
    }
  }

  async function deleteUser(userId, username) {
    // Double confirmation for safety
    const confirm1 = window.confirm(
      `⚠️ WARNING: This will permanently delete user "${username}" and ALL their data!\n\n` +
      `This includes:\n` +
      `• User account\n` +
      `• Wallet and balances\n` +
      `• Contest entries\n` +
      `• Transaction history\n` +
      `• Chat mappings\n\n` +
      `This action CANNOT be undone!\n\n` +
      `Are you sure you want to continue?`
    );
    
    if (!confirm1) return;
    
    const confirm2 = window.confirm(
      `FINAL CONFIRMATION: You are about to permanently delete user "${username}"\n\n` +
      `Type "DELETE" in the next prompt to confirm.`
    );
    
    if (!confirm2) return;
    
    const finalConfirm = window.prompt(
      `Type "DELETE" to confirm deletion of user "${username}":`
    );
    
    if (finalConfirm !== "DELETE") {
      alert("Deletion cancelled. You must type 'DELETE' exactly to confirm.");
      return;
    }
    
    try {
      const r = await fetch(`/api/v1/admin/users/${userId}`, {
        method: "DELETE",
        headers: { 
          Authorization: "Bearer " + sessionStorage.getItem("admin_token"),
          "Content-Type": "application/json"
        }
      });
      
      if (r.ok) {
        const result = await r.json();
        alert(`✅ ${result.message}`);
        await search(); // Reload the list
      } else {
        const errorData = await r.json().catch(() => null);
        setError(`Failed to delete user: ${errorData?.detail?.error || errorData?.detail || ''}`);
      }
    } catch (err) {
      setError("Error deleting user: " + err.message);
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
                      <button
                        className="text-sm bg-red-800 text-white px-3 py-1 rounded hover:bg-red-900"
                        onClick={() => deleteUser(u.id, u.username)}
                        title="⚠️ Permanently delete user and all data"
                      >
                        🗑️ Delete
                      </button>
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
