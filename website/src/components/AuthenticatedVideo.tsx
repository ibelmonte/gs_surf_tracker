'use client';

interface AuthenticatedVideoProps {
  src: string;  // Format: /files/{user_id}/{session_id}/output.mp4
  className?: string;
}

/**
 * Component that plays videos via nginx streaming server.
 * Videos are served publicly from nginx with obscured URLs (UUID-based paths).
 */
export function AuthenticatedVideo({ src, className = '' }: AuthenticatedVideoProps) {
  // Convert API path to nginx URL
  // src format: /files/83afc276.../4ebf4c43.../output.mp4
  // nginx serves at: http://localhost:8081/videos/83afc276.../4ebf4c43.../output.mp4
  const nginxUrl = `http://localhost:8081/videos${src.replace('/files', '')}`;

  return (
    <video
      controls
      className={className}
      preload="metadata"
      src={nginxUrl}
    >
      Your browser does not support the video tag.
    </video>
  );
}
