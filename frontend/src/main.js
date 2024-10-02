import "bootstrap/dist/css/bootstrap.css";
import "bootstrap/js/dist/collapse";
import "./global.css";
import './global.scss';

import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import java from 'highlight.js/lib/languages/java';
import makefile from 'highlight.js/lib/languages/makefile';
import python from 'highlight.js/lib/languages/python';
import rust from 'highlight.js/lib/languages/rust';
import shell from 'highlight.js/lib/languages/shell';
import x86asm from 'highlight.js/lib/languages/x86asm';
import xml from 'highlight.js/lib/languages/xml';

hljs.registerLanguage('c-like', cpp);
hljs.registerLanguage('c', c); 
hljs.registerLanguage('cpp', cpp); 
hljs.registerLanguage('csharp', csharp);
hljs.registerLanguage('java', java); 
hljs.registerLanguage('python', python); 
hljs.registerLanguage('xml', xml); 
hljs.registerLanguage('bash', bash); 
hljs.registerLanguage('shell-session', shell);
hljs.registerLanguage('makefile', makefile); 
hljs.registerLanguage('assembler', x86asm); 
hljs.registerLanguage('asm', x86asm); 
hljs.registerLanguage('x86asm', x86asm);
hljs.registerLanguage('rust', rust);
hljs.highlightAll();

import * as Diff2Html from 'diff2html';
import 'diff2html/bundles/css/diff2html.min.css';
window.Diff2Html = Diff2Html;

// Import iconify icons used in UI, don't remove this line (almost forgot to put it back)
import '@iconify/iconify';
import AnsiUp from 'ansi_up';
import App from './App.svelte';
import ColorTheme from "./ColorTheme.svelte";
import CtrlP from './CtrlP.svelte';
import Notifications from './Notifications.svelte';
import PipelineStatus from './PipelineStatus.svelte';
import TaskDetail from './TaskDetail.svelte';
import UploadSolution from './UploadSolution.svelte';
import { safeMarkdown } from './markdown.js';

class ReplaceHtmlElement extends HTMLElement {
	constructor() {
		super();
		this.attachShadow({mode: 'open'});
		this.shadowRoot.innerHTML = '<slot></slot>';
		this.shadowRoot.querySelector('slot').addEventListener('slotchange', () => {
			this.onConnect();
			this.style.display = 'block';
		}, {once: true});
	}
	connectedCallback() {
		this.style.display = 'none';
	}
};

customElements.define('kelvin-terminal-output', class extends ReplaceHtmlElement {
	onConnect() {
		const res = new AnsiUp().ansi_to_html(this.innerText);
		this.innerHTML = '<pre>' + res + '</pre>';
	}
});

customElements.define('kelvin-markdown', class extends ReplaceHtmlElement {
    onConnect() {
		this.innerHTML = safeMarkdown(this.innerText, {breaks: false});
		this.removeAttribute('hidden')
		this.classList.add('md');
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
createElement('upload-solution', UploadSolution);
createElement('pipeline-status', PipelineStatus);
createElement('ctrlp', CtrlP);
createElement("color-theme", ColorTheme);

function focusTab() {
	const hash = document.location.hash.replace('#', '').split('-')[0].split(';')[0];
	const link = document.querySelector(`[data-toggle="tab"][href="#${hash}"]`);
	if(!link) {
		return;
	}

	link.closest('ul').querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
	link.classList.add('active');

	document.querySelectorAll('.tab-content .tab-pane').forEach(el => el.classList.remove('active'));

	document.querySelector('#tab_' + hash).classList.add('active');
}

window.addEventListener("hashchange", focusTab);
window.addEventListener("DOMContentLoaded", focusTab);

import { defineCustomElement } from 'vue';
import Example from './ExampleComponent.vue';

customElements.define(
    'kelvin-example',
    defineCustomElement(Example, {
        shadowRoot: false // https://github.com/vuejs/core/issues/4314#issuecomment-2266382877
    })
);
