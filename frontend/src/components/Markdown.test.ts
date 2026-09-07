import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import Markdown from './Markdown.vue';

describe('Markdown', () => {
    it('Should render empty markdown', () => {
        const wrapper = mount(Markdown, { props: { content: '' } });
        expect(wrapper.html()).toMatchSnapshot();
    });

    it('Should render example markdown', () => {
        const wrapper = mount(Markdown, {
            props: {
                content: `# Title
## Subtitle
### Subsubtitle

Some **bold** text and also *italic* text.
This is _underlined_ and this is ~~strikethrough~~.
Here is some \`inline code\` and here is a code block:
\`\`\`javascript
console.log('Hello, world!');
\`\`\`
Also there is [link](https://example.com) and an image:
![alt text](https://example.com/image.jpg)

1. First
2. Second
3. Third

- One
- Two
- Three

> Blockquote
> is very useful

Also we don't forget about tables:
| Header 1 | Header 2 |
|----------|----------|
| Cell 1   | Cell 2   |
| Cell 3   | Cell 4   |
which looks like, that we don't currently render :(.
`
            }
        });
        expect(wrapper.html()).toMatchSnapshot();
    });
});
