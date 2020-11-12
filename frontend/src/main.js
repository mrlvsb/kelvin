import 'highlight.js/styles/github.css'
import hljs from 'highlight.js/lib/core'
import clike from 'highlight.js/lib/languages/c-like'
import c from 'highlight.js/lib/languages/c'
import cpp from 'highlight.js/lib/languages/cpp'
import java from 'highlight.js/lib/languages/java'
import python from 'highlight.js/lib/languages/python'
import xml from 'highlight.js/lib/languages/xml'
import bash from 'highlight.js/lib/languages/bash'
import shell from 'highlight.js/lib/languages/shell'
import makefile from 'highlight.js/lib/languages/makefile'

hljs.registerLanguage('c-like', clike);
hljs.registerLanguage('c', c); 
hljs.registerLanguage('cpp', cpp); 
hljs.registerLanguage('java', java); 
hljs.registerLanguage('python', python); 
hljs.registerLanguage('xml', xml); 
hljs.registerLanguage('bash', bash); 
hljs.registerLanguage('shell-session', shell);
hljs.registerLanguage('makefile', makefile); 
hljs.initHighlightingOnLoad();

import App from './App.svelte'
import TaskDetail from './TaskDetail.svelte'
import Notifications from './Notifications.svelte'
import AnsiUp from 'ansi_up'

customElements.define('kelvin-terminal-output', class extends HTMLElement {
    connectedCallback() {
        setTimeout(() => {
            const res = (new (AnsiUp.default)()).ansi_to_html(this.innerText);
            this.innerHTML = '<pre>' + res + '</pre>';
        }, 0);
    }
});


function createElement(name, component) {
	customElements.define('kelvin-' + name, class extends HTMLElement {
		connectedCallback() {
			let attrs = {};
			for(let i = 0; i < this.attributes.length; i++) {
				let attr = this.attributes[i];
				let name = attr.name.replace('-', '_')
				if(attr.value[0] == '{' || attr.value[0] == '[') {
					attrs[name] = JSON.parse(attr.value);
				} else {
					attrs[name] = attr.value;
				}
			}

			new component({
				target: this,
				props: attrs,
			})
		}
	});
}

createElement('app', App);
createElement('submit-sources', TaskDetail);
createElement('notifications', Notifications);
