import 'bootstrap/dist/css/bootstrap.min.css'

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
import x86asm from 'highlight.js/lib/languages/x86asm'

hljs.registerLanguage('c-like', clike);
hljs.registerLanguage('c', c); 
hljs.registerLanguage('cpp', cpp); 
hljs.registerLanguage('java', java); 
hljs.registerLanguage('python', python); 
hljs.registerLanguage('xml', xml); 
hljs.registerLanguage('bash', bash); 
hljs.registerLanguage('shell-session', shell);
hljs.registerLanguage('makefile', makefile); 
hljs.registerLanguage('assembler', x86asm); 
hljs.initHighlightingOnLoad();

import 'diff2html/bundles/css/diff2html.min.css'
import * as Diff2Html from 'diff2html'
window.Diff2Html = Diff2Html;

import Iconify from '@iconify/iconify';

import App from './App.svelte'
import TaskDetail from './TaskDetail.svelte'
import Notifications from './Notifications.svelte'
import AnsiUp from 'ansi_up'
import UploadSolution from './UploadSolution.svelte'
import PipelineStatus from './PipelineStatus.svelte'
import {safeMarkdown} from './markdown.js'

class ReplaceHtmlElement extends HTMLElement {
	constructor() {
		super();
		this.attachShadow({mode: 'open'});
		this.shadowRoot.innerHTML = '<slot></slot>';
		this.shadowRoot.querySelector('slot').addEventListener('slotchange', () => {
			this.onConnect();
		}, {once: true});
	}
};

customElements.define('kelvin-terminal-output', class extends ReplaceHtmlElement {
	onConnect() {
		const res = (new (AnsiUp.default)()).ansi_to_html(this.innerText);
		this.innerHTML = '<pre>' + res + '</pre>';
	}
});

customElements.define('kelvin-markdown', class extends ReplaceHtmlElement {
    onConnect() {
		this.innerHTML = safeMarkdown(this.innerText);
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


function focusTab() {
	const hash = document.location.hash.replace('#', '').split('-')[0];
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