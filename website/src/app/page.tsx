export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">Surf Tracker</h1>
        <p className="text-xl text-gray-600 mb-8">
          AI-powered surf performance analysis
        </p>
        <div className="flex gap-4 justify-center">
          <a
            href="/register"
            className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
          >
            Get Started
          </a>
          <a
            href="/login"
            className="bg-gray-200 text-gray-800 px-6 py-3 rounded-lg hover:bg-gray-300"
          >
            Login
          </a>
        </div>
      </div>
    </main>
  )
}
