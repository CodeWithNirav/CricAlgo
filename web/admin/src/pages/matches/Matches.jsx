import React, {useEffect, useState} from "react";

export default function Matches(){
  const [matches,setMatches] = useState([]);
  
  useEffect(()=>{ 
    fetch("/api/v1/admin/matches",{
      headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r=>r.json())
    .then(d=>setMatches(d))
    .catch(err => console.error("Failed to fetch matches:", err));
  },[]);
  
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Matches</h2>
      <div className="mb-4">
        <a className="bg-green-600 text-white px-3 py-1 rounded" href="#create-match">Create Match</a>
      </div>
      <ul>
        {matches.map(m=>(
          <li key={m.id} className="mb-2 border p-2 rounded bg-white">
            <div className="flex justify-between">
              <div>
                <div className="font-semibold">{m.title || `Match ${m.id}`}</div>
                <div className="text-sm text-gray-600">{m.starts_at || "Time not set"}</div>
              </div>
              <div className="space-x-2">
                <a className="text-blue-600" href={`#/match/${m.id}`}>View Contests</a>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
