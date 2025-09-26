import React, {useEffect, useState} from "react";

export default function ContestDetail({contestId}){
  const [contest,setContest] = useState(null);
  const [entries,setEntries] = useState([]);
  const [selected,setSelected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  async function loadContestData() {
    if(!contestId) return;
    
    try {
      setLoading(true);
      setError(null);
      
      // Load contest details
      const contestResponse = await fetch(`/api/v1/admin/contests/${contestId}`,{
        headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
      });
      
      if (!contestResponse.ok) {
        const errorData = await contestResponse.json().catch(() => null);
        throw new Error(errorData?.detail?.error || errorData?.detail || `HTTP ${contestResponse.status}`);
      }
      
      const contestData = await contestResponse.json();
      setContest(contestData);
      
      // Load contest entries
      const entriesResponse = await fetch(`/api/v1/admin/contests/${contestId}/entries`,{
        headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
      });
      
      if (!entriesResponse.ok) {
        const errorData = await entriesResponse.json().catch(() => null);
        throw new Error(errorData?.detail?.error || errorData?.detail || `HTTP ${entriesResponse.status}`);
      }
      
      const entriesData = await entriesResponse.json();
      setEntries(entriesData);
      
    } catch (err) {
      console.error("Failed to load contest data:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }
  
  function toggle(id){
    setSelected(prev => 
      prev.includes(id) 
        ? prev.filter(x => x !== id)
        : [...prev, id]
    );
  }
  
  async function selectWinners(){
    if (selected.length === 0) {
      alert("Please select at least one winner");
      return;
    }
    
    try {
      const response = await fetch(`/api/v1/admin/contests/${contestId}/select_winners`,{
        method:"POST",
        headers:{
          "Content-Type":"application/json",
          "Authorization":"Bearer "+sessionStorage.getItem("admin_token")
        }, 
        body: JSON.stringify({winners:selected})
      });
      
      if (response.ok) {
        const result = await response.json();
        if (result.settlement && result.settlement.success) {
          alert("Winners selected and contest settled successfully! Winning amounts have been credited to the winners' accounts.");
        } else if (result.settlement_error) {
          alert(`Winners selected but settlement failed: ${result.settlement_error}. Please contact support.`);
        } else {
          alert("Winners selected successfully!");
        }
        await loadContestData(); // Reload data
        setSelected([]); // Clear selection
      } else {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail?.error || errorData?.detail || `HTTP ${response.status}`);
      }
    } catch (err) {
      console.error("Failed to select winners:", err);
      alert("Failed to select winners: " + err.message);
    }
  }
  
  
  useEffect(() => {
    loadContestData();
  }, [contestId]);
  
  if (loading) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-semibold mb-4">Contest {contestId}</h2>
        <div className="text-gray-600">Loading contest details...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <h2 className="text-xl font-semibold mb-4">Contest {contestId}</h2>
        <div className="p-3 bg-red-100 border border-red-400 text-red-700 rounded">
          Error: {error}
        </div>
        <button 
          onClick={loadContestData}
          className="mt-3 bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Contest Details</h2>
      
      {contest && (
        <div className="mb-6 bg-white p-4 rounded shadow-sm border">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h3 className="font-semibold text-lg mb-2">{contest.title || `Contest ${contest.code}`}</h3>
              <div className="space-y-1 text-sm">
                <div><strong>Code:</strong> {contest.code}</div>
                <div><strong>Entry Fee:</strong> {contest.entry_fee} {contest.currency}</div>
                <div><strong>Max Players:</strong> {contest.max_players || "Unlimited"}</div>
                {contest.user_link && (
                  <div><strong>User Link:</strong> 
                    <a href={contest.user_link} target="_blank" rel="noopener noreferrer" className="ml-1 text-blue-600 hover:underline">
                      {contest.user_link}
                    </a>
                  </div>
                )}
                <div><strong>Status:</strong> 
                  <span className={`ml-1 px-2 py-1 rounded text-xs ${
                    contest.status === 'open' ? 'bg-green-100 text-green-800' :
                    contest.status === 'closed' ? 'bg-yellow-100 text-yellow-800' :
                    contest.status === 'settled' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {contest.status?.toUpperCase()}
                  </span>
                </div>
              </div>
            </div>
            <div>
              <div className="text-sm">
                <div><strong>Prize Structure:</strong></div>
                <div className="mt-1 p-2 bg-gray-50 rounded text-xs">
                  {Object.entries(contest.prize_structure || {}).map(([rank, percentage]) => (
                    <div key={rank}>Rank {rank}: {(percentage * 100).toFixed(1)}%</div>
                  ))}
                </div>
                <div className="mt-2"><strong>Commission:</strong> {contest.commission_pct}%</div>
              </div>
            </div>
          </div>
        </div>
      )}
      
      <div className="mb-6 flex flex-wrap gap-3 items-center">
        <button 
          onClick={selectWinners} 
          className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 disabled:bg-gray-400"
          disabled={selected.length === 0}
        >
          Select Winners & Settle ({selected.length})
        </button>
        <a 
          className="text-blue-600 hover:text-blue-800 underline text-sm" 
          href={`/api/v1/admin/contests/${contestId}/export`}
          target="_blank"
        >
          Export P&L CSV
        </a>
      </div>
      
      <div className="bg-white rounded shadow-sm border">
        <div className="p-4 border-b">
          <h3 className="text-lg font-semibold">Contest Entries ({entries.length})</h3>
        </div>
        {entries.length === 0 ? (
          <div className="p-4 text-gray-500 text-center">No entries yet</div>
        ) : (
          <div className="divide-y">
            {entries.map(en => (
              <div key={en.id} className="p-4 flex justify-between items-center hover:bg-gray-50">
                <div className="flex-1">
                  <div className="font-medium">
                    {en.username || `User ${en.telegram_id}`}
                  </div>
                  <div className="text-sm text-gray-600">
                    Telegram ID: {en.telegram_id} | Amount: {en.amount_debited} {contest?.currency}
                  </div>
                  {en.winner_rank && (
                    <div className="text-sm text-green-600 font-medium">
                      Winner - Rank {en.winner_rank}
                    </div>
                  )}
                </div>
                <div className="ml-4">
                  <input 
                    type="checkbox" 
                    checked={selected.includes(en.id)} 
                    onChange={() => toggle(en.id)}
                    className="w-4 h-4 text-blue-600 rounded"
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}