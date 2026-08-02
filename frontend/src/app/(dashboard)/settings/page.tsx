'use client';

import { useState } from 'react';
import { Save, Check } from 'lucide-react';

const SETTINGS_GROUPS = [
  {
    id: 'pipeline', title: 'Pipeline Settings',
    settings: [
      { id: 'frame_skip_rate', label: 'Frame Skip Rate', desc: 'Number of frames to skip during extraction', type: 'number', val: 5 },
      { id: 'min_event_duration_ms', label: 'Min Event Duration (ms)', desc: 'Minimum duration for an event to be registered', type: 'number', val: 1500 },
    ]
  },
  {
    id: 'detection', title: 'Detection Parameters',
    settings: [
      { id: 'detection_confidence', label: 'Detection Confidence', desc: 'Threshold for object/event confidence (0-1)', type: 'number', val: 0.75 },
      { id: 'min_motion_threshold', label: 'Motion Threshold', desc: 'Minimum motion vector magnitude to trigger analysis', type: 'number', val: 0.4 },
    ]
  },
  {
    id: 'temporal', title: 'Temporal Intelligence',
    settings: [
      { id: 'story_gap_threshold_ms', label: 'Story Gap Threshold (ms)', desc: 'Max time gap between events to link them', type: 'number', val: 5000 },
      { id: 'compression_policy', label: 'Compression Policy', desc: 'Strategy for generating final timeline', type: 'select', val: 'narrative_priority', options: ['narrative_priority', 'max_compression', 'all_events'] },
    ]
  }
];

// Build initial values map from the settings definition
const buildInitialValues = () => {
  const vals: Record<string, string | number> = {};
  SETTINGS_GROUPS.forEach(g => g.settings.forEach(s => { vals[s.id] = s.val; }));
  return vals;
};

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('pipeline');
  const [values, setValues] = useState<Record<string, string | number>>(buildInitialValues);
  const [saveState, setSaveState] = useState<SaveState>('idle');

  const handleChange = (id: string, value: string | number) => {
    setValues(prev => ({ ...prev, [id]: value }));
    // Reset saved indicator when user edits after a successful save
    if (saveState === 'saved') setSaveState('idle');
  };

  const handleSave = async () => {
    setSaveState('saving');
    try {
      const res = await fetch('/api/v1/settings/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
      setSaveState(res.ok ? 'saved' : 'error');
      // Reset to idle after 2 seconds
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      setSaveState('error');
      setTimeout(() => setSaveState('idle'), 2000);
    }
  };

  const saveLabel =
    saveState === 'saving' ? 'Saving...' :
    saveState === 'saved'  ? 'Saved!'    :
    saveState === 'error'  ? 'Error'     : 'Save Changes';

  const saveIcon = saveState === 'saved' ? <Check className="w-4 h-4" /> : <Save className="w-4 h-4" />;

  return (
    <div className="max-w-4xl space-y-6 animate-fade-in h-full flex flex-col">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">System Settings</h1>
          <p className="text-muted mt-1">Configure global parameters for the Time Compression Engine.</p>
        </div>
        <button
          onClick={handleSave}
          disabled={saveState === 'saving'}
          aria-label="Save settings"
          className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors text-sm disabled:opacity-60 ${
            saveState === 'saved'  ? 'bg-emerald-600 text-white' :
            saveState === 'error'  ? 'bg-red-600 text-white'    :
            'bg-accent hover:bg-accent-hover text-white'
          }`}
        >
          {saveIcon} {saveLabel}
        </button>
      </div>

      <div className="flex gap-6 flex-1 min-h-0 mt-6">
        <div className="w-64 space-y-1">
          {SETTINGS_GROUPS.map(g => (
            <button
              key={g.id}
              onClick={() => setActiveTab(g.id)}
              role="tab"
              aria-selected={activeTab === g.id}
              className={`w-full text-left px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === g.id ? 'bg-surface text-white border border-border' : 'text-muted hover:text-white hover:bg-surface/50 border border-transparent'
              }`}
            >
              {g.title}
            </button>
          ))}
        </div>

        <div className="flex-1 glass rounded-xl border border-border p-8 overflow-y-auto">
          {SETTINGS_GROUPS.map(g => g.id === activeTab && (
            <div key={g.id} className="space-y-8 animate-slide-up">
              <h2 className="text-xl font-semibold text-white border-b border-border pb-4">{g.title}</h2>
              
              <div className="space-y-6">
                {g.settings.map(s => (
                  <div key={s.id} className="flex justify-between items-start gap-8">
                    <div className="flex-1">
                      <label htmlFor={s.id} className="block font-medium text-white text-sm mb-1">{s.label}</label>
                      <p className="text-sm text-muted">{s.desc}</p>
                    </div>
                    <div className="w-64">
                      {s.type === 'number' ? (
                        <input
                          id={s.id}
                          type="number"
                          value={values[s.id] as number}
                          onChange={e => handleChange(s.id, e.target.valueAsNumber)}
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-accent outline-none"
                        />
                      ) : (
                        <select
                          id={s.id}
                          value={values[s.id] as string}
                          onChange={e => handleChange(s.id, e.target.value)}
                          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-white text-sm focus:border-accent outline-none"
                        >
                          {s.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                        </select>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
