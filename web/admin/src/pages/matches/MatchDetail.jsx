import React, {useEffect, useState} from "react";

export default function MatchDetail({matchId}){
  const [contests,setContests] = useState([]);
  
  useEffect(()=>{ 
    if(!matchId) return; 
    fetch(`/api/v1/admin/matches/${matchId}/contests`,{
      headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r=>r.json())
    .then(d=>setContests(d))
    .catch(err => console.error("Failed to fetch contests:", err));
  },[matchId]);
  
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Contests for Match {matchId}</h2>
      <button 
        className="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
        onClick={() => {
          const title = prompt("Enter contest title:");
          const entryFee = prompt("Enter entry fee:");
          const maxPlayers = prompt("Enter max players:");
          if (title && entryFee && maxPlayers) {
            fetch(`/api/v1/admin/matches/${matchId}/contests`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "Authorization": "Bearer " + sessionStorage.getItem("admin_token")
              },
              body: JSON.stringify({
                title: title,
                entry_fee: entryFee,
                max_players: parseInt(maxPlayers),
                prize_structure: [{"pos": 1, "pct": 100}]
              })
            })
            .then(r => {
              if (r.ok) {
                return r.json();
              } else {
                return r.json().then(errorData => {
                  throw new Error(errorData?.detail?.error || errorData?.detail || `HTTP ${r.status}`);
                });
              }
            })
            .then(data => {
              alert("Contest created successfully!");
              window.location.reload();
            })
            .catch(err => {
              console.error("Contest creation error:", err);
              const errorMessage = err.message || err.toString() || "Unknown error occurred";
              alert("Error creating contest: " + errorMessage);
            });
          }
        }}
      >
        Create Contest
      </button>
      <ul className="mt-4">
        {contests.map(c=>(
          <li key={c.id} className="border p-2 rounded bg-white mb-2">
            <div className="flex justify-between">
              <div>
                <div className="font-semibold">{c.title || `Contest ${c.id}`}</div>
                <div className="text-sm text-gray-600">Entry: {c.entry_fee}</div>
              </div>
              <div>
                <button 
                  className="text-blue-600 hover:text-blue-800 underline"
                  onClick={() => {
                    window.location.hash = `contest/${c.id}`;
                  }}
                >
                  Open
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
