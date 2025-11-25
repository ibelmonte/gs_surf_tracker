'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { sessionsApi, apiClient } from '@/lib/api-client';
import Link from 'next/link';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Component to load authenticated images
function AuthenticatedImage({ src, alt, className }: { src: string; alt: string; className: string }) {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadImage = async () => {
      try {
        // Extract the path relative to OUTPUT_DIR
        // Convert: /data/output/{user_id}/{session_id}/... to {user_id}/{session_id}/...
        const pathMatch = src.match(/\/data\/output\/(.*)/);
        const relativePath = pathMatch ? pathMatch[1] : src;

        console.log('Original src:', src);
        console.log('Extracted path:', relativePath);

        const response = await apiClient.get(`/files/${relativePath}`, {
          responseType: 'blob',
        });
        const url = URL.createObjectURL(response.data);
        setImgSrc(url);
        setLoading(false);
      } catch (err) {
        console.error('Failed to load image:', err);
        setLoading(false);
      }
    };

    loadImage();

    return () => {
      if (imgSrc) {
        URL.revokeObjectURL(imgSrc);
      }
    };
  }, [src]);

  if (loading) {
    return <div className={className + ' bg-gray-200 animate-pulse'}></div>;
  }

  if (!imgSrc) {
    return <div className={className + ' bg-gray-100 flex items-center justify-center text-gray-400'}>
      Failed to load
    </div>;
  }

  return <img src={imgSrc} alt={alt} className={className} />;
}

interface Session {
  id: string;
  location?: string;
  session_date?: string;
  status: string;
  created_at: string;
  output_path?: string;
  results_json?: {
    surfers: Array<{
      id: number;
      total_maneuvers: number;
      events: Array<{
        frame: number;
        timestamp: number;
        maneuver_type: string;
        turn_metrics: {
          angle_degrees: number;
          direction: string;
          angular_speed_deg_s: number;
        };
        pose_features: {
          body_lean: number;
          knee_bend: number;
          arm_extension: number;
        };
        trajectory_features: {
          turn_radius: number;
          speed: number;
        };
      }>;
      pictures: string[];
    }>;
    output_video?: string;
  };
}

export default function SessionPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSurfer, setSelectedSurfer] = useState<number>(0);

  useEffect(() => {
    loadSession();
  }, [params.id]);

  const loadSession = async () => {
    try {
      const data = await sessionsApi.get(params.id);
      setSession(data);
      setLoading(false);
    } catch (err) {
      router.push('/dashboard');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-xl text-gray-600">Loading session...</div>
      </div>
    );
  }

  if (!session || !session.results_json) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-xl text-gray-600 mb-4">No results available</p>
          <Link href="/dashboard" className="text-blue-600 hover:text-blue-700">
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const surfer = session.results_json.surfers[selectedSurfer];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <Link href="/dashboard" className="text-blue-600 hover:text-blue-700 text-sm mb-2 block">
                ← Back to Dashboard
              </Link>
              <h1 className="text-2xl font-bold text-gray-900">
                {session.location || 'Session Results'}
              </h1>
              <p className="text-sm text-gray-600 mt-1">
                {session.session_date || new Date(session.created_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Summary */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Session Summary</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <p className="text-sm text-gray-600">Surfers Detected</p>
              <p className="text-2xl font-bold text-gray-900">{session.results_json.surfers.length}</p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Total Maneuvers</p>
              <p className="text-2xl font-bold text-gray-900">
                {session.results_json.surfers.reduce((sum, s) => sum + s.total_maneuvers, 0)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-600">Status</p>
              <p className="text-2xl font-bold text-green-600">Completed</p>
            </div>
          </div>
        </div>

        {/* Surfer Tabs */}
        {session.results_json.surfers.length > 1 && (
          <div className="bg-white rounded-lg shadow mb-6 p-4">
            <div className="flex gap-2 overflow-x-auto">
              {session.results_json.surfers.map((s, idx) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedSurfer(idx)}
                  className={`px-4 py-2 rounded-lg whitespace-nowrap ${
                    selectedSurfer === idx
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  Surfer {s.id} ({s.total_maneuvers} maneuvers)
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Surfer Details */}
        {surfer && (
          <div className="space-y-6">
            {/* Maneuvers List */}
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">
                Surfer {surfer.id} - {surfer.total_maneuvers} Maneuvers
              </h3>

              <div className="space-y-4">
                {surfer.events.map((event, idx) => (
                  <div key={idx} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex justify-between items-start mb-3">
                      <div>
                        <span className="inline-block px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm font-medium">
                          {event.maneuver_type.toUpperCase()}
                        </span>
                        <p className="text-sm text-gray-600 mt-1">
                          Frame {event.frame} • {event.timestamp.toFixed(2)}s
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
                      <div>
                        <p className="text-gray-600 font-medium">Turn Metrics</p>
                        <p>Angle: {event.turn_metrics.angle_degrees.toFixed(1)}°</p>
                        <p>Direction: {event.turn_metrics.direction}</p>
                        <p>Speed: {event.turn_metrics.angular_speed_deg_s.toFixed(1)}°/s</p>
                      </div>

                      <div>
                        <p className="text-gray-600 font-medium">Pose</p>
                        <p>Body Lean: {event.pose_features.body_lean.toFixed(1)}°</p>
                        <p>Knee Bend: {event.pose_features.knee_bend.toFixed(1)}°</p>
                        <p>Arm Extension: {(event.pose_features.arm_extension * 100).toFixed(0)}%</p>
                      </div>

                      <div>
                        <p className="text-gray-600 font-medium">Trajectory</p>
                        <p>Turn Radius: {event.trajectory_features.turn_radius.toFixed(1)}px</p>
                        <p>Speed: {event.trajectory_features.speed.toFixed(1)}px/s</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Frame Captures */}
            {surfer.pictures && surfer.pictures.length > 0 && (
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">Frame Captures</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {surfer.pictures.map((pic, idx) => (
                    <div key={idx} className="border border-gray-200 rounded-lg overflow-hidden">
                      <AuthenticatedImage
                        src={pic}
                        alt={`Frame ${idx + 1}`}
                        className="w-full h-48 object-cover bg-gray-100"
                      />
                      <div className="p-2 text-sm text-gray-600 text-center">
                        Frame {surfer.events[idx]?.frame || idx + 1}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
