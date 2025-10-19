function OutputSection({ data, onBack }) {
    if (!data || !data.images) {
      return (
        <div className="result-section">
          <p>{data?.status || "⏳ Загрузка..."}</p>
        </div>
      );
    }
  
    return (
      <div className="result-section">
        <h2>🏡 Результат</h2>
        <p><strong>Описание:</strong> {data.description}</p>
  
        {data.images.map((img, index) => (
          <img 
            key={index} 
            src={img} 
            alt={`Фото ${index + 1}`} 
            style={{ width: '200px', borderRadius: '8px', margin: '8px' }}
          />
        ))}
  
        <button onClick={onBack}>🔙 Вернуться назад</button>
      </div>
    );
  }

export default OutputSection;