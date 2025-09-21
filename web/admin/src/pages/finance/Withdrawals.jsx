import React, {useEffect, useState} from "react";
export default function Withdrawals(){
  const [items,setItems] = useState([]);
  useEffect(()=>{ fetch("/api/v1/admin/withdrawals?status=pending",{headers:{Authorization: "Bearer "+sessionStorage.getItem("admin_token")}}).then(r=>r.json()).then(d=>setItems(d)) },[]);
  async function act(id,action){
    await fetch(`/api/v1/admin/withdrawals/${id}/${action}`,{method:"POST",headers:{"Authorization":"Bearer "+sessionStorage.getItem("admin_token")}});
    setItems(items.filter(i=>i.id!==id));
  }
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Pending Withdrawals</h2>
      <table className="min-w-full bg-white">
        <thead><tr><th>ID</th><th>User</th><th>Amount</th><th>Address</th><th>Action</th></tr></thead>
        <tbody>
        {items.map(it=>(
          <tr key={it.id} className="border-t">
            <td className="p-2">{it.id}</td>
            <td className="p-2">{it.telegram_id || it.username}</td>
            <td className="p-2">{it.amount}</td>
            <td className="p-2">{it.address}</td>
            <td className="p-2">
              <button className="mr-2 bg-green-600 text-white px-2 py-1 rounded" onClick={()=>act(it.id,"approve")}>Approve</button>
              <button className="bg-red-600 text-white px-2 py-1 rounded" onClick={()=>act(it.id,"reject")}>Reject</button>
            </td>
          </tr>
        ))}
        </tbody>
      </table>
    </div>
  );
}
