import { useState } from 'react';
import InputSection from './AppBodies/InputSection';
import OutputSection from './AppBodies/OutputSection';
import './App.css';

function App() {
  const [mode, setMode] = useState('input'); // 'input' или 'result'
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const handleLinkSubmit = async (link) => {
    try {
      let formattedLink = link.trim();
      if (!formattedLink.startsWith('http')) {
        formattedLink = 'https://' + formattedLink;
      }

      const url = new URL(formattedLink);

      // Проверяем домен и структуру
      if (!url.hostname.endsWith('krisha.kz')) {
        throw new Error('Неверный домен');
      }
      if (!url.pathname.startsWith('/a/show/')) {
        throw new Error('Неверная структура ссылки');
      }

      // Извлекаем ID из ссылки
      const parts = url.pathname.split('/');
      const listingId = parts[parts.length - 1]; // например "1006040941"

      if (!listingId) {
        throw new Error('ID объявления не найден');
      }

      setError('');
      setMode('result');
      setResult({ status: '⏳ Загружаем данные с сервера...' });

      // 👇 Делаем GET-запрос на Django API
      const response = await fetch(`http://127.0.0.1:8000/api/krisha/${listingId}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' },
      });

      if (!response.ok) {
        throw new Error(`Ошибка сервера: ${response.status}`);
      }

      const data = await response.json();
      setResult(data);

    } catch (err) {
      console.error(err);
      setError('❌ Введите корректную ссылку на Krisha.kz');
      setMode('input');
    }
  };

  const handleBack = () => {
    setMode('input');
    setResult(null);
  };

  return (
    <div className="App">
      <h1>🏗 HiggsField HomeVision</h1>

      {mode === 'input' && (
        <InputSection onSubmit={handleLinkSubmit} error={error} />
      )}

      {mode === 'result' && (
        <OutputSection data={result} onBack={handleBack} />
      )}
    </div>
  );
}

export default App;
