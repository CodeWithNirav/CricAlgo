import React, {useEffect, useState} from "react";
export default function Deposits(){
  const [items,setItems] = useState([]);
  const [loading,setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(()=>{ 
    fetch("/api/v1/admin/deposits?status=pending",{
      headers:{Authorization: "Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r => {
      if (!r.ok) {
        throw new Error(`HTTP ${r.status}: ${r.statusText}`);
      }
      return r.json();
    })
    .then(d=>{
      setItems(d);
      setLoading(false);
    })
    .catch(err => {
      console.error("Deposits API error:", err);
      setError(err.message);
      setLoading(false);
    });
  },[]);
  
  async function act(id,action,note=""){
    try {
      await fetch("/api/v1/admin/deposits/"+id+"/"+action,{
        method:"POST",
        headers:{"Content-Type":"application/json","Authorization":"Bearer "+sessionStorage.getItem("admin_token")}, 
        body: JSON.stringify({note})
      });
      setItems(items.filter(i=>i.id!==id));
    } catch (err) {
      console.error("Action error:", err);
      alert("Action failed: " + err.message);
    }
  }
  
  if(loading) return <div className="p-4">Loading...</div>;
  if(error) return <div className="p-4 text-red-600">Error: {error}</div>;
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Pending Deposits</h2>
      <table className="min-w-full bg-white">
        <thead><tr><th>ID</th><th>User</th><th>Amount</th><th>Tx</th><th>Action</th></tr></thead>
        <tbody>
        {items.map(it=>(
          <tr key={it.id} className="border-t">
            <td className="p-2">{it.id}</td>
            <td className="p-2">{it.telegram_id || it.username}</td>
            <td className="p-2">{it.amount}</td>
            <td className="p-2">{it.tx_hash}</td>
            <td className="p-2">
              <button className="mr-2 bg-green-600 text-white px-2 py-1 rounded" onClick={()=>act(it.id,"approve")}>Approve</button>
              <button className="bg-red-600 text-white px-2 py-1 rounded" onClick={()=>{ const n=prompt("Rejection note"); act(it.id,"reject",n||"")}}>Reject</button>
            </td>
          </tr>
        ))}
        </tbody>
      </table>
    </div>
  );
}
