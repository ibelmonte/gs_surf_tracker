'use client';

import { useState, useEffect } from 'react';
import { rankingsApi } from '@/lib/api-client';

interface RankingEntry {
  rank: number;
  user_id: string;
  user_name: string;
  total_score: number;
  session_count: number;
  is_current_user: boolean;
}

interface LeaderboardData {
  period: string;
  period_label: string;
  top_entries: RankingEntry[];
  current_user_entry?: RankingEntry;
  total_participants: number;
}

type Period = 'daily' | 'monthly' | 'yearly';

export function RankingsWidget() {
  const [selectedPeriod, setSelectedPeriod] = useState<Period>('daily');
  const [leaderboard, setLeaderboard] = useState<LeaderboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLeaderboard();
  }, [selectedPeriod]);

  const loadLeaderboard = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await rankingsApi.getLeaderboard(selectedPeriod);
      setLeaderboard(data);
    } catch (err: any) {
      console.error('Failed to load leaderboard:', err);
      setError('Failed to load rankings');
    } finally {
      setLoading(false);
    }
  };

  const getRankBadge = (rank: number) => {
    if (rank === 1) return '🥇';
    if (rank === 2) return '🥈';
    if (rank === 3) return '🥉';
    return `#${rank}`;
  };

  const getPeriodLabel = (period: Period) => {
    switch (period) {
      case 'daily':
        return 'Daily';
      case 'monthly':
        return 'Monthly';
      case 'yearly':
        return 'Yearly';
    }
  };

  return (
    <div className="bg-white rounded-lg shadow">
      <div className="p-6 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Leaderboard</h2>

        {/* Period Tabs */}
        <div className="flex gap-2">
          {(['daily', 'monthly', 'yearly'] as Period[]).map((period) => (
            <button
              key={period}
              onClick={() => setSelectedPeriod(period)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedPeriod === period
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {getPeriodLabel(period)}
            </button>
          ))}
        </div>
      </div>

      {/* Leaderboard Content */}
      <div className="p-6">
        {loading ? (
          <div className="text-center py-8 text-gray-600">
            Loading rankings...
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-600">
            {error}
          </div>
        ) : !leaderboard || leaderboard.top_entries.length === 0 ? (
          <div className="text-center py-8 text-gray-600">
            No rankings available yet
          </div>
        ) : (
          <>
            {/* Period Label */}
            <div className="mb-4 text-center">
              <p className="text-sm text-gray-600">
                {leaderboard.period_label}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {leaderboard.total_participants} participant{leaderboard.total_participants !== 1 ? 's' : ''}
              </p>
            </div>

            {/* Top 10 Rankings */}
            <div className="space-y-2">
              {leaderboard.top_entries.map((entry) => (
                <div
                  key={entry.user_id}
                  className={`flex items-center justify-between p-3 rounded-lg transition-colors ${
                    entry.is_current_user
                      ? 'bg-blue-50 border-2 border-blue-300'
                      : 'bg-gray-50 hover:bg-gray-100'
                  }`}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <span className="text-xl font-bold text-gray-700 w-12 flex-shrink-0">
                      {getRankBadge(entry.rank)}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className={`font-medium truncate ${
                        entry.is_current_user ? 'text-blue-900' : 'text-gray-900'
                      }`}>
                        {entry.user_name}
                        {entry.is_current_user && (
                          <span className="ml-2 text-xs font-normal text-blue-600">(You)</span>
                        )}
                      </p>
                      <p className="text-xs text-gray-600">
                        {entry.session_count} session{entry.session_count !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0 ml-2">
                    <p className="font-bold text-gray-900">
                      {Math.round(entry.total_score).toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-600">points</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Current User Entry (if outside top 10) */}
            {leaderboard.current_user_entry && (
              <>
                <div className="my-4 text-center">
                  <span className="text-gray-400 text-sm">⋯</span>
                </div>
                <div className="p-3 rounded-lg bg-blue-50 border-2 border-blue-300">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <span className="text-lg font-bold text-gray-700 w-12 flex-shrink-0">
                        #{leaderboard.current_user_entry.rank}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-blue-900 truncate">
                          {leaderboard.current_user_entry.user_name}
                          <span className="ml-2 text-xs font-normal text-blue-600">(You)</span>
                        </p>
                        <p className="text-xs text-gray-600">
                          {leaderboard.current_user_entry.session_count} session{leaderboard.current_user_entry.session_count !== 1 ? 's' : ''}
                        </p>
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0 ml-2">
                      <p className="font-bold text-gray-900">
                        {Math.round(leaderboard.current_user_entry.total_score).toLocaleString()}
                      </p>
                      <p className="text-xs text-gray-600">points</p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
