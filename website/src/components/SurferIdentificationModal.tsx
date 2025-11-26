'use client';

import { useState } from 'react';
import { AuthenticatedImage } from './AuthenticatedImage';

interface Surfer {
  id: number;
  total_maneuvers: number;
  events: Array<{
    frame: number;
    timestamp: number;
    maneuver_type: string;
  }>;
  pictures: string[];
}

interface SurferIdentificationModalProps {
  sessionId: string;
  surfers: Surfer[];
  onClose: () => void;
  onSuccess: () => void;
}

export function SurferIdentificationModal({
  sessionId,
  surfers,
  onClose,
  onSuccess,
}: SurferIdentificationModalProps) {
  const [selectedSurfers, setSelectedSurfers] = useState<Set<number>>(new Set());
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [mergeStats, setMergeStats] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleSurfer = (surferId: number) => {
    const newSelected = new Set(selectedSurfers);
    if (newSelected.has(surferId)) {
      newSelected.delete(surferId);
    } else {
      newSelected.add(surferId);
    }
    setSelectedSurfers(newSelected);
  };

  const handleMerge = () => {
    if (selectedSurfers.size === 0) {
      setError('Please select at least one surfer');
      return;
    }
    setShowConfirmation(true);
  };

  const confirmMerge = async () => {
    setLoading(true);
    setError(null);
    setShowConfirmation(false); // Hide confirmation, show loading

    try {
      const { sessionsApi } = await import('@/lib/api-client');
      const response = await sessionsApi.mergeSurfers(sessionId, Array.from(selectedSurfers));
      setMergeStats(response);
      setSuccess(true);
      setLoading(false);
    } catch (err: any) {
      console.error('Failed to merge surfers:', err);
      setError(err.response?.data?.detail || 'Failed to merge surfers');
      setLoading(false);
    }
  };

  const handleSuccessClose = () => {
    setSuccess(false);
    onSuccess(); // This triggers the page refresh
  };

  // Loading state
  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-8">
          <div className="text-center">
            <div className="mb-4">
              <svg className="animate-spin h-16 w-16 text-blue-600 mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Merging Surfers...</h3>
            <p className="text-gray-600">
              Please wait while we combine the selected surfers into a single identity.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Success state
  if (success && mergeStats) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
          <div className="text-center mb-6">
            <div className="mx-auto flex items-center justify-center h-16 w-16 rounded-full bg-green-100 mb-4">
              <svg className="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
              </svg>
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Merge Complete!</h3>
            <p className="text-gray-600 mb-4">
              {mergeStats.message}
            </p>
          </div>

          <div className="bg-blue-50 rounded-lg p-4 mb-6 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-700">Merged Surfer ID:</span>
              <span className="font-semibold text-gray-900">{mergeStats.merged_surfer_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-700">Total Maneuvers:</span>
              <span className="font-semibold text-gray-900">{mergeStats.total_events_merged}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-700">Surfers Removed:</span>
              <span className="font-semibold text-gray-900">{mergeStats.surfers_removed}</span>
            </div>
          </div>

          <button
            onClick={handleSuccessClose}
            className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium"
          >
            Close and View Results
          </button>
        </div>
      </div>
    );
  }

  // Confirmation state
  if (showConfirmation) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
          <h3 className="text-xl font-bold text-gray-900 mb-4">Confirm Merge</h3>
          <div className="mb-6 space-y-2">
            <p className="text-gray-700">
              You are about to merge <strong>{selectedSurfers.size}</strong> surfer(s) into a single identity.
            </p>
            <p className="text-red-600 font-medium">
              ⚠️ This action cannot be undone.
            </p>
            <p className="text-gray-600 text-sm">
              Unselected surfers will be permanently removed from the session.
            </p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setShowConfirmation(false)}
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={confirmMerge}
              className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
            >
              Confirm Merge
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full my-8">
        {/* Header */}
        <div className="border-b border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">Identify Yourself</h2>
              <p className="text-gray-600 mt-1">
                Select all surfers that represent you to merge them into a single identity
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Surfer Grid */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            {surfers.map((surfer) => {
              const isSelected = selectedSurfers.has(surfer.id);
              const thumbnails = surfer.pictures.slice(0, 4);

              return (
                <div
                  key={surfer.id}
                  onClick={() => toggleSurfer(surfer.id)}
                  className={`border-2 rounded-lg p-4 cursor-pointer transition-all ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  {/* Header */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSurfer(surfer.id)}
                        className="w-5 h-5 text-blue-600 rounded"
                      />
                      <span className="font-semibold text-gray-900">
                        Surfer {surfer.id}
                      </span>
                    </div>
                    <span className="text-sm text-gray-600">
                      {surfer.total_maneuvers} maneuvers
                    </span>
                  </div>

                  {/* Thumbnails */}
                  <div className="grid grid-cols-2 gap-2">
                    {thumbnails.map((pic, idx) => (
                      <AuthenticatedImage
                        key={idx}
                        src={pic}
                        alt={`Surfer ${surfer.id} - Image ${idx + 1}`}
                        className="w-full h-24 object-cover rounded bg-gray-100"
                      />
                    ))}
                    {thumbnails.length < 4 && (
                      Array.from({ length: 4 - thumbnails.length }).map((_, idx) => (
                        <div
                          key={`empty-${idx}`}
                          className="w-full h-24 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs"
                        >
                          No image
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Warning */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
            <div className="flex gap-2">
              <svg className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
              <div className="text-sm text-yellow-800">
                <p className="font-medium">This action cannot be undone</p>
                <p className="mt-1">
                  Unselected surfers will be permanently removed from this session.
                  Make sure to select all surfers that represent you.
                </p>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex justify-between items-center">
            <p className="text-sm text-gray-600">
              {selectedSurfers.size} of {surfers.length} surfer(s) selected
            </p>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleMerge}
                disabled={selectedSurfers.size === 0}
                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Merge {selectedSurfers.size > 0 ? `${selectedSurfers.size} Surfer${selectedSurfers.size > 1 ? 's' : ''}` : 'Surfers'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
