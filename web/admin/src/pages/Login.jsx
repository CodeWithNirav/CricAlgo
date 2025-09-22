import React, { useState } from "react";

export default function Login(){
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");

  async function submit(e){
    e.preventDefault();
    setErr("");
    try {
      const res = await fetch("/api/v1/admin/login", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify({username: user, password: pass})
      });
      const j = await res.json();
      if(!res.ok){ 
        setErr(j.detail?.error || j.detail || "Login failed"); 
        return; 
      }
      // store token in sessionStorage for now
      sessionStorage.setItem("admin_token", j.access_token);
      window.location.href = "/admin";
    } catch (e) {
      setErr(String(e));
    }
  }

  return (
    <div className="w-full max-w-md p-6 bg-white rounded shadow">
      <h1 className="text-2xl font-semibold mb-4">CricAlgo Admin Login</h1>
      <form onSubmit={submit}>
        <label className="block mb-2">Username</label>
        <input value={user} onChange={e=>setUser(e.target.value)} className="w-full p-2 border rounded mb-3"/>
        <label className="block mb-2">Password</label>
        <input type="password" value={pass} onChange={e=>setPass(e.target.value)} className="w-full p-2 border rounded mb-3"/>
        {err && <div className="text-red-600 mb-2">{err}</div>}
        <button className="w-full bg-blue-600 text-white p-2 rounded">Login</button>
      </form>
    </div>
  );
}
