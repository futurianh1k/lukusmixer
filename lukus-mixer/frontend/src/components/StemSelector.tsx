import React from 'react';
import { Mic2, Drum, Guitar, Piano, Waves, Music, LucideIcon } from 'lucide-react';
import type { StemSelectorProps } from '../types/api';

interface StemConfig {
  label: string;
  color: string;
  textColor: string;
  icon: LucideIcon;
}

const STEM_CONFIG: Record<string, StemConfig> = {
  vocals: { label: 'Vocals', color: 'bg-green-500', textColor: 'text-green-400', icon: Mic2 },
  lead_vocals: { label: 'Lead Vocals', color: 'bg-green-500', textColor: 'text-green-400', icon: Mic2 },
  backing_vocals: { label: 'Backing Vocals', color: 'bg-emerald-500', textColor: 'text-emerald-400', icon: Mic2 },
  drums: { label: 'Drums', color: 'bg-orange-500', textColor: 'text-orange-400', icon: Drum },
  kick: { label: 'Kick', color: 'bg-orange-500', textColor: 'text-orange-400', icon: Drum },
  snare: { label: 'Snare', color: 'bg-amber-500', textColor: 'text-amber-400', icon: Drum },
  toms: { label: 'Toms', color: 'bg-yellow-500', textColor: 'text-yellow-400', icon: Drum },
  cymbals: { label: 'Cymbals', color: 'bg-lime-500', textColor: 'text-lime-400', icon: Drum },
  bass: { label: 'Bass', color: 'bg-purple-500', textColor: 'text-purple-400', icon: Waves },
  guitar: { label: 'Guitar', color: 'bg-cyan-500', textColor: 'text-cyan-400', icon: Guitar },
  piano: { label: 'Piano', color: 'bg-pink-500', textColor: 'text-pink-400', icon: Piano },
  strings: { label: 'Strings', color: 'bg-violet-500', textColor: 'text-violet-400', icon: Music },
  brass: { label: 'Brass', color: 'bg-amber-500', textColor: 'text-amber-400', icon: Music },
  woodwinds: { label: 'Woodwinds', color: 'bg-emerald-500', textColor: 'text-emerald-400', icon: Music },
  synthesizer: { label: 'Synthesizer', color: 'bg-fuchsia-500', textColor: 'text-fuchsia-400', icon: Music },
  other: { label: 'Other', color: 'bg-slate-500', textColor: 'text-slate-400', icon: Music },
};

function StemSelector({ availableStems, selectedStems, onChange }: StemSelectorProps): React.ReactElement {
  const toggleStem = (stem: string): void => {
    if (selectedStems.includes(stem)) {
      if (selectedStems.length > 1) {
        onChange(selectedStems.filter(s => s !== stem));
      }
    } else {
      onChange([...selectedStems, stem]);
    }
  };

  const selectAll = (): void => {
    onChange([...availableStems]);
  };

  return (
    <div>
      <div className="flex justify-end mb-3">
        <button 
          onClick={selectAll}
          className="text-xs text-lukus-400 hover:text-lukus-300 transition-colors"
        >
          Select All
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        {availableStems.map(stem => {
          const config = STEM_CONFIG[stem];
          const isSelected = selectedStems.includes(stem);
          const Icon = config?.icon || Music;
          
          return (
            <button
              key={stem}
              onClick={() => toggleStem(stem)}
              className={`stem-tag flex items-center gap-2 
                ${isSelected 
                  ? `${config?.color || 'bg-dark-600'} text-white` 
                  : 'bg-dark-800 text-dark-400 hover:bg-dark-700'
                }
                ${isSelected ? 'selected ring-white/30' : ''}
              `}
            >
              <Icon className="w-4 h-4" />
              <span>{config?.label || stem}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default StemSelector;
