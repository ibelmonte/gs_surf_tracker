import Link from 'next/link';

export default function HomePage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-blue-100 to-cyan-100">
      {/* Navigation */}
      <nav className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <h1 className="text-2xl font-bold text-gray-900">Surf Tracker</h1>
          <div className="flex gap-4">
            <Link href="/login" className="text-gray-700 hover:text-gray-900">
              Sign In
            </Link>
            <Link
              href="/register"
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div className="text-center mb-16">
          <h2 className="text-5xl font-bold text-gray-900 mb-6">
            Track Your Surf Sessions
          </h2>
          <p className="text-xl text-gray-700 mb-8 max-w-2xl mx-auto">
            AI-powered video analysis to detect surfers, track movements, and analyze your maneuvers.
            Get detailed insights into every turn, every session.
          </p>
          <Link
            href="/register"
            className="inline-block bg-blue-600 text-white px-8 py-4 rounded-lg text-lg font-medium hover:bg-blue-700 transition-colors"
          >
            Start Tracking Free
          </Link>
        </div>

        {/* Features Grid */}
        <div className="grid md:grid-cols-3 gap-8 mt-20">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-4xl mb-4">🏄</div>
            <h3 className="text-xl font-semibold mb-3 text-gray-900">Multi-Surfer Detection</h3>
            <p className="text-gray-600">
              Automatically detect and track multiple surfers in the same video with YOLOv8 and BoTSORT tracking.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-4xl mb-4">📊</div>
            <h3 className="text-xl font-semibold mb-3 text-gray-900">Turn Analysis</h3>
            <p className="text-gray-600">
              Get detailed metrics on every maneuver: turn angle, direction, angular speed, and trajectory features.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-4xl mb-4">🎥</div>
            <h3 className="text-xl font-semibold mb-3 text-gray-900">Pose Detection</h3>
            <p className="text-gray-600">
              MediaPipe pose estimation analyzes body lean, knee bend, and arm extension for each maneuver.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-4xl mb-4">📸</div>
            <h3 className="text-xl font-semibold mb-3 text-gray-900">Frame Captures</h3>
            <p className="text-gray-600">
              Automatic snapshots at key moments - perfect for sharing your best turns on social media.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-4xl mb-4">🎬</div>
            <h3 className="text-xl font-semibold mb-3 text-gray-900">Annotated Videos</h3>
            <p className="text-gray-600">
              Get your video back with bounding boxes, tracking IDs, and turn counts overlaid in real-time.
            </p>
          </div>

          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-4xl mb-4">📱</div>
            <h3 className="text-xl font-semibold mb-3 text-gray-900">Easy Upload</h3>
            <p className="text-gray-600">
              Simply upload your surf video and let our AI do the rest. Processing typically takes under 2 minutes.
            </p>
          </div>
        </div>

        {/* How It Works */}
        <div className="mt-24 text-center">
          <h3 className="text-3xl font-bold text-gray-900 mb-12">How It Works</h3>
          <div className="grid md:grid-cols-4 gap-6">
            <div>
              <div className="bg-blue-600 text-white w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                1
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Upload Video</h4>
              <p className="text-gray-600 text-sm">Upload your surf session video from your device</p>
            </div>
            <div>
              <div className="bg-blue-600 text-white w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                2
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">AI Processing</h4>
              <p className="text-gray-600 text-sm">Our AI detects surfers, tracks movements, and analyzes maneuvers</p>
            </div>
            <div>
              <div className="bg-blue-600 text-white w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                3
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Get Results</h4>
              <p className="text-gray-600 text-sm">View detailed analytics, frame captures, and annotated video</p>
            </div>
            <div>
              <div className="bg-blue-600 text-white w-12 h-12 rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                4
              </div>
              <h4 className="font-semibold text-gray-900 mb-2">Track Progress</h4>
              <p className="text-gray-600 text-sm">Compare sessions and improve your technique over time</p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="mt-24 text-center bg-white rounded-lg shadow-lg p-12">
          <h3 className="text-3xl font-bold text-gray-900 mb-4">Ready to Analyze Your Surfing?</h3>
          <p className="text-gray-600 mb-8">Join surfers who are tracking and improving their performance</p>
          <Link
            href="/register"
            className="inline-block bg-blue-600 text-white px-8 py-4 rounded-lg text-lg font-medium hover:bg-blue-700 transition-colors"
          >
            Create Free Account
          </Link>
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-white mt-20 py-8 border-t border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-gray-600">
          <p>Surf Tracker - AI-Powered Surf Video Analysis</p>
        </div>
      </footer>
    </div>
  );
}
