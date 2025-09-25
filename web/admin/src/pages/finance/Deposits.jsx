import React, {useEffect, useState} from "react";
export default function Deposits(){
  const [items,setItems] = useState([]);
  const [loading,setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(()=>{ 
    fetch("/api/v1/admin/deposits",{
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
  
  async function act(id,action,note="",amount=""){
    try {
      const body = {note};
      if (action === "approve" && amount) {
        body.amount = parseFloat(amount);
      }
      
      const response = await fetch("/api/v1/admin/deposits/"+id+"/"+action,{
        method:"POST",
        headers:{"Content-Type":"application/json","Authorization":"Bearer "+sessionStorage.getItem("admin_token")}, 
        body: JSON.stringify(body)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
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
      <h2 className="text-xl font-semibold mb-4">Manual Deposit Approvals</h2>
      <table className="min-w-full bg-white">
        <thead><tr><th>ID</th><th>User</th><th>Tx Hash</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead>
        <tbody>
        {items.map(it=>(
          <tr key={it.id} className="border-t">
            <td className="p-2">{it.id}</td>
            <td className="p-2">
              <div>
                <div>@{it.username || 'Unknown'}</div>
                <div className="text-sm text-gray-500">ID: {it.telegram_id}</div>
              </div>
            </td>
            <td className="p-2">
              <div className="font-mono text-sm break-all max-w-xs">
                {it.tx_hash}
              </div>
            </td>
            <td className="p-2">
              <input 
                type="number" 
                step="0.01" 
                placeholder="Enter amount" 
                className="w-24 px-2 py-1 border rounded"
                id={`amount-${it.id}`}
                defaultValue={it.amount || ""}
              />
            </td>
            <td className="p-2">
              <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-sm">
                Pending
              </span>
            </td>
            <td className="p-2">
              <button 
                className="mr-2 bg-green-600 text-white px-3 py-1 rounded text-sm" 
                onClick={()=>{
                  const amount = document.getElementById(`amount-${it.id}`).value;
                  if (!amount || parseFloat(amount) <= 0) {
                    alert("Please enter a valid amount");
                    return;
                  }
                  const note = prompt("Approval note (optional):");
                  act(it.id,"approve",note||"",amount);
                }}
              >
                Approve
              </button>
              <button 
                className="bg-red-600 text-white px-3 py-1 rounded text-sm" 
                onClick={()=>{ 
                  const note = prompt("Rejection reason:");
                  if (note !== null) {
                    act(it.id,"reject",note||"");
                  }
                }}
              >
                Reject
              </button>
            </td>
          </tr>
        ))}
        </tbody>
      </table>
      {items.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No pending manual deposits
        </div>
      )}
    </div>
  );
}
