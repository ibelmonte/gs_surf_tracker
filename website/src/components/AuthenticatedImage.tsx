'use client';

import { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api-client';

interface AuthenticatedImageProps {
  src: string;
  alt: string;
  className?: string;
}

/**
 * Component that loads images with authentication headers.
 * Fetches images via API client with Bearer token, converts to blob URL.
 * Includes loading skeleton and error fallback states.
 */
export function AuthenticatedImage({ src, alt, className = '' }: AuthenticatedImageProps) {
  const [imgSrc, setImgSrc] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

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
        setError(true);
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
    return <div className={`${className} bg-gray-200 animate-pulse`}></div>;
  }

  if (error || !imgSrc) {
    return (
      <div className={`${className} bg-gray-100 flex items-center justify-center text-gray-400 text-sm`}>
        Failed to load
      </div>
    );
  }

  return <img src={imgSrc} alt={alt} className={className} />;
}
