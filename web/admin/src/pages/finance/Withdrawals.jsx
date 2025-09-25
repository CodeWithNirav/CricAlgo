import React, {useEffect, useState} from "react";
export default function Withdrawals(){
  const [items,setItems] = useState([]);
  
  const fetchWithdrawals = async () => {
    try {
      const response = await fetch("/api/v1/admin/withdrawals?status=pending",{
        headers:{Authorization: "Bearer "+sessionStorage.getItem("admin_token")}
      });
      const data = await response.json();
      setItems(data);
    } catch (error) {
      console.error("Failed to fetch withdrawals:", error);
    }
  };
  
  useEffect(() => {
    fetchWithdrawals();
  }, []);
  async function act(id,action){
    console.log(`Processing ${action} for withdrawal ${id}`);
    let body = {};
    if (action === "reject") {
      const note = prompt("Enter rejection reason:");
      if (!note) return;
      body = { note: note };
    }
    
    try {
      const url = `/api/v1/admin/withdrawals/${id}/${action}`;
      console.log(`Calling API: ${url}`);
      const response = await fetch(url,{
        method:"POST",
        headers:{
          "Authorization":"Bearer "+sessionStorage.getItem("admin_token"),
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      });
      
      console.log(`Response status: ${response.status}`);
      if (response.ok) {
        const result = await response.json();
        console.log(`Success response:`, result);
        alert(`${action === 'approve' ? 'Approved' : 'Rejected'} withdrawal successfully!`);
        // Refresh the withdrawals list to get updated data from server
        await fetchWithdrawals();
      } else {
        const errorData = await response.json();
        console.error(`Error response:`, errorData);
        alert(`Error: ${errorData.detail || 'Failed to process withdrawal'}`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
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
