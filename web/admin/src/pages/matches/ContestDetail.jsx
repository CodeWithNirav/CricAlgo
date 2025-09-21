import React, {useEffect, useState} from "react";

export default function ContestDetail({contestId}){
  const [contest,setContest] = useState(null);
  const [entries,setEntries] = useState([]);
  const [selected,setSelected] = useState([]);
  
  useEffect(()=>{ 
    if(!contestId) return; 
    fetch(`/api/v1/admin/contests/${contestId}`,{
      headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r=>r.json())
    .then(d=>setContest(d))
    .catch(err => console.error("Failed to fetch contest:", err));
    
    fetch(`/api/v1/admin/contests/${contestId}/entries`,{
      headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r=>r.json())
    .then(d=>setEntries(d))
    .catch(err => console.error("Failed to fetch entries:", err));
  },[contestId]);
  
  function toggle(eid){ 
    setSelected(s=> s.includes(eid)? s.filter(x=>x!==eid): [...s,eid]) 
  }
  
  async function selectWinners(){
    try {
      await fetch(`/api/v1/admin/contests/${contestId}/select_winners`,{
        method:"POST",
        headers:{
          "Content-Type":"application/json",
          "Authorization":"Bearer "+sessionStorage.getItem("admin_token")
        }, 
        body: JSON.stringify({winners:selected})
      });
      alert("Winners selected");
    } catch (err) {
      console.error("Failed to select winners:", err);
      alert("Failed to select winners");
    }
  }
  
  async function settle(){
    try {
      await fetch(`/api/v1/admin/contests/${contestId}/settle`,{
        method:"POST", 
        headers:{"Authorization":"Bearer "+sessionStorage.getItem("admin_token")}
      });
      alert("Settle requested");
    } catch (err) {
      console.error("Failed to settle contest:", err);
      alert("Failed to settle contest");
    }
  }
  
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Contest {contestId}</h2>
      {contest && <div className="mb-4 bg-white p-3 rounded">
        <div className="mb-2"><strong>{contest.title}</strong></div>
        <div>Entry fee: {contest.entry_fee}</div>
        <div>Prize structure: {JSON.stringify(contest.prize_structure)}</div>
      </div>}
      <div className="mb-4">
        <button onClick={selectWinners} className="bg-blue-600 text-white px-3 py-1 rounded mr-2">Select Winners</button>
        <button onClick={settle} className="bg-green-600 text-white px-3 py-1 rounded">Settle Contest</button>
        <a className="ml-4 text-sm text-gray-700" href={`/api/v1/admin/contests/${contestId}/export`}>Export P&L CSV</a>
      </div>
      <h3 className="text-lg font-semibold mb-2">Entrants</h3>
      <ul>
        {entries.map(en=>(
          <li key={en.id} className="border p-2 rounded mb-2 bg-white flex justify-between">
            <div>{en.telegram_id || en.username} — {en.amount_debited}</div>
            <div><input type="checkbox" checked={selected.includes(en.id)} onChange={()=>toggle(en.id)} /></div>
          </li>
        ))}
      </ul>
    </div>
  );
}
