import { useEffect, useState } from "react";
import { Check, Download, Loader2, Lock, ShieldCheck, Trash2, X } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api, errorMessage } from "../services/api";

/** Privacy centre: what we keep, how it is protected, and the patient's rights. */
export default function PrivacyPanel({ onClose, toast }) {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState("");
  const [del, setDel] = useState({ open: false, password: "", confirm: "" });

  const load = () => api.get("/api/privacy/summary").then((r) => setData(r.data)).catch((e) => toast.error(errorMessage(e)));
  useEffect(() => { load(); }, []); // eslint-disable-line

  const toggleConsent = async () => {
    setBusy("consent");
    try {
      const r = await api.patch("/api/auth/me", { ai_data_consent: !data.consent.ai_and_voice });
      setUser(r.data);
      await load();
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(""); }
  };
  const exportData = async () => {
    setBusy("export");
    try {
      const r = await api.get("/api/privacy/export", { responseType: "blob" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(r.data);
      a.download = "medimemory-my-data.json";
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { toast.error(errorMessage(e)); } finally { setBusy(""); }
  };
  const deleteAccount = async () => {
    setBusy("delete");
    try {
      await api.post("/api/privacy/delete-account", { password: del.password, confirm: del.confirm });
      toast.success("Your account and all your data were deleted.");
      await logout?.();
      navigate("/");
    } catch (e) { toast.error(errorMessage(e)); setBusy(""); }
  };

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-navy/40" onClick={onClose}>
      <aside className="flex h-full w-full max-w-md flex-col overflow-y-auto bg-white shadow-2xl" onClick={(e) => e.stopPropagation()} aria-label="Privacy centre">
        <div className="flex items-center gap-3 border-b border-line px-5 py-4">
          <span className="flex h-10 w-10 items-center justify-center rounded-full bg-teal-50 text-teal"><ShieldCheck className="h-5 w-5" /></span>
          <div className="flex-1"><p className="font-semibold text-ink">Your privacy</p><p className="text-xs text-muted">What we keep, how it's protected, your rights</p></div>
          <button className="rounded-full p-2 text-muted hover:bg-canvas" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        {!data ? <div className="flex flex-1 items-center justify-center"><Loader2 className="h-6 w-6 animate-spin text-teal" /></div> : (
          <div className="space-y-6 px-5 py-5">
            <ul className="space-y-3">
              {data.protections.map((p) => (
                <li key={p.key} className="flex gap-3">
                  <span className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${p.on ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}`}>
                    {p.on ? <Check className="h-4 w-4" /> : <X className="h-4 w-4" />}
                  </span>
                  <div><p className="text-sm font-semibold text-ink">{p.title}</p><p className="text-xs text-muted">{p.detail}</p></div>
                </li>
              ))}
            </ul>

            <div className="rounded-2xl bg-canvas p-4">
              <p className="text-sm font-semibold text-ink">Removed before anything reached the AI</p>
              {data.removed_before_ai.length ? (
                <div className="mt-2 flex flex-wrap gap-2">
                  {data.removed_before_ai.map((r) => <span key={r.kind} className="chip bg-white text-navy">{r.count} × {r.label}</span>)}
                </div>
              ) : <p className="mt-1 text-xs text-muted">Nothing personal has been found in your visits so far.</p>}
              {data.photos_sent_to_ai > 0 && <p className="mt-2 text-xs text-amber-800">{data.photos_sent_to_ai} unclear photo(s) were read by AI vision with your consent; photos can't be redacted.</p>}
            </div>

            <div>
              <p className="text-sm font-semibold text-ink">Services that receive data</p>
              <ul className="mt-2 space-y-2">
                {data.services.map((s) => (
                  <li key={s.name} className="rounded-xl border border-line p-3 text-xs">
                    <p className="font-semibold text-ink">{s.name}</p><p className="text-muted">{s.purpose}. Receives: {s.receives}.</p>
                  </li>
                ))}
              </ul>
              <label className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-line p-3">
                <span className="text-sm"><b>AI and voice processing</b><br /><span className="text-xs text-muted">Turn off to stop all sending. You can turn it on again any time.</span></span>
                <button onClick={toggleConsent} disabled={busy === "consent"} role="switch" aria-checked={data.consent.ai_and_voice}
                  className={`relative h-7 w-12 shrink-0 rounded-full transition ${data.consent.ai_and_voice ? "bg-teal" : "bg-line"}`}>
                  <span className={`absolute top-1 h-5 w-5 rounded-full bg-white shadow transition ${data.consent.ai_and_voice ? "left-6" : "left-1"}`} />
                </button>
              </label>
            </div>

            <div>
              <p className="text-sm font-semibold text-ink">What we keep</p>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                {[["Visits", data.stored.visits_confirmed], ["Instructions", data.stored.instructions], ["Documents", data.stored.documents]].map(([k, n]) => (
                  <div key={k} className="rounded-xl bg-canvas p-2"><p className="text-lg font-semibold text-navy">{n}</p><p className="text-[11px] text-muted">{k}</p></div>
                ))}
              </div>
            </div>

            {data.recent_activity.length > 0 && (
              <div>
                <p className="text-sm font-semibold text-ink">Recent activity on your account</p>
                <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto text-xs text-muted">
                  {data.recent_activity.map((a, i) => <li key={i} className="flex justify-between gap-2"><span className="font-mono">{a.action}</span><span>{new Date(a.at + "Z").toLocaleString()}</span></li>)}
                </ul>
              </div>
            )}

            <div className="space-y-2 border-t border-line pt-5">
              <button className="btn-outline w-full" onClick={exportData} disabled={busy === "export"}>
                {busy === "export" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />} Download all my data
              </button>
              {!del.open ? (
                <button className="btn-ghost w-full text-red-600" onClick={() => setDel({ ...del, open: true })}><Trash2 className="h-4 w-4" /> Delete my account and all data</button>
              ) : (
                <div className="space-y-2 rounded-xl border border-red-200 bg-red-50 p-3">
                  <p className="text-xs text-red-800">This permanently deletes your account, visits, documents and audio. It cannot be undone.</p>
                  <input type="password" className="input" placeholder="Your password" value={del.password} onChange={(e) => setDel({ ...del, password: e.target.value })} />
                  <input className="input" placeholder='Type DELETE to confirm' value={del.confirm} onChange={(e) => setDel({ ...del, confirm: e.target.value })} />
                  <div className="flex gap-2">
                    <button className="btn-danger flex-1" disabled={busy === "delete" || del.confirm !== "DELETE" || !del.password} onClick={deleteAccount}>Delete permanently</button>
                    <button className="btn-ghost" onClick={() => setDel({ open: false, password: "", confirm: "" })}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
            <p className="flex items-center gap-1.5 text-[11px] text-muted"><Lock className="h-3 w-3" /> Your rights to consent, access and erasure follow India's DPDP Act, 2023.</p>
          </div>
        )}
      </aside>
    </div>
  );
}
