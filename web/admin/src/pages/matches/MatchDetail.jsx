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
      <a className="bg-green-600 text-white px-3 py-1 rounded" href={`#/match/${matchId}/create-contest`}>Create Contest</a>
      <ul className="mt-4">
        {contests.map(c=>(
          <li key={c.id} className="border p-2 rounded bg-white mb-2">
            <div className="flex justify-between">
              <div>
                <div className="font-semibold">{c.title || `Contest ${c.id}`}</div>
                <div className="text-sm text-gray-600">Entry: {c.entry_fee}</div>
              </div>
              <div>
                <a className="text-blue-600" href={`#/contest/${c.id}`}>Open</a>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
