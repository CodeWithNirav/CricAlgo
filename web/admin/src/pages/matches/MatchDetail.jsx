import React, {useEffect, useState} from "react";

export default function MatchDetail({matchId}){
  const [contests,setContests] = useState([]);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    entry_fee: '',
    max_players: '',
    user_link: '',
    code: ''
  });
  
  useEffect(()=>{ 
    if(!matchId) return; 
    fetch(`/api/v1/admin/matches/${matchId}/contests`,{
      headers:{Authorization:"Bearer "+sessionStorage.getItem("admin_token")}
    })
    .then(r=>r.json())
    .then(d=>setContests(d))
    .catch(err => console.error("Failed to fetch contests:", err));
  },[matchId]);
  
  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.title || !formData.entry_fee || !formData.max_players || !formData.code) {
      alert("Please fill in all required fields");
      return;
    }
    
    try {
      const response = await fetch(`/api/v1/admin/matches/${matchId}/contests`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": "Bearer " + sessionStorage.getItem("admin_token")
        },
        body: JSON.stringify({
          title: formData.title,
          entry_fee: formData.entry_fee,
          max_players: parseInt(formData.max_players),
          user_link: formData.user_link || null,
          code: formData.code,
          prize_structure: [{"pos": 1, "pct": 100}]
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        alert("Contest created successfully!");
        setShowCreateForm(false);
        setFormData({ title: '', entry_fee: '', max_players: '', user_link: '', code: '' });
        window.location.reload();
      } else {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail?.error || errorData?.detail || `HTTP ${response.status}`);
      }
    } catch (err) {
      console.error("Contest creation error:", err);
      const errorMessage = err.message || err.toString() || "Unknown error occurred";
      alert("Error creating contest: " + errorMessage);
    }
  };
  
  return (
    <div className="p-4">
      <h2 className="text-xl font-semibold mb-4">Contests for Match {matchId}</h2>
      <button 
        className="bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700"
        onClick={() => setShowCreateForm(true)}
      >
        Create Contest
      </button>
      
      {/* Create Contest Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg w-full max-w-md">
            <h3 className="text-lg font-semibold mb-4">Create New Contest</h3>
            <form onSubmit={handleSubmit}>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contest Title *
                </label>
                <input
                  type="text"
                  name="title"
                  value={formData.title}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Contest Code *
                </label>
                <input
                  type="text"
                  name="code"
                  value={formData.code}
                  onChange={handleInputChange}
                  placeholder="Enter unique contest code"
                  maxLength={56}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
                <p className="text-xs text-gray-500 mt-1">
                  Unique code for this contest (max 56 characters)
                </p>
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Entry Fee *
                </label>
                <input
                  type="number"
                  step="0.01"
                  name="entry_fee"
                  value={formData.entry_fee}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Max Players *
                </label>
                <input
                  type="number"
                  name="max_players"
                  value={formData.max_players}
                  onChange={handleInputChange}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  required
                />
              </div>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  User Link (Optional)
                </label>
                <input
                  type="url"
                  name="user_link"
                  value={formData.user_link}
                  onChange={handleInputChange}
                  placeholder="https://example.com/join-contest"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Link that users will receive after joining confirmation
                </p>
              </div>
              
              <div className="flex justify-end space-x-2">
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700"
                >
                  Create Contest
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      <ul className="mt-4">
        {contests.map(c=>(
          <li key={c.id} className="border p-2 rounded bg-white mb-2">
            <div className="flex justify-between">
              <div>
                <div className="font-semibold">{c.title || `Contest ${c.id}`}</div>
                <div className="text-sm text-gray-600">Entry: {c.entry_fee}</div>
                <div className="text-sm text-gray-600">Code: {c.code}</div>
                {c.user_link && (
                  <div className="text-sm text-blue-600">
                    <a href={c.user_link} target="_blank" rel="noopener noreferrer" className="hover:underline">
                      User Link: {c.user_link}
                    </a>
                  </div>
                )}
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
