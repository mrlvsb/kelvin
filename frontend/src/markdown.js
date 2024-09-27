import { marked } from 'marked';
import DOMPurify from 'dompurify';
import hljs from 'highlight.js/lib/core';

marked.setOptions({
    highlight: function (code, lang) {
        if (lang) {
            try {
                return hljs.highlight(lang, code).value;
            } catch (err) {
                if (typeof Sentry !== 'undefined') {
                    // eslint-disable-next-line no-undef
                    Sentry.captureException(err);
                }
            }
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true
});

const sanitizeOpts = {
    ALLOWED_TAGS: ['img', 'p', 'b', 'strong', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a', 'i', 'ul', 'ol', 'li', 'pre', 'code', 'a', 'br', 'span'],
    ALLOWED_ATTR: ['href', 'src', 'class']
};

export function safeMarkdown(text, opts = null) {
    return DOMPurify.sanitize(marked(text, opts), sanitizeOpts);
}
