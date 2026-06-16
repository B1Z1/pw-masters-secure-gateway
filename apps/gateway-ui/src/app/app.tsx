import { useState } from 'react';

export function App() {
  const [status, setStatus] = useState<string>('unknown');
  const [error, setError] = useState<string | null>(null);

  const checkHealth = async () => {
    setError(null);
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      setStatus(JSON.stringify(data));
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <main style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>LLM Gateway</h1>
      <p>Secure anonymization gateway — infrastructure runtime (Epic 1).</p>
      <button onClick={checkHealth}>Check backend health</button>
      {error ? (
        <pre style={{ color: 'crimson' }}>Error: {error}</pre>
      ) : (
        <pre>Backend status: {status}</pre>
      )}
    </main>
  );
}

export default App;
