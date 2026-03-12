"use client";
import React, { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";
import 'maplibre-gl/dist/maplibre-gl.css';

export default function LandingPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [grievanceId, setGrievanceId] = useState("");
  const [mapPin, setMapPin] = useState<{ lat: number; lng: number } | null>(null);
  const [description, setDescription] = useState("");
  const [email, setEmail] = useState("");
  const [uploadedUrls, setUploadedUrls] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const mapRef = useRef<HTMLDivElement>(null);
  const mapObj = useRef<any>(null);
  const markerObj = useRef<any>(null);

  useEffect(() => {
    if (!mapRef.current) return;
    import('maplibre-gl').then(mod => {
      const maplibregl = mod.default;
      mapObj.current = new maplibregl.Map({
        container: mapRef.current!,
        style: "https://tiles.openfreemap.org/styles/liberty",
        center: [77.2090, 28.6139],
        zoom: 11,
      });

      mapObj.current.on('click', (e: any) => {
        const { lat, lng } = e.lngLat;
        setMapPin({ lat, lng });
        if (!markerObj.current) {
          markerObj.current = new maplibregl.Marker({ color: "#ef4444" }).setLngLat([lng, lat]).addTo(mapObj.current!);
        } else {
          markerObj.current.setLngLat([lng, lat]);
        }
      });
    });

    return () => mapObj.current?.remove();
  }, []);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!mapPin) {
      setError("Please click on the map to pin the location.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const result = await api.complaints.submit({
        raw_text: description,
        lat: mapPin.lat,
        lng: mapPin.lng,
        media_urls: uploadedUrls,
        channel: "web",
        citizen_email: email || undefined,
      });
      setSuccess(result.grievance_id);
      setDescription("");
      setMapPin(null);
      if (markerObj.current) markerObj.current.remove();
      markerObj.current = null;
    } catch (err: any) {
      setError(String(err.message || err));
    } finally {
      setSubmitting(false);
    }
  }

  function handleTrack() {
    if (grievanceId.trim()) router.push(`/track/${grievanceId.trim()}`);
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const { upload_url, file_path } = await api.complaints.getUploadUrl();
      await fetch(upload_url, { method: "PUT", body: file, headers: { "Content-Type": file.type } });
      setUploadedUrls(prev => [...prev, file_path]);
    } catch (err) {
      console.error(err);
      setError("File upload failed.");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-8">
        
        {/* Submit Complaint */}
        <div className="bg-white rounded border border-gray-200 p-6 md:p-8">
          <div className="mb-6">
            <h2 className="text-2xl font-bold text-gray-900 border-b pb-4 mb-2 flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-700 rounded-lg flex items-center justify-center text-white font-bold">PS</div>
              Submit a Complaint
            </h2>
            <p className="text-sm text-gray-500">Report civic issues directly to the MCD.</p>
          </div>

          {success ? (
            <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-6 text-center">
              <div className="text-4xl mb-3">✅</div>
              <h3 className="text-lg font-semibold mb-2">Complaint Submitted</h3>
              <p className="text-sm mb-4">Your grievance ID is:</p>
              <code className="bg-white px-3 py-2 rounded border border-green-200 font-mono font-bold text-lg select-all">{success}</code>
              <button 
                onClick={() => setSuccess("")} 
                className="mt-6 text-sm font-medium text-green-700 hover:text-green-800 underline block w-full"
              >
                Submit another complaint
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-5">
              {error && <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md border border-red-100">{error}</div>}
              
              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Description</label>
                <textarea 
                  required
                  rows={3}
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                  className="w-full border border-gray-200 rounded-md p-2.5 text-sm focus:ring-2 focus:ring-blue-700 focus:outline-none transition-shadow"
                  placeholder="Describe the issue (e.g., Broken streetlight near the park entirely out)"
                />
              </div>

              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Location</label>
                <div ref={mapRef} className="w-full h-48 bg-gray-100 rounded-md border border-gray-200 overflow-hidden" />
                <p className="text-xs text-gray-500 mt-1">Click on the map to drop a pin precisely where the issue is.</p>
              </div>

              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Proof Photo (Optional)</label>
                <input 
                  type="file" 
                  accept="image/*"
                  onChange={handleFile}
                  className="w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 transition-colors"
                />
                {uploadedUrls.map((url, i) => <p key={i} className="text-xs text-green-600 mt-1">✓ {url.split('/').pop()}</p>)}
              </div>

              <div className="space-y-1">
                <label className="text-sm font-semibold text-gray-700">Email for Receipt (Optional)</label>
                <input 
                  type="email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full border border-gray-200 rounded-md p-2.5 text-sm focus:ring-2 focus:ring-blue-700 focus:outline-none transition-shadow"
                  placeholder="citizen@example.com"
                />
              </div>

              <button 
                type="submit" 
                disabled={submitting}
                className="w-full bg-blue-700 hover:bg-blue-800 disabled:opacity-50 text-white font-semibold py-3 px-4 rounded-md transition-colors"
              >
                {submitting ? "Submitting..." : "Submit Complaint"}
              </button>
            </form>
          )}
        </div>

        {/* Track Complaint & Dashboard Link */}
        <div className="space-y-8">
          <div className="bg-white rounded border border-gray-200 p-6 md:p-8">
            <h2 className="text-2xl font-bold text-gray-900 border-b pb-4 mb-6">Track Complaint</h2>
            <div className="flex gap-2">
              <input 
                type="text" 
                value={grievanceId}
                onChange={e => setGrievanceId(e.target.value)}
                placeholder="MCD-20250315-XXXXX"
                className="flex-1 border border-gray-200 rounded-md p-2.5 text-sm focus:ring-2 focus:ring-blue-700 focus:outline-none font-mono uppercase"
              />
              <button 
                onClick={handleTrack}
                disabled={!grievanceId.trim()}
                className="bg-gray-900 hover:bg-black disabled:opacity-50 text-white font-semibold py-2.5 px-6 rounded-md transition-colors"
              >
                Go
              </button>
            </div>
            <p className="text-sm text-gray-500 mt-4 leading-relaxed">
              Enter your Grievance ID to view the current status, timeline, and SLA details.
            </p>
          </div>

          <div className="bg-blue-50 rounded border border-blue-100 p-6 md:p-8">
            <h3 className="font-semibold text-blue-900 mb-2">Officer Portal</h3>
            <p className="text-sm text-blue-800 mb-4">
              Are you an MCD official or registered contractor? Log in to your dashboard to manage complaints.
            </p>
            <button 
              onClick={() => router.push('/login')}
              className="bg-white border border-blue-200 text-blue-700 font-semibold py-2 px-4 rounded w-full hover:bg-blue-50 transition-colors"
            >
              Go to Login
            </button>
            
            <div className="mt-8 pt-6 border-t border-blue-100">
               <h3 className="font-semibold text-blue-900 mb-2">Public Heatmap</h3>
               <p className="text-sm text-blue-800 mb-4">
                 View the live public map showing complaint density across all wards.
               </p>
               <button 
                 onClick={() => router.push('/map')}
                 className="bg-white border border-blue-200 text-blue-700 font-semibold py-2 px-4 rounded w-full hover:bg-blue-50 transition-colors"
               >
                 View Ward Map
               </button>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
