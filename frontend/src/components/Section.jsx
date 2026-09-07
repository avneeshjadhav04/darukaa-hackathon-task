import { ChevronRight } from 'lucide-react';
import { useState } from 'react';

export default function Section({ title, icon: Icon, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className={'section' + (open ? ' open' : '')}>
      <header onClick={() => setOpen(!open)}>
        <span className="left">
          <ChevronRight size={15} className="chev" />
          {Icon && <Icon size={15} />}
          <span>{title}</span>
        </span>
        {badge}
      </header>
      {open && <div className="body">{children}</div>}
    </div>
  );
}
