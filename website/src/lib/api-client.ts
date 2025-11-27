/**
 * API client for communicating with the FastAPI backend.
 */

import axios, { AxiosInstance } from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance
export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
apiClient.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor to handle 401 errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      // Clear tokens and redirect to login
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  register: async (data: { email: string; password: string; name: string }) => {
    const response = await apiClient.post('/auth/register', data);
    return response.data;
  },

  login: async (data: { email: string; password: string }) => {
    const response = await apiClient.post('/auth/login', data);
    if (response.data.access_token) {
      localStorage.setItem('access_token', response.data.access_token);
      localStorage.setItem('refresh_token', response.data.refresh_token);
    }
    return response.data;
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },

  getCurrentUser: async () => {
    const response = await apiClient.get('/profile/me');
    return response.data;
  },

  resendConfirmation: async (email: string) => {
    const response = await apiClient.post('/auth/resend-confirmation', { email });
    return response.data;
  },
};

// Sessions API
export const sessionsApi = {
  list: async () => {
    const response = await apiClient.get('/sessions/');
    return response.data.sessions || [];
  },

  get: async (sessionId: string) => {
    const response = await apiClient.get(`/sessions/${sessionId}`);
    return response.data;
  },

  upload: async (file: File, metadata: { location?: string; date?: string }) => {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata.location) formData.append('location', metadata.location);
    if (metadata.date) formData.append('date', metadata.date);

    const response = await apiClient.post('/sessions/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  delete: async (sessionId: string) => {
    const response = await apiClient.delete(`/sessions/${sessionId}`);
    return response.data;
  },

  mergeSurfers: async (sessionId: string, surferIds: number[]) => {
    const response = await apiClient.post(`/sessions/${sessionId}/merge-surfers`, {
      surfer_ids: surferIds,
    });
    return response.data;
  },
};

// Profile API
export const profileApi = {
  get: async () => {
    const response = await apiClient.get('/profile');
    return response.data;
  },

  update: async (data: { name?: string }) => {
    const response = await apiClient.put('/profile', data);
    return response.data;
  },

  updatePassword: async (data: { current_password: string; new_password: string }) => {
    const response = await apiClient.put('/profile/password', data);
    return response.data;
  },
};

// Rankings API
export const rankingsApi = {
  getLeaderboard: async (period: 'daily' | 'monthly' | 'yearly', referenceDate?: string) => {
    const params = referenceDate ? { reference_date: referenceDate } : {};
    const response = await apiClient.get(`/rankings/leaderboard/${period}`, { params });
    return response.data;
  },

  getUserRanking: async (period: 'daily' | 'monthly' | 'yearly', userId: string, referenceDate?: string) => {
    const params = referenceDate ? { reference_date: referenceDate } : {};
    const response = await apiClient.get(`/rankings/leaderboard/${period}/user/${userId}`, { params });
    return response.data;
  },

  triggerRecalculation: async (period: 'daily' | 'monthly' | 'yearly', referenceDate?: string) => {
    const params = referenceDate ? { reference_date: referenceDate } : {};
    const response = await apiClient.post(`/rankings/recalculate/${period}`, null, { params });
    return response.data;
  },
};
