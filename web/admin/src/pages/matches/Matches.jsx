import React, {useEffect, useState} from "react";

export default function Matches(){
  const [matches,setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(()=>{ 
    console.log("Matches component loaded");
    console.log("Admin token:", sessionStorage.getItem("admin_token"));
    
    setLoading(true);
    setError(null);
    
    fetch("/api/v1/admin/matches",{
      headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r => {
      console.log("API response status:", r.status);
      if (!r.ok) {
        return r.json().then(errorData => {
          throw new Error(`HTTP ${r.status}: ${errorData?.detail?.error || errorData?.detail || r.statusText}`);
        });
      }
      return r.json();
    })
    .then(d => {
      console.log("API response data:", d);
      setMatches(d);
      setLoading(false);
    })
    .catch(err => {
      console.error("Failed to fetch matches:", err);
      setError(err.message);
      setLoading(false);
    });
  },[]);
  
  if (loading) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-semibold mb-4">Matches</h2>
        <div className="text-gray-600">Loading matches...</div>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-semibold mb-4">Matches</h2>
        <div className="text-red-600 mb-4">Error: {error}</div>
        <div className="text-sm text-gray-600">
          <p>Debug info:</p>
          <p>Token: {sessionStorage.getItem("admin_token") ? "Present" : "Missing"}</p>
          <p>API URL: /api/v1/admin/matches</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Matches</h2>
      <div className="mb-4">
        <button 
          className="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
          onClick={() => {
            const title = prompt("Enter match title:");
            const startTime = prompt("Enter start time (YYYY-MM-DDTHH:MM:SSZ):");
            if (title && startTime) {
              fetch("/api/v1/admin/matches", {
                method: "POST",
                headers: {
                  "Content-Type": "application/json",
                  "Authorization": "Bearer " + sessionStorage.getItem("admin_token")
                },
                body: JSON.stringify({
                  title: title,
                  start_time: startTime,
                  external_id: "manual-" + Date.now()
                })
              })
              .then(r => r.json())
              .then(data => {
                alert("Match created successfully!");
                window.location.reload();
              })
              .catch(err => {
                alert("Error creating match: " + err.message);
              });
            }
          }}
        >
          Create Match
        </button>
      </div>
      <div className="mb-4 text-sm text-gray-600">
        Found {matches.length} matches
      </div>
      <ul>
        {matches.map(m=>(
          <li key={m.id} className="mb-2 border p-2 rounded bg-white">
            <div className="flex justify-between">
              <div>
                <div className="font-semibold">{m.title || `Match ${m.id}`}</div>
                <div className="text-sm text-gray-600">{m.starts_at || "Time not set"}</div>
                <div className="text-sm">
                  <span className={`px-2 py-1 rounded text-xs ${
                    m.status === 'scheduled' ? 'bg-blue-100 text-blue-800' :
                    m.status === 'live' ? 'bg-green-100 text-green-800' :
                    m.status === 'finished' ? 'bg-gray-100 text-gray-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {m.status?.toUpperCase() || 'UNKNOWN'}
                  </span>
                </div>
              </div>
              <div className="space-x-2">
                <button 
                  className="text-blue-600 hover:text-blue-800 underline"
                  onClick={() => {
                    window.location.hash = `match/${m.id}`;
                  }}
                >
                  View Contests
                </button>
                {m.status !== 'finished' && (
                  <button 
                    className="text-red-600 hover:text-red-800 underline"
                    onClick={() => {
                      if (confirm(`Are you sure you want to mark match "${m.title}" as finished?`)) {
                        fetch(`/api/v1/admin/matches/${m.id}/finish`, {
                          method: "POST",
                          headers: {
                            "Content-Type": "application/json",
                            "Authorization": "Bearer " + sessionStorage.getItem("admin_token")
                          }
                        })
                        .then(r => r.json())
                        .then(data => {
                          alert("Match marked as finished successfully!");
                          window.location.reload();
                        })
                        .catch(err => {
                          alert("Error finishing match: " + err.message);
                        });
                      }
                    }}
                  >
                    Finish Match
                  </button>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}