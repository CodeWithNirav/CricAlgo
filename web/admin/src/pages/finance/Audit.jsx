import React, {useEffect, useState} from "react";
export default function Audit(){
  const [items,setItems] = useState([]);
  useEffect(()=>{ fetch("/api/v1/admin/audit",{headers:{Authorization: "Bearer "+sessionStorage.getItem("admin_token")}}).then(r=>r.json()).then(d=>setItems(d)) },[]);
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Audit Log</h2>
      <table className="min-w-full bg-white">
        <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Details</th></tr></thead>
        <tbody>
        {items.map(it=>(
          <tr key={it.id} className="border-t">
            <td className="p-2">{it.created_at}</td>
            <td className="p-2">{it.admin_username||it.actor}</td>
            <td className="p-2">{it.action}</td>
            <td className="p-2">{JSON.stringify(it.details)}</td>
          </tr>
        ))}
        </tbody>
      </table>
      <a className="inline-block mt-4 bg-blue-600 text-white px-3 py-1 rounded" href="/api/v1/admin/audit/export">Export CSV</a>
    </div>
  );
}
