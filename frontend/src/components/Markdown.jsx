import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import ReactMarkdown from 'react-markdown';
import { memo } from 'react';

function MarkdownImpl({ text, className = '' }) {
  return (
    <div className={'md ' + className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          a: (props) => <a {...props} target="_blank" rel="noreferrer noopener" />,
        }}
      >
        {text || ''}
      </ReactMarkdown>
    </div>
  );
}

const Markdown = memo(MarkdownImpl);
export default Markdown;