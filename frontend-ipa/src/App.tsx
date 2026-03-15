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

type Language = 'ipa_english' | 'ipa_swedish' | 'ipa_german' | 'ipa_finnish' | 'ipa_portuguese' | 'ipa_spanish' | 'ipa_dutch';
const LANGUAGES: Language[] = ['ipa_english', 'ipa_swedish', 'ipa_german', 'ipa_finnish', 'ipa_portuguese', 'ipa_spanish', 'ipa_dutch'];

const LANG_NAMES: Record<Language, string> = {
  ipa_english: 'English',
  ipa_swedish: 'Svenska',
  ipa_german: 'Deutsch',
  ipa_finnish: 'Suomi',
  ipa_portuguese: 'Português',
  ipa_spanish: 'Español',
  ipa_dutch: 'Nederlands'
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

  const [language, setLanguage] = useState<Language>('ipa_english');
  const [cards, setCards] = useState<Card[]>([]);
  const [deckIds, setDeckIds] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showFront, setShowFront] = useState(true);
  const [, setLoading] = useState(false);
  const [, setStatus] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [pronunciationResult, setPronunciationResult] = useState<{ transcript: string, feedback: string } | null>(null);
  const [userAudioBlob, setUserAudioBlob] = useState<Blob | null>(null);
  const [nativeAudioBlob, setNativeAudioBlob] = useState<Blob | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [selectedLevels, setSelectedLevels] = useState<string[]>(['None', 'Phonetics']);

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

  useEffect(() => { loadCards(); }, [language]);

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
      setStatus(`Loaded ${fetched.length} cards.`);
    } catch (e) { setStatus('Load failed.'); } finally { setLoading(false); }
  };

  const shuffleDeck = () => {
    const shuffled = [...deckIds].sort(() => Math.random() - 0.5);
    setDeckIds(shuffled);
    setCurrentIndex(0);
    setShowFront(true);
    setStatus('Deck shuffled.');
  };

  const saveCard = async (cardData: any) => {
    try {
      if (editorOpen && currentCard) {
        // Edit existing
        await axios.put(`http://localhost:8001/cards/${currentCard.id}`, cardData);
      } else {
        // Create new
        await axios.post('http://localhost:8001/cards', cardData);
      }
      setEditorOpen(false);
      loadCards();
    } catch (e) {
      alert('Failed to save card');
    }
  };

  const deleteCard = async () => {
    if (!currentCard) return;
    if (window.confirm(`Are you sure you want to delete "${currentCard.term}"?`)) {
      try {
        await axios.delete(`http://localhost:8001/cards/${currentCard.id}`);
        loadCards();
      } catch (e) {
        alert('Failed to delete card');
      }
    }
  };

  const handleReview = async (quality: number) => {
    if (!currentCard) return;
    await axios.post('http://localhost:8001/cards/review', { card_id: parseInt(currentCard.id), quality });
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
      // For IPA practice, we want the native language voice
      const baseLang = language.replace('ipa_', '');
      const res = await axios.post('http://localhost:8001/native_audio', { text: text || currentCard?.term, language: baseLang }, { responseType: 'blob' });
      const blob = res.data as Blob;
      if (!text) setNativeAudioBlob(blob);
      const url = URL.createObjectURL(blob);
      new Audio(url).play();
    } catch (e) {}
  };

  const speakIPA = async (ipa: string) => { 
    try {
      const baseLang = language.replace('ipa_', '');
      const res = await axios.post('http://localhost:8001/speak_ipa', { text: ipa, language: baseLang }, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const audio = new Audio(url);
      audio.play();
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
      const baseLang = language.replace('ipa_', '');
      fd.append('language', baseLang);
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
          <h1>phonethic</h1>
          <span className="eth-symbol">ð</span>
        </div>
        <div className="language-selector">
          {LANGUAGES.map(l => <button key={l} className={language === l ? 'active' : ''} onClick={() => setLanguage(l)}>{LANG_NAMES[l]}</button>)}
        </div>
      </header>


      <div className="controls">
        <button onClick={generateStudyPlan} className="btn primary"><BrainCircuit size={18} /> Daily Review</button>
        <button onClick={() => { setEditorOpen(true); }} className="btn secondary"><PlusCircle size={18} /> Add Word</button>
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
                    <button onClick={(e) => { e.stopPropagation(); speakIPA(currentCard.term); }} className="btn icon-btn speak-main-btn"><Volume2 size={32} /></button>
                    <h2 className="ipa-main-symbol">{currentCard.term}</h2>
                  </div>
                  {currentCard.level && <span className="card-level-badge">{currentCard.level}</span>}
                </div>
              ) : (
                <div className="card-content">
                  <div className="card-actions-top">
                    <button onClick={(e) => { e.stopPropagation(); setEditorOpen(true); }} className="btn icon-btn mini-btn"><Edit size={14} /> Edit</button>
                    <button onClick={(e) => { e.stopPropagation(); deleteCard(); }} className="btn icon-btn mini-btn delete-btn"><Trash2 size={14} /></button>
                  </div>
                  <h2 className="main-translation">{currentCard.translation}</h2>
                  <div className="ipa-example-box">
                    <div className="example-term-row">
                      <button onClick={(e) => { e.stopPropagation(); playNative(currentCard.example); }} className="btn icon-btn mini-btn"><Volume2 size={16} /></button>
                      <span className="example-word">{currentCard.example}</span>
                      <span className="example-ipa">{currentCard.ipa}</span>
                    </div>
                    <p className="example-trans">{currentCard.example_translation}</p>
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
            <h3>Settings - {LANG_NAMES[language]}</h3>
            <div className="settings-section">
              <h4>Levels</h4>
              <div className="level-grid">
                {['None', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map(lvl => (
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
        card={currentCard} 
        language={language}
        onClose={() => setEditorOpen(false)} 
        onSave={saveCard} 
      />
    </div>
  );
}
