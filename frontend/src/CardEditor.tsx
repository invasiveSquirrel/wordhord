import { useState } from 'react';
import { X } from 'lucide-react';
import './CardEditor.css';

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

interface CardEditorProps {
  card?: Card;
  onClose: () => void;
  onSave: (card: Omit<Card, 'id' | 'passed' | 'failed'>) => void;
  isOpen: boolean;
}

export default function CardEditor({ card, onClose, onSave, isOpen }: CardEditorProps) {
  const [formData, setFormData] = useState({
    term: card?.term || '',
    translation: card?.translation || '',
    ipa: card?.ipa || '',
    gender: card?.gender || '',
    tone: card?.tone || '',
    part_of_speech: card?.part_of_speech || '',
    conjugations: card?.conjugations || '',
    prefix: card?.prefix || '',
    preposition: card?.preposition || '',
    case: card?.case || '',
    example: card?.example || '',
    example_translation: card?.example_translation || '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.term || !formData.translation) {
      alert('Term and Translation are required');
      return;
    }
    onSave(formData);
    setFormData({
      term: '',
      translation: '',
      ipa: '',
      gender: '',
      tone: '',
      part_of_speech: '',
      conjugations: '',
      prefix: '',
      preposition: '',
      case: '',
      example: '',
      example_translation: '',
    });
  };

  if (!isOpen) return null;

  return (
    <div className="editor-overlay" onClick={onClose}>
      <div className="editor-modal" onClick={(e) => e.stopPropagation()}>
        <div className="editor-header">
          <h2>{card ? 'Edit Card' : 'Create New Card'}</h2>
          <button className="editor-close" onClick={onClose}>
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="editor-form">
          <div className="form-row">
            <div className="form-group required">
              <label htmlFor="term">Word/Term *</label>
              <input
                type="text"
                id="term"
                name="term"
                value={formData.term}
                onChange={handleChange}
                placeholder="e.g., ser"
                autoFocus
              />
            </div>

            <div className="form-group required">
              <label htmlFor="translation">English Translation *</label>
              <input
                type="text"
                id="translation"
                name="translation"
                value={formData.translation}
                onChange={handleChange}
                placeholder="e.g., to be"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="ipa">IPA Pronunciation</label>
              <input
                type="text"
                id="ipa"
                name="ipa"
                value={formData.ipa}
                onChange={handleChange}
                placeholder="e.g., [seɾ]"
              />
            </div>

            <div className="form-group">
              <label htmlFor="tone">Tone (Accent 1/2)</label>
              <select
                id="tone"
                name="tone"
                value={formData.tone}
                onChange={handleChange}
              >
                <option value="">None</option>
                <option value="Accent 1">Accent 1</option>
                <option value="Accent 2">Accent 2</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="part_of_speech">Part of Speech</label>
              <select
                id="part_of_speech"
                name="part_of_speech"
                value={formData.part_of_speech}
                onChange={handleChange}
              >
                <option value="">Select</option>
                <option value="Noun">Noun</option>
                <option value="Verb">Verb</option>
                <option value="Adjective">Adjective</option>
                <option value="Adverb">Adverb</option>
                <option value="Preposition">Preposition</option>
                <option value="Pronoun">Pronoun</option>
                <option value="Conjunction">Conjunction</option>
                <option value="Interjection">Interjection</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="gender">Gender</label>
              <select
                id="gender"
                name="gender"
                value={formData.gender}
                onChange={handleChange}
              >
                <option value="">None</option>
                <option value="Masculine">Masculine</option>
                <option value="Feminine">Feminine</option>
                <option value="Neuter">Neuter</option>
                <option value="Common">Common</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="prefix">Prefix (German)</label>
              <select
                id="prefix"
                name="prefix"
                value={formData.prefix}
                onChange={handleChange}
              >
                <option value="">None</option>
                <option value="Separable">Separable</option>
                <option value="Inseparable">Inseparable</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="case">Grammatical Case</label>
              <select
                id="case"
                name="case"
                value={formData.case}
                onChange={handleChange}
              >
                <option value="">None</option>
                <option value="Accusative">Accusative</option>
                <option value="Dative">Dative</option>
                <option value="Genitive">Genitive</option>
                <option value="Nominative">Nominative</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="preposition">Associated Preposition</label>
            <input
              type="text"
              id="preposition"
              name="preposition"
              value={formData.preposition}
              onChange={handleChange}
              placeholder="e.g., auf, med, etc."
            />
          </div>

          <div className="form-group">
            <label htmlFor="conjugations">Conjugations/Forms</label>
            <textarea
              id="conjugations"
              name="conjugations"
              value={formData.conjugations}
              onChange={handleChange}
              placeholder="e.g., soy, eres, es (present); fui, fuiste, fue (past); sido (participle)"
              rows={2}
            />
          </div>

          <div className="form-group">
            <label htmlFor="example">Example Sentence</label>
            <textarea
              id="example"
              name="example"
              value={formData.example}
              onChange={handleChange}
              placeholder="e.g., Yo soy ingeniero"
              rows={2}
            />
          </div>

          <div className="form-group">
            <label htmlFor="example_translation">Example Translation</label>
            <textarea
              id="example_translation"
              name="example_translation"
              value={formData.example_translation}
              onChange={handleChange}
              placeholder="e.g., I am an engineer"
              rows={2}
            />
          </div>

          <div className="editor-footer">
            <button type="button" className="btn secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn primary">
              {card ? 'Update Card' : 'Create Card'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
