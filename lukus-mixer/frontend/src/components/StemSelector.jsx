import React from 'react';
import { Mic2, Drum, Guitar, Piano, Waves, Music } from 'lucide-react';

const STEM_CONFIG = {
  vocals: { 
    label: 'Vocals', 
    color: 'bg-green-500', 
    textColor: 'text-green-400',
    icon: Mic2 
  },
  drums: { 
    label: 'Drums', 
    color: 'bg-orange-500', 
    textColor: 'text-orange-400',
    icon: Drum 
  },
  bass: { 
    label: 'Bass', 
    color: 'bg-purple-500', 
    textColor: 'text-purple-400',
    icon: Waves 
  },
  guitar: { 
    label: 'Electric Guitar', 
    color: 'bg-cyan-500', 
    textColor: 'text-cyan-400',
    icon: Guitar 
  },
  piano: { 
    label: 'Piano', 
    color: 'bg-pink-500', 
    textColor: 'text-pink-400',
    icon: Piano 
  },
  other: { 
    label: 'Other', 
    color: 'bg-slate-500', 
    textColor: 'text-slate-400',
    icon: Music 
  },
};

function StemSelector({ availableStems, selectedStems, onChange }) {
  const toggleStem = (stem) => {
    if (selectedStems.includes(stem)) {
      // 최소 1개는 선택되어야 함
      if (selectedStems.length > 1) {
        onChange(selectedStems.filter(s => s !== stem));
      }
    } else {
      onChange([...selectedStems, stem]);
    }
  };

  const selectAll = () => {
    onChange([...availableStems]);
  };

  return (
    <div>
      {/* Select All 버튼 */}
      <div className="flex justify-end mb-3">
        <button 
          onClick={selectAll}
          className="text-xs text-lukus-400 hover:text-lukus-300 transition-colors"
        >
          Select All
        </button>
      </div>

      {/* 스템 태그들 */}
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
