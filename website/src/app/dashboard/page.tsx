'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { authApi, sessionsApi } from '@/lib/api-client';
import { RankingsWidget } from '@/components/RankingsWidget';
import Link from 'next/link';

interface Session {
  id: string;
  location?: string;
  session_date?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  created_at: string;
  results_json?: any;
}

export default function DashboardPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [uploadModal, setUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadMetadata, setUploadMetadata] = useState({ location: '', date: '' });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    try {
      const [userRes, sessionsRes] = await Promise.all([
        authApi.getCurrentUser(),
        sessionsApi.list(),
      ]);
      setUser(userRes);
      setSessions(sessionsRes);
      setLoading(false);
    } catch (err) {
      router.push('/login');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) return;

    setUploading(true);
    setError('');

    try {
      await sessionsApi.upload(uploadFile, uploadMetadata);
      setUploadModal(false);
      setUploadFile(null);
      setUploadMetadata({ location: '', date: '' });
      loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleLogout = () => {
    authApi.logout();
    router.push('/');
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'bg-green-100 text-green-800';
      case 'processing':
        return 'bg-blue-100 text-blue-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-yellow-100 text-yellow-800';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl text-gray-600">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Surf Tracker</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-700">Hi, {user?.name || user?.email}</span>
            <Link
              href="/profile"
              className="text-gray-600 hover:text-gray-900"
            >
              Profile
            </Link>
            <button
              onClick={handleLogout}
              className="text-gray-600 hover:text-gray-900"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* Main Content - Two Column Layout */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Sessions (60% on desktop) */}
          <div className="lg:col-span-2">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-xl font-semibold text-gray-900">Your Sessions</h2>
              <button
                onClick={() => setUploadModal(true)}
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
              >
                Upload Video
              </button>
            </div>

            {/* Sessions List */}
            {sessions.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg shadow">
                <p className="text-gray-600 mb-4">No sessions yet</p>
                <button
                  onClick={() => setUploadModal(true)}
                  className="text-blue-600 hover:text-blue-700 font-medium"
                >
                  Upload your first video
                </button>
              </div>
            ) : (
              <div className="grid gap-4">
                {sessions.map((session) => (
                  <div
                    key={session.id}
                    className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <h3 className="text-lg font-medium text-gray-900">
                            {session.location || 'Unknown Location'}
                          </h3>
                          <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(session.status)}`}>
                            {session.status}
                          </span>
                        </div>
                        <p className="text-sm text-gray-600">
                          {session.session_date || new Date(session.created_at).toLocaleDateString()}
                        </p>
                        {session.results_json && session.results_json.surfers && (
                          <p className="text-sm text-gray-700 mt-2">
                            {session.results_json.surfers.length} surfer(s) detected
                          </p>
                        )}
                      </div>
                      {session.status === 'completed' && (
                        <Link
                          href={`/sessions/${session.id}`}
                          className="text-blue-600 hover:text-blue-700 font-medium text-sm"
                        >
                          View Results →
                        </Link>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Right Column: Rankings (40% on desktop) */}
          <div className="lg:col-span-1">
            <RankingsWidget />
          </div>
        </div>
      </main>

      {/* Upload Modal */}
      {uploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-md w-full p-6">
            <h3 className="text-xl font-bold mb-4">Upload Video</h3>

            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
                {error}
              </div>
            )}

            <form onSubmit={handleUpload} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Video File
                </label>
                <input
                  type="file"
                  accept="video/*"
                  required
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Location
                </label>
                <input
                  type="text"
                  value={uploadMetadata.location}
                  onChange={(e) => setUploadMetadata({ ...uploadMetadata, location: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                  placeholder="e.g., Bondi Beach"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Date
                </label>
                <input
                  type="date"
                  value={uploadMetadata.date}
                  onChange={(e) => setUploadMetadata({ ...uploadMetadata, date: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setUploadModal(false);
                    setError('');
                  }}
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
                  disabled={uploading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-blue-300"
                  disabled={uploading || !uploadFile}
                >
                  {uploading ? 'Uploading...' : 'Upload'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
