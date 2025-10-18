function OutputSection({ data, onBack, images}) {
    return (
      <div className="result-section">
        <h2>🏡 Результат</h2>
        <p><strong>Описание:</strong> {data.description}</p>
        <ul>
        {images.map((imageString) => (
            <img 
                src = {imageString}
                alt = "photo of the appartment"
                style={{ width: '300px', borderRadius: '10px' }}
            />
        ))}
        </ul>
  
        <button onClick={onBack}>🔙 Вернуться назад</button>
      </div>
    );
  }
  
  export default OutputSection;
  