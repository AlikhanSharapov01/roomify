import { useState } from 'react';

function InputSection({ onSubmit, error }) {
  const [link, setLink] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(link);
  };

  return (
    <div className="input-section">
      <h2>🔗 Вставь ссылку на объект</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Например: https://krisha.kz/a/show/12345"
          value={link}
          onChange={(e) => setLink(e.target.value)}
        />
        <button type="submit">Проверить</button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  );
}

export default InputSection;
