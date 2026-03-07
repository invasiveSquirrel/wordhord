import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Mic, MicOff, Volume2, PlusCircle, CheckCircle, XCircle, BrainCircuit, X, Minus, Edit, Trash2, Play } from 'lucide-react';
import './App.css';
import CardEditor from './CardEditor';

interface Card {
  id: string;
  term: string;
  translation: string;
  example: string;
  example_translation: string;
  ipa?: string;
  gender?: string;
  part_of_speech?: string;
  conjugations?: string;
  tone?: string;
  prefix?: string;
  preposition?: string;
  case?: string;
  passed: number;
  failed: number;
}

type Language = 'swedish' | 'german' | 'finnish' | 'portuguese' | 'spanish' | 'dutch' | 'scottish_gaelic';
const LANGUAGES: Language[] = ['swedish', 'german', 'finnish', 'portuguese', 'spanish', 'dutch', 'scottish_gaelic'];

const AudioVisualizer = ({ audioBlob, color, label, onPlay }: { audioBlob: Blob | null, color: string, label: string, onPlay?: () => void }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!audioBlob || !canvasRef.current) return;
    
    const draw = async () => {
      try {
        const arrayBuffer = await audioBlob.arrayBuffer();
        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        
        const width = canvas.width;
        const height = canvas.height;
        ctx.clearRect(0, 0, width, height);

        const data = audioBuffer.getChannelData(0);
        const step = Math.ceil(data.length / width);
        const amp = height / 2;

        ctx.fillStyle = color;
        for (let i = 0; i < width; i++) {
          let min = 1.0;
          let max = -1.0;
          for (let j = 0; j < step; j++) {
            const datum = data[(i * step) + j];
            if (datum < min) min = datum;
            if (datum > max) max = datum;
          }
          ctx.fillRect(i, (1 + min) * amp, 1, Math.max(1, (max - min) * amp));
        }
      } catch (e) {
        console.error('Visualization error', e);
      }
    };
    draw();
  }, [audioBlob, color]);

  return (
    <div className="visualizer-container">
      <div className="visualizer-header">
        <p>{label}</p>
        {audioBlob && onPlay && (
          <button onClick={onPlay} className="btn icon-btn mini-btn">
            <Play size={12} />
          </button>
        )}
      </div>
      <canvas ref={canvasRef} width={400} height={60} className="visualizer-canvas"></canvas>
    </div>
  );
};

export default function App() {
  const [language, setLanguage] = useState<Language>('swedish');
  const [cards, setCards] = useState<Card[]>([]);
  const [deckIds, setDeckIds] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showFront, setShowFront] = useState(true);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [pronunciationResult, setPronunciationResult] = useState<{ transcript: string, feedback: string } | null>(null);
  const [userAudioBlob, setUserAudioBlob] = useState<Blob | null>(null);
  const [nativeAudioBlob, setNativeAudioBlob] = useState<Blob | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editingCard, setEditingCard] = useState<Card | undefined>(undefined);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    loadCards();
  }, [language]);

  const loadCards = async () => {
    setLoading(true);
    setStatus('Loading cards...');
    try {
      const res = await axios.get(`http://localhost:8001/cards/${language}`);
      const fetchedCards = res.data.cards.map((c: any) => ({
        ...c, passed: 0, failed: 0, id: String(c.id)
      }));
      setCards(fetchedCards);
      setDeckIds(fetchedCards.map((c: Card) => c.id));
      setCurrentIndex(0);
      setShowFront(true);
      resetAudioStates();
      setStatus(`Loaded ${fetchedCards.length} cards.`);
    } catch (e) {
      setStatus('Failed to load cards.');
    } finally {
      setLoading(false);
    }
  };

  const resetAudioStates = () => {
    setUserAudioBlob(null);
    setNativeAudioBlob(null);
    setPronunciationResult(null);
  }

  const shuffleCards = () => {
    const shuffled = [...deckIds].sort(() => Math.random() - 0.5);
    setDeckIds(shuffled);
    setCurrentIndex(0);
    setShowFront(true);
    resetAudioStates();
    setStatus('Deck shuffled.');
  };

  const currentCardId = deckIds[currentIndex];
  const currentCard = cards.find(c => c.id === currentCardId);

  const handleNext = () => {
    if (currentIndex < deckIds.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setShowFront(true);
      resetAudioStates();
    } else {
      generateStudyPlan();
    }
  };

  const updateCardStats = (id: string, pass: boolean) => {
    setCards(prev => prev.map(c => c.id === id ? { ...c, passed: c.passed + (pass ? 1 : 0), failed: c.failed + (pass ? 0 : 1) } : c));
  };

  const generateStudyPlan = async () => {
    setLoading(true);
    setStatus('Generating study plan...');
    try {
      const res = await axios.post('http://localhost:8001/cards/next', {
        language,
        cards: cards.map(c => ({ id: c.id, passed: c.passed, failed: c.failed }))
      });
      if (res.data.ids?.length > 0) {
        setDeckIds(res.data.ids);
        setCurrentIndex(0);
        setShowFront(true);
        resetAudioStates();
        setStatus('New study plan ready.');
      }
    } catch (e) {
      setStatus('Error generating plan.');
    } finally {
      setLoading(false);
    }
  };

  const generateRelatedCards = async () => {
    setLoading(true);
    setStatus('Creating new cards...');
    try {
      const res = await axios.post('http://localhost:8001/cards/generate', {
        language,
        existing_terms: cards.map(c => c.term)
      });
      const newCards = res.data.cards.map((c: any) => ({
        ...c, passed: 0, failed: 0, id: String(c.id) || Math.random().toString(36).substring(7)
      }));
      setCards(prev => [...prev, ...newCards]);
      setStatus(`Added ${newCards.length} cards.`);
    } catch (e) {
      setStatus('Failed to generate cards.');
    } finally {
      setLoading(false);
    }
  };

  const fetchNativeAudio = async () => {
    if (!currentCard || nativeAudioBlob) return;
    setStatus('Fetching native audio...');
    try {
      const res = await axios.post('http://localhost:8001/native_audio', {
        text: currentCard.example || currentCard.term,
        language
      }, { responseType: 'blob' });
      setNativeAudioBlob(res.data);
      setStatus('Native audio ready.');
    } catch (e) {
      console.error("Native audio fetch failed", e);
      setStatus('Failed to fetch native audio.');
    }
  };

  const playBlob = (blob: Blob | null) => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.play();
  };

  const startRecording = async (expectedText: string) => {
    try {
      // Also fetch native audio if we don't have it yet, so we can compare
      fetchNativeAudio();

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setUserAudioBlob(audioBlob);
        const formData = new FormData();
        formData.append('audio', audioBlob);
        formData.append('language', language);
        formData.append('expected_text', expectedText);

        setLoading(true);
        setStatus('Evaluating...');
        try {
          const res = await axios.post('http://localhost:8001/evaluate_pronunciation', formData);
          setPronunciationResult({ transcript: res.data.transcript, feedback: res.data.feedback });
          setStatus('Feedback ready.');
        } catch (error) {
          setStatus('Evaluation failed.');
        } finally {
          setLoading(false);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (err) {
      setStatus('Mic error.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  };

  const handleCreateCard = async (cardData: Omit<Card, 'id' | 'passed' | 'failed'>) => {
    setLoading(true);
    setStatus('Creating card...');
    try {
      await axios.post('http://localhost:8001/cards/create', {
        language,
        ...cardData
      });
      setStatus('Card created! Reloading...');
      await loadCards();
      setEditorOpen(false);
    } catch (error) {
      setStatus('Failed to create card.');
    } finally {
      setLoading(false);
    }
  };

  const handleEditCard = async (cardData: Omit<Card, 'id' | 'passed' | 'failed'>) => {
    if (!editingCard) return;
    setLoading(true);
    setStatus('Updating card...');
    try {
      await axios.post('http://localhost:8001/cards/update', {
        language,
        ...cardData
      });
      setStatus('Card updated! Reloading...');
      await loadCards();
      setEditorOpen(false);
      setEditingCard(undefined);
    } catch (error) {
      setStatus('Failed to update card.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteCard = async () => {
    if (!currentCard || !confirm(`Delete "${currentCard.term}"?`)) return;
    
    setLoading(true);
    setStatus('Deleting card...');
    try {
      await axios.delete(`http://localhost:8001/cards/${language}/${currentCard.term}`);
      setStatus('Card deleted! Reloading...');
      await loadCards();
    } catch (error) {
      setStatus('Failed to delete card.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-container">
      <header>
        <h1>
          Wordhord<span className="eth-symbol">ð</span>
        </h1>
        <div className="language-selector">
          {LANGUAGES.map((lang) => (
            <button key={lang} className={language === lang ? 'active' : ''} onClick={() => setLanguage(lang)}>
              {lang}
            </button>
          ))}
        </div>
      </header>

      <div className="controls">
        <button onClick={generateStudyPlan} disabled={loading || cards.length === 0} className="btn primary">
          <BrainCircuit size={18} /> Study Plan
        </button>
        <button onClick={shuffleCards} disabled={loading || deckIds.length === 0} className="btn secondary">
           Shuffle Deck
        </button>
        <button onClick={generateRelatedCards} disabled={loading} className="btn secondary">
          <PlusCircle size={18} /> New Cards
        </button>
        <button onClick={() => { setEditingCard(undefined); setEditorOpen(true); }} disabled={loading} className="btn secondary">
          <PlusCircle size={18} /> Create Card
        </button>
      </div>

      <div className="status-bar">{status}</div>

      <main>
        {currentCard ? (
          <div className="flashcard-container">
            <div className={`flashcard ${showFront ? 'front' : 'back'}`} onClick={() => setShowFront(!showFront)}>
              {showFront ? (
                <div className="card-content">
                  <h2>{currentCard.term}</h2>
                  <p className="hint">Tap to flip</p>
                </div>
              ) : (
                <div className="card-content">
                  <h2>{currentCard.translation}</h2>
                  <hr />
                  {(currentCard.ipa || currentCard.gender || currentCard.part_of_speech || currentCard.conjugations || (language === 'swedish' && currentCard.tone) || currentCard.prefix || currentCard.preposition || currentCard.case) && (
                    <div className="linguistics-box">
                      {currentCard.part_of_speech && <p><strong>Part of Speech:</strong> {currentCard.part_of_speech}</p>}
                      {currentCard.ipa && <p><strong>IPA:</strong> {currentCard.ipa}</p>}
                      {language === 'swedish' && currentCard.tone && <p><strong>Tone:</strong> {currentCard.tone}</p>}
                      {language === 'german' && currentCard.prefix && <p><strong>Prefix:</strong> {currentCard.prefix}</p>}
                      {(currentCard.preposition || currentCard.case) && (
                        <p><strong>Usage:</strong> {currentCard.preposition}{currentCard.case ? ` (${currentCard.case})` : ''}</p>
                      )}
                      {currentCard.gender && <p><strong>Gender:</strong> {currentCard.gender}</p>}
                      {currentCard.conjugations && <p><strong>Forms:</strong> {currentCard.conjugations}</p>}
                    </div>
                  )}
                  <div className="example-box">
                    <p className="example-text">"{currentCard.example}"</p>
                    <p className="example-trans">({currentCard.example_translation})</p>
                  </div>
                </div>
              )}
            </div>
            
            {!showFront && (
              <div className="actions">
                <button onClick={() => { fetchNativeAudio(); playBlob(nativeAudioBlob); }} className="btn icon-btn">
                  <Volume2 size={18} /> {nativeAudioBlob ? 'Replay Native' : 'Fetch & Play Native'}
                </button>
                <button className={`btn icon-btn ${isRecording ? 'recording' : ''}`} 
                  onClick={() => isRecording ? stopRecording() : startRecording(currentCard.example || currentCard.term)}>
                  {isRecording ? <MicOff size={18} /> : <Mic size={18} />} {isRecording ? 'Stop' : (userAudioBlob ? 'Rerecord Speech' : 'Test Speech')}
                </button>
                <button onClick={() => { setEditingCard(currentCard); setEditorOpen(true); }} className="btn icon-btn edit-btn">
                  <Edit size={18} /> Edit
                </button>
                <button onClick={handleDeleteCard} className="btn icon-btn delete-btn">
                  <Trash2 size={18} /> Delete
                </button>
              </div>
            )}

            {!showFront && (nativeAudioBlob || userAudioBlob) && (
              <div className="visualizations">
                 {nativeAudioBlob && <AudioVisualizer audioBlob={nativeAudioBlob} color="#89b4fa" label="Native Voice" onPlay={() => playBlob(nativeAudioBlob)} />}
                 {userAudioBlob && <AudioVisualizer audioBlob={userAudioBlob} color="#a6e3a1" label="Your Voice" onPlay={() => playBlob(userAudioBlob)} />}
              </div>
            )}

            {pronunciationResult && !showFront && (
              <div className="feedback-box">
                <h4>🗣️ Feedback</h4>
                <p><strong>Heard:</strong> "{pronunciationResult.transcript}"</p>
                <p><strong>Tips:</strong> {pronunciationResult.feedback}</p>
              </div>
            )}

            {!showFront && (
              <div className="evaluate-actions">
                <button onClick={() => { updateCardStats(currentCard.id, false); handleNext(); }} className="btn fail-btn"><XCircle /> Again</button>
                <button onClick={() => { updateCardStats(currentCard.id, true); handleNext(); }} className="btn pass-btn"><CheckCircle /> Got it</button>
              </div>
            )}
            <div className="progress">Card {currentIndex + 1} of {deckIds.length}</div>
          </div>
        ) : (
          !loading && <div className="empty-state">No cards. Study in Polyglossia first!</div>
        )}
      </main>

      <CardEditor
        isOpen={editorOpen}
        card={editingCard}
        onClose={() => {
          setEditorOpen(false);
          setEditingCard(undefined);
        }}
        onSave={editingCard ? handleEditCard : handleCreateCard}
      />
    </div>
  );
}
