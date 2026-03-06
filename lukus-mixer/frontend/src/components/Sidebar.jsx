import React from 'react';
import { 
  Music2, 
  Mic2, 
  Sparkles, 
  Split, 
  Compass, 
  LayoutGrid,
  Library,
  Disc3,
  ChevronUp,
  Star
} from 'lucide-react';

const menuItems = [
  { icon: Music2, label: 'AI Text to Music', active: false },
  { icon: Sparkles, label: 'AI Music Generator', active: false },
  { icon: Mic2, label: 'AI Sample Generator', active: false },
  { icon: Split, label: 'Stem Splitter', active: true },
  { divider: true },
  { icon: Compass, label: 'Discover', active: false },
  { icon: LayoutGrid, label: 'Templates', active: false },
  { divider: true },
  { icon: Library, label: 'Library', active: false },
  { icon: Disc3, label: 'Releases', active: false },
];

function Sidebar() {
  return (
    <div className="w-[220px] bg-dark-950 border-r border-dark-800 flex flex-col">
      {/* 로고 */}
      <div className="p-4 border-b border-dark-800">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-orange-400 to-orange-600 rounded-lg flex items-center justify-center">
            <Music2 className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold text-white">LUKUS</span>
        </div>
      </div>

      {/* 메뉴 */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {menuItems.map((item, index) => {
          if (item.divider) {
            return <div key={index} className="my-2 mx-4 border-t border-dark-800" />;
          }
          
          const Icon = item.icon;
          return (
            <button
              key={index}
              className={`w-full flex items-center gap-3 px-4 py-2.5 text-sm transition-colors
                ${item.active 
                  ? 'bg-lukus-500/10 text-lukus-400 border-r-2 border-lukus-500' 
                  : 'text-dark-400 hover:text-white hover:bg-dark-800/50'
                }`}
            >
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* 유저 */}
      <div className="p-4 border-t border-dark-800">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-dark-700 rounded-full flex items-center justify-center">
            <span className="text-sm">U</span>
          </div>
          <span className="text-sm text-dark-300 flex-1 truncate">user@lukus.kr</span>
          <button className="text-dark-500 hover:text-white">
            <ChevronUp className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
