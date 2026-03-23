import { useState, useEffect, useRef, useMemo } from 'react';
import axios from 'axios';
import { Mic, MicOff, Volume2, PlusCircle, BrainCircuit, Edit, Trash2, Settings, RefreshCw, Repeat } from 'lucide-react';
import './App.css';
import CardEditor from './CardEditor';

interface Card {
  id: string;
  language: string;
  term: string;
  translation: string;
  example: string;
  example_translation: string;
  level?: string;
  ipa?: string;
  gender?: string;
  plural?: string;
  part_of_speech?: string;
  conjugations?: string;
  tone?: string;
  prefix?: string;
  preposition?: string;
  case?: string;
  accusative?: string;
  passed: number;
  failed: number;
}

type Language = 'swedish' | 'german' | 'finnish' | 'portuguese' | 'spanish' | 'dutch' | 'scottish gaelic';
const LANGUAGES: Language[] = ['swedish', 'german', 'finnish', 'portuguese', 'spanish', 'dutch', 'scottish gaelic'];

const LANG_NAMES: Record<Language, string> = {
  swedish: 'Svenska',
  german: 'Deutsch',
  finnish: 'Suomi',
  portuguese: 'Português',
  spanish: 'Español',
  dutch: 'Nederlands',
  'scottish gaelic': 'Gàidhlig'
};

const AudioVisualizer = ({ audioBlob, color, label }: { audioBlob: Blob | null, color: string, label: string }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!audioBlob || !canvasRef.current) return;
    const draw = async () => {
      const buffer = await audioBlob.arrayBuffer();
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const audioBuffer = await ctx.decodeAudioData(buffer);
      const canvas = canvasRef.current!;
      const drawCtx = canvas.getContext('2d')!;
      drawCtx.clearRect(0, 0, canvas.width, canvas.height);
      const data = audioBuffer.getChannelData(0);
      const step = Math.ceil(data.length / canvas.width);
      drawCtx.fillStyle = color;
      for (let i = 0; i < canvas.width; i++) {
        let min = 1.0, max = -1.0;
        for (let j = 0; j < step; j++) {
          const datum = data[(i * step) + j];
          if (datum < min) min = datum;
          if (datum > max) max = datum;
        }
        drawCtx.fillRect(i, (1 + min) * (canvas.height/2), 1, Math.max(1, (max - min) * (canvas.height/2)));
      }
    };
    draw();
  }, [audioBlob, color]);
  return <div className="visualizer-container"><p>{label}</p><canvas ref={canvasRef} width={400} height={50} className="visualizer-canvas"></canvas></div>;
};

export default function App() {
  const [renderError, setRenderError] = useState<string | null>(null);

  useEffect(() => {
    const handleError = (e: ErrorEvent) => setRenderError(e.message);
    window.addEventListener('error', handleError);
    return () => window.removeEventListener('error', handleError);
  }, []);

  const [language, setLanguage] = useState<Language>('swedish');
  const [cards, setCards] = useState<Card[]>([]);
  const [deckIds, setDeckIds] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showFront, setShowFront] = useState(true);
  const [, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [isRecording, setIsRecording] = useState(false);
  const [pronunciationResult, setPronunciationResult] = useState<{ transcript: string, feedback: string } | null>(null);
  const [userAudioBlob, setUserAudioBlob] = useState<Blob | null>(null);
  const [nativeAudioBlob, setNativeAudioBlob] = useState<Blob | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingCard, setEditingCard] = useState<Card | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [vocabCount, setVocabCount] = useState<number>(0);
  const [selectedLevels, setSelectedLevels] = useState<string[]>(['None', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Expression', 'Advice']);
  const [synonyms, setSynonyms] = useState<string[]>([]);
  const [showSynonyms, setShowSynonyms] = useState(false);
  const [synonymSource, setSynonymSource] = useState('dm');
  const [loadingSynonyms, setLoadingSynonyms] = useState(false);

  const cardMap = useMemo(() => {
    const map = new Map<string, Card>();
    cards.forEach(c => map.set(c.id, c));
    return map;
  }, [cards]);

  const currentCard = useMemo(() => cardMap.get(deckIds[currentIndex]), [cardMap, deckIds, currentIndex]);

  const resetAudioStates = () => {
    setNativeAudioBlob(null);
    setUserAudioBlob(null);
    setPronunciationResult(null);
  };

  useEffect(() => { 
    loadCards(); 
    loadVocabCount();
  }, [language]);

  const loadVocabCount = async () => {
    try {
      const res = await axios.get(`http://localhost:8001/count/${language}`);
      setVocabCount(res.data.total);
    } catch (e) {
      console.error("Failed to load vocab count", e);
    }
  };

  const loadCards = async () => {
    setLoading(true);
    try {
      const levelsParam = selectedLevels.map(l => l === 'None' ? '' : l).join(',');
      const res = await axios.get(`http://localhost:8001/cards/${language}?levels=${levelsParam}&limit=10000`);
      const fetched = res.data.cards.map((c: any) => ({ ...c, id: String(c.id) }));
      setCards(fetched);
      setDeckIds(fetched.map((c: Card) => c.id));
      setCurrentIndex(0);
      setShowFront(true);
      resetAudioStates();
      loadVocabCount();
      setStatus(`Loaded ${fetched.length} cards.`);
    } catch (e) { setStatus('Load failed.'); } finally { setLoading(false); }
  };

  const fetchSynonyms = async () => {
    if (!currentCard) return;
    setLoadingSynonyms(true);
    try {
      const term = currentCard.term.split(' ')[0]; // Basic first word logic if there are articles
      const res = await axios.get(`http://localhost:8001/synonyms/${encodeURIComponent(currentCard.term)}?lang=${language.substring(0,2).toLowerCase()}&source=${synonymSource}`);
      setSynonyms(res.data.synonyms || []);
    } catch (e) {
      console.error("Failed to load synonyms", e);
      setSynonyms([]);
    } finally {
      setLoadingSynonyms(false);
    }
  };

  const toggleSynonyms = () => {
    if (!showSynonyms && synonyms.length === 0) {
      fetchSynonyms();
    }
    setShowSynonyms(!showSynonyms);
  };

  const shuffleDeck = () => {
    const shuffled = [...deckIds].sort(() => Math.random() - 0.5);
    setDeckIds(shuffled);
    setCurrentIndex(0);
    setShowFront(true);
    setShowSynonyms(false);
    setSynonyms([]);
    setStatus('Deck shuffled.');
  };

  const saveCard = async (cardData: any) => {
    try {
      if (editingCard) {
        // Edit existing
        await axios.put(`http://localhost:8001/cards/${editingCard.id}`, cardData);
      } else {
        // Create new
        await axios.post('http://localhost:8001/cards', cardData);
      }
      setEditorOpen(false);
      setEditingCard(null);
      await loadCards();
    } catch (e: any) {
      alert(`Failed to save card: ${e.response?.data?.detail || e.message}`);
    }
  };

  const deleteCard = async () => {
    if (!currentCard) return;
    if (window.confirm(`Are you sure you want to delete "${currentCard.term}"?`)) {
      try {
        await axios.delete(`http://localhost:8001/cards/${currentCard.id}`);
        // Remove from deck
        setDeckIds(prev => prev.filter(id => id !== currentCard.id));
        // Keep currentIndex the same, which will now point to the next card
        // If it was the last card, we might need to decrement
        if (currentIndex >= deckIds.length - 1 && currentIndex > 0) {
           setCurrentIndex(currentIndex - 1);
        }
        setShowFront(true);
        await loadCards();
      } catch (e: any) {
        alert(`Failed to delete card: ${e.response?.data?.detail || e.message}`);
      }
    }
  };

  const handleReview = async (quality: number) => {
    if (!currentCard) return;
    await axios.post('http://localhost:8001/cards/review', { card_id: parseInt(currentCard.id), quality });
    setShowSynonyms(false);
    setSynonyms([]);
    if (currentIndex < deckIds.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowFront(true);
      resetAudioStates();
    } else {
      generateStudyPlan();
    }
  };

  const generateStudyPlan = async () => {
    setLoading(true);
    try {
      const res = await axios.post('http://localhost:8001/cards/next', { language, levels: selectedLevels });
      if (res.data.ids?.length > 0) {
        setDeckIds(res.data.ids);
        setCurrentIndex(0);
        setShowFront(true);
        resetAudioStates();
        setStatus('Daily review ready.');
      } else { setStatus('Nothing due.'); }
    } catch (e) { setStatus('Plan error.'); } finally { setLoading(false); }
  };

  const playNative = async (text?: string) => {
    try {
      // Force IPA source for Gaelic if available
      const sourceText = (language === 'scottish gaelic' && !text) 
        ? currentCard?.ipa || currentCard?.term 
        : text || currentCard?.term;

      const res = await axios.post('http://localhost:8001/native_audio', { 
        text: sourceText, 
        language,
        speed: playbackRate
      }, { responseType: 'blob' });
      
      const blob = new Blob([res.data], { type: 'audio/mpeg' });
      if (!text) setNativeAudioBlob(blob);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play().catch(e => console.error("Playback failed:", e));
    } catch (e) {
      console.error("Native audio failed:", e);
    }
  };

  const speakIPA = async (ipa: string) => { 
    try {
      const res = await axios.post('http://localhost:8001/speak_ipa', { 
        text: ipa, 
        language,
        speed: playbackRate
      }, { responseType: 'blob' });
      
      const contentType = res.headers['content-type'] || 'audio/wav';
      // Handle cases where response might be an object instead of direct blob
      let blob: Blob;
      if (res.data instanceof Blob) {
        blob = res.data;
      } else if (res.data && res.data.data) {
        // Axios sometimes returns object with data property if not handled correctly
        blob = new Blob([new Uint8Array(res.data.data)], { type: contentType });
      } else {
        blob = new Blob([res.data], { type: contentType });
      }

      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.play().catch(e => console.error("IPA playback failed:", e));
    } catch (e) {
      console.error("Speak IPA failed", e);
    }
  };

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
    const chunks: Blob[] = [];
    mr.ondataavailable = (e) => chunks.push(e.data);
    mr.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      setUserAudioBlob(blob);
      const fd = new FormData();
      fd.append('audio', blob);
      fd.append('language', language);
      fd.append('expected_text', currentCard?.example || currentCard?.term || '');
      setLoading(true);
      try {
        const res = await axios.post('http://localhost:8001/evaluate_pronunciation', fd);
        setPronunciationResult({ transcript: res.data.transcript, feedback: res.data.feedback });
      } catch (e) {} finally { setLoading(false); }
    };
    mr.start();
    setIsRecording(true);
    setTimeout(() => { if (mr.state === 'recording') mr.stop(); setIsRecording(false); }, 5000);
  };

  return (
    <div className="app-container">
      <header>
        <div className="logo">
          <h1>wordhord</h1>
          <span className="eth-symbol">ð</span>
        </div>
        <div className="header-controls">
          <select 
            className="speed-dropdown" 
            value={playbackRate} 
            onChange={(e) => setPlaybackRate(parseFloat(e.target.value))}
            title="Reading Speed"
          >
            {[1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7].map(rate => (
              <option key={rate} value={rate}>
                {rate}x
              </option>
            ))}
          </select>
          <div className="language-selector">
            {LANGUAGES.map(l => <button key={l} className={language === l ? 'active' : ''} onClick={() => setLanguage(l)}>{LANG_NAMES[l]}</button>)}
          </div>
        </div>
      </header>

      <div className="controls">
        <button onClick={generateStudyPlan} className="btn primary"><BrainCircuit size={18} /> Daily Review</button>
        <button onClick={() => { setEditingCard(null); setEditorOpen(true); }} className="btn primary"><PlusCircle size={18} /> Add Word</button>
        <button onClick={async () => {
          setLoading(true);
          try {
            await axios.post('http://localhost:8001/migrate');
          } catch (e) {
            console.error("Migration failed:", e);
          }
          setLoading(false);
          loadCards();
        }} className="btn secondary"><RefreshCw size={16} /> Reload</button>
                 <button onClick={shuffleDeck} className="btn secondary"><Repeat size={16} /> Shuffle</button>
               </div>

      <main>
        {currentCard ? (
          <div className="flashcard-container">
            <div className={`flashcard ${showFront ? 'front' : 'back'}`} onClick={() => setShowFront(!showFront)}>
              {showFront ? (
                <div className="card-content">
                  <div className="term-row">
                    <button onClick={(e) => { e.stopPropagation(); playNative(); }} className="btn icon-btn speak-main-btn"><Volume2 size={32} /></button>
                    <h2>{currentCard.term}</h2>
                  </div>
                  {currentCard.level && <span className="card-level-badge">{currentCard.level}</span>}
                </div>
              ) : (
                <div className="card-content">
                  <div className="card-actions-top">
                    <button onClick={(e) => { e.stopPropagation(); setEditingCard(currentCard || null); setEditorOpen(true); }} className="btn icon-btn mini-btn"><Edit size={14} /> Edit</button>
                    <button onClick={(e) => { e.stopPropagation(); deleteCard(); }} className="btn icon-btn mini-btn delete-btn"><Trash2 size={14} /></button>
                  </div>
                  <h2 className="main-translation">{currentCard.translation}</h2>
                  <div className="linguistics-grid">
                    {currentCard.ipa && (
                      <div className="ling-item ipa-item">
                        <strong>IPA:</strong> {currentCard.ipa} 
                        <button onClick={(e) => { e.stopPropagation(); speakIPA(currentCard.ipa!); }} className="btn icon-btn mini-btn inline-btn">
                          <Volume2 size={14} />
                        </button>
                      </div>
                    )}
                    {currentCard.part_of_speech && <div className="ling-item pos-item"><strong>PoS:</strong> {currentCard.part_of_speech}</div>}
                    {currentCard.gender && <div className="ling-item gender-item"><strong>Gender:</strong> {currentCard.gender}</div>}
                    {currentCard.tone && <div className="ling-item tone-item"><strong>Tone:</strong> {currentCard.tone}</div>}
                    {currentCard.plural && <div className="ling-item plural-item"><strong>Plural:</strong> {currentCard.plural}</div>}
                    {currentCard.conjugations && <div className="ling-item conj-item"><strong>Forms:</strong> {currentCard.conjugations}</div>}
                  </div>
                  {currentCard.example && (
                    <div className="example-section">
                      <p className="example-text">"{currentCard.example}"</p>
                      <p className="example-trans">({currentCard.example_translation})</p>
                      <div className="example-actions">
                        <button onClick={(e) => { e.stopPropagation(); playNative(currentCard.example); }} className="btn icon-btn mini-btn"><Repeat size={14} /> Listen to Example</button>
                      </div>
                    </div>
                  )}

                  <div className="synonym-section" onClick={(e) => e.stopPropagation()}>
                    <button className="btn outline-btn toggle-synonyms-btn" onClick={toggleSynonyms}>
                      {showSynonyms ? 'Hide Synonyms' : 'Show Synonyms'}
                    </button>
                    {showSynonyms && (
                      <div className="synonyms-content">
                        <div className="synonym-source-selector">
                          <label>Source: </label>
                          <select value={synonymSource} onChange={(e) => { setSynonymSource(e.target.value); setSynonyms([]); }} className="source-select">
                            <option value="dm">Datamuse</option>
                            <option value="mw">Merriam-Webster</option>
                            <option value="ox">Oxford Dictionaries</option>
                          </select>
                          <button onClick={fetchSynonyms} className="btn mini-btn primary" disabled={loadingSynonyms}>
                            {loadingSynonyms ? 'Loading...' : 'Fetch'}
                          </button>
                        </div>
                        {loadingSynonyms ? (
                          <p>Loading synonyms...</p>
                        ) : synonyms.length > 0 ? (
                          <ul className="synonyms-list">
                            {synonyms.map((s, idx) => <li key={idx}>{s}</li>)}
                          </ul>
                        ) : (
                          <p>No synonyms found.</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            
            {!showFront && (
              <div className="review-interface">
                <div className="srs-evaluation">
                  <div className="srs-buttons">
                    <button onClick={() => handleReview(0)} className="srs-btn srs-0">Forgot</button>
                    <button onClick={() => handleReview(3)} className="srs-btn srs-3">Hard</button>
                    <button onClick={() => handleReview(4)} className="srs-btn srs-4">Good</button>
                    <button onClick={() => handleReview(5)} className="srs-btn srs-5">Easy</button>
                  </div>
                </div>
                <div className="voice-actions">
                  <button className={`btn icon-btn ${isRecording ? 'recording' : ''}`} onClick={() => isRecording ? null : startRecording()}>
                    {isRecording ? <MicOff size={18} /> : <Mic size={18} />} {isRecording ? 'Listening...' : 'Evaluate My Speech'}
                  </button>
                </div>
                {(nativeAudioBlob || userAudioBlob) && (
                  <div className="visualizations">
                    {nativeAudioBlob && <AudioVisualizer audioBlob={nativeAudioBlob} color="#89b4fa" label="Native" />}
                    {userAudioBlob && <AudioVisualizer audioBlob={userAudioBlob} color="#a6e3a1" label="You" />}
                  </div>
                )}
                {pronunciationResult && <div className="feedback-box"><p><strong>Heard:</strong> "{pronunciationResult.transcript}"</p><p>{pronunciationResult.feedback}</p></div>}
              </div>
            )}
          </div>
        ) : <div className="empty-state">No cards due.</div>}
      </main>

      <button className="settings-trigger" onClick={() => setSettingsOpen(true)}><Settings size={24} /></button>

      {settingsOpen && (
        <div className="modal-overlay">
          <div className="modal-content settings-modal">
            <div className="settings-header">
              <h3>Settings - {LANG_NAMES[language]}</h3>
              <div className="vocab-stats">
                <span className="stat-label">Total Vocabulary:</span>
                <span className="stat-value">{vocabCount.toLocaleString()} cards</span>
              </div>
            </div>
            
            <div className="settings-section">
              <h4>Levels</h4>
              <div className="level-grid">
                {['None', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'Expression', 'Advice'].map(lvl => (
                  <button key={lvl} className={`level-btn ${selectedLevels.includes(lvl) ? 'active' : ''}`} onClick={() => setSelectedLevels(prev => prev.includes(lvl) ? prev.filter(x => x !== lvl) : [...prev, lvl])}>{lvl}</button>
                ))}
              </div>
            </div>
            <button onClick={async () => { await axios.post('http://localhost:8001/progress/reset', { language }); loadCards(); }} className="btn fail-btn">Reset Progress</button>
            <div className="modal-footer"><button onClick={() => { setSettingsOpen(false); loadCards(); }} className="btn primary">Close</button></div>
          </div>
        </div>
      )}

      <CardEditor 
        isOpen={editorOpen} 
        card={editingCard || undefined} 
        language={language}
        onClose={() => { setEditorOpen(false); setEditingCard(null); }} 
        onSave={saveCard} 
      />
    </div>
  );
}
